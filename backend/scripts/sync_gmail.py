"""Optional one-shot Gmail catch-up, separate from the discovery scheduler.

Run under an approved daily timer after Gmail connection and rollout. It
never starts ACE's cloud discovery scheduler.
"""

from sqlalchemy import select

from backend.app.api.routers.inbox import sync_once
from backend.app.db.models import GmailConnectionRecord
from backend.app.db.session import SessionLocal
from backend.app.inbox.gmail import GmailError, GmailTemporaryError


def main() -> int:
    with SessionLocal() as session:
        rows = session.scalars(select(GmailConnectionRecord).where(GmailConnectionRecord.state == "ready")).all()
        failed = 0
        for connection in rows:
            try:
                sync_once(session, connection)
            except GmailError as exc:
                if not isinstance(exc, GmailTemporaryError):
                    connection.state = "error"
                connection.last_error = str(exc)[:120]
                session.commit()
                failed += 1
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
