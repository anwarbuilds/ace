"""Fictional persistence contracts: classify meaning without inventing a target."""
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.app.api.routers import inbox
from backend.app.config import get_settings
from backend.app.db.models import ApplicationEventRecord as Event, JobMarkRecord
from backend.app.inbox import historical_cleanup as cleanup
from backend.app.inbox.filed_evidence import ACTION_PREFIX, REJECTION_PREFIX
from backend.app.inbox.queue import decision_expression, projected_decision
from backend.app.inbox.reconcile import reconcile
from backend.tests.test_inbox_persistence import (
    NOW, database, job_events, message, owner_request, row_for, statuses, stored,
)


BODIES = {
    'rejection': 'Your application was rejected.',
    'online_assessment': 'Please complete your online assessment.',
    'interview': 'Please book your technical interview.',
    'offer': 'We are pleased to offer you the Software Engineer position.',
    'recruiter_reply': 'We would like to speak with you about your application.',
    'action_required': 'Please upload your transcript for your application.',
}


def unknown_message(key, body, **kwargs):
    data = message(key, body, **kwargs)
    for header in data['payload']['headers']:
        if header['name'] == 'From':
            header['value'] = 'talent@unrecorded-employer.example'
        if header['name'] == 'Authentication-Results':
            header['value'] = 'mx.google.com; dmarc=pass header.from=unrecorded-employer.example'
    return data


@pytest.mark.parametrize('kind', sorted(BODIES))
def test_filing_recognized_unlinked_meaning_never_creates_application_or_company_outcome(database, kind):
    session, conn = database
    data = unknown_message('filed-' + kind, BODIES[kind])
    expected = 'classified_rejection' if kind == 'rejection' else 'classified_action'
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=True) == expected
    row = row_for(session, data['id'])
    assert row.decision == 'update' and projected_decision(row) == expected
    assert row.selected_application_key is None and row.classification == kind
    assert row.decision_reason.startswith(REJECTION_PREFIX if kind == 'rejection' else ACTION_PREFIX)
    assert statuses(session) == ['applied'] * 3
    [audit] = session.scalars(select(Event)).all()
    assert audit.kind == 'email_classified' and audit.actor == 'classifier'
    assert audit.application_key == f'email:{row.id}'
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=False) == 'duplicate'
    item = inbox._item(row)
    assert item['understanding']['update_policy'] == 'no_status_change'
    assert item['understanding']['review_reason'] is None


@pytest.mark.parametrize('preview,opt_in,server_on', [(True, True, True), (False, False, True), (False, True, False)])
@pytest.mark.parametrize('kind', ['online_assessment', 'interview', 'offer'])
def test_positive_mutation_switches_do_not_prevent_classification(database, monkeypatch, preview, opt_in, server_on, kind):
    session, conn = database
    conn.auto_outcomes_enabled = opt_in
    monkeypatch.setenv('GMAIL_AUTO_OUTCOMES_ALLOWED', str(server_on).lower())
    get_settings.cache_clear()
    data = message('positive-policy-' + kind, 'Req ID: SE-101. ' + BODIES[kind])
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=preview) == 'classified_action'
    row = row_for(session, data['id'])
    assert row.decision == 'update' and row.selected_application_key is None
    assert statuses(session) == ['applied'] * 3 and not job_events(session)


def test_live_exact_positive_with_opt_in_keeps_application_event_path(database):
    session, conn = database
    data = message('live-exact-action', 'Req ID: SE-101. Please complete your online assessment.')
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=False) == 'automatic'
    assert statuses(session) == ['applied', 'screening', 'applied']
    assert [(e.kind, e.application_key) for e in job_events(session)] == [('online_assessment', 'job:2')]


@pytest.mark.parametrize('kind', ['rejection', 'interview'])
def test_authenticated_personal_mail_has_recognized_meaning_but_never_employer_authority(database, kind):
    session, conn = database
    data = message('personal-authenticated-' + kind, 'Req ID: SE-101. ' + BODIES[kind])
    for header in data['payload']['headers']:
        if header['name'] == 'From':
            header['value'] = 'Fictional recruiter <person@gmail.com>'
        if header['name'] == 'Authentication-Results':
            header['value'] = 'mx.google.com; dmarc=pass header.from=gmail.com'
    evidence = inbox._message_evidence(data)
    assert evidence.sender_authenticated
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=False) == (
        'classified_rejection' if kind == 'rejection' else 'classified_action')
    row = row_for(session, data['id'])
    assert row.selected_application_key is None
    assert statuses(session) == ['applied'] * 3 and not job_events(session)
    assert not session.scalars(select(Event).where(Event.kind == 'company_rejection')).all()


def test_old_interview_is_visible_without_reopening_a_rejected_application(database):
    session, conn = database
    target = session.get(JobMarkRecord, 2)
    target.application_status = 'rejected'
    target.status_changed_at = NOW
    session.commit()
    data = message('interview-before-rejection', 'Req ID: SE-101. Please book your technical interview.', received_at=NOW-timedelta(days=3))
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=True) == 'classified_action'
    assert statuses(session) == ['applied', 'rejected', 'applied']
    assert not job_events(session)


@pytest.mark.parametrize('protection', ['deferred', 'owner_refiling', 'undo', 'owner_event', 'verified_event'])
def test_file_apply_does_not_replace_owner_or_recorded_evidence(database, protection):
    session, conn = database
    row = stored(session, conn, 'protected-' + protection, 'review', 'Application update', reason='No application could be matched with confidence')
    data = unknown_message(row.gmail_id, BODIES['interview'])
    evidence = inbox._message_evidence(data)
    decision = reconcile(evidence, inbox._identities(session))
    assert decision.disposition == 'classified_action'
    if protection == 'deferred':
        row.decision = 'deferred'
    elif protection == 'owner_refiling':
        row.decision = 'update'
        row.decision_reason = 'You marked it a status update with no decision yet'
    elif protection == 'undo':
        row.decision_reason = "You undid ACE's change for this email"
    else:
        session.add(Event(application_key='job:1', kind='interview', actor='owner' if protection == 'owner_event' else 'verified_automation',
                          reason='Fictional existing decision', gmail_message_id=row.id, occurred_at=NOW, dedupe_key='protect-' + protection))
    session.commit()
    before = cleanup.row_state(row)
    with pytest.raises(ValueError, match='protect'):
        inbox._apply(session, conn, row, decision, evidence, preview=True)
    assert cleanup.row_state(row) == before
    assert statuses(session) == ['applied'] * 3


@pytest.mark.parametrize('obstruction', ['partial', 'authentication', 'spam', 'trash', 'changed_meaning', 'mixed_meaning'])
def test_filing_requires_complete_current_authenticated_non_spam_evidence(database, obstruction):
    session, conn = database
    row = stored(session, conn, 'obstruction-' + obstruction, 'review', 'Application update', reason='No match')
    evidence = inbox._message_evidence(unknown_message(row.gmail_id, BODIES['interview']))
    decision = reconcile(evidence, inbox._identities(session))
    evidence = replace(evidence, complete=False) if obstruction == 'partial' else evidence
    evidence = replace(evidence, sender_authenticated=False) if obstruction == 'authentication' else evidence
    evidence = replace(evidence, body='Your application was rejected.') if obstruction == 'changed_meaning' else evidence
    evidence = replace(evidence, body=BODIES['interview'] + ' ' + BODIES['rejection']) if obstruction == 'mixed_meaning' else evidence
    inbox._apply(session, conn, row, decision, evidence, preview=True, allow_automation=obstruction not in {'spam', 'trash'})
    assert row.decision == 'review' and row.selected_application_key is None
    assert not list(session.scalars(select(Event))) and statuses(session) == ['applied'] * 3


def test_category_filters_counts_and_pagination_do_not_put_recognized_actions_in_pending(database):
    session, conn = database
    for index, kind in enumerate(['online_assessment', 'online_assessment', 'interview', 'offer', 'rejection']):
        data = unknown_message(f'category-filed-{index}', BODIES[kind], received_at=NOW-timedelta(minutes=index))
        inbox._ingest(session, conn, data, inbox._identities(session), preview=True)
    session.commit()
    all_messages = inbox.messages(owner_request(), session, None, 0, 100)
    counts = all_messages['counts']
    assert (counts['needs_review'], counts['classified_actions'], counts['classified_rejections']) == (0, 4, 1)
    assert (counts['assessments'], counts['interviews'], counts['offers'], counts['rejections']) == (2, 1, 1, 1)
    assert inbox.messages(owner_request(), session, 'pending', 0, 100)['total'] == 0
    assert inbox.messages(owner_request(), session, 'filed', 0, 100)['total'] == 5
    first = inbox.messages(owner_request(), session, 'assessments', 0, 1)
    second = inbox.messages(owner_request(), session, 'assessments', 1, 1)
    assert first['total'] == second['total'] == 2 and first['has_more'] and not second['has_more']
    assert first['items'][0]['id'] != second['items'][0]['id']


def test_a_marker_on_a_linked_saved_row_cannot_claim_unlinked_filing_in_either_projection(database):
    session, conn = database
    row = stored(session, conn, 'linked-with-marker', 'update', 'Application update', reason=ACTION_PREFIX + 'Fictional retained reason')
    row.classification = 'interview'
    row.selected_application_key = 'job:1'
    session.commit()
    assert projected_decision(row) == session.scalar(select(decision_expression()).where(type(row).id == row.id)) == 'update'
    assert inbox.messages(owner_request(), session, 'classified_action', 0, 50)['total'] == 0


def test_reviewed_historical_filing_has_only_classifier_audit_and_is_reversible(database):
    session, conn = database
    row = stored(session, conn, 'historical-filed-action', 'review', 'Application update', version='12', reason='No application could be matched with confidence')
    row.classification = 'online_assessment'
    session.commit()
    data = unknown_message(row.gmail_id, BODIES['online_assessment'])
    before = cleanup.row_state(row)
    entry = cleanup.projection(session, conn, row, data)
    assert entry['patch']['decision'] == 'update' and entry['patch']['selected_application_key'] is None
    assert not entry['would_change_status'] and not entry['would_record_outcome']
    event = cleanup.apply_prepared(session, conn, entry, cleanup.projection(session, conn, row, data), 'filed-action-01')
    session.commit()
    assert projected_decision(row) == 'classified_action'
    assert event.kind == 'email_rechecked' and event.actor == 'classifier' and event.application_key == f'email:{row.id}'
    assert statuses(session) == ['applied'] * 3 and not job_events(session)
    cleanup.revert_prepared(session, conn, entry, 'filed-action-01')
    session.commit()
    assert cleanup.row_state(row) == before and statuses(session) == ['applied'] * 3


def test_historical_exact_positive_is_filed_while_its_application_status_is_preserved(database):
    session, conn = database
    row = stored(session, conn, 'historical-exact-positive', 'exact_preview', 'Application update', version='12', reason='Clear online assessment matched by its job ID')
    row.classification = 'online_assessment'
    row.selected_application_key = 'job:2'
    session.commit()
    data = message(row.gmail_id, 'Req ID: SE-101. Please complete your online assessment.')
    entry = cleanup.projection(session, conn, row, data)
    assert entry['patch']['decision'] == 'update' and entry['patch']['selected_application_key'] is None
    assert entry['patch']['decision_reason'].startswith(ACTION_PREFIX)
    assert not entry['would_change_status'] and not entry['would_record_outcome']
    cleanup.apply_prepared(session, conn, entry, cleanup.projection(session, conn, row, data), 'filed-exact-positive-01')
    session.commit()
    assert projected_decision(row) == 'classified_action'
    assert statuses(session) == ['applied'] * 3 and not job_events(session)

