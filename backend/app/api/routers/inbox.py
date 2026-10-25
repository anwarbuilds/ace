"""Owner-only Gmail preview, reconciliation, review and audit endpoints."""

from __future__ import annotations

import base64
import re
import secrets
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.marks import APPLICATION_STATUSES
from backend.app.auth.crypto import same
from backend.app.auth.guard import current_owner, is_local_peer
from backend.app.config import get_settings
from backend.app.db.models import (
    ApplicationEventRecord, ExternalApplicationRecord, GmailConnectionRecord,
    GmailMessageRecord, JobMarkRecord, JobRecord, UserRecord,
)
from backend.app.inbox import gmail
from backend.app.inbox.reconcile import ApplicationIdentity, EmailEvidence, PARSER_VERSION, reconcile

router = APIRouter()
STATE_COOKIE = "ace_gmail_state"
NONCE_COOKIE = "ace_gmail_nonce"
VERIFIER_COOKIE = "ace_gmail_verifier"


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
        "last_synced_at": conn.last_synced_at.isoformat() if conn and conn.last_synced_at else None,
        "last_error": conn.last_error if conn else None,
        "auto_outcomes_enabled": bool(conn and conn.auto_outcomes_enabled),
        "automation_available": get_settings().gmail_auto_outcomes_allowed,
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


def _body(payload: dict) -> str:
    """Use only plain text. Never execute, render or persist HTML email."""
    if payload.get("mimeType") == "text/plain":
        encoded = payload.get("body", {}).get("data", "")
        try:
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", "replace")[:10000]
        except (ValueError, TypeError):
            return ""
    return "\n".join(_body(part) for part in payload.get("parts", []) if isinstance(part, dict))[:10000]


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
    return EmailEvidence(headers.get("from", "")[:320], headers.get("subject", "")[:500], _body(data.get("payload", {})) or str(data.get("snippet", ""))[:500], stamp, authenticated)


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
    # Company/title text is only used to present plausible review candidates.
    # Exact IDs are checked against the full application set in reconcile().
    decision = reconcile(evidence, identities)
    candidate_keys = list(decision.candidates)
    if decision.requisition_id is None:
        text = (evidence.subject + " " + evidence.body).casefold()
        candidate_keys = [a.key for a in identities if a.company.casefold() in text][:20]
    disposition = "exact_preview" if preview and decision.disposition == "verified" else decision.disposition
    row = GmailMessageRecord(
        connection_id=conn.id, gmail_id=gmail_id, thread_id=data.get("threadId"),
        received_at=evidence.received_at, sender=evidence.sender, subject=evidence.subject,
        snippet=str(data.get("snippet", ""))[:500], classification=decision.classification,
        requisition_id=decision.requisition_id, decision=disposition,
        candidate_keys=candidate_keys, decision_reason=decision.reason,
        selected_application_key=decision.target if disposition == "verified" else None,
        parser_version=PARSER_VERSION,
    )
    session.add(row)
    session.flush()
    _append_event(session, f"email:{row.id}", "email_classified", None, disposition,
                  actor="classifier", reason=decision.reason, message_id=row.id,
                  occurred_at=evidence.received_at,
                  dedupe_key=f"gmail:{conn.id}:{gmail_id}:classification")
    if decision.disposition == "verified" and not preview and conn.auto_outcomes_enabled and get_settings().gmail_auto_outcomes_allowed and decision.target:
        target = _target(session, decision.target)
        changed = target.status_changed_at if target else None
        if changed is not None and changed.tzinfo is None:
            changed = changed.replace(tzinfo=timezone.utc)
        received = evidence.received_at if evidence.received_at.tzinfo else evidence.received_at.replace(tzinfo=timezone.utc)
        if not target or target.application_status in {"accepted", "rejected", "withdrawn"} or (changed is not None and changed > received):
            row.decision = "review"
            row.selected_application_key = None
            row.decision_reason = "A newer or terminal application status is protected"
        else:
            before = target.application_status
            after = {"rejection": "rejected", "interview": "interviewing", "offer": "offer"}.get(decision.classification, before)
            if after != before:
                target.application_status = after
                target.status_changed_at = evidence.received_at
            _append_event(session, decision.target, decision.classification, before, after, actor="verified_automation", reason=decision.reason, message_id=row.id, occurred_at=evidence.received_at, dedupe_key=f"gmail:{conn.id}:{gmail_id}:{decision.classification}")
            row.decision = "automatic"
            row.selected_application_key = decision.target
    elif decision.disposition == "verified" and not preview:
        row.decision = "review"
        row.decision_reason = "Verified identity, but automatic outcomes are disabled"
    return row.decision


class EmailDisposition(BaseModel):
    action: str


@router.patch("/api/inbox/messages/{message_id}/decision")
def decide_message(message_id: int, body: EmailDisposition, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    row = session.get(GmailMessageRecord, message_id)
    if not conn or not row or row.connection_id != conn.id or row.decision not in {"review", "exact_preview", "deferred"}:
        raise HTTPException(409, "This email is not in the review queue.")
    if body.action not in {"unrelated", "deferred"}:
        raise HTTPException(422, "Choose unrelated or deferred.")
    before = row.decision
    row.decision = body.action
    row.decision_reason = "Owner marked the email " + body.action
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


def sync_once(session: Session, conn: GmailConnectionRecord) -> dict:
    """Resumable catch-up. Advance the cursor only after evidence commits."""
    if conn.state != "ready" or not conn.encrypted_refresh_token:
        return {"state": conn.state, "counts": {}}
    s = get_settings()
    token = gmail.access_token(gmail.decrypt_token(conn.encrypted_refresh_token, s.gmail_token_key), client_id=s.gmail_client_id, client_secret=s.gmail_client_secret)
    identities = _identities(session)
    counts: dict[str, int] = {}
    next_cursor: str | None = None
    message_ids: list[str] = []
    partial = False
    if conn.history_id:
        try:
            page_token: str | None = None
            while True:
                params = {"startHistoryId": conn.history_id, "historyTypes": "messageAdded", "maxResults": 100}
                if page_token:
                    params["pageToken"] = page_token
                batch = gmail.get_json("/history", token, params)
                next_cursor = str(batch.get("historyId") or conn.history_id)
                for history in batch.get("history", []):
                    message_ids.extend(str(item["message"]["id"]) for item in history.get("messagesAdded", []) if item.get("message", {}).get("id"))
                page_token = batch.get("nextPageToken")
                if not page_token:
                    break
        except gmail.GmailCursorExpired:
            conn.history_id = None
            next_cursor = None
    if not conn.history_id:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y/%m/%d")
        batch = gmail.get_json("/messages", token, {"q": f"after:{cutoff}", "maxResults": 500})
        message_ids = [str(item["id"]) for item in batch.get("messages", [])]
        partial = bool(batch.get("nextPageToken"))
        if not partial:
            profile = gmail.get_json("/profile", token)
            next_cursor = str(profile.get("historyId")) if profile.get("historyId") else None
    for message_id in dict.fromkeys(message_ids):
        try:
            data = gmail.get_json("/messages/" + message_id, token, {"format": "full"})
        except gmail.GmailCursorExpired:
            continue  # Message was deleted after it appeared in history.
        result = _ingest(session, conn, data, identities, preview=not bool(conn.preview_complete and conn.history_id))
        counts[result] = counts.get(result, 0) + 1
    if not partial and next_cursor:
        conn.history_id = next_cursor
        conn.preview_complete = True
    conn.last_synced_at = datetime.now(timezone.utc)
    conn.last_error = None
    session.commit()
    return {"state": conn.state, "counts": counts, "partial": partial, "as_of": conn.last_synced_at.isoformat()}


@router.post("/api/inbox/sync")
def sync(request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    if not conn:
        raise HTTPException(409, "Connect Gmail before syncing.")
    try:
        return sync_once(session, conn)
    except gmail.GmailError as exc:
        conn.last_error = str(exc)
        conn.state = "error"
        session.commit()
        raise HTTPException(502, str(exc)) from exc


class SyncRequest(BaseModel):
    days: int = Field(30, ge=1, le=365)
    page_token: str | None = None


@router.post("/api/inbox/backfill")
def backfill(body: SyncRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    """Historical import is always preview-only, regardless of settings."""
    conn = _connection(session, current_owner(request))
    if not conn or not conn.encrypted_refresh_token or conn.state == "disconnected":
        raise HTTPException(409, "Connect Gmail before previewing a backfill.")
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
        for item in batch.get("messages", []):
            data = gmail.get_json("/messages/" + str(item["id"]), token, {"format": "full"})
            outcome = _ingest(session, conn, data, identities, preview=True)
            counts[outcome] = counts.get(outcome, 0) + 1
        conn.last_synced_at = datetime.now(timezone.utc)
        conn.last_error = None
        if not batch.get("nextPageToken") and conn.preview_baseline_history_id and not conn.history_id:
            conn.history_id = conn.preview_baseline_history_id
            conn.preview_complete = True
        session.commit()
        return {"preview_only": True, "counts": counts, "next_page_token": batch.get("nextPageToken"), "as_of": conn.last_synced_at.isoformat()}
    except gmail.GmailError as exc:
        session.rollback()
        conn = _connection(session, current_owner(request))
        assert conn is not None
        conn.last_error = str(exc)
        session.commit()
        raise HTTPException(502, str(exc)) from exc


def _message_rows(session: Session, connection_id: int, decision: str | None = None) -> list[GmailMessageRecord]:
    """Apply Analytics review filters before the existing bounded mailbox page."""
    query = select(GmailMessageRecord).where(GmailMessageRecord.connection_id == connection_id)
    if decision in {"review", "exact_preview"}:
        query = query.where(GmailMessageRecord.decision == decision)
    elif decision == "ambiguous":
        query = query.where(GmailMessageRecord.decision == "review", GmailMessageRecord.candidate_keys[1].as_string().is_not(None))
    elif decision is not None:
        raise HTTPException(422, "Choose a supported evidence review filter.")
    return list(session.scalars(query.order_by(GmailMessageRecord.received_at.desc(), GmailMessageRecord.id.desc()).limit(100)))


@router.get("/api/inbox/messages")
def messages(request: Request, session: Session = Depends(get_session), decision: str | None = None) -> dict:
    conn = _connection(session, current_owner(request))
    if not conn:
        return {"items": [], "review_count": 0}
    rows = _message_rows(session, conn.id, decision)
    return {"items": [{"id": r.id, "received_at": r.received_at.isoformat(), "sender": r.sender, "subject": r.subject, "snippet": r.snippet, "classification": r.classification, "requisition_id": r.requisition_id, "decision": r.decision, "candidate_keys": r.candidate_keys or [], "reason": r.decision_reason, "selected_application_key": r.selected_application_key} for r in rows], "review_count": sum(r.decision in {"review", "exact_preview"} for r in rows)}


@router.get("/api/inbox/applications")
def applications(request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    return {"items": [{"key": a.key, "company": a.company, "title": a.title, "requisition_id": a.requisition_id, "applied_at": a.submitted_at.isoformat() if a.submitted_at else None, "status": a.current_status} for a in _identities(session)]}


@router.get("/api/inbox/events")
def events(request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    rows = session.scalars(select(ApplicationEventRecord).where(~ApplicationEventRecord.application_key.like("action:%")).order_by(ApplicationEventRecord.recorded_at.desc()).limit(100)).all()
    return {"items": [{"id": e.id, "application_key": e.application_key, "kind": e.kind, "before": e.previous_status, "after": e.new_status, "actor": e.actor, "reason": e.reason, "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None, "recorded_at": e.recorded_at.isoformat(), "undo_of_id": e.undo_of_id, "gmail_message_id": e.gmail_message_id} for e in rows]}


class ManualDecision(BaseModel):
    message_id: int
    application_key: str
    status: str
    expected_status: str
    confirmed: bool = False


@router.post("/api/inbox/review")
def review(body: ManualDecision, request: Request, session: Session = Depends(get_session)) -> dict:
    conn = _connection(session, current_owner(request))
    message = session.get(GmailMessageRecord, body.message_id)
    if not body.confirmed or not conn or not message or message.connection_id != conn.id or message.decision not in {"review", "exact_preview", "deferred"}:
        raise HTTPException(409, "Choose a pending email and confirm the exact application.")
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(422, "Unknown application status.")
    target = _target(session, body.application_key)
    if not target or (target.application_status or "applied") != body.expected_status:
        raise HTTPException(409, "Application status changed. Reload before confirming.")
    before = target.application_status
    target.application_status = body.status
    target.status_changed_at = datetime.now(timezone.utc)
    event = _append_event(session, body.application_key, "manual_correction", before, body.status, actor="owner", reason="Owner selected the exact application after reviewing email evidence", message_id=message.id)
    message.decision = "manual"
    message.selected_application_key = body.application_key
    session.commit()
    return {"event_id": event.id, "application_key": body.application_key, "status": body.status}


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
    session.commit()
    return {"event_id": correction.id, "application_key": event.application_key, "status": event.previous_status}
