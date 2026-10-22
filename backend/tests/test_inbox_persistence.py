"""Database assertions for preview, ambiguity, duplicate import and history."""

import base64
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.routers.inbox import _identities, _ingest
from backend.app.api.marks import mark_counts
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import ApplicationEventRecord, GmailConnectionRecord, GmailMessageRecord, JobMarkRecord, JobRecord


NOW = datetime.now(timezone.utc)


def message(message_id: str, body: str, received_at: datetime = NOW) -> dict:
    return {"id": message_id, "threadId": "thread-1", "internalDate": str(int(received_at.timestamp() * 1000)),
            "snippet": body, "payload": {"headers": [{"name": "Authentication-Results", "value": "mx.google.com; dmarc=pass header.from=careers.silverpine.example"},
                                                  {"name": "From", "value": "talent@careers.silverpine.example"},
                                                  {"name": "Subject", "value": "Application update"},
                                                  {"name": "Date", "value": received_at.strftime("%a, %d %b %Y %H:%M:%S +0000")}],
                                        "mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}}


def test_preview_ambiguous_exact_and_duplicate_are_safe(monkeypatch):
    monkeypatch.setenv("GMAIL_AUTO_OUTCOMES_ALLOWED", "true")
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        conn = GmailConnectionRecord(owner_id=1, email="fictional@example.test", encrypted_refresh_token=b"fixture", scope="gmail.readonly", state="ready", auto_outcomes_enabled=True)
        session.add(conn)
        for index in range(3):
            job = JobRecord(source="test", source_account="fictional", external_id=str(index), company="Silverpine Labs", title="Software Engineer", location="US", description="Fictional test opening", official_url=f"https://careers.silverpine.example/jobs/{index}", content_hash="h", first_seen_at=NOW-timedelta(days=40), last_seen_at=NOW, is_active=True, requisition_id=f"SE-10{index}")
            session.add(job); session.flush()
            session.add(JobMarkRecord(job_id=job.id, applied_at=NOW-timedelta(days=30), application_status="applied"))
        session.flush()
        identities = _identities(session)
        ambiguous = message("ambiguous", "We have decided to move forward with other candidates.")
        assert _ingest(session, conn, ambiguous, identities, preview=False) == "review"
        assert session.scalar(select(func.count()).select_from(ApplicationEventRecord).where(ApplicationEventRecord.application_key.like("job:%"))) == 0
        assert [r.application_status for r in session.scalars(select(JobMarkRecord).order_by(JobMarkRecord.job_id))] == ["applied"] * 3

        exact = message("exact", "Req ID: SE-101. We have decided to move forward with other candidates.")
        assert _ingest(session, conn, exact, identities, preview=True) == "exact_preview"
        assert session.scalar(select(func.count()).select_from(ApplicationEventRecord).where(ApplicationEventRecord.application_key.like("job:%"))) == 0
        assert _ingest(session, conn, exact, identities, preview=False) == "duplicate"
        assert session.scalar(select(func.count()).select_from(ApplicationEventRecord).where(ApplicationEventRecord.application_key.like("job:%"))) == 0

        assessment = message("assessment", "Req ID: SE-101. Please complete the online assessment.")
        assert _ingest(session, conn, assessment, identities, preview=False) == "automatic"
        live = message("live", "Req ID: SE-101. We have decided to move forward with other candidates.")
        assert _ingest(session, conn, live, identities, preview=False) == "automatic"
        assert _ingest(session, conn, live, identities, preview=False) == "duplicate"
        marks = list(session.scalars(select(JobMarkRecord).order_by(JobMarkRecord.job_id)))
        assert [r.application_status for r in marks] == ["applied", "rejected", "applied"]
        assert mark_counts(session)["applications_total"] == 3
        assert {e.kind for e in session.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.application_key.like("job:%")))} == {"online_assessment", "rejection"}
        assert session.scalar(select(func.count()).select_from(GmailMessageRecord)) == 4
        interview = message("new-interview", "Req ID: SE-102. We invite you to interview.")
        assert _ingest(session, conn, interview, identities, preview=False) == "automatic"
        older_rejection = message("old-rejection", "Req ID: SE-102. We have decided to move forward with other candidates.", NOW - timedelta(days=1))
        assert _ingest(session, conn, older_rejection, identities, preview=False) == "review"
        assert marks[2].application_status == "interviewing"
        assert mark_counts(session)["applications_total"] == 3
    get_settings.cache_clear()
