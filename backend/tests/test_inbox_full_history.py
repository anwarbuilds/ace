"""Full retained Gmail history; fictional IDs, isolated SQL, no network."""
from collections import Counter
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from backend.app.api.routers import inbox
from backend.app.db.models import GmailMessageRecord
from backend.app.inbox import gmail
from backend.tests.test_gmail_reads import database, fictional_mail, owner_request


class Mailbox:
    def __init__(self, ids, page_size=500):
        self.ids = ids
        self.page_size = page_size
        self.calls = []
        self.details = []
        self.history = {"historyId": "snapshot-complete"}
        self.failure_at = None

    def get(self, path, token, params=None):
        self.calls.append((path, dict(params or {})))
        if path == "/profile":
            return {"historyId": "baseline-before-list"}
        if path == "/messages":
            assert params["q"] == gmail.job_query() and "labelIds" not in params
            assert params["includeSpamTrash"] == "false"
            offset = int(params.get("pageToken", 0))
            return {"messages": [{"id": key} for key in self.ids[offset:offset+self.page_size]],
                    **({"nextPageToken": str(offset+self.page_size)} if offset+self.page_size < len(self.ids) else {})}
        if path == "/history":
            return self.history(params) if callable(self.history) else self.history
        key = path.rsplit("/", 1)[-1]
        if self.failure_at is not None and len(self.details) == self.failure_at:
            self.failure_at = None
            raise gmail.GmailRateLimited("Fictional quota interruption")
        if params.get("format") == "minimal":
            return {"id": key, "labelIds": []}
        self.details.append(key)
        data = fictional_mail(key)
        data["internalDate"] = "1262304000000"  # January 2010, outside every recent window.
        return data


def finish(session, conn, limit=100):
    for _ in range(limit):
        result = inbox.sync_once(session, conn, 0)
        if not result["more"]:
            return result
        assert not result["coverage"]["complete"] and result["partial"]
        assert not conn.preview_complete
    raise AssertionError("Fictional mailbox did not finish")


def test_full_history_imports_more_than_500_old_messages_in_committed_batches(monkeypatch, database):
    session, conn = database
    box = Mailbox([f"old-fictional-{index}" for index in range(1107)])
    monkeypatch.setattr(gmail, "get_json", box.get)
    previous = 0
    while True:
        result = inbox.sync_once(session, conn, 0)
        assert len(box.details) - previous <= 60
        previous = len(box.details)
        if not result["more"]:
            break
        assert not result["coverage"]["complete"] and conn.history_id is None
    assert len(box.details) == len(set(box.details)) == 1107
    assert result["coverage"]["gmail"] == result["coverage"]["in_ace"] == 1107
    assert result["coverage"]["days"] == 0 and not result["coverage"]["includes_spam_trash"]
    assert conn.history_id == "snapshot-complete" and conn.preview_complete
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 1107
    assert session.scalar(select(func.min(GmailMessageRecord.received_at))).year == 2010


def test_full_listing_has_no_60_page_ceiling_and_bounds_each_request(monkeypatch, database):
    session, conn = database
    box = Mailbox([f"page-fictional-{index}" for index in range(67)], page_size=1)
    monkeypatch.setattr(gmail, "get_json", box.get)
    for _ in range(20):
        before = len(box.calls)
        result = inbox.sync_once(session, conn, 0)
        assert sum(path == "/messages" for path, params in box.calls[before:]) <= 5
        if not result["more"]:
            break
    assert result["coverage"]["complete"] and result["coverage"]["gmail"] == 67
    assert sum(path == "/messages" for path, params in box.calls) == 67


def test_quota_and_process_restart_preserve_rows_and_do_not_redownload_them(monkeypatch, database):
    session, conn = database
    box = Mailbox([f"restart-fictional-{index}" for index in range(125)])
    box.failure_at = 7
    monkeypatch.setattr(gmail, "get_json", box.get)
    with pytest.raises(gmail.GmailRateLimited):
        inbox.sync_once(session, conn, 0)
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 7
    assert conn.history_id is None and not conn.preview_complete
    assert inbox._public(conn)["coverage"] is None
    inbox._FULL_SCANS.clear()  # Process restart: verification must start fresh.
    result = finish(session, conn)
    assert result["coverage"]["complete"] and len(box.details) == 125
    assert all(count == 1 for count in Counter(box.details).values())


def test_history_after_listing_catches_arrivals_deletions_and_more_than_five_pages(monkeypatch, database):
    session, conn = database
    box = Mailbox(["retained-fictional", "deleted-fictional"])
    history_calls = []
    def history(params):
        history_calls.append(params)
        box.ids = ["retained-fictional", "arrived-during-scan"]
        offset = int(params.get("pageToken", 0))
        assert params["startHistoryId"] == "baseline-before-list"
        return {"historyId": "caught-up-history", "history": ([{"messagesAdded": [{"message": {"id": "arrived-during-scan"}}],
                "messagesDeleted": [{"message": {"id": "deleted-fictional"}}]}] if offset == 0 else []),
                **({"nextPageToken": str(offset+1)} if offset < 6 else {})}
    box.history = history
    monkeypatch.setattr(gmail, "get_json", box.get)
    first = inbox.sync_once(session, conn, 0)
    assert first["more"] and conn.history_id is None
    second = inbox.sync_once(session, conn, 0)
    assert second["more"] and not second["coverage"]["complete"] and conn.history_id is None
    result = finish(session, conn)
    assert len(history_calls) == 7 and conn.history_id == "caught-up-history"
    assert result["coverage"]["gmail"] == result["coverage"]["in_ace"] == 2
    # Deleting from Gmail never deletes already retained evidence from SQL.
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 3


def test_full_incremental_cursor_is_independent_of_a_later_narrow_window(monkeypatch, database):
    session, conn = database
    box = Mailbox(["initial-fictional"])
    monkeypatch.setattr(gmail, "get_json", box.get)
    finish(session, conn)
    conn.history_id = "narrow-window-cursor"; session.commit()
    def history(params):
        box.ids = ["initial-fictional", "next-fictional"]
        assert params["startHistoryId"] == "snapshot-complete"
        return {"historyId": "next-snapshot", "history": [{"messagesAdded": [{"message": {"id": "next-fictional"}}]}]}
    box.history = history
    result = inbox.sync_once(session, conn, 0)
    assert result["more"]  # History IDs are never body-read before a scoped re-list.
    result = finish(session, conn)
    assert not result["more"] and conn.history_id == "next-snapshot"
    assert result["coverage"]["gmail"] == 2
    assert sum(path == "/messages" for path, params in box.calls) == 2


def test_expired_history_forces_fresh_scan_without_losing_committed_evidence(monkeypatch, database):
    session, conn = database
    box = Mailbox(["expiration-fictional"])
    monkeypatch.setattr(gmail, "get_json", box.get)
    finish(session, conn)
    def expired(params): raise gmail.GmailCursorExpired("Fictional expired cursor")
    box.history = expired
    with pytest.raises(gmail.GmailTemporaryError, match="verify all history"):
        inbox.sync_once(session, conn, 0)
    assert conn.history_id is None and not conn.preview_complete
    assert inbox._public(conn)["coverage"] is None
    box.history = {"historyId": "new-snapshot"}
    assert finish(session, conn)["coverage"]["gmail"] == 1
    assert box.details == ["expiration-fictional"]


def test_repeated_listing_never_claims_complete(monkeypatch, database):
    session, conn = database
    box = Mailbox([])
    def get(path, token, params=None):
        if path == "/messages":return {"messages": [], "nextPageToken": "repeated-token"}
        return box.get(path, token, params)
    monkeypatch.setattr(gmail, "get_json", get)
    with pytest.raises(gmail.GmailTemporaryError, match="repeated a listing page"):
        inbox.sync_once(session, conn, 0)
    assert conn.history_id is None and inbox._public(conn)["coverage"] is None


def test_all_time_is_the_authenticated_sync_default(monkeypatch, database):
    session, conn = database
    box = Mailbox([])
    monkeypatch.setattr(gmail, "get_json", box.get)
    assert inbox.VerifyRequest().days == inbox.SyncRequest().days == 0
    assert inbox.sync(owner_request(), session)["coverage"]["days"] == 0


def test_read_only_coverage_report_lists_every_page_with_no_date_filter(monkeypatch):
    from backend.scripts.inbox_coverage_report import gmail_ids
    calls = []
    def get(path, token, params):
        assert path == "/messages" and params["q"] == gmail.job_query() and params["includeSpamTrash"] == "false"
        offset = int(params.get("pageToken", 0)); calls.append(offset)
        return {"messages": [{"id": f"report-fictional-{offset}"}],
                **({"nextPageToken": str(offset+1)} if offset < 65 else {})}
    monkeypatch.setattr(gmail, "get_json", get)
    ids, complete = gmail_ids("fictional-token", None)
    assert complete and len(ids) == len(calls) == 66



@pytest.mark.parametrize("change",["pause","reconnect"])
def test_full_history_cannot_save_after_pause_or_grant_change(monkeypatch,database,change):
    session,conn=database
    box=Mailbox(["authorization-fictional"])
    def get(path,token,params=None):
        result=box.get(path,token,params)
        if path.startswith("/messages/"):
            if change=="pause":conn.state="paused"
            else:conn.encrypted_refresh_token=b"changed-fictional-grant"
            session.commit()
        return result
    monkeypatch.setattr(gmail,"get_json",get)
    result=inbox.sync_once(session,conn,0)
    assert result["state"]==("paused" if change=="pause" else "disconnected")
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord))==0
    assert inbox._public(conn)["coverage"] is None


@pytest.mark.parametrize("payload",[{}, {"id":"different-fictional-id"}])
def test_malformed_detail_never_turns_a_missing_manifest_id_into_verified_coverage(monkeypatch,database,payload):
    session,conn=database
    box=Mailbox(["expected-fictional-id"])
    def get(path,token,params=None):
        return payload if path.startswith("/messages/") else box.get(path,token,params)
    monkeypatch.setattr(gmail,"get_json",get)
    with pytest.raises(gmail.GmailTemporaryError,match="incomplete email response"):
        inbox.sync_once(session,conn,0)
    assert conn.history_id is None and inbox._public(conn)["coverage"] is None
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord))==0



def test_legacy_backfill_default_also_verifies_all_history(monkeypatch,database):
    session,conn=database
    box=Mailbox([])
    monkeypatch.setattr(gmail,"get_json",box.get)
    assert inbox.backfill(inbox.SyncRequest(),owner_request(),session)["coverage"]["days"]==0



@pytest.mark.parametrize("confirmed",[True,False])
def test_missing_detail_requires_confirmed_deletion_before_full_coverage(monkeypatch,database,confirmed):
    session,conn=database
    box=Mailbox(["missing-detail-fictional"])
    if confirmed:
        box.history={"historyId":"deleted-snapshot","history":[{"messagesDeleted":[{"message":{"id":"missing-detail-fictional"}}]}]}
    def get(path,token,params=None):
        if path.startswith("/messages/"):raise gmail.GmailCursorExpired("Fictional unavailable detail")
        return box.get(path,token,params)
    monkeypatch.setattr(gmail,"get_json",get)
    first=inbox.sync_once(session,conn,0)
    assert first["coverage"]["missing"]==1 and not first["coverage"]["complete"]
    if confirmed:
        result=inbox.sync_once(session,conn,0)
        assert result["coverage"]["complete"] and result["coverage"]["gmail"]==0
    else:
        with pytest.raises(gmail.GmailTemporaryError,match="deletion is unconfirmed"):
            inbox.sync_once(session,conn,0)
        assert inbox._public(conn)["coverage"] is None and not conn.preview_complete


def test_expired_page_token_restarts_manifest_without_marking_oauth_invalid(monkeypatch,database):
    session,conn=database
    box=Mailbox(["page-expiration-fictional"],page_size=1)
    def get(path,token,params=None):
        if path=="/messages":
            if params.get("pageToken"):raise gmail.GmailPageExpired("Fictional page expiration")
            return {"messages":[{"id":"page-expiration-fictional"}],"nextPageToken":"expired-page"}
        return box.get(path,token,params)
    monkeypatch.setattr(gmail,"get_json",get)
    with pytest.raises(gmail.GmailTemporaryError,match="verify all history"):
        inbox.sync_once(session,conn,0)
    assert conn.state=="ready" and inbox._public(conn)["coverage"] is None



@pytest.mark.parametrize("temporary",[True,False])
def test_full_backfill_preserves_gmail_failure_status_and_saved_connection(monkeypatch,database,temporary):
    from fastapi import HTTPException
    session,conn=database
    def fail(*args,**kwargs):
        error=gmail.GmailRateLimited if temporary else gmail.GmailError
        raise error("Fictional Gmail failure "*30)
    monkeypatch.setattr(gmail,"get_json",fail)
    with pytest.raises(HTTPException) as error:
        inbox.backfill(inbox.SyncRequest(),owner_request(),session)
    assert error.value.status_code==(429 if temporary else 502)
    assert conn.state==("ready" if temporary else "error")
    assert len(conn.last_error)==120 and conn.history_id is None
    assert session.scalar(select(func.count()).select_from(GmailMessageRecord))==0
