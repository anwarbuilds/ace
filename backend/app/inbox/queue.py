"""Shared, non-destructive projection of legacy unclassified correspondence.

Recognized outcomes, partial reads, owner filings and Undo remain pending.
No age cutoff: historical evidence is as important as recent evidence.
"""
from sqlalchemy import and_, case, func
from backend.app.db.models import GmailMessageRecord as Mail
from backend.app.inbox.reconcile import UNCLEAR_REASON

PENDING = ("review", "exact_preview", "deferred")
OWNER_UNDO = "You undid ACE's change for this email"
SAVED_REASON = "Saved application correspondence; no confirmed outcome to record"


def passive_clause():
    return and_(Mail.decision.in_(("review", "exact_preview")),
                Mail.classification == "unclear",
                func.coalesce(Mail.decision_reason, "") == UNCLEAR_REASON)


def decision_expression():
    return case((passive_clause(), "update"), else_=Mail.decision)


def projected_decision(row):
    if (row.decision in ("review", "exact_preview") and row.classification == "unclear"
            and row.decision_reason == UNCLEAR_REASON):
        return "update"
    return row.decision


def projected_reason(row):
    return SAVED_REASON if projected_decision(row) != row.decision else row.decision_reason
