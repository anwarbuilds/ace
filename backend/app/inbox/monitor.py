"""Bounded Gmail checks for connected owners while the website is closed.

Runs inside the API, separate from job discovery. The existing sync primitive
owns scope, duplicate prevention, pause/grant checks and outcome permissions.
This worker never invokes historical reclassification.
"""
from __future__ import annotations

from contextlib import contextmanager
import logging
from threading import Event, Thread
import time

from sqlalchemy import select, text, update

from backend.app.config import get_settings
from backend.app.db.models import GmailConnectionRecord
from backend.app.inbox import gmail

log = logging.getLogger(__name__)
INTERVAL_SECONDS = 180
QUOTA_COOLDOWN_SECONDS = 1800
_ADVISORY_KEY = 1702341187


@contextmanager
def single_monitor(engine):
    """A dedicated connection holds the lock across ingestion commits.

    Never return a session-level advisory lock to the pool. Another API process
    can take over when this one exits; discovery uses a separate lock namespace.
    """
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as connection:
        locked = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_KEY}))
        connection.commit()  # Session lock survives; no idle transaction during Gmail reads.
        try:
            yield connection if locked else None
        finally:
            if locked:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_KEY})
                connection.commit()


def check_connections(sessions, *, stopping=lambda: False) -> float:
    """One bounded sync per ready connection; return a quota cooldown or zero."""
    from backend.app.api.routers.inbox import _settings_ready, sync_once
    if stopping() or not get_settings().gmail_background_sync_enabled or not _settings_ready():
        return False
    with sessions() as session:
        ids = list(session.scalars(select(GmailConnectionRecord.id).where(
            GmailConnectionRecord.state == "ready", GmailConnectionRecord.encrypted_refresh_token != b"")))
    for connection_id in ids:
        if stopping():
            break
        with sessions() as session:
            conn = session.get(GmailConnectionRecord, connection_id)
            if not conn or conn.state != "ready" or not conn.encrypted_refresh_token:
                continue
            grant = bytes(conn.encrypted_refresh_token)
            try:
                sync_once(session, conn, 0, should_stop=stopping)
            except gmail.GmailError as error:
                session.rollback()
                if stopping():
                    return False
                # Never undo a concurrent Pause, disconnect or new OAuth grant.
                changes = {"last_error": str(error)[:120]}
                if not isinstance(error, gmail.GmailTemporaryError):
                    changes["state"] = "error"
                session.execute(update(GmailConnectionRecord).where(
                    GmailConnectionRecord.id == connection_id,
                    GmailConnectionRecord.state == "ready",
                    GmailConnectionRecord.encrypted_refresh_token == grant,
                ).values(**changes).execution_options(synchronize_session=False))
                session.commit()
                if isinstance(error, gmail.GmailRateLimited):
                    return max(QUOTA_COOLDOWN_SECONDS, error.retry_after)
            except Exception:
                session.rollback()
                # No exception string/traceback: database or provider errors can
                # contain private addresses, query parameters or message data.
                log.error("Gmail background check failed; saved progress is retained")
    return False


class GmailMonitor:
    def __init__(self, sessions, engine):
        self.sessions, self.engine = sessions, engine
        self.stop_requested = Event()
        self.thread = Thread(target=self.run, name="ace-gmail-monitor", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_requested.set()
        self.thread.join(timeout=1)

    def run(self):
        # Delay startup to keep readiness independent of Gmail availability.
        while not self.stop_requested.wait(15):
            try:
                with single_monitor(self.engine) as acquired:
                    if not acquired:
                        self.stop_requested.wait(INTERVAL_SECONDS)
                        continue
                    while not self.stop_requested.is_set():
                        # Verify the dedicated lock connection is alive before
                        # each tick. A lost lease must not keep processing mail.
                        if self.engine.dialect.name == "postgresql":
                            acquired.execute(text("SELECT 1"))
                            acquired.commit()
                        started = time.monotonic()
                        limited = check_connections(self.sessions, stopping=self.stop_requested.is_set)
                        delay = limited if limited else max(15, INTERVAL_SECONDS - (time.monotonic()-started))
                        if self.stop_requested.wait(delay):
                            return
            except Exception:
                log.error("Gmail monitor unavailable; next check will retry")
                self.stop_requested.wait(INTERVAL_SECONDS)
