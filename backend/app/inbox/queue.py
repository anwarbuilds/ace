"""One review policy for Inbox and Analytics, including retained legacy rows.

Unclassified correspondence is searchable without becoming a demand for owner
work. Historical mail cannot update applications recorded much later. No source
row, owner decision or evidence event is rewritten by this projection.
"""
from datetime import timedelta, timezone
from sqlalchemy import and_, case, or_, select, func, union_all
from backend.app.db.models import GmailMessageRecord as Mail, JobMarkRecord, ExternalApplicationRecord

PENDING = ("review", "exact_preview", "deferred")
OWNER_UNDO = "You undid ACE's change for this email"
SAVED_REASON = "Saved application correspondence; no confirmed outcome to record"
HISTORY_REASON = "Earlier job correspondence; no application from that period is recorded"


def history_cutoff(session):
    dates = union_all(select(JobMarkRecord.applied_at.label("at")).where(JobMarkRecord.applied_at.is_not(None)),
                      select(ExternalApplicationRecord.applied_at.label("at")).where(ExternalApplicationRecord.applied_at.is_not(None))).subquery()
    first = session.scalar(select(func.min(dates.c.at)))
    if first is not None:
        return (first.replace(tzinfo=timezone.utc) if first.tzinfo is None else first) - timedelta(days=1)
    return None


def passive_clause(cutoff=None):
    reasons = [Mail.classification.in_(("unclear", "unknown", "application_confirmation")),
               Mail.decision_reason == "Email predates application"]
    if cutoff is not None:
        reasons.append(Mail.received_at < cutoff)
    return and_(Mail.decision.in_(("review", "exact_preview")),
                Mail.decision_reason != OWNER_UNDO, or_(*reasons))


def decision_expression(cutoff=None):
    return case((passive_clause(cutoff), "update"), else_=Mail.decision)


def projected_decision(row, cutoff=None):
    if row.decision not in ("review", "exact_preview") or row.decision_reason == OWNER_UNDO:
        return row.decision
    stamp = row.received_at.replace(tzinfo=timezone.utc) if row.received_at.tzinfo is None else row.received_at
    if (row.classification in ("unclear", "unknown", "application_confirmation")
            or row.decision_reason == "Email predates application" or (cutoff is not None and stamp < cutoff)):
        return "update"
    return row.decision


def projected_reason(row, cutoff=None):
    if projected_decision(row, cutoff) == row.decision:
        return row.decision_reason
    if row.classification in ("unclear", "unknown", "application_confirmation"):
        return SAVED_REASON
    return HISTORY_REASON
