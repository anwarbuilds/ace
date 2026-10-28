"""Fictional Google responses only. Never access a mailbox or sleep."""
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
import os

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.inbox import gmail
from backend.app.api.routers import inbox
from backend.app.auth.guard import Principal
from backend.app.db.base import Base
from backend.app.db.models import GmailConnectionRecord, GmailMessageRecord, ApplicationEventRecord, UserRecord, JobRecord, JobMarkRecord


def response(status=200, reason=None, headers=None):
    return httpx.Response(status, json={"error": {"errors": [{"reason": reason}]}} if reason else {"messages": []},
                          headers=headers, request=httpx.Request("GET", "https://gmail.googleapis.com/fictional"))


@pytest.fixture
def sleeps(monkeypatch):
    waits = []
    monkeypatch.setattr(gmail.time, "sleep", waits.append)
    monkeypatch.setattr(gmail.secrets, "randbelow", lambda maximum: 0)
    return waits


@pytest.mark.parametrize("status,reason", [(403, "rateLimitExceeded"), (403, "userRateLimitExceeded"), (429, None), (500, None), (503, None)])
def test_transient_read_recovers_with_backoff(monkeypatch, sleeps, status, reason):
    replies = iter([response(status, reason), response()])
    monkeypatch.setattr(gmail.httpx, "get", lambda *a, **k: next(replies))
    assert gmail.get_json("/messages", "fictional-token") == {"messages": []}
    assert sleeps == [1]


def test_quota_retries_are_bounded(monkeypatch, sleeps):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        return response(403, "rateLimitExceeded")
    monkeypatch.setattr(gmail.httpx, "get", get)
    with pytest.raises(gmail.GmailRateLimited, match="still authorized"):
        gmail.get_json("/messages", "fictional-token")
    assert len(calls) == 4
    assert sleeps == [1, 2, 4]


@pytest.mark.parametrize("header,expected_waits", [("2", [2]), ("120", [])])
def test_retry_after_is_respected_without_blocking_for_long_windows(monkeypatch, sleeps, header, expected_waits):
    replies = iter([response(429, headers={"Retry-After": header}), response()])
    monkeypatch.setattr(gmail.httpx, "get", lambda *a, **k: next(replies))
    if header == "120":
        with pytest.raises(gmail.GmailRateLimited) as error:
            gmail.get_json("/messages", "fictional-token")
        assert error.value.retry_after == 120
    else:
        assert gmail.get_json("/messages", "fictional-token") == {"messages": []}
    assert sleeps == expected_waits


@pytest.mark.parametrize("status,reason,error_type", [(403, "insufficientPermissions", gmail.GmailError), (401, None, gmail.GmailError), (404, None, gmail.GmailCursorExpired)])
def test_permission_and_missing_resource_errors_are_not_retried(monkeypatch, sleeps, status, reason, error_type):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        return response(status, reason)
    monkeypatch.setattr(gmail.httpx, "get", get)
    with pytest.raises(error_type) as error:
        gmail.get_json("/history", "fictional-token")
    assert "fictional-token" not in str(error.value)
    assert len(calls) == 1 and not sleeps


def test_transport_timeout_can_recover(monkeypatch, sleeps):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("fictional transport error")
        return response()
    monkeypatch.setattr(gmail.httpx, "get", get)
    assert gmail.get_json("/profile", "fictional-token") == {"messages": []}
    assert sleeps == [1]


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get("ACE_GMAIL_TEST_DATABASE_URL", "sqlite://")
    if url != "sqlite://":
        parsed = make_url(url)
        assert parsed.host == "127.0.0.1" and parsed.port == 18549 and parsed.database == "ace_gmail_regression"
    inbox._COVERAGE.clear()
    inbox._FULL_SCANS.clear()
    inbox._TOKENS.clear()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(inbox.gmail, "decrypt_token", lambda *a: "fictional-refresh")
    monkeypatch.setattr(inbox.gmail, "access_token", lambda *a, **k: "fictional-access")
    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        session.add(UserRecord(id=1, email="owner-fixture@example.test", password_hash="fictional", created_at=now, password_changed_at=now))
        session.flush()
        conn = GmailConnectionRecord(owner_id=1, email="fixture@example.test", encrypted_refresh_token=b"fictional", scope=gmail.SCOPE, state="ready", preview_complete=False)
        session.add(conn); session.commit()
        yield session, conn
    Base.metadata.drop_all(engine)
    engine.dispose()


def owner_request():
    return SimpleNamespace(state=SimpleNamespace(principal=Principal(kind="session", user=SimpleNamespace(id=1))))


@pytest.mark.parametrize("temporary", [True, False])
def test_temporary_failure_does_not_mark_authorization_as_error(monkeypatch, database, temporary):
    session, conn = database
    def fail(*args):
        raise gmail.GmailRateLimited("Fictional rate limit") if temporary else gmail.GmailError("Fictional authorization failure")
    monkeypatch.setattr(inbox, "sync_once", fail)
    with pytest.raises(HTTPException) as error:
        inbox.sync(owner_request(), session)
    assert error.value.status_code == (429 if temporary else 502)
    assert conn.state == ("ready" if temporary else "error")
    assert conn.history_id is None and conn.last_synced_at is None


@pytest.mark.parametrize("preview", [True, False])
def test_existing_evidence_skips_google_detail_reads(monkeypatch, database, preview):
    session, conn = database
    row = GmailMessageRecord(connection_id=conn.id, gmail_id="already-imported", received_at=datetime.now(timezone.utc),
                             sender="fictional@example.test", subject="Fictional", snippet="Fictional", classification="unknown", decision="ignored", candidate_keys=[], decision_reason="Fictional fixture", parser_version="test")
    session.add(row); session.commit()
    calls = []
    def get(path, *args):
        calls.append(path)
        if path == "/profile":
            return {"historyId": "fixture-cursor"}
        if path == "/messages":
            return {"messages": [{"id": "already-imported"}, {"id": "already-imported"}]}
        if path == "/history": return {"historyId": "fixture-cursor"}
        raise AssertionError("Already imported message must not be downloaded again")
    monkeypatch.setattr(inbox.gmail, "get_json", get)
    result = inbox.backfill(inbox.SyncRequest(days=30), owner_request(), session) if preview else inbox.sync_once(session, conn, 30)
    assert result["counts"] == {"duplicate": 1}
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 1
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 0
    # Only a check for new email moves the sync time; an older page does not.
    assert (conn.last_synced_at is None) == preview
    assert not any(path.startswith("/messages/") for path in calls)


def test_backfill_tolerates_a_message_deleted_after_listing(monkeypatch, database):
    session, conn = database
    def get(path, *args):
        if path == "/profile":
            return {"historyId": "fixture-cursor"}
        if path == "/messages":
            return {"messages": [{"id": "deleted-fixture"}]}
        raise gmail.GmailCursorExpired("Fictional deleted message")
    monkeypatch.setattr(inbox.gmail, "get_json", get)
    result = inbox.backfill(inbox.SyncRequest(days=30), owner_request(), session)
    assert result["preview_only"] is True
    assert conn.history_id == "fixture-cursor"
    assert conn.last_synced_at is None  # Importing older email is not a check for new email.
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 0


def test_failed_backfill_does_not_advance_the_cursor(monkeypatch, database):
    session, conn = database
    def get(path, *args):
        if path == "/profile":
            return {"historyId": "fixture-cursor"}
        if path == "/messages":
            return {"messages": [{"id": "limited-fixture"}]}
        raise gmail.GmailRateLimited("Fictional rate limit")
    monkeypatch.setattr(inbox.gmail, "get_json", get)
    with pytest.raises(HTTPException) as error:
        inbox.backfill(inbox.SyncRequest(days=30), owner_request(), session)
    assert error.value.status_code == 429
    assert conn.state == "ready" and conn.history_id is None
    assert conn.preview_baseline_history_id is None and not conn.preview_complete
    assert conn.last_synced_at is None
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 0


@pytest.mark.parametrize("preview", [True, False])
def test_long_errors_fit_the_existing_postgres_column(monkeypatch, database, preview):
    session, conn = database
    def fail(*args, **kwargs):
        raise gmail.GmailRateLimited("Fictional error " * 30)
    monkeypatch.setattr(inbox.gmail, "get_json", fail)
    monkeypatch.setattr(inbox, "sync_once", fail)
    with pytest.raises(HTTPException) as error:
        if preview:
            inbox.backfill(inbox.SyncRequest(days=30), owner_request(), session)
        else:
            inbox.sync(owner_request(), session)
    assert error.value.status_code == 429
    session.refresh(conn)
    assert len(conn.last_error) == GmailConnectionRecord.__table__.c.last_error.type.length == 120
    assert conn.state == "ready" and conn.last_synced_at is None


def test_review_counts_and_pagination_include_older_pending_messages(database):
    session, conn = database
    now = datetime.now(timezone.utc)
    decisions = ["ignored"] * 150 + ["review"] * 120 + ["exact_preview"] * 5 + ["deferred"] * 2 + ["automatic"] * 3 + ["manual"] * 4
    for index, decision in enumerate(decisions):
        session.add(GmailMessageRecord(connection_id=conn.id, gmail_id=f"fictional-{index}", received_at=now-timedelta(minutes=index),
                                      sender="fixture@example.test", subject="Fictional", snippet="Fictional", classification="unknown", decision=decision,
                                      candidate_keys=[], decision_reason="Fictional fixture", parser_version="test"))
    session.commit()
    pages = [inbox.messages(owner_request(), session, "pending", offset, 50) for offset in (0,50,100)]
    assert [len(page["items"]) for page in pages] == [50,50,27]
    assert all(page["total"] == page["review_count"] == 127 for page in pages)
    assert [page["has_more"] for page in pages] == [True,True,False]
    assert pages[0]["counts"] == {"stored":284,"needs_review":127,"automatic":3,"manual":4,"reviewed":7,"receipts":0,"updates":0,"unlinked":0,"company_rejections":0,"stale":0}
    ids=[row["id"] for page in pages for row in page["items"]]
    assert len(ids)==len(set(ids))==127
    assert all(row["decision"] != "ignored" for page in pages for row in page["items"])
    assert len(inbox._message_rows(session, conn.id)) == 100  # Compatibility: all-email reads remain bounded.


def test_review_records_email_time_and_preserves_audit_time(database):
    session, conn = database
    now = datetime.now(timezone.utc)
    received = now-timedelta(days=10)
    job=JobRecord(source="fixture",source_account="fictional",external_id="fixture-review",company="Fictional Labs",title="Fictional role",location="US",description="Fictional",official_url="https://fictional.example/jobs",content_hash="fixture",first_seen_at=now-timedelta(days=30),last_seen_at=now,is_active=True)
    session.add(job);session.flush()
    mark=JobMarkRecord(job_id=job.id,applied_at=now-timedelta(days=20),application_status="applied")
    message=GmailMessageRecord(connection_id=conn.id,gmail_id="review-fixture",received_at=received,sender="fixture@example.test",subject="Fictional assessment",snippet="Fictional",classification="online_assessment",decision="review",candidate_keys=[f"job:{job.id}"],decision_reason="Fictional fixture",parser_version="test")
    session.add_all([mark,message]);session.commit()
    result=inbox.review(inbox.ManualDecision(message_id=message.id,application_key=f"job:{job.id}",status="screening",expected_status="applied",confirmed=True),owner_request(),session)
    event=session.get(ApplicationEventRecord,result["event_id"])
    assert event.occurred_at.replace(tzinfo=timezone.utc)==received
    assert event.recorded_at.replace(tzinfo=timezone.utc)>received
    assert mark.application_status=="screening" and message.decision=="manual"


# Reliable Inbox P1: many list pages, bounded detail reads and honest coverage.
def fictional_mail(key):
    return {"id": key, "internalDate": "1793000000000", "snippet": "Fictional newsletter",
            "payload": {"headers": [{"name": "From", "value": "fictional@newsletter.example"},
                                     {"name": "Subject", "value": "Fictional news"}]}}


def test_list_message_ids_follows_every_page_and_deduplicates(monkeypatch):
    calls = []
    def get(path, token, params):
        calls.append(params.copy())
        return ({"messages": [{"id": "newest"}, {"id": "middle"}], "nextPageToken": "page-two"}
                if not params.get("pageToken") else {"messages": [{"id": "middle"}, {"id": "oldest"}]})
    monkeypatch.setattr(gmail, "get_json", get)
    assert gmail.list_message_ids("fictional", "after:2026/01/01") == (["newest", "middle", "oldest"], True)
    assert calls[1] == {"q": "after:2026/01/01", "maxResults": 500, "pageToken": "page-two"}
    assert gmail.list_message_ids("fictional", "after:2026/01/01", max_pages=1) == (["newest", "middle"], False)


def test_window_larger_than_500_finishes_in_saved_60_message_batches(monkeypatch, database):
    session, conn = database
    ids = [f"fictional-{index}" for index in range(1107)]
    details = []
    calls = []
    def get(path, token, params=None):
        calls.append(path)
        if path == "/profile": return {"historyId": "before-listing"}
        if path == "/messages":
            page = int(params.get("pageToken", "0"))
            return {"messages": [{"id": key} for key in ids[page:page+500]],
                    **({"nextPageToken": str(page+500)} if page+500 < len(ids) else {})}
        if path == "/history": return {"historyId": "later-history"}
        if params.get("format") == "minimal": return {"id": path.split("/")[-1]}
        details.append(path.split("/")[-1])
        return fictional_mail(details[-1])
    monkeypatch.setattr(gmail, "get_json", get)
    for round in range(30):
        before = len(details)
        step = inbox.sync_once(session, conn, 90)
        assert len(details) - before <= 60
        assert step["coverage"]["in_ace"] == len(details)
        if not step["more"]: break
        assert conn.history_id is None
    assert step["coverage"]["gmail"] == 1107 and step["coverage"]["missing"] == 0
    assert conn.history_id == "later-history"
    assert details == ids and calls[:2] == ["/profile", "/messages"]
    assert conn.preview_complete and not step["partial"]
    assert inbox.connection(owner_request(), session)["coverage"] == step["coverage"]
    again = inbox.sync_once(session, conn, 90)
    assert not again["more"] and len(details) == 1107
    inbox._COVERAGE.clear()
    inbox._FULL_SCANS.clear()  # An API restart cannot retain a coverage claim.
    assert inbox.connection(owner_request(), session)["coverage"] is None


def test_quota_failure_keeps_each_saved_email_and_never_sets_cursor(monkeypatch, database):
    session, conn = database
    ids = ["fictional-1", "fictional-2", "fictional-3"]
    failing = True
    def get(path, token, params=None):
        if path == "/profile": return {"historyId": "before-listing"}
        if path == "/messages": return {"messages": [{"id": key} for key in ids]}
        if failing and path.endswith("fictional-3"): raise gmail.GmailRateLimited("Fictional quota")
        return fictional_mail(path.split("/")[-1])
    monkeypatch.setattr(gmail, "get_json", get)
    with pytest.raises(HTTPException) as error:
        inbox.sync(owner_request(), session, inbox.VerifyRequest(days=30))
    assert error.value.status_code == 429
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 2
    assert conn.history_id is None and not conn.preview_complete
    assert inbox.connection(owner_request(), session)["coverage"] is None
    failing = False
    assert inbox.sync_once(session, conn, 30)["remaining"] == 0
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 3


def test_incomplete_listing_never_marks_coverage_or_cursor_complete(monkeypatch, database):
    session, conn = database
    def get(path, *args):
        if path == "/profile": return {"historyId": "fictional"}
        if path == "/messages": return {"messages": [], "nextPageToken": "fictional-next-" + str(len(calls))}
        raise AssertionError("History cannot run while listing is incomplete")
    calls=[]
    def counted(*args):
        calls.append(1);return get(*args)
    monkeypatch.setattr(gmail, "get_json", counted)
    result = inbox.sync_once(session, conn, 30)
    assert result["remaining"] == 0 and result["partial"] and result["more"]
    assert not result["coverage"]["complete"] and conn.history_id is None and not conn.preview_complete


def test_history_expiry_recovers_by_verifying_the_window(monkeypatch, database):
    session, conn = database
    from backend.app.inbox.full_history import FullMailboxScan
    inbox._FULL_SCANS[inbox._coverage_key(conn, 30)] = FullMailboxScan("expired", phase="complete", snapshot="expired")
    def get(path, *args):
        if path == "/history": raise gmail.GmailCursorExpired("Fictional expiry")
        raise AssertionError("Expired cursor must fail visibly")
    monkeypatch.setattr(gmail,"get_json",get)
    with pytest.raises(gmail.GmailTemporaryError):inbox.sync_once(session,conn,30)
    assert inbox._coverage_key(conn,30) not in inbox._FULL_SCANS
    def fresh(path,*args):
        if path=="/profile":return {"historyId":"safe-baseline"}
        if path=="/history":return {"historyId":"safe-snapshot"}
        if path=="/messages":return {"messages":[{"id":"fictional-1"}]}
        return fictional_mail("fictional-1")
    monkeypatch.setattr(gmail,"get_json",fresh)
    for _ in range(3):
        step=inbox.sync_once(session,conn,30)
        if not step["more"]:break
    assert step["coverage"]["complete"] and conn.history_id=="safe-snapshot"


def test_new_email_during_listing_is_not_skipped_by_the_cursor(monkeypatch, database):
    session, conn = database
    listed = 0
    def get(path, *args):
        nonlocal listed
        if path == "/profile": return {"historyId": "baseline"}
        if path == "/messages":
            listed += 1
            return {"messages": [] if listed == 1 else [{"id":"late-fictional"}]}
        if path == "/history":
            return {"historyId": "after-arrival", "history": [{"messagesAdded": [{"message": {"id": "late-fictional"}}]}]}
        return fictional_mail("late-fictional")
    monkeypatch.setattr(gmail, "get_json", get)
    inbox.sync_once(session, conn, 30)
    assert conn.history_id is None
    assert inbox.sync_once(session, conn, 30)["counts"] == {"ignored": 1}
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 1


def test_busy_connection_does_not_start_another_mailbox_operation(monkeypatch, database):
    session, conn = database
    def unexpected(*args): raise AssertionError("Busy must not call Gmail")
    monkeypatch.setattr(gmail, "get_json", unexpected)
    lock = inbox._sync_lock(conn.id)
    with lock:
        assert inbox.sync_once(session, conn, 30)["state"] == "busy"
        assert inbox.backfill(inbox.SyncRequest(days=30), owner_request(), session)["state"] == "busy"
        assert inbox.recheck(inbox.RecheckRequest(), owner_request(), session)["state"] == "busy"


def test_deleted_message_requires_history_confirmation_before_full_coverage(monkeypatch, database):
    session, conn = database
    def get(path, *args):
        if path == "/profile": return {"historyId": "safe"}
        if path == "/messages":return {"messages": [{"id": "deleted-fictional"}]}
        if path == "/history":return {"historyId":"deleted-snapshot", "history":[{"messagesDeleted":[{"message":{"id":"deleted-fictional"}}]}]}
        raise gmail.GmailCursorExpired("Fictional deletion")
    monkeypatch.setattr(gmail, "get_json", get)
    assert inbox.sync_once(session,conn,30)["partial"]
    result = inbox.sync_once(session, conn, 30)
    assert result["coverage"]["gmail"] == result["coverage"]["missing"] == 0
    assert not result["partial"]


def test_duplicate_integrity_race_is_safe_but_other_integrity_errors_propagate(monkeypatch, database):
    from sqlalchemy.exc import IntegrityError
    session, conn = database
    def get(path, *args):
        if path in {"/profile","/history"}: return {"historyId": "safe"}
        if path == "/messages": return {"messages": [{"id": "race-fictional"}]}
        return fictional_mail("race-fictional")
    monkeypatch.setattr(gmail, "get_json", get)
    real_ingest = inbox._ingest
    def race(*args, **kwargs):
        real_ingest(*args, **kwargs); session.commit()
        raise IntegrityError("fictional concurrent insert", {}, Exception("fictional"))
    monkeypatch.setattr(inbox, "_ingest", race)
    assert inbox.sync_once(session, conn, 30)["counts"] == {"duplicate": 1}
    session.query(GmailMessageRecord).delete(); session.commit()
    inbox._FULL_SCANS.clear()
    def broken(*args, **kwargs): raise IntegrityError("fictional unrelated failure", {}, Exception("fictional"))
    monkeypatch.setattr(inbox, "_ingest", broken)
    with pytest.raises(IntegrityError): inbox.sync_once(session, conn, 30)
    assert not inbox._sync_lock(conn.id).locked()


def test_pausing_during_a_batch_stops_further_reads_and_does_not_set_cursor(monkeypatch, database):
    session, conn = database
    reads = []
    def get(path, *args):
        if path == "/profile": return {"historyId": "before-listing"}
        if path == "/messages": return {"messages": [{"id": "fictional-1"}, {"id": "fictional-2"}]}
        reads.append(path)
        conn.state = "paused"
        session.commit()
        return fictional_mail("fictional-1")
    monkeypatch.setattr(gmail, "get_json", get)
    result = inbox.sync_once(session, conn, 30)
    assert len(reads) == 1 and result["state"] == "paused"
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 0
    assert result["partial"] and not conn.preview_complete and conn.history_id is None
    assert inbox.connection(owner_request(), session)["coverage"] is None


def test_missing_profile_cursor_is_temporary_and_never_claims_verified_coverage(monkeypatch, database):
    session, conn = database
    monkeypatch.setattr(gmail, "get_json", lambda *args: {})
    with pytest.raises(gmail.GmailTemporaryError): inbox.sync_once(session, conn, 30)
    assert conn.history_id is None and not conn.preview_complete
    assert inbox.connection(owner_request(), session)["coverage"] is None



def test_expired_pagination_is_retryable_but_does_not_retry_the_bad_token(monkeypatch,sleeps):
    monkeypatch.setattr(gmail.httpx,"get",lambda *a,**k:response(400,"invalidArgument"))
    with pytest.raises(gmail.GmailPageExpired,match="Restart verification"):
        gmail.get_json("/messages","fictional-token",{"pageToken":"fictional-page"})
    assert not sleeps
