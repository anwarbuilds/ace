"""Shared, non-destructive projection of legacy unclassified correspondence.

Fresh complete recognized evidence can be filed independently of application
linkage, with source verification kept separate from application authority. Partial reads and protected owner choices retain their
existing states. No age cutoff removes historical evidence.
"""
from sqlalchemy import and_, case, func, or_
from backend.app.db.models import GmailMessageRecord as Mail
from backend.app.inbox.reconcile import UNCLEAR_REASON, UNLINKED_REASON
from backend.app.inbox.company_outcomes import COMPANY_REASON
from backend.app.inbox.filed_evidence import ACTION_KINDS, ACTION_PREFIX, DECISIONS as FILED_DECISIONS, LEGACY_ACTION_REASONS, REJECTION_PREFIX

PENDING = ("review", "exact_preview", "deferred")
OWNER_UNDO = "You undid ACE's change for this email"
SAVED_REASON = "Saved application correspondence; no confirmed outcome to record"


def passive_clause():
    return and_(Mail.decision.in_(("review", "exact_preview")),
                Mail.classification == "unclear",
                func.coalesce(Mail.decision_reason, "") == UNCLEAR_REASON)


def decision_expression():
    return case((and_(Mail.decision == "update", Mail.classification == "rejection",
                      Mail.decision_reason == COMPANY_REASON), "company_rejection"),
                (and_(Mail.decision == "update", Mail.classification == "rejection",
                      Mail.decision_reason == UNLINKED_REASON), "unlinked"),
                (and_(Mail.decision == "update", Mail.selected_application_key.is_(None), Mail.classification == "rejection",
                      func.substr(Mail.decision_reason, 1, len(REJECTION_PREFIX)) == REJECTION_PREFIX), "classified_rejection"),
                (and_(Mail.decision == "update", Mail.selected_application_key.is_(None), Mail.classification.in_(sorted(ACTION_KINDS)),
                      or_(func.substr(Mail.decision_reason, 1, len(ACTION_PREFIX)) == ACTION_PREFIX,
                          *(and_(Mail.classification == kind, Mail.decision_reason == reason)
                            for kind, reason in LEGACY_ACTION_REASONS.items()))), "classified_action"),
                (passive_clause(), "update"), else_=Mail.decision)


def projected_decision(row):
    if row.decision == "update" and row.classification == "rejection" and row.decision_reason == COMPANY_REASON:
        return "company_rejection"
    if row.decision == "update" and row.classification == "rejection" and row.decision_reason == UNLINKED_REASON:
        return "unlinked"
    if (row.decision == "update" and row.selected_application_key is None and row.classification == "rejection"
            and (row.decision_reason or "").startswith(REJECTION_PREFIX)):
        return "classified_rejection"
    if (row.decision == "update" and row.selected_application_key is None and row.classification in ACTION_KINDS
            and ((row.decision_reason or "").startswith(ACTION_PREFIX)
                 or (row.classification in LEGACY_ACTION_REASONS
                     and row.decision_reason == LEGACY_ACTION_REASONS[row.classification]))):
        return "classified_action"
    if (row.decision in ("review", "exact_preview") and row.classification == "unclear"
            and row.decision_reason == UNCLEAR_REASON):
        return "update"
    return row.decision


def projected_reason(row):
    return SAVED_REASON if row.decision in ("review", "exact_preview") and projected_decision(row) == "update" else row.decision_reason


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
    "The posting links and application evidence do not identify one application",
    "The posting link and named requisition disagree",
    "The posting link and named role disagree",
    "The requisition and named role point to different applications",
    "No recorded application at this employer existed when the email arrived",
)


def workflow_expression():
    projected = decision_expression()
    return case(
        (projected.in_(sorted(FILED_DECISIONS)), projected),
        (projected == "company_rejection", "company_recorded"),
        (projected.in_(("automatic", "manual")), "recorded"),
        (projected == "deferred", "deferred"),
        (projected.in_(("ignored", "unrelated")), "routine"),
        (projected.in_(("receipt", "update")), "filed"),
        (projected == "unlinked", "unlinked_outcome"),
        (and_(Mail.selected_application_key.is_(None), Mail.decision_reason.in_(LINK_REASONS)), "awaiting_link"),
        else_="owner_review",
    )


def workflow_state(row):
    decision = projected_decision(row)
    if decision in FILED_DECISIONS:
        return decision
    if decision == "company_rejection":
        return "company_recorded"
    if decision in ("automatic", "manual"):
        return "recorded"
    if decision == "deferred":
        return "deferred"
    if decision in ("ignored", "unrelated"):
        return "routine"
    if decision in ("receipt", "update"):
        return "filed"
    if decision == "unlinked":
        return "unlinked_outcome"
    if not row.selected_application_key and row.decision_reason in LINK_REASONS:
        return "awaiting_link"
    return "owner_review"
