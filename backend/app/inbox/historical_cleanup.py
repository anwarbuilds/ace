"""Explicitly scoped, status-preserving historical classification cleanup.

No discovery, global recheck switch, application mutation or outcome recording.
The operator must supply a reviewed private cohort and prepare a fresh plan.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from sqlalchemy import select

from backend.app.api.routers import inbox
from backend.app.db.models import GmailMessageRecord as Mail, ApplicationEventRecord as Event
from backend.app.inbox.reconcile import PARSER_VERSION, read_intent, reassess, file_recognized
from backend.app.inbox.company_outcomes import COMPANY_REASON, KIND as COMPANY_KIND, event_company
from backend.app.inbox.filed_evidence import DECISIONS as FILED_DECISIONS
from backend.app.config import get_settings

FIELDS = ('classification', 'decision', 'decision_reason', 'requisition_id',
          'candidate_keys', 'selected_application_key', 'snippet', 'parser_version')


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def row_state(row) -> dict:
    return {c.name: getattr(row, c.name) for c in Mail.__table__.columns}


def eligible(session, row) -> bool:
    return bool(row and row.decision in {'review', 'exact_preview'}
                and not row.decision_reason.startswith(('You undid', 'You marked', 'You chose', 'You recorded'))
                and not session.scalar(select(Event.id).where(Event.gmail_message_id == row.id,
                      Event.actor.in_(('owner', 'verified_automation'))).limit(1)))


def projection(session, conn, row, data) -> dict:
    evidence = inbox._message_evidence(data)
    identities = inbox._identities(session)
    reading = read_intent(evidence)
    decision = reassess(evidence, identities, row.classification, conn.email,
                       thread_keys=inbox._thread_keys(session, conn, data, evidence, identities),
                       previous_reason=row.decision_reason)
    if decision.disposition == 'verified' and decision.classification != 'rejection':
        # Classification-only history does not replay a positive stage update.
        # Its recognized invitation remains useful without changing that stage.
        decision = file_recognized(decision, evidence)
    company_outcome = decision.disposition == COMPANY_KIND and get_settings().gmail_auto_rejections
    disposition = ('update' if company_outcome or decision.disposition in FILED_DECISIONS else 'review' if decision.disposition in {'verified', COMPANY_KIND}
                   else 'update' if decision.disposition == 'unlinked' else decision.disposition)
    reason = decision.reason
    if company_outcome:
        reason = COMPANY_REASON
    if decision.disposition == 'verified':
        reason += '; historical cleanup preserves application statuses'
    patch = dict(classification=decision.classification, decision=disposition,
                 decision_reason=reason[:300], requisition_id=decision.requisition_id,
                 candidate_keys=list(decision.candidates),
                 selected_application_key=decision.matched_target,
                 snippet=reading.excerpt or row.snippet, parser_version=PARSER_VERSION)
    assert disposition in {'review', 'exact_preview', 'receipt', 'update', 'ignored', 'unlinked'}
    result = {'message_id': row.id, 'before_hash': digest(row_state(row)),
            'before': {name: getattr(row, name) for name in FIELDS}, 'patch': patch,
            'evidence_hash': digest(asdict(evidence)), 'complete': evidence.complete,
            'reading': reading.classification, 'reading_reason': reading.explanation,
            'would_change_status': False, 'would_record_outcome': False}
    if company_outcome:
        result.update(company=decision.company, would_record_company_outcome=True)
    return result


def event_key(conn, row, operation: str) -> str:
    return f'email-cleanup:{operation}:{conn.id}:{row.id}:{PARSER_VERSION}'


def apply_prepared(session, conn, entry, fresh, operation: str):
    """CAS under a short row lock after network reads, with an append-only event.

    A changed owner decision, body, matching context or plan aborts this row.
    The caller commits and journals. An existing operation event is resumable.
    """
    row = session.scalar(select(Mail).where(Mail.id == entry['message_id'], Mail.connection_id == conn.id)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise ValueError('Cohort evidence no longer exists')
    prior = session.scalar(select(Event).where(Event.dedupe_key == event_key(conn, row, operation)))
    if prior:
        if any(getattr(row, name) != entry['patch'][name] for name in FIELDS):
            raise ValueError('Previously cleaned evidence changed; owner state is protected')
        return prior
    if not eligible(session, row) or digest(row_state(row)) != entry['before_hash']:
        raise ValueError('Evidence or owner decision changed since preview')
    if fresh != entry:
        raise ValueError('Fresh evidence or reconciliation differs from reviewed preview')
    for name in FIELDS:
        setattr(row, name, entry['patch'][name])
    if entry.get('would_record_company_outcome'):
        if not get_settings().gmail_auto_rejections:
            raise ValueError('Automatic rejection recording was disabled')
        inbox._record_company_rejection(session, conn, row, entry['company'], entry['reading_reason'])
    return inbox._append_event(session, f'email:{row.id}', 'email_rechecked', entry['before']['decision'], row.decision,
                               actor='classifier', reason=row.decision_reason, message_id=row.id,
                               occurred_at=row.received_at, dedupe_key=event_key(conn, row, operation))


def revert_prepared(session, conn, entry, operation: str):
    """Revert only this operation's untouched email fields, never restore a DB.

    Owner edits, later email events and any mismatch block this row. Old events
    remain; the correction is appended to the same email audit trail.
    """
    row = session.scalar(select(Mail).where(Mail.id == entry['message_id'], Mail.connection_id == conn.id)
                         .with_for_update().execution_options(populate_existing=True))
    if not row:
        raise ValueError('Evidence no longer exists')
    event = session.scalar(select(Event).where(Event.dedupe_key == event_key(conn, row, operation)))
    latest = session.scalar(select(Event.id).where(Event.gmail_message_id == row.id).order_by(Event.id.desc()).limit(1))
    if not event or latest != event.id or any(getattr(row, name) != entry['patch'][name] for name in FIELDS):
        raise ValueError('Later evidence or owner action blocks rollback')
    before = row.decision
    if entry.get('would_record_company_outcome'):
        recorded = session.scalar(select(Event).where(
            Event.gmail_message_id == row.id, Event.kind == COMPANY_KIND,
            Event.dedupe_key == f'gmail:{conn.id}:{row.gmail_id}:{COMPANY_KIND}'))
        if (not recorded or event_company(recorded) != entry['company']
                or session.scalar(select(Event.id).where(Event.undo_of_id == recorded.id))):
            raise ValueError('Company evidence changed; rollback is blocked')
        inbox._append_event(session, recorded.application_key, 'undo', recorded.new_status, recorded.previous_status,
                            actor='classifier', reason='Reverted the guarded company rejection filing',
                            message_id=row.id, undo_of=recorded.id,
                            dedupe_key=event_key(conn, row, operation) + ':company-revert')
    for name in FIELDS:
        setattr(row, name, entry['before'][name])
    return inbox._append_event(session, f'email:{row.id}', 'email_cleanup_reverted', before, row.decision,
                               actor='classifier', reason='Reverted the guarded historical classification cleanup',
                               message_id=row.id, undo_of=event.id,
                               dedupe_key=event_key(conn, row, operation) + ':revert')
