"""Conservative, deterministic recruiting-email classification and matching.

This module has no Gmail access and no database writes. A caller may write a
status only when ``decision == 'verified'`` and the owner has enabled that
separate feature. The default disposition is review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from urllib.parse import urlparse

PARSER_VERSION = "1"
_REJECTION = re.compile(r"\b(?:we (?:have )?(?:decided|chosen) to (?:move forward|proceed) with other candidates|your application (?:was|has been) (?:unsuccessful|declined)|you (?:have )?not been selected)\b", re.I)
_ASSESSMENT = re.compile(r"\b(?:online assessment|coding assessment|take.home assessment)\b", re.I)
_INTERVIEW = re.compile(r"\b(?:invite you to interview|schedule (?:an? |your )?interview|interview invitation)\b", re.I)
_OFFER = re.compile(r"\b(?:offer of employment|pleased to offer you)\b", re.I)
_CONFIRMATION = re.compile(r"\b(?:application (?:received|submitted)|thank you for applying)\b", re.I)
_RECRUITER = re.compile(r"\b(?:would like to (?:speak|talk|connect) with you about (?:the|your) (?:role|application)|reaching out to discuss your application)\b", re.I)
_REQ = re.compile(r"\b(?:requisition|req(?:uisition)?[. #_-]*id|job[. #_-]*id)\s*[:#-]\s*([A-Za-z0-9][A-Za-z0-9._-]{2,79})\b", re.I)
_UNTRUSTED_DOMAIN = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com"}


@dataclass(frozen=True)
class ApplicationIdentity:
    key: str
    company: str
    title: str
    requisition_id: str | None
    submitted_at: datetime | None
    current_status: str
    official_url: str | None = None
    status_changed_at: datetime | None = None


@dataclass(frozen=True)
class EmailEvidence:
    sender: str
    subject: str
    body: str
    received_at: datetime
    sender_authenticated: bool = False


@dataclass(frozen=True)
class Decision:
    classification: str
    requisition_id: str | None
    candidates: tuple[str, ...]
    target: str | None
    disposition: str
    reason: str
    sender_verified: bool


def _new_text(body: str) -> str:
    """Drop common quoted/forwarded material before looking for intent."""
    return re.split(r"(?im)^\s*(?:on .{5,160} wrote:|[- ]*forwarded message[- ]*|from:\s.+$|>.*$)", body, maxsplit=1)[0][:8000]


def classify(evidence: EmailEvidence) -> tuple[str, str | None]:
    subject = "" if re.match(r"(?i)^\s*(?:fwd?|forward):", evidence.subject) else evidence.subject
    text = f"{subject}\n{_new_text(evidence.body)}"
    reqs = {match.group(1).casefold() for match in _REQ.finditer(text)}
    requisition = next(iter(reqs)) if len(reqs) == 1 else None
    if _REJECTION.search(text):
        return "rejection", requisition
    if _OFFER.search(text):
        return "offer", requisition
    if _INTERVIEW.search(text):
        return "interview", requisition
    if _ASSESSMENT.search(text):
        return "online_assessment", requisition
    if _RECRUITER.search(text):
        return "recruiter_reply", requisition
    if _CONFIRMATION.search(text):
        return "application_confirmation", requisition
    return "unknown", requisition


def _sender_matches(sender: str, app: ApplicationIdentity) -> bool:
    """Only an exact employer host or its subdomain establishes origin.

    Shared ATS domains and personal email hosts never establish employer
    identity automatically. The owner can still reconcile them manually.
    """
    host = (urlparse(app.official_url or "").hostname or "").lower()
    domain = parseaddr(sender)[1].rpartition("@")[2].lower()
    if not host or not domain or domain in _UNTRUSTED_DOMAIN:
        return False
    if any(x in host for x in ("greenhouse.io", "lever.co", "myworkdayjobs.com", "ashbyhq.com")):
        return False
    return domain == host or domain.endswith("." + host)


def reconcile(evidence: EmailEvidence, applications: list[ApplicationIdentity]) -> Decision:
    classification, req = classify(evidence)
    company_role_candidates = tuple(a.key for a in applications)
    if classification == "unknown":
        return Decision(classification, req, company_role_candidates, None, "ignored", "No explicit recruiting outcome", False)
    if classification == "application_confirmation":
        return Decision(classification, req, company_role_candidates, None, "review", "Confirmation is not an outcome", False)
    if not req:
        return Decision(classification, None, company_role_candidates, None, "review", "No unique application-specific identifier", False)
    exact = [a for a in applications if a.requisition_id and a.requisition_id.casefold() == req]
    if len(exact) != 1:
        return Decision(classification, req, tuple(a.key for a in exact) or company_role_candidates, None, "review", "Exact identifier is missing or ambiguous", False)
    app = exact[0]
    verified = evidence.sender_authenticated and _sender_matches(evidence.sender, app)
    if not verified:
        return Decision(classification, req, (app.key,), None, "review", "Sender authentication and employer domain are not independently verified", False)
    sent_at = app.submitted_at
    received = evidence.received_at
    if sent_at is None:
        return Decision(classification, req, (app.key,), None, "review", "Application submission time is unavailable", True)
    if (sent_at.replace(tzinfo=timezone.utc) if sent_at.tzinfo is None else sent_at) > (received.replace(tzinfo=timezone.utc) if received.tzinfo is None else received):
        return Decision(classification, req, (app.key,), None, "review", "Email predates application", True)
    if app.current_status in {"accepted", "rejected", "withdrawn"}:
        return Decision(classification, req, (app.key,), None, "review", "Existing terminal status is protected", True)
    if app.status_changed_at is not None and (app.status_changed_at.replace(tzinfo=timezone.utc) if app.status_changed_at.tzinfo is None else app.status_changed_at) > (received.replace(tzinfo=timezone.utc) if received.tzinfo is None else received):
        return Decision(classification, req, (app.key,), None, "review", "Newer application status is protected", True)
    return Decision(classification, req, (app.key,), app.key, "verified", "Unique requisition, verified sender and plausible timing", True)
