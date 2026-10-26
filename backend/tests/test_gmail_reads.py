"""Fictional Google responses only. Never access a mailbox or sleep."""
from types import SimpleNamespace
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.inbox import gmail
from backend.app.api.routers import inbox
from backend.app.auth.guard import Principal
from backend.app.db.base import Base
from backend.app.db.models import GmailConnectionRecord, GmailMessageRecord, ApplicationEventRecord


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
        with pytest.raises(gmail.GmailRateLimited):
            gmail.get_json("/messages", "fictional-token")
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
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(inbox.gmail, "decrypt_token", lambda *a: "fictional-refresh")
    monkeypatch.setattr(inbox.gmail, "access_token", lambda *a, **k: "fictional-access")
    with Session(engine) as session:
        conn = GmailConnectionRecord(owner_id=1, email="fixture@example.test", encrypted_refresh_token=b"fictional", scope=gmail.SCOPE, state="ready", preview_complete=False)
        session.add(conn); session.commit()
        yield session, conn


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
        raise AssertionError("Already imported message must not be downloaded again")
    monkeypatch.setattr(inbox.gmail, "get_json", get)
    result = inbox.backfill(inbox.SyncRequest(), owner_request(), session) if preview else inbox.sync_once(session, conn)
    assert result["counts"] == {"duplicate": 1}
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 1
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 0
    assert conn.last_synced_at is not None
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
    result = inbox.backfill(inbox.SyncRequest(), owner_request(), session)
    assert result["preview_only"] is True
    assert conn.history_id == "fixture-cursor"
    assert conn.last_synced_at is not None
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
        inbox.backfill(inbox.SyncRequest(), owner_request(), session)
    assert error.value.status_code == 429
    assert conn.state == "ready" and conn.history_id is None
    assert conn.preview_baseline_history_id is None and not conn.preview_complete
    assert conn.last_synced_at is None
    assert session.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 0
