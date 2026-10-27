"""Owner-only Gmail preview, reconciliation, review and audit endpoints."""

from __future__ import annotations

import html
from collections import deque
import re
import secrets
import time
from threading import Lock
from datetime import date, datetime, time as day_time, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.api.deps import get_session
from backend.app.api.marks import APPLICATION_STATUSES
from backend.app.applications.service import external_match_key
from backend.app.auth.crypto import same
from backend.app.auth.guard import current_owner, is_local_peer
from backend.app.config import get_settings
from backend.app.db.models import (
    ApplicationEventRecord, ExternalApplicationRecord, GmailConnectionRecord,
    GmailMessageRecord, JobMarkRecord, JobRecord, UserRecord,
)
from backend.app.inbox import display, gmail
from backend.app.inbox.full_history import FullMailboxScan
from backend.app.inbox.reconcile import (
    ApplicationIdentity, Decision, EmailEvidence, MAX_CLASSIFIER_BODY, PARSER_VERSION, RECEIPT_REASON, conflict, reconcile,
)

router = APIRouter()
STATE_COOKIE = "ace_gmail_state"
NONCE_COOKIE = "ace_gmail_nonce"
VERIFIER_COOKIE = "ace_gmail_verifier"
PENDING = ("review", "exact_preview", "deferred")
# Emails ACE has not applied to an application can still be decided by hand.
DECIDABLE = PENDING + ("ignored", "receipt", "unrelated", "update")
# Subject words that put an email ACE found no outcome in among the
# recruiting email, so an outcome ACE could not read is still in view.
_ABOUT_APPLICATIONS = ("application", "applying", "applied", "candidacy", "interview", "assessment")
_OUTCOME_STATUS = {"rejection": "rejected", "interview": "interviewing", "offer": "offer",
                   "online_assessment": "screening", "recruiter_reply": "screening"}
# What the owner can say an email was.
_KINDS = {"rejection", "interview", "online_assessment", "offer", "recruiter_reply"}
_TOKENS: dict[tuple[int, bytes], tuple[float, str]] = {}
_LOCKS: dict[int, Lock] = {}
_LOCKS_GUARD = Lock()
# Ephemeral verification, keyed by connection, grant and selected window.
# Never persist an "all imported" claim across an API restart or reconnection.
_COVERAGE: dict[tuple[int, bytes, int], dict] = {}
_FULL_SCANS: dict[tuple[int, bytes, int], FullMailboxScan] = {}


def _sync_lock(connection_id: int):
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(connection_id, Lock())


def _coverage_key(conn: GmailConnectionRecord, days: int) -> tuple[int, bytes, int]:
    return conn.id, bytes(conn.encrypted_refresh_token), days


def _forget_coverage(connection_id: int) -> None:
    for key in list(_FULL_SCANS):
        if key[0] == connection_id:
            _FULL_SCANS.pop(key, None)
    for key in list(_COVERAGE):
        if key[0] == connection_id:
            _COVERAGE.pop(key, None)


def _secure(request: Request) -> bool:
    return request.url.scheme == "https" or (request.headers.get("x-forwarded-proto") == "https" and is_local_peer(request))


def _settings_ready() -> bool:
    s = get_settings()
    return gmail.configured(s.gmail_client_id, s.gmail_client_secret, s.gmail_redirect_uri, s.gmail_token_key)


def _connection(session: Session, owner: UserRecord) -> GmailConnectionRecord | None:
    return session.scalar(select(GmailConnectionRecord).where(GmailConnectionRecord.owner_id == owner.id))


def _public(conn: GmailConnectionRecord | None) -> dict:
    return {
        "connected": bool(conn and conn.encrypted_refresh_token),
        "state": conn.state if conn else "disconnected",
        "email": conn.email if conn and conn.encrypted_refresh_token else None,
        # The last check for new email. Importing older email does not move it.
        "last_synced_at": conn.last_synced_at.isoformat() if conn and conn.last_synced_at else None,
        "following_changes": bool(conn and conn.history_id),
        "coverage": next((value for key, value in reversed(list(_COVERAGE.items()))
                          if conn and key[:2] == (conn.id, bytes(conn.encrypted_refresh_token))), None),
        "last_error": conn.last_error if conn else None,
        "auto_outcomes_enabled": bool(conn and conn.auto_outcomes_enabled),
        "automation_available": get_settings().gmail_auto_outcomes_allowed,
        "auto_rejections": get_settings().gmail_auto_rejections,
    }


@router.get("/api/inbox/connection")
def connection(request: Request, session: Session = Depends(get_session)) -> dict:
    owner = current_owner(request)
    return {"available": _settings_ready(), **_public(_connection(session, owner))}


@router.get("/api/inbox/google/start")
def start(request: Request, session: Session = Depends(get_session)) -> RedirectResponse:
    current_owner(request)
    if not _settings_ready():
        raise HTTPException(503, "Gmail connection is not configured.")
    s = get_settings()
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = gmail.pkce_pair()
    response = RedirectResponse(gmail.authorization_url(s.gmail_client_id, s.gmail_redirect_uri, state, nonce, challenge), status_code=303)
    for name, value in ((STATE_COOKIE, state), (NONCE_COOKIE, nonce), (VERIFIER_COOKIE, verifier)):
        response.set_cookie(name, value, max_age=600, path="/api/inbox/google", httponly=True, secure=_secure(request), samesite="lax")
    return response


@router.get("/api/inbox/google/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = "", session: Session = Depends(get_session)) -> RedirectResponse:
    owner = current_owner(request)
    expected = request.cookies.get(STATE_COOKIE, "")
    nonce = request.cookies.get(NONCE_COOKIE, "")
    verifier = request.cookies.get(VERIFIER_COOKIE, "")
    if error or not code or not state or not expected or not same(state, expected) or not nonce or not verifier or not _settings_ready():
        raise HTTPException(400, "Gmail authorization was cancelled or expired.")
    s = get_settings()
    try:
        email, refresh = gmail.exchange_code(code, verifier, nonce, client_id=s.gmail_client_id, client_secret=s.gmail_client_secret, redirect_uri=s.gmail_redirect_uri)
    except gmail.GmailError as exc:
        raise HTTPException(400, str(exc)) from exc
    conn = _connection(session, owner)
    if conn and conn.email.casefold() != email.casefold() and session.scalar(select(GmailMessageRecord.id).where(GmailMessageRecord.connection_id == conn.id).limit(1)):
        gmail.revoke(refresh)
        raise HTTPException(409, "A different Gmail account cannot be connected while prior account evidence remains.")
    if conn is None:
        conn = GmailConnectionRecord(owner_id=owner.id, email=email, encrypted_refresh_token=b"", scope=gmail.SCOPE)
        session.add(conn)
    if conn.id is not None:
        _forget_coverage(conn.id)
    conn.email = email
    conn.encrypted_refresh_token = gmail.encrypt_token(refresh, s.gmail_token_key)
    conn.state = "paused"  # A new grant never starts background sync.
    conn.history_id = None
    conn.preview_baseline_history_id = None
    conn.preview_complete = False
    conn.auto_outcomes_enabled = False
    conn.last_error = None
    session.commit()
    response = RedirectResponse(s.web_base_url.rstrip("/") + "/app/applications/inbox?connected=1", status_code=303)
    for name in (STATE_COOKIE, NONCE_COOKIE, VERIFIER_COOKIE):
        response.delete_cookie(name, path="/api/inbox/google")
    return response


class ConnectionUpdate(BaseModel):
    paused: bool = True


@router.patch("/api/inbox/connection")
def update_connection(body: ConnectionUpdate, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    if not conn or not conn.encrypted_refresh_token:
        raise HTTPException(404, "Gmail is not connected.")
    conn.state = "paused" if body.paused else "ready"
    session.commit()
    return _public(conn)


@router.delete("/api/inbox/connection")
def disconnect(request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    if conn and conn.encrypted_refresh_token:
        try:
            gmail.revoke(gmail.decrypt_token(conn.encrypted_refresh_token, get_settings().gmail_token_key))
        except gmail.GmailError:
            pass
        _forget_coverage(conn.id)
        conn.encrypted_refresh_token = b""
        conn.state = "disconnected"
        conn.auto_outcomes_enabled = False
        conn.history_id = None
        conn.preview_baseline_history_id = None
        conn.preview_complete = False
        session.commit()
    return _public(conn)


@router.delete("/api/inbox/snippets")
def purge_snippets(request: Request, session: Session = Depends(get_session)) -> dict:
    """Remove retained preview text while preserving decision IDs and audit."""
    conn = _connection(session, current_owner(request))
    if not conn:
        return {"purged": 0}
    rows = session.scalars(select(GmailMessageRecord).where(GmailMessageRecord.connection_id == conn.id, GmailMessageRecord.snippet != "")).all()
    for row in rows:
        row.snippet = ""
    session.commit()
    return {"purged": len(rows)}


def _identities(session: Session) -> list[ApplicationIdentity]:
    rows = session.execute(
        select(JobMarkRecord.job_id, JobRecord.company, JobRecord.title, JobRecord.requisition_id, JobMarkRecord.applied_at, JobMarkRecord.application_status, JobRecord.official_url, JobMarkRecord.status_changed_at)
        .join(JobRecord, JobRecord.id == JobMarkRecord.job_id)
        .where(JobMarkRecord.applied_at.is_not(None))
    ).all()
    identities = [ApplicationIdentity(f"job:{id}", company, title, req, at, status or "applied", url, changed) for id, company, title, req, at, status, url, changed in rows]
    identities += [ApplicationIdentity(f"external:{row.id}", row.company, row.title, None, row.applied_at, row.application_status or "applied", row.url, row.status_changed_at) for row in session.scalars(select(ExternalApplicationRecord)).all()]
    return identities


class _Text(HTMLParser):
    """Readable text from an HTML email. Nothing is rendered or fetched."""

    _SKIP = {"script", "style", "head", "title", "noscript"}
    _BREAK = {"br", "p", "div", "tr", "li", "ul", "ol", "table", "section", "article", "header", "footer",
              "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "body":
            self.skip = 0  # A head left unclosed ends where the body starts.
        if tag in self._SKIP:
            self.skip += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _html_text(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _parts(payload: dict, mime: str) -> list[str]:
    return [display.decode(part) for part in display.parts(payload, mime)]


def _body(payload: dict, limit: int = MAX_CLASSIFIER_BODY) -> str:
    """Plain text when the email has it, else the text of its HTML.

    HTML is never executed or stored here; many employer systems send only
    HTML, and reading its text is how their wording and job IDs count.
    """
    plain = "\n".join(text for text in _parts(payload, "text/plain") if text.strip())
    if plain:
        return plain[:limit]
    return "\n".join(_html_text(text) for text in _parts(payload, "text/html"))[:limit]


def _headers(payload: dict) -> dict[str, str]:
    return {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in payload.get("headers", [])}


def _message_evidence(data: dict) -> EmailEvidence:
    raw_headers = data.get("payload", {}).get("headers", [])
    headers = {h.get("name", "").lower(): h.get("value", "") for h in raw_headers}
    sender_domain = parseaddr(headers.get("from", ""))[1].rpartition("@")[2].casefold()
    # Gmail's own Authentication-Results is the first mx.google.com result.
    # A displayed From address alone is never sufficient for automation.
    auth = next((str(h.get("value", "")) for h in raw_headers
                 if h.get("name", "").casefold() == "authentication-results"
                 and re.match(r"(?i)^\s*mx\.google\.com\s*;", str(h.get("value", "")))), "")
    dmarc = re.search(r"(?i)\bdmarc=pass\b[^;]*\bheader\.from=([a-z0-9.-]+)", auth)
    authenticated = bool(sender_domain and dmarc and dmarc.group(1).casefold() == sender_domain)
    try:
        stamp = parsedate_to_datetime(headers.get("date", ""))
    except (TypeError, ValueError):
        stamp = datetime.fromtimestamp(int(data["internalDate"]) / 1000, timezone.utc)
    # Read one extra character to distinguish a complete boundary-sized body
    # from text clipped before the classifier sees the outcome or role ID.
    body = _body(data.get("payload", {}), MAX_CLASSIFIER_BODY + 1)
    complete = bool(body) and len(body) <= MAX_CLASSIFIER_BODY
    body = body[:MAX_CLASSIFIER_BODY]
    # Gmail's snippet is a couple of hundred characters; a rejection further
    # down an email that opens with thanks would be missed, so say so.
    return EmailEvidence(headers.get("from", "")[:320], headers.get("subject", "")[:500],
                         body or html.unescape(str(data.get("snippet", "")))[:500], stamp, authenticated, complete)


def _access(conn: GmailConnectionRecord) -> str:
    """A Gmail access token, reused for half an hour instead of one per email."""
    key = (conn.id, bytes(conn.encrypted_refresh_token))
    cached = _TOKENS.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    s = get_settings()
    token = gmail.access_token(gmail.decrypt_token(conn.encrypted_refresh_token, s.gmail_token_key), client_id=s.gmail_client_id, client_secret=s.gmail_client_secret)
    _TOKENS.clear()
    _TOKENS[key] = (time.monotonic() + 1800, token)
    return token


def _target(session: Session, key: str):
    kind, sep, value = key.partition(":")
    if not sep or not value.isdigit():
        raise HTTPException(422, "Unknown application identity.")
    if kind == "job":
        return session.scalar(select(JobMarkRecord).where(JobMarkRecord.job_id == int(value), JobMarkRecord.applied_at.is_not(None)).with_for_update())
    if kind == "external":
        return session.scalar(select(ExternalApplicationRecord).where(ExternalApplicationRecord.id == int(value)).with_for_update())
    return None


def _append_event(session: Session, key: str, kind: str, before: str | None, after: str | None, *, actor: str, reason: str, message_id: int | None = None, undo_of: int | None = None, occurred_at: datetime | None = None, dedupe_key: str | None = None) -> ApplicationEventRecord:
    event = ApplicationEventRecord(application_key=key, kind=kind, previous_status=before, new_status=after, actor=actor, reason=reason, gmail_message_id=message_id, undo_of_id=undo_of, occurred_at=occurred_at, dedupe_key=dedupe_key or f"owner:{secrets.token_hex(20)}")
    session.add(event)
    session.flush()
    return event


def _ingest(session: Session, conn: GmailConnectionRecord, data: dict, identities: list[ApplicationIdentity], *, preview: bool) -> str:
    gmail_id = str(data.get("id", ""))
    if not gmail_id:
        return "ignored"
    existing = session.scalar(select(GmailMessageRecord).where(GmailMessageRecord.connection_id == conn.id, GmailMessageRecord.gmail_id == gmail_id))
    if existing:
        return "duplicate"
    evidence = _message_evidence(data)
    decision = reconcile(evidence, identities, conn.email)
    row = GmailMessageRecord(
        connection_id=conn.id, gmail_id=gmail_id, thread_id=data.get("threadId"),
        received_at=evidence.received_at, sender=evidence.sender, subject=evidence.subject,
        snippet=html.unescape(str(data.get("snippet", "")))[:500], classification=decision.classification,
        requisition_id=decision.requisition_id, decision=decision.disposition,
        candidate_keys=list(decision.candidates), decision_reason=decision.reason,
        parser_version=PARSER_VERSION,
    )
    session.add(row)
    session.flush()
    _apply(session, conn, row, decision, evidence, preview=preview, allow_automation=not {"SPAM", "TRASH"}.intersection(data.get("labelIds", [])))
    _append_event(session, f"email:{row.id}", "email_classified", None, row.decision,
                  actor="classifier", reason=row.decision_reason, message_id=row.id,
                  occurred_at=evidence.received_at,
                  dedupe_key=f"gmail:{conn.id}:{gmail_id}:classification")
    return row.decision


def _apply(session: Session, conn: GmailConnectionRecord, row: GmailMessageRecord, decision: Decision, evidence: EmailEvidence, *, preview: bool, allow_automation: bool = True) -> None:
    """Record what an email decided, changing a status only when allowed.

    A clear rejection matched to exactly one application is recorded at once,
    from a historical import too, unless the server switch turns that off.
    Other outcomes still need the separately approved automation and a live
    import. Every change is in the audit trail with Undo.
    """
    row.decision = decision.disposition
    row.selected_application_key = decision.target if decision.disposition == "receipt" else None
    if decision.disposition != "verified" or not decision.target:
        return
    if not allow_automation:
        row.decision = "review"
        row.decision_reason = "Email is in Spam or Trash; confirm its outcome before updating an application"
        return
    s = get_settings()
    rejection = decision.classification == "rejection"
    allowed = s.gmail_auto_rejections if rejection else (not preview and conn.auto_outcomes_enabled and s.gmail_auto_outcomes_allowed)
    if not allowed:
        row.decision = "exact_preview" if preview else "review"
        if not preview:
            row.decision_reason = decision.reason + "; automatic updates are off"
        return
    if session.scalar(select(ApplicationEventRecord.id).where(ApplicationEventRecord.gmail_message_id == row.id, ApplicationEventRecord.actor == "verified_automation").limit(1)):
        row.decision = "review"
        row.decision_reason = "You undid ACE's change for this email"
        return
    target = _target(session, decision.target)
    live = ApplicationIdentity(decision.target, "", "", None, target.applied_at, target.application_status or "applied", None, target.status_changed_at) if target else None
    reason = conflict(live, decision.classification, evidence.received_at) if live else "The application no longer exists"
    if reason:
        row.decision = "review"
        row.decision_reason = reason
        return
    before = target.application_status
    after = _OUTCOME_STATUS.get(decision.classification, before)
    if after != before:
        target.application_status = after
        target.status_changed_at = evidence.received_at
    _append_event(session, decision.target, decision.classification, before, after, actor="verified_automation", reason=decision.reason, message_id=row.id, occurred_at=evidence.received_at, dedupe_key=f"gmail:{conn.id}:{row.gmail_id}:{decision.classification}")
    row.decision = "automatic"
    row.selected_application_key = decision.target


class EmailDisposition(BaseModel):
    action: str


@router.patch("/api/inbox/messages/{message_id}/decision")
def decide_message(message_id: int, body: EmailDisposition, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    row = session.get(GmailMessageRecord, message_id)
    if not conn or not row or row.connection_id != conn.id:
        raise HTTPException(404, "Email not found.")
    if row.decision not in DECIDABLE:
        raise HTTPException(409, "This email already changed an application. Undo that change first.")
    reasons = {"unrelated": "You marked it not about your applications", "deferred": "You chose to decide later",
               "receipt": "You marked it an application receipt",
               "update": "You marked it a status update with no decision yet"}
    if body.action not in reasons:
        raise HTTPException(422, "Choose unrelated, receipt, update or deferred.")
    before = row.decision
    row.decision = body.action
    row.decision_reason = reasons[body.action]
    _append_event(session, f"email:{row.id}", "email_review", before, body.action,
                  actor="owner", reason=row.decision_reason, message_id=row.id)
    session.commit()
    return {"id": row.id, "decision": row.decision}


class AutomationUpdate(BaseModel):
    enabled: bool
    confirmed: bool = False


@router.patch("/api/inbox/automation")
def automation(body: AutomationUpdate, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    if not conn or not conn.encrypted_refresh_token:
        raise HTTPException(409, "Connect Gmail before changing automation.")
    if body.enabled and (not body.confirmed or not get_settings().gmail_auto_outcomes_allowed):
        raise HTTPException(409, "Verified outcome updates are locked until the owner approves the pilot and enables the server flag.")
    conn.auto_outcomes_enabled = body.enabled
    session.commit()
    return _public(conn)


def _new_message_ids(session: Session, conn: GmailConnectionRecord, message_ids: list[str]) -> tuple[list[str], int]:
    """Already imported evidence needs no second Gmail detail read."""
    unique = list(dict.fromkeys(message_ids))
    existing: set[str] = set()
    for offset in range(0, len(unique), 500):
        existing.update(session.scalars(select(GmailMessageRecord.gmail_id).where(
            GmailMessageRecord.connection_id == conn.id, GmailMessageRecord.gmail_id.in_(unique[offset:offset + 500]))))
    return [key for key in unique if key not in existing], len(existing)


def sync_once(session: Session, conn: GmailConnectionRecord, days: int = 0) -> dict:
    """Verify the entire selected window, saving at most 60 new emails per call."""
    lock = _sync_lock(conn.id)
    if not lock.acquire(blocking=False):
        return {"state": "busy", "counts": {}}
    try:
        # A waiting HTTP request may have loaded the connection before a prior
        # batch committed. Read its current cursor/settings after taking the lock.
        session.refresh(conn)
        return _sync_full_locked(session, conn) if days == 0 else _sync_locked(session, conn, max(30, min(days, 365)))
    finally:
        lock.release()


def _sync_locked(session: Session, conn: GmailConnectionRecord, days: int) -> dict:
    if conn.state != "ready" or not conn.encrypted_refresh_token:
        return {"state": conn.state, "counts": {}}
    key = _coverage_key(conn, days)
    # Invalidate the old claim before any network operation can fail.
    _COVERAGE.pop(key, None)
    token = _access(conn)
    # Baseline BEFORE listing, so mail arriving during the listing is picked
    # up by history on the next call. Never use a profile read after listing.
    profile = gmail.get_json("/profile", token)
    baseline = str(profile["historyId"]) if profile.get("historyId") else None
    if not baseline:
        raise gmail.GmailTemporaryError("Gmail did not return a history cursor. Try again later.")
    window_ids, complete = gmail.list_message_ids(token, gmail.window_query(days))
    history_ids: list[str] = []
    history_complete = True
    if conn.history_id:
        try:
            page = None
            for _ in range(60):
                params = {"startHistoryId": conn.history_id, "historyTypes": "messageAdded", "maxResults": 500}
                if page:
                    params["pageToken"] = page
                batch = gmail.get_json("/history", token, params)
                for history in batch.get("history", []):
                    history_ids.extend(str(item["message"]["id"]) for item in history.get("messagesAdded", []) if item.get("message", {}).get("id"))
                page = batch.get("nextPageToken")
                if not page:
                    break
            history_complete = not bool(page)
        except gmail.GmailCursorExpired:
            conn.history_id = None
            conn.preview_complete = False
    new_ids, duplicates = _new_message_ids(session, conn, window_ids + history_ids)
    counts: dict[str, int] = {"duplicate": duplicates} if duplicates else {}
    identities = _identities(session)
    preview = not bool(conn.preview_complete and conn.history_id)
    deleted: set[str] = set()
    live_ids = set(history_ids)
    for message_id in new_ids[:60]:
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
            break
        try:
            data = gmail.get_json("/messages/" + message_id, token, {"format": "full"})
        except gmail.GmailCursorExpired:
            deleted.add(message_id)
            continue
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
            break
        try:
            # A wider verification is a historical import even after the
            # connection has a cursor. Only new history IDs are live outcomes.
            result = _ingest(session, conn, data, identities, preview=preview or message_id not in live_ids)
            session.commit()  # A later quota failure cannot lose saved progress.
        except IntegrityError:
            session.rollback()
            if _new_message_ids(session, conn, [message_id])[0]:
                raise  # Never hide an integrity failure unrelated to a duplicate.
            result = "duplicate"
        counts[result] = counts.get(result, 0) + 1
        if result == "automatic":
            identities = _identities(session)
    # Deleted messages are not evidence. Re-list them away, without claiming a
    # verified count for the earlier listing that still contained them.
    if deleted:
        window_ids, complete = gmail.list_message_ids(token, gmail.window_query(days))
    missing, _ = _new_message_ids(session, conn, window_ids)
    remaining_ids, _ = _new_message_ids(session, conn, window_ids + [item for item in history_ids if item not in deleted])
    remaining = len(remaining_ids)
    session.refresh(conn)
    if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
        return {"state": conn.state if conn.state != "ready" else "disconnected", "counts": counts,
                "remaining": remaining, "partial": True}
    finished = complete and history_complete and remaining == 0
    if finished and baseline:
        conn.history_id = baseline
        conn.preview_complete = True
    conn.last_synced_at = datetime.now(timezone.utc)
    conn.last_error = None
    session.commit()
    coverage = {"days": days, "gmail": len(window_ids), "in_ace": len(window_ids) - len(missing),
                "missing": len(missing), "checked_at": conn.last_synced_at.isoformat(), "complete": complete}
    _COVERAGE[key] = coverage
    return {"state": conn.state, "counts": counts, "remaining": remaining,
            "partial": not finished, "coverage": coverage, "as_of": coverage["checked_at"]}


def _sync_full_locked(session: Session, conn: GmailConnectionRecord) -> dict:
    """All retained mail, including Spam/Trash, with bounded resumable work.

    List at most five pages and read at most sixty details per call. A manifest
    follows every page without a date/page ceiling, then catches changes from
    the pre-list history baseline before certifying a complete snapshot.
    """
    if conn.state != "ready" or not conn.encrypted_refresh_token:
        return {"state": conn.state, "counts": {}}
    key = _coverage_key(conn, 0)
    _COVERAGE.pop(key, None)
    token = _access(conn)
    scan = _FULL_SCANS.get(key)
    if scan is None:
        profile = gmail.get_json("/profile", token)
        baseline = str(profile.get("historyId") or "")
        if not baseline:
            raise gmail.GmailTemporaryError("Gmail did not return a history cursor. Try again later.")
        scan = FullMailboxScan(baseline)
        _FULL_SCANS[key] = scan
    elif scan.phase == "complete":
        scan.phase = "history"
        scan.baseline = scan.snapshot
        scan.history_page = None
        scan.seen_history_pages.clear()
        scan.live = True

    counts: dict[str, int] = {}

    def remember(ids) -> None:
        unseen = list(dict.fromkeys(str(item) for item in ids if item and str(item) not in scan.ids))
        missing, duplicates = _new_message_ids(session, conn, unseen)
        scan.ids.update(unseen)
        scan.pending.extend(missing)
        if duplicates:
            counts["duplicate"] = counts.get("duplicate", 0) + duplicates

    def reset() -> None:
        _FULL_SCANS.pop(key, None)
        conn.history_id = None
        conn.preview_complete = False
        session.commit()

    try:
        if scan.phase == "listing":
            for _ in range(5):
                if len(scan.pending) >= 60:
                    break
                params = {"maxResults": 500, "includeSpamTrash": "true"}
                if scan.page:
                    params["pageToken"] = scan.page
                batch = gmail.get_json("/messages", token, params)
                remember(item.get("id") for item in batch.get("messages", []))
                page = batch.get("nextPageToken")
                if not page:
                    scan.phase = "history_wait"
                    break
                if page in scan.seen_pages:
                    reset()
                    raise gmail.GmailTemporaryError("Gmail repeated a listing page. Saved email is kept; check again to restart verification.")
                scan.seen_pages.add(page)
                scan.page = page
        if scan.phase == "history_wait" and not scan.pending:
            scan.phase = "history"
        if scan.phase == "history":
            for _ in range(5):
                params = {"startHistoryId": scan.baseline, "maxResults": 500}
                if scan.history_page:
                    params["pageToken"] = scan.history_page
                batch = gmail.get_json("/history", token, params)
                for change in batch.get("history", []):
                    remember(item.get("message", {}).get("id") for item in change.get("messagesAdded", []))
                    deleted = {str(item.get("message", {}).get("id")) for item in change.get("messagesDeleted", [])}
                    scan.ids.difference_update(deleted)
                    scan.unavailable.difference_update(deleted)
                    if deleted:
                        scan.pending = deque(item for item in scan.pending if item not in deleted)
                page = batch.get("nextPageToken")
                if not page:
                    scan.snapshot = str(batch.get("historyId") or "")
                    if not scan.snapshot:
                        raise gmail.GmailTemporaryError("Gmail did not return a completed history snapshot. Check again.")
                    scan.snapshot_at = datetime.now(timezone.utc).isoformat()
                    scan.phase = "importing_changes"
                    break
                if page in scan.seen_history_pages:
                    reset()
                    raise gmail.GmailTemporaryError("Gmail repeated a history page. Saved email is kept; check again to restart verification.")
                scan.seen_history_pages.add(page)
                scan.history_page = page
    except (gmail.GmailCursorExpired, gmail.GmailPageExpired) as exc:
        reset()
        raise gmail.GmailTemporaryError("Gmail history or listing expired. Saved email is kept; check again to verify all history.") from exc

    identities = _identities(session)
    for _ in range(min(60, len(scan.pending))):
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
            return {"state": conn.state if conn.state != "ready" else "disconnected", "counts": counts, "partial": True, "more": True}
        message_id = scan.pending[0]
        try:
            data = gmail.get_json("/messages/" + message_id, token, {"format": "full"})
        except gmail.GmailCursorExpired:
            # A failed detail read alone cannot prove the listed ID is gone.
            # Only a deletion event, or a fresh full listing, can resolve it.
            scan.unavailable.add(message_id)
            scan.pending.popleft()
            continue
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
            return {"state": conn.state if conn.state != "ready" else "disconnected", "counts": counts, "partial": True, "more": True}
        if str(data.get("id") or "") != message_id:
            raise gmail.GmailTemporaryError("Gmail returned an incomplete email response. Saved progress is kept; check again.")
        try:
            result = _ingest(session, conn, data, identities, preview=not scan.live)
            session.commit()
        except IntegrityError:
            session.rollback()
            if _new_message_ids(session, conn, [message_id])[0]:
                raise
            result = "duplicate"
        scan.pending.popleft()
        counts[result] = counts.get(result, 0) + 1
        if result == "automatic":
            identities = _identities(session)

    session.refresh(conn)
    if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != key[1]:
        return {"state": conn.state if conn.state != "ready" else "disconnected", "counts": counts, "partial": True, "more": True}
    if scan.phase == "importing_changes" and not scan.pending:
        if scan.unavailable:
            reset()
            raise gmail.GmailTemporaryError("Some listed emails are unavailable and deletion is unconfirmed. Saved progress is kept; verify all history again.")
        scan.phase = "complete"
        conn.history_id = scan.snapshot
        conn.preview_complete = True
    conn.last_synced_at = datetime.now(timezone.utc)
    conn.last_error = None
    session.commit()
    finished = scan.phase == "complete"
    missing = len(scan.pending) + len(scan.unavailable)
    coverage = {"days": 0, "scope": "all", "includes_spam_trash": True,
                "gmail": len(scan.ids), "in_ace": len(scan.ids) - missing,
                "missing": missing, "complete": finished, "phase": scan.phase,
                "checked_at": scan.snapshot_at if finished else conn.last_synced_at.isoformat()}
    _COVERAGE[key] = coverage
    return {"state": conn.state, "counts": counts, "remaining": len(scan.pending),
            "partial": not finished, "more": not finished, "coverage": coverage,
            "as_of": coverage["checked_at"]}


class VerifyRequest(BaseModel):
    days: Literal[0] | Annotated[int, Field(ge=30, le=365)] = 0  # Zero means all retained mail.


@router.post("/api/inbox/sync")
def sync(request: Request, session: Session = Depends(get_session), body: VerifyRequest | None = None) -> dict:
    conn = _connection(session, current_owner(request))
    if not conn:
        raise HTTPException(409, "Connect Gmail before syncing.")
    try:
        return sync_once(session, conn, body.days if body else 0)
    except gmail.GmailError as exc:
        conn.last_error = str(exc)[:120]
        if not isinstance(exc, gmail.GmailTemporaryError):
            conn.state = "error"
        session.commit()
        raise HTTPException(429 if isinstance(exc, gmail.GmailRateLimited) else 502, str(exc)) from exc


class SyncRequest(BaseModel):
    days: int = Field(0, ge=0, le=365)
    page_token: str | None = None


@router.post("/api/inbox/backfill")
def backfill(body: SyncRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    """Historical import. Clear rejections are recorded; other outcomes wait for review."""
    conn = _connection(session, current_owner(request))
    if not conn or not conn.encrypted_refresh_token or conn.state == "disconnected":
        raise HTTPException(409, "Connect Gmail before previewing a backfill.")
    if body.days == 0:
        # Share sync's bounded work, lock and Gmail error response handling.
        return sync(request, session, VerifyRequest())
    lock = _sync_lock(conn.id)
    if not lock.acquire(blocking=False):
        return {"state": "busy", "counts": {}}
    try:
        session.refresh(conn)
        return _backfill_locked(body, request, session, conn)
    finally:
        lock.release()


def _backfill_locked(body: SyncRequest, request: Request, session: Session, conn: GmailConnectionRecord) -> dict:
    s = get_settings()
    try:
        token = gmail.access_token(gmail.decrypt_token(conn.encrypted_refresh_token, s.gmail_token_key), client_id=s.gmail_client_id, client_secret=s.gmail_client_secret)
        if not body.page_token and not conn.history_id:
            profile = gmail.get_json("/profile", token)
            conn.preview_baseline_history_id = str(profile.get("historyId")) if profile.get("historyId") else None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=body.days)).strftime("%Y/%m/%d")
        batch = gmail.get_json("/messages", token, {"q": f"after:{cutoff}", "maxResults": 100, **({"pageToken": body.page_token} if body.page_token else {})})
        identities = _identities(session)
        counts: dict[str, int] = {}
        new_ids, duplicates = _new_message_ids(session, conn, [str(item["id"]) for item in batch.get("messages", [])])
        if duplicates:
            counts["duplicate"] = duplicates
        for message_id in new_ids:
            try:
                data = gmail.get_json("/messages/" + message_id, token, {"format": "full"})
            except gmail.GmailCursorExpired:
                continue  # Deleted after listing; no evidence or outcome exists.
            outcome = _ingest(session, conn, data, identities, preview=True)
            counts[outcome] = counts.get(outcome, 0) + 1
        # Older pages say nothing about new email, so the time of the last
        # check for new email (last_synced_at) stays where sync left it.
        conn.last_error = None
        if not batch.get("nextPageToken") and conn.preview_baseline_history_id and not conn.history_id:
            conn.history_id = conn.preview_baseline_history_id
            conn.preview_complete = True
        session.commit()
        return {"preview_only": True, "counts": counts, "next_page_token": batch.get("nextPageToken"), "as_of": datetime.now(timezone.utc).isoformat()}
    except gmail.GmailError as exc:
        session.rollback()
        conn = _connection(session, current_owner(request))
        assert conn is not None
        conn.last_error = str(exc)[:120]
        session.commit()
        raise HTTPException(429 if isinstance(exc, gmail.GmailRateLimited) else 502, str(exc)) from exc


def _message_query(connection_id: int, decision: str | None = None, q: str | None = None):
    query = select(GmailMessageRecord).where(GmailMessageRecord.connection_id == connection_id)
    if decision == "pending":
        query = query.where(GmailMessageRecord.decision.in_(PENDING))
    elif decision == "recruiting":
        # Everything about applications, newest first, whatever ACE did with it.
        named = or_(*(GmailMessageRecord.subject.ilike(f"%{word}%") for word in _ABOUT_APPLICATIONS))
        query = query.where(or_(GmailMessageRecord.decision.not_in(("ignored", "unrelated")),
                                and_(GmailMessageRecord.decision == "ignored", named)))
    elif decision in {"review", "exact_preview", "deferred", "ignored", "manual", "automatic", "unrelated", "receipt", "update"}:
        query = query.where(GmailMessageRecord.decision == decision)
    elif decision == "ambiguous":
        query = query.where(GmailMessageRecord.decision == "review", GmailMessageRecord.candidate_keys[1].as_string().is_not(None))
    elif decision is not None:
        raise HTTPException(422, "Choose a supported evidence review filter.")
    for word in (q or "").split()[:6]:
        pattern = "%" + re.sub(r"([\\%_])", r"\\\1", word) + "%"
        query = query.where(or_(GmailMessageRecord.sender.ilike(pattern, escape="\\"),
                                GmailMessageRecord.subject.ilike(pattern, escape="\\"),
                                GmailMessageRecord.snippet.ilike(pattern, escape="\\")))
    return query


def _message_rows(session: Session, connection_id: int, decision: str | None = None, offset: int = 0, limit: int = 100,
                  q: str | None = None) -> list[GmailMessageRecord]:
    """Filter before pagination, so ignored mail cannot hide pending evidence."""
    return list(session.scalars(_message_query(connection_id, decision, q).order_by(
        GmailMessageRecord.received_at.desc(), GmailMessageRecord.id.desc()).offset(offset).limit(limit)))


def _stale_query(connection_id: int):
    """Re-read every stale undecided/ACE-filed email, without age/keyword gaps.

    Owner filings and recorded outcomes remain protected across all history.
    """
    return select(GmailMessageRecord).where(
        GmailMessageRecord.connection_id == connection_id, GmailMessageRecord.parser_version != PARSER_VERSION,
        or_(GmailMessageRecord.decision.in_(PENDING),
            and_(GmailMessageRecord.decision == "receipt", GmailMessageRecord.decision_reason == RECEIPT_REASON),
            GmailMessageRecord.decision == "ignored"))


def _item(r: GmailMessageRecord) -> dict:
    return {"id": r.id, "received_at": r.received_at.isoformat(), "sender": r.sender, "subject": r.subject,
            "snippet": html.unescape(r.snippet), "classification": r.classification, "requisition_id": r.requisition_id,
            "decision": r.decision, "candidate_keys": r.candidate_keys or [], "reason": r.decision_reason,
            "selected_application_key": r.selected_application_key}


@router.get("/api/inbox/messages")
def messages(request: Request, session: Session = Depends(get_session), decision: str | None = None,
             offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
             q: Annotated[str | None, Query(max_length=100)] = None) -> dict:
    """One page of imported email. ``decision=auto`` shows what waits for the
    owner when anything does, else the recent recruiting email."""
    conn = _connection(session, current_owner(request))
    counts = {"stored": 0, "needs_review": 0, "automatic": 0, "manual": 0, "reviewed": 0, "receipts": 0, "updates": 0, "stale": 0}
    if not conn:
        return {"items": [], "review_count": 0, "total": 0, "offset": offset, "has_more": False,
                "view": ("pending" if decision == "auto" else decision) or "all", "latest_received_at": None, "counts": counts}
    by_decision = dict(session.execute(select(GmailMessageRecord.decision, func.count()).where(
        GmailMessageRecord.connection_id == conn.id).group_by(GmailMessageRecord.decision)).all())
    review_count = sum(by_decision.get(key, 0) for key in PENDING)
    if decision == "auto":
        decision = "pending" if review_count else "recruiting"
    stale = session.scalar(select(func.count()).select_from(_stale_query(conn.id).subquery())) or 0
    latest = session.scalar(select(func.max(GmailMessageRecord.received_at)).where(GmailMessageRecord.connection_id == conn.id))
    total = session.scalar(select(func.count()).select_from(_message_query(conn.id, decision, q).subquery())) or 0
    rows = _message_rows(session, conn.id, decision, offset, limit, q)
    counts.update({"stored": sum(by_decision.values()), "needs_review": review_count,
                   "automatic": by_decision.get("automatic", 0), "manual": by_decision.get("manual", 0),
                   "reviewed": sum(by_decision.get(key, 0) for key in ("manual", "automatic", "unrelated", "update")),
                   "receipts": by_decision.get("receipt", 0), "updates": by_decision.get("update", 0), "stale": stale})
    return {"items": [_item(r) for r in rows], "review_count": review_count, "total": total, "offset": offset,
            "has_more": offset + len(rows) < total, "view": decision or "all",
            "latest_received_at": latest.isoformat() if latest else None, "counts": counts}


def _owned(session: Session, request: Request, message_id: int) -> tuple[GmailConnectionRecord, GmailMessageRecord]:
    conn = _connection(session, current_owner(request))
    row = session.get(GmailMessageRecord, message_id)
    if not conn or not row or row.connection_id != conn.id:
        raise HTTPException(404, "Email not found.")
    return conn, row


@router.get("/api/inbox/messages/{message_id}")
def message(message_id: int, request: Request, session: Session = Depends(get_session)) -> dict:
    """One imported email, so a link from Analytics can open it."""
    return _item(_owned(session, request, message_id)[1])


@router.get("/api/inbox/messages/{message_id}/full")
def full_message(message_id: int, request: Request, session: Session = Depends(get_session)) -> dict:
    """The whole email, read from Gmail now and never stored.

    ``document`` is the email's own HTML rebuilt for a sandboxed frame (see
    ``display``); ``text`` is the readable text for search and fallbacks.
    """
    conn, row = _owned(session, request, message_id)
    if not conn.encrypted_refresh_token:
        raise HTTPException(404, "Email not found.")
    try:
        token = _access(conn)
        data = gmail.get_json("/messages/" + row.gmail_id, token, {"format": "full"})

        def attachment(key: str) -> str:
            try:
                return str(gmail.get_json(f"/messages/{row.gmail_id}/attachments/{key}", token).get("data", ""))
            except gmail.GmailError:
                return ""  # A picture that cannot be read never hides the email.

        payload = data.get("payload", {})
        snippet = html.unescape(str(data.get("snippet", "")))
        text = _body(payload, 60000) or snippet
        shown = display.show(payload, attachment, fallback=snippet)
    except gmail.GmailCursorExpired as exc:
        raise HTTPException(404, "This email is no longer in Gmail.") from exc
    except gmail.GmailError as exc:
        if not isinstance(exc, gmail.GmailTemporaryError):
            _TOKENS.clear()
        raise HTTPException(429 if isinstance(exc, gmail.GmailRateLimited) else 502, str(exc)) from exc
    headers = _headers(payload)
    message_key = headers.get("message-id", "").strip()
    return {"id": row.id, "sender": headers.get("from") or row.sender, "to": headers.get("to", ""), "cc": headers.get("cc", ""),
            "subject": headers.get("subject") or row.subject, "received_at": row.received_at.isoformat(), "text": text,
            "document": shown.document, "format": shown.kind, "blocked_images": shown.blocked_images,
            "message_id_header": message_key[:300] or None, "thread_id": row.thread_id}


class RecheckRequest(BaseModel):
    limit: int = Field(25, ge=1, le=50)


@router.post("/api/inbox/recheck")
def recheck(body: RecheckRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    """Decide email read under older rules again, under the current ones.

    That is every waiting email and every receipt ACE filed itself. Each is
    read from Gmail again (the full text is not stored) and decided as a
    historical import would be: a clear rejection is recorded, a receipt
    stays a receipt, anything unclear waits. Run it again until none remain.
    """
    conn = _connection(session, current_owner(request))
    if not conn or not conn.encrypted_refresh_token or conn.state == "disconnected":
        raise HTTPException(409, "Connect Gmail before rechecking email.")
    lock = _sync_lock(conn.id)
    if not lock.acquire(blocking=False):
        return {"state": "busy", "checked": 0, "counts": {}, "remaining": 0}
    try:
        session.refresh(conn)
        return _recheck_locked(body, session, conn)
    finally:
        lock.release()


def _recheck_locked(body: RecheckRequest, session: Session, conn: GmailConnectionRecord) -> dict:
    stale = _stale_query(conn.id)
    rows = list(session.scalars(stale.order_by(GmailMessageRecord.received_at.desc(), GmailMessageRecord.id.desc()).limit(body.limit)))
    counts: dict[str, int] = {}
    grant = bytes(conn.encrypted_refresh_token)
    checked = 0
    stopped = None
    identities = _identities(session) if rows else []
    for row in rows:
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != grant:
            stopped = conn.state if conn.state != "ready" else "disconnected"
            break
        data = {}
        try:
            data = gmail.get_json("/messages/" + row.gmail_id, _access(conn), {"format": "full"})
            evidence = _message_evidence(data)
        except gmail.GmailCursorExpired:
            # Deleted from Gmail: decide from what was kept, which cannot
            # prove the sender, so nothing changes automatically.
            evidence = EmailEvidence(row.sender, row.subject, html.unescape(row.snippet), row.received_at, complete=False)
        except gmail.GmailError as exc:
            if not isinstance(exc, gmail.GmailTemporaryError):
                _TOKENS.clear()
            raise HTTPException(429 if isinstance(exc, gmail.GmailRateLimited) else 502, str(exc)) from exc
        checked += 1
        session.refresh(conn)
        if conn.state != "ready" or bytes(conn.encrypted_refresh_token) != grant:
            stopped = conn.state if conn.state != "ready" else "disconnected"
            break
        # Network reads hold no row lock. The owner may file/confirm/undo this
        # email while Gmail responds. Re-select eligibility from the database,
        # refreshing the identity map and locking only for the short write.
        current = session.scalar(stale.where(GmailMessageRecord.id == row.id)
                                 .with_for_update().execution_options(populate_existing=True))
        if current is None:
            continue
        row = current
        decision = reconcile(evidence, identities, conn.email)
        before = row.decision
        row.classification = decision.classification
        row.requisition_id = decision.requisition_id
        row.candidate_keys = list(decision.candidates)
        row.decision_reason = decision.reason
        row.parser_version = PARSER_VERSION
        _apply(session, conn, row, decision, evidence, preview=True, allow_automation=not {"SPAM", "TRASH"}.intersection(data.get("labelIds", [])))
        if before == "deferred" and row.decision in PENDING:
            row.decision = "deferred"
        _append_event(session, f"email:{row.id}", "email_rechecked", before, row.decision, actor="classifier",
                      reason=row.decision_reason, message_id=row.id, occurred_at=row.received_at,
                      dedupe_key=f"gmail:{conn.id}:{row.gmail_id}:recheck:{PARSER_VERSION}")
        session.commit()
        identities = _identities(session) if row.decision == "automatic" else identities
        counts[row.decision] = counts.get(row.decision, 0) + 1
    remaining = session.scalar(select(func.count()).select_from(stale.subquery())) or 0
    return {"checked": checked, "counts": counts, "remaining": remaining,
            **({"state": stopped} if stopped else {})}


@router.get("/api/inbox/applications")
def applications(request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    return {"items": [{"key": a.key, "company": a.company, "title": a.title, "requisition_id": a.requisition_id, "applied_at": a.submitted_at.isoformat() if a.submitted_at else None, "status": a.current_status} for a in _identities(session)]}


@router.get("/api/inbox/events")
def events(request: Request, session: Session = Depends(get_session),
           message_id: Annotated[int | None, Query(ge=1)] = None) -> dict:
    current_owner(request)
    query = select(ApplicationEventRecord).where(~ApplicationEventRecord.application_key.like("action:%"))
    if message_id is not None:
        _owned(session, request, message_id)
        linked = ApplicationEventRecord.__table__.alias("linked_email_events")
        query = query.where(or_(ApplicationEventRecord.gmail_message_id == message_id,
                               ApplicationEventRecord.undo_of_id.in_(select(linked.c.id).where(linked.c.gmail_message_id == message_id))))
    rows = session.scalars(query.order_by(ApplicationEventRecord.recorded_at.desc()).limit(100)).all()
    return {"items": [{"id": e.id, "application_key": e.application_key, "kind": e.kind, "before": e.previous_status, "after": e.new_status, "actor": e.actor, "reason": e.reason, "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None, "recorded_at": e.recorded_at.isoformat(), "undo_of_id": e.undo_of_id, "gmail_message_id": e.gmail_message_id} for e in rows]}


class ManualDecision(BaseModel):
    message_id: int
    application_key: str
    status: str
    expected_status: str
    confirmed: bool = False
    # What the owner says the email is, so Analytics counts it that way.
    kind: str | None = None


@router.post("/api/inbox/review")
def review(body: ManualDecision, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    message = session.get(GmailMessageRecord, body.message_id)
    if not body.confirmed or not conn or not message or message.connection_id != conn.id or message.decision not in DECIDABLE:
        raise HTTPException(409, "Choose a pending email and confirm the exact application.")
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(422, "Unknown application status.")
    if body.kind is not None and body.kind not in _KINDS:
        raise HTTPException(422, "Unknown email outcome.")
    target = _target(session, body.application_key)
    if not target or (target.application_status or "applied") != body.expected_status:
        raise HTTPException(409, "Application status changed. Reload before confirming.")
    before = target.application_status
    target.application_status = body.status
    target.status_changed_at = datetime.now(timezone.utc)
    event = _append_event(session, body.application_key, "manual_correction", before, body.status, actor="owner", reason="Owner selected the exact application after reviewing email evidence", message_id=message.id, occurred_at=message.received_at)
    message.decision = "manual"
    message.selected_application_key = body.application_key
    if body.kind:
        message.classification = body.kind
    session.commit()
    return {"event_id": event.id, "application_key": body.application_key, "status": body.status}


class AddedApplication(BaseModel):
    message_id: int
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    status: str
    kind: str | None = None
    applied_on: date | None = None


@router.post("/api/inbox/applications")
def add_application(body: AddedApplication, request: Request, session: Session = Depends(get_session)) -> dict:
    """An application ACE never knew about, added from the email about it.

    Applications made outside ACE leave nothing to choose, so an email about
    one could never be recorded. This keeps it as external history (the same
    record an import makes, reused when company and role already match) and
    records what the email says, with the usual event and Undo.
    """
    conn = _connection(session, current_owner(request))
    message = session.get(GmailMessageRecord, body.message_id)
    if not conn or not message or message.connection_id != conn.id or message.decision not in DECIDABLE:
        raise HTTPException(409, "Choose a pending email first.")
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(422, "Unknown application status.")
    if body.kind is not None and body.kind not in _KINDS:
        raise HTTPException(422, "Unknown email outcome.")
    company, title = " ".join(body.company.split()), " ".join(body.title.split())
    if not company or not title:
        raise HTTPException(422, "Give the company and the role.")
    key = external_match_key(company=company, title=title)
    application = session.scalar(select(ExternalApplicationRecord).where(ExternalApplicationRecord.match_key == key).with_for_update())
    created = application is None
    if application is None:
        applied = datetime.combine(body.applied_on, day_time(12, 0), tzinfo=timezone.utc) if body.applied_on else None
        application = ExternalApplicationRecord(company=company, title=title, match_key=key, applied_at=applied, application_status="applied")
        session.add(application)
        session.flush()
    application_key = f"external:{application.id}"
    before = application.application_status or "applied"
    application.application_status = body.status
    application.status_changed_at = datetime.now(timezone.utc)
    event = _append_event(session, application_key, "manual_correction", before, body.status, actor="owner",
                          reason="Owner added the application from an email and recorded what it said",
                          message_id=message.id, occurred_at=message.received_at)
    message.decision = "manual"
    message.selected_application_key = application_key
    if body.kind:
        message.classification = body.kind
    session.commit()
    return {"event_id": event.id, "application_key": application_key, "status": body.status, "created": created}


@router.post("/api/inbox/events/{event_id}/undo")
def undo(event_id: int, request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    event = session.get(ApplicationEventRecord, event_id)
    if not event or event.actor not in {"owner", "verified_automation"} or event.kind == "undo" or not event.application_key.startswith(("job:", "external:")):
        raise HTTPException(404, "Change cannot be undone.")
    if session.scalar(select(ApplicationEventRecord.id).where(ApplicationEventRecord.undo_of_id == event_id)):
        raise HTTPException(409, "This change was already undone.")
    target = _target(session, event.application_key)
    if not target or target.application_status != event.new_status:
        raise HTTPException(409, "A newer status exists. Review the application before correcting it.")
    target.application_status = event.previous_status
    target.status_changed_at = datetime.now(timezone.utc)
    correction = _append_event(session, event.application_key, "undo", event.new_status, event.previous_status, actor="owner", reason="Owner undid an earlier reconciliation", undo_of=event.id)
    # The email goes back to the queue, so the owner can say what it means.
    message = session.get(GmailMessageRecord, event.gmail_message_id) if event.gmail_message_id else None
    if message and message.decision in {"automatic", "manual"} and message.selected_application_key == event.application_key:
        message.decision = "review"
        message.selected_application_key = None
        message.decision_reason = "You undid the change this email made"
    session.commit()
    return {"event_id": correction.id, "application_key": event.application_key, "status": event.previous_status}
