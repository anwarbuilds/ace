"""Bridge legacy resume history into Resume Studio without changing scoring.

The original ``resumes`` rows remain the source used by the matcher. This
bridge copies their text into Resume Studio documents and versions so the new
interface can see the complete history. It does not activate a resume or
rescore jobs, which makes it safe to run during a staged migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CareerFactEventRecord,
    CareerFactRecord,
    ResumeDocumentRecord,
    ResumeRecord,
    ResumeVersionRecord,
)
from backend.app.studio.facts import suggest_facts
from backend.app.studio.sections import read_structure
from backend.app.studio.service import sha256


@dataclass(frozen=True)
class LegacyBackfillResult:
    documents_created: int = 0
    versions_created: int = 0
    facts_created: int = 0
    skipped: int = 0


def _legacy_id(document: ResumeDocumentRecord) -> int | None:
    report = document.report or {}
    value = report.get("legacy_resume_id") if isinstance(report, dict) else None
    return value if isinstance(value, int) else None


def _filename(resume: ResumeRecord) -> str:
    original = (resume.filename or resume.label or f"resume-{resume.id}").strip()
    stem = original.rsplit(".", 1)[0] if "." in original else original
    safe = "".join(
        character
        for character in stem
        if character.isalnum() or character in " ._-"
    )
    return f"{safe.strip()[:220] or f'resume-{resume.id}'}-legacy.txt"


def _add_suggested_facts(
    session: Session,
    *,
    document: ResumeDocumentRecord,
    text: str,
    now: datetime,
) -> int:
    count = 0
    for suggested in suggest_facts(read_structure(text)):
        fact = CareerFactRecord(
            kind=suggested.kind,
            title=suggested.title,
            organization=suggested.organization,
            start_date=suggested.start,
            end_date=suggested.end,
            bullets=suggested.bullets,
            skills=suggested.skills,
            evidence=suggested.evidence,
            status="suggested",
            origin="parsed",
            source_document_id=document.id,
            note="",
            created_at=now,
            updated_at=now,
        )
        session.add(fact)
        session.flush()
        session.add(
            CareerFactEventRecord(
                fact_id=fact.id,
                action="created",
                from_status="",
                to_status="suggested",
                before=None,
                at=now,
            )
        )
        count += 1
    return count


def backfill_legacy_resumes(session: Session, *, now: datetime) -> LegacyBackfillResult:
    """Import each missing legacy resume once and return aggregate counts."""

    resumes = session.scalars(
        select(ResumeRecord).order_by(ResumeRecord.uploaded_at, ResumeRecord.id)
    ).all()
    imported = {
        legacy_id
        for document in session.scalars(select(ResumeDocumentRecord)).all()
        if (legacy_id := _legacy_id(document)) is not None
    }
    has_primary = bool(
        session.scalar(
            select(func.count(ResumeVersionRecord.id)).where(
                ResumeVersionRecord.is_primary.is_(True)
            )
        )
    )
    active_id = next(
        (resume.id for resume in reversed(resumes) if resume.is_active),
        None,
    )
    documents_created = versions_created = facts_created = skipped = 0

    for resume in resumes:
        if resume.id in imported:
            skipped += 1
            continue
        text = resume.raw_text or ""
        payload = text.encode("utf-8")
        created_at = resume.uploaded_at or now
        document = ResumeDocumentRecord(
            kind="resume",
            filename=_filename(resume),
            media_type="text/plain",
            size_bytes=len(payload),
            sha256=sha256(payload),
            data=payload,
            extracted_text=text,
            parser="text",
            report={
                "source": "legacy_resume",
                "legacy_resume_id": resume.id,
                "original_filename": resume.filename,
            },
            created_at=created_at,
        )
        session.add(document)
        session.flush()
        documents_created += 1

        primary = not has_primary and resume.id == active_id
        version = ResumeVersionRecord(
            label=(resume.label or "Resume")[:255],
            kind="master",
            document_id=document.id,
            body_text=text,
            content_hash=sha256(text),
            status="approved",
            is_primary=primary,
            created_at=created_at,
            approved_at=created_at,
        )
        session.add(version)
        versions_created += 1
        if primary:
            has_primary = True
            facts_created += _add_suggested_facts(
                session,
                document=document,
                text=text,
                now=created_at,
            )

    session.flush()
    return LegacyBackfillResult(
        documents_created=documents_created,
        versions_created=versions_created,
        facts_created=facts_created,
        skipped=skipped,
    )
