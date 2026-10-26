"""Database assertions for automatic rejections, ambiguity, duplicates and history."""

import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.routers import inbox
from backend.app.api.routers.inbox import _identities, _ingest
from backend.app.api.marks import mark_counts
from backend.app.auth.guard import Principal
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import ApplicationEventRecord, GmailConnectionRecord, GmailMessageRecord, JobMarkRecord, JobRecord, UserRecord
from backend.app.inbox.reconcile import PARSER_VERSION


NOW = datetime.now(timezone.utc)


def message(message_id: str, body: str, received_at: datetime = NOW) -> dict:
    return {"id": message_id, "threadId": "thread-1", "internalDate": str(int(received_at.timestamp() * 1000)),
            "snippet": body, "payload": {"headers": [{"name": "Authentication-Results", "value": "mx.google.com; dmarc=pass header.from=careers.silverpine.example"},
                                                  {"name": "From", "value": "talent@careers.silverpine.example"},
                                                  {"name": "Subject", "value": "Application update"},
                                                  {"name": "Date", "value": received_at.strftime("%a, %d %b %Y %H:%M:%S +0000")}],
                                        "mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}}


def job_events(session: Session) -> list[ApplicationEventRecord]:
    return list(session.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.application_key.like("job:%")).order_by(ApplicationEventRecord.id)))


def statuses(session: Session) -> list[str]:
    return [r.application_status for r in session.scalars(select(JobMarkRecord).order_by(JobMarkRecord.job_id))]


@pytest.fixture
def database(monkeypatch):
    monkeypatch.delenv("GMAIL_AUTO_REJECTIONS", raising=False)
    monkeypatch.setenv("GMAIL_AUTO_OUTCOMES_ALLOWED", "true")
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(UserRecord(id=1, email="owner-fixture@example.test", password_hash="fictional", created_at=NOW, password_changed_at=NOW))
        conn = GmailConnectionRecord(owner_id=1, email="fictional@example.test", encrypted_refresh_token=b"fixture", scope="gmail.readonly", state="ready", auto_outcomes_enabled=True)
        session.add(conn)
        for index in range(3):
            job = JobRecord(source="test", source_account="fictional", external_id=str(index), company="Silverpine Labs", title="Software Engineer", location="US", description="Fictional test opening", official_url=f"https://careers.silverpine.example/jobs/{index}", content_hash="h", first_seen_at=NOW-timedelta(days=40), last_seen_at=NOW, is_active=True, requisition_id=f"SE-10{index}")
            session.add(job); session.flush()
            session.add(JobMarkRecord(job_id=job.id, applied_at=NOW-timedelta(days=30), application_status="applied"))
        session.commit()
        yield session, conn
    get_settings.cache_clear()


@pytest.fixture
def gmail_reads(monkeypatch):
    monkeypatch.setattr(inbox.gmail, "decrypt_token", lambda *a: "fictional-refresh")
    monkeypatch.setattr(inbox.gmail, "access_token", lambda *a, **k: "fictional-access")
    inbox._TOKENS.clear()
    yield
    inbox._TOKENS.clear()


def owner_request():
    return SimpleNamespace(state=SimpleNamespace(principal=Principal(kind="session", user=SimpleNamespace(id=1))))


def row_for(session: Session, gmail_id: str) -> GmailMessageRecord:
    return session.scalar(select(GmailMessageRecord).where(GmailMessageRecord.gmail_id == gmail_id))


def test_clear_rejection_is_recorded_even_from_a_historical_import(database):
    session, conn = database
    identities = _identities(session)
    ambiguous = message("ambiguous", "We have decided to move forward with other candidates.")
    assert _ingest(session, conn, ambiguous, identities, preview=True) == "review"
    assert job_events(session) == []

    exact = message("exact", "Req ID: SE-101. We have decided to move forward with other candidates.")
    assert _ingest(session, conn, exact, identities, preview=True) == "automatic"
    assert _ingest(session, conn, exact, identities, preview=False) == "duplicate"
    assert statuses(session) == ["applied", "rejected", "applied"]
    [event] = job_events(session)
    assert (event.kind, event.actor, event.previous_status, event.new_status) == ("rejection", "verified_automation", "applied", "rejected")
    row = row_for(session, "exact")
    assert row.selected_application_key == event.application_key and row.parser_version == PARSER_VERSION
    assert mark_counts(session)["applications_total"] == 3


def test_positive_outcomes_keep_the_stricter_path(database):
    session, conn = database
    identities = _identities(session)
    preview = message("preview-interview", "Req ID: SE-102. We invite you to interview.")
    assert _ingest(session, conn, preview, identities, preview=True) == "exact_preview"
    assessment = message("assessment", "Req ID: SE-100. Please complete the online assessment.")
    assert _ingest(session, conn, assessment, identities, preview=False) == "automatic"
    interview = message("new-interview", "Req ID: SE-102. We invite you to interview.")
    assert _ingest(session, conn, interview, identities, preview=False) == "automatic"
    assert statuses(session) == ["applied", "applied", "interviewing"]
    # A rejection older than the interview cannot undo the newer stage.
    older = message("old-rejection", "Req ID: SE-102. We have decided to move forward with other candidates.", NOW - timedelta(days=1))
    assert _ingest(session, conn, older, _identities(session), preview=False) == "review"
    assert statuses(session) == ["applied", "applied", "interviewing"]
    assert {e.kind for e in job_events(session)} == {"online_assessment", "interview"}
    assert mark_counts(session)["applications_total"] == 3


def test_server_switch_sends_rejections_back_to_review(database, monkeypatch):
    session, conn = database
    monkeypatch.setenv("GMAIL_AUTO_REJECTIONS", "false")
    get_settings.cache_clear()
    exact = message("exact", "Req ID: SE-101. You have not been selected.")
    assert _ingest(session, conn, exact, _identities(session), preview=False) == "review"
    assert job_events(session) == []


def test_receipts_are_filed_without_changing_anything(database):
    session, conn = database
    receipt = message("receipt", "Thank you for applying. We have received your application for Req ID: SE-100.")
    assert _ingest(session, conn, receipt, _identities(session), preview=True) == "receipt"
    assert job_events(session) == []
    counts = inbox.messages(owner_request(), session, None, 0, 50)["counts"]
    assert counts["receipts"] == 1 and counts["needs_review"] == 0


def test_one_click_review_records_what_the_owner_says_and_undo_returns_the_email(database):
    session, conn = database
    _ingest(session, conn, message("unclear", "We have decided to move forward with other candidates."), _identities(session), preview=True)
    row = row_for(session, "unclear")
    first = row.candidate_keys[0]
    result = inbox.review(inbox.ManualDecision(message_id=row.id, application_key=first, status="screening", expected_status="applied",
                                               confirmed=True, kind="online_assessment"), owner_request(), session)
    assert row.decision == "manual" and row.classification == "online_assessment"
    with pytest.raises(HTTPException):
        inbox.review(inbox.ManualDecision(message_id=row.id, application_key=first, status="rejected", expected_status="screening",
                                          confirmed=True), owner_request(), session)
    inbox.undo(result["event_id"], owner_request(), session)
    assert row.decision == "review" and row.selected_application_key is None
    assert statuses(session) == ["applied"] * 3


def test_owner_can_decide_an_email_ace_ignored_but_not_one_already_applied(database):
    session, conn = database
    _ingest(session, conn, message("noise", "Weekly newsletter about our culture."), _identities(session), preview=True)
    noise = row_for(session, "noise")
    assert noise.decision == "ignored"
    assert inbox.decide_message(noise.id, inbox.EmailDisposition(action="receipt"), owner_request(), session)["decision"] == "receipt"
    _ingest(session, conn, message("done", "Req ID: SE-101. You have not been selected."), _identities(session), preview=True)
    done = row_for(session, "done")
    assert done.decision == "automatic"
    with pytest.raises(HTTPException) as error:
        inbox.decide_message(done.id, inbox.EmailDisposition(action="unrelated"), owner_request(), session)
    assert error.value.status_code == 409


def test_undone_automatic_change_is_not_repeated_by_a_recheck(database, gmail_reads, monkeypatch):
    session, conn = database
    exact = message("exact", "Req ID: SE-101. You have not been selected.")
    _ingest(session, conn, exact, _identities(session), preview=True)
    [event] = job_events(session)
    inbox.undo(event.id, owner_request(), session)
    row = row_for(session, "exact")
    row.parser_version = "1"
    session.commit()
    monkeypatch.setattr(inbox.gmail, "get_json", lambda path, *a: exact)
    result = inbox.recheck(inbox.RecheckRequest(), owner_request(), session)
    assert result["counts"] == {"review": 1} and result["remaining"] == 0
    assert row.decision_reason == "You undid ACE's change for this email"
    assert statuses(session) == ["applied"] * 3


def test_recheck_applies_current_rules_to_waiting_email(database, gmail_reads, monkeypatch):
    session, conn = database
    bodies = {"old-exact": ("Ref: SE-102. We won't be moving forward with your application.", "review", "1"),
              "old-deferred": ("Thank you for applying. Unfortunately, we will not be moving forward.", "deferred", "1"),
              "old-receipt": ("Thank you for applying. We have received your application.", "review", "1"),
              "current": ("Req ID: SE-100. We invite you to interview.", "exact_preview", PARSER_VERSION)}
    for name, (_body, decision, version) in bodies.items():
        session.add(GmailMessageRecord(connection_id=conn.id, gmail_id=name, received_at=NOW - timedelta(hours=1), sender="talent@careers.silverpine.example",
                                       subject="Application update", snippet="Fictional", classification="unknown", decision=decision, candidate_keys=[],
                                       decision_reason="Fictional fixture", parser_version=version))
    session.commit()
    reads = []

    def get(path, *args):
        reads.append(path)
        name = path.rsplit("/", 1)[1]
        return message(name, bodies[name][0], NOW - timedelta(hours=1))

    monkeypatch.setattr(inbox.gmail, "get_json", get)
    assert inbox.messages(owner_request(), session, None, 0, 50)["counts"]["stale"] == 3
    result = inbox.recheck(inbox.RecheckRequest(limit=2), owner_request(), session)
    assert result["checked"] == 2 and result["remaining"] == 1
    assert inbox.recheck(inbox.RecheckRequest(), owner_request(), session)["remaining"] == 0
    decisions = {r.gmail_id: r.decision for r in session.scalars(select(GmailMessageRecord))}
    # The generic rejection fits three applications, so it stays deferred.
    assert decisions == {"old-exact": "automatic", "old-deferred": "deferred", "old-receipt": "receipt", "current": "exact_preview"}
    assert "/messages/current" not in reads
    assert statuses(session) == ["applied", "applied", "rejected"]
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord).where(ApplicationEventRecord.kind == "email_rechecked")) == 3


def test_full_email_is_read_live_and_never_stored(database, gmail_reads, monkeypatch):
    session, conn = database
    _ingest(session, conn, message("full", "Req ID: SE-100. Thank you for applying."), _identities(session), preview=True)
    row = row_for(session, "full")
    long_body = "Hello,\n\n" + "A long paragraph about the role. " * 40 + "\nBest regards"
    monkeypatch.setattr(inbox.gmail, "get_json", lambda path, *a: message("full", long_body))
    assert inbox.full_message(row.id, owner_request(), session)["text"] == long_body
    assert len(row.snippet) <= 500 and "Best regards" not in row.snippet

    def gone(*args):
        raise inbox.gmail.GmailCursorExpired("Fictional deleted message")

    monkeypatch.setattr(inbox.gmail, "get_json", gone)
    with pytest.raises(HTTPException) as error:
        inbox.full_message(row.id, owner_request(), session)
    assert error.value.status_code == 404


def stored(session: Session, conn, gmail_id: str, decision: str, subject: str, *, sender: str = "talent@careers.silverpine.example",
           reason: str = "Fictional fixture", version: str = PARSER_VERSION, minutes: int = 0, snippet: str = "Fictional") -> GmailMessageRecord:
    row = GmailMessageRecord(connection_id=conn.id, gmail_id=gmail_id, received_at=NOW - timedelta(minutes=minutes), sender=sender,
                             subject=subject, snippet=snippet, classification="unknown", decision=decision, candidate_keys=[],
                             decision_reason=reason, parser_version=version)
    session.add(row)
    session.flush()
    return row


def test_default_view_shows_recruiting_email_and_search_finds_it(database):
    session, conn = database
    stored(session, conn, "auto", "automatic", "Your application to Silverpine Labs", minutes=1)
    stored(session, conn, "receipt", "receipt", "Thanks for applying", minutes=2)
    stored(session, conn, "noise", "ignored", "Weekly newsletter", minutes=3)
    maybe = stored(session, conn, "maybe", "ignored", "Update on your application", sender="Wayfern Fiction <no-reply@ashbyhq.example>", minutes=4)
    stored(session, conn, "elsewhere", "unrelated", "Your application for a fictional credit card", minutes=5)
    session.commit()
    page = inbox.messages(owner_request(), session, "auto", 0, 50)
    # Nothing waits, so the newest recruiting email shows, whatever ACE did with it.
    assert page["view"] == "recruiting"
    assert page["latest_received_at"][:16] == (NOW - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")
    assert [item["subject"] for item in page["items"]] == ["Your application to Silverpine Labs", "Thanks for applying", "Update on your application"]
    found = inbox.messages(owner_request(), session, None, 0, 50, "  WAYFERN  ")
    assert [item["id"] for item in found["items"]] == [maybe.id] and found["total"] == 1
    assert inbox.messages(owner_request(), session, None, 0, 50, "100%_")["total"] == 0  # Wildcards are literal.
    assert inbox.message(maybe.id, owner_request(), session)["subject"] == "Update on your application"
    stored(session, conn, "waiting", "review", "Interview invitation")
    session.commit()
    assert inbox.messages(owner_request(), session, "auto", 0, 50)["view"] == "pending"
    with pytest.raises(HTTPException) as error:
        inbox.message(maybe.id + 100, owner_request(), session)
    assert error.value.status_code == 404


def test_owner_can_file_a_status_update_that_changes_nothing(database):
    session, conn = database
    row = stored(session, conn, "update", "ignored", "Your application is under review")
    session.commit()
    assert inbox.decide_message(row.id, inbox.EmailDisposition(action="update"), owner_request(), session)["decision"] == "update"
    counts = inbox.messages(owner_request(), session, "update", 0, 50)
    assert counts["counts"]["updates"] == 1 and [item["id"] for item in counts["items"]] == [row.id]
    assert job_events(session) == [] and statuses(session) == ["applied"] * 3


def test_recheck_rereads_receipts_ace_filed_but_never_the_owners(database, gmail_reads, monkeypatch):
    session, conn = database
    from backend.app.inbox.reconcile import RECEIPT_REASON
    bodies = {"ace-receipt": "Req ID: SE-101. Thank you for applying. Unfortunately, we won't be moving forward.",
              "owner-receipt": "Thank you for applying."}
    stored(session, conn, "ace-receipt", "receipt", "Application update", reason=RECEIPT_REASON, version="2", minutes=60)
    stored(session, conn, "owner-receipt", "receipt", "Application update", reason="You marked it an application receipt", version="2", minutes=61)
    session.commit()
    monkeypatch.setattr(inbox.gmail, "get_json", lambda path, *a: message(path.rsplit("/", 1)[1], bodies[path.rsplit("/", 1)[1]], NOW - timedelta(hours=1)))
    assert inbox.messages(owner_request(), session, None, 0, 50)["counts"]["stale"] == 1
    assert inbox.recheck(inbox.RecheckRequest(), owner_request(), session) == {"checked": 1, "counts": {"automatic": 1}, "remaining": 0}
    assert row_for(session, "owner-receipt").decision == "receipt"
    assert statuses(session) == ["applied", "rejected", "applied"]


def test_full_email_is_its_own_html_made_safe(database, gmail_reads, monkeypatch):
    session, conn = database
    _ingest(session, conn, message("styled", "Req ID: SE-100. Thank you for applying."), _identities(session), preview=True)
    row = row_for(session, "styled")
    markup = ('<html><body onload="steal()"><p>Hello <b>Fixture</b> \u2014 thanks.</p><img src="cid:logo@fixture" alt="Logo">'
              '<img src="https://tracker.example/logo.png"><a href="https://careers.example/jobs">Careers</a><script>steal()</script></body></html>')
    full = {"id": "styled", "threadId": "thread-1", "snippet": "Hello Fixture", "payload": {"mimeType": "multipart/related", "headers": [
        {"name": "From", "value": "Silverpine Talent <talent@careers.silverpine.example>"}, {"name": "To", "value": "fictional@example.test"},
        {"name": "Subject", "value": "Your application"}, {"name": "Message-ID", "value": "<fixture-1@careers.silverpine.example>"}], "parts": [
        {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(b"Hello Fixture, thanks.").decode()}},
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(markup.encode()).decode()}},
        {"mimeType": "image/png", "headers": [{"name": "Content-ID", "value": "<logo@fixture>"}], "body": {"attachmentId": "logo-1"}}]}}
    reads = []

    def get(path, *args):
        reads.append(path)
        if path.endswith("/attachments/logo-1"):
            return {"data": base64.urlsafe_b64encode(b"fictional png").decode()}
        return full

    monkeypatch.setattr(inbox.gmail, "get_json", get)
    shown = inbox.full_message(row.id, owner_request(), session)
    assert reads == ["/messages/styled", "/messages/styled/attachments/logo-1"]
    assert shown["format"] == "html" and shown["blocked_images"] == 1 and shown["text"] == "Hello Fixture, thanks."
    assert shown["sender"] == "Silverpine Talent <talent@careers.silverpine.example>" and shown["to"] == "fictional@example.test"
    assert shown["message_id_header"] == "<fixture-1@careers.silverpine.example>" and shown["thread_id"] == "thread-1"
    document = shown["document"]
    assert "Hello <b>Fixture</b>, thanks." in document and "data:image/png;base64," in document
    assert "steal" not in document and "tracker.example" not in document and "\u2014" not in document
    assert 'href="https://careers.example/jobs" target="_blank" rel="noopener noreferrer"' in document
    assert len(row.snippet) <= 500 and "steal" not in row.snippet  # Nothing new is stored.
