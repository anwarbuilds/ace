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


# Identity work is a distinct owner task from interpreting wording, approving a
# protected status or completing an employer-requested action. Keep SQL lists
# and Python item labels on the same projection so pagination/counts agree.
LINK_REASONS = (
    "No application could be matched with confidence",
    "More than one application has this job ID",
    "The email names more than one company you applied to",
    "You applied to several roles there and the email does not say which",
    "The company is named only in the email text",
    "The email may be about a different role there",
    "The email names multiple requisitions; choose the application it concerns",
    "The requisition and named employer point to different applications",
)


def workflow_expression():
    projected = decision_expression()
    return case(
        (projected.in_(("automatic", "manual")), "recorded"),
        (projected == "deferred", "deferred"),
        (projected.in_(("ignored", "unrelated")), "routine"),
        (projected.in_(("receipt", "update")), "filed"),
        (and_(Mail.selected_application_key.is_(None), Mail.decision_reason.in_(LINK_REASONS)), "awaiting_link"),
        else_="owner_review",
    )


def workflow_state(row):
    decision = projected_decision(row)
    if decision in ("automatic", "manual"):
        return "recorded"
    if decision == "deferred":
        return "deferred"
    if decision in ("ignored", "unrelated"):
        return "routine"
    if decision in ("receipt", "update"):
        return "filed"
    if not row.selected_application_key and row.decision_reason in LINK_REASONS:
        return "awaiting_link"
    return "owner_review"
