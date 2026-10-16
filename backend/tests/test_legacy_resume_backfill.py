"""Legacy resume history appears in Resume Studio exactly once."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    CareerFactRecord,
    ResumeDocumentRecord,
    ResumeRecord,
    ResumeVersionRecord,
)
from backend.app.studio.legacy import backfill_legacy_resumes


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def _resume(identifier: int, *, active: bool, text: str, age: int) -> ResumeRecord:
    at = NOW - timedelta(days=age)
    return ResumeRecord(
        id=identifier,
        label=f"Resume {identifier}",
        filename=f"resume-{identifier}.pdf",
        content_hash=f"hash-{identifier}",
        raw_text=text,
        extracted_skills={},
        is_active=active,
        uploaded_at=at,
    )


def test_backfill_preserves_history_primary_text_and_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    active_text = """Summary
Software engineer

Skills
Python, TypeScript

Experience
Engineer | Example Corp | 2024 to Present
* Built reliable services.
"""
    with Session(engine) as session:
        session.add_all(
            [
                _resume(1, active=False, text="Summary\nEarlier resume", age=20),
                _resume(2, active=True, text=active_text, age=2),
            ]
        )
        session.commit()

        first = backfill_legacy_resumes(session, now=NOW)
        session.commit()
        second = backfill_legacy_resumes(session, now=NOW)
        session.commit()

        assert first.documents_created == first.versions_created == 2
        assert first.facts_created > 0
        assert second.documents_created == second.versions_created == 0
        assert second.skipped == 2
        assert (
            session.scalar(select(func.count()).select_from(ResumeDocumentRecord))
            == 2
        )
        assert (
            session.scalar(select(func.count()).select_from(ResumeVersionRecord))
            == 2
        )

        primary = session.scalar(
            select(ResumeVersionRecord).where(ResumeVersionRecord.is_primary.is_(True))
        )
        assert primary is not None and primary.body_text == active_text
        document = session.get(ResumeDocumentRecord, primary.document_id)
        assert document is not None
        assert document.data.decode() == active_text
        assert document.report["legacy_resume_id"] == 2
        assert (
            session.scalar(select(func.count()).select_from(CareerFactRecord))
            == first.facts_created
        )
