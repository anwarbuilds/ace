"""Resume Studio's rules over the database.

Pure functions over a session and an explicit `now`, like the auth
service, so every rule is tested without a server.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CareerFactEventRecord,
    CareerFactRecord,
    JobEvaluationRecord,
    JobRecord,
    ResumeAssessmentRecord,
    ResumeDocumentRecord,
    ResumeVersionRecord,
)
from backend.app.intelligence.eligibility import ACTIVE_PROFILE
from backend.app.matching.service import rescore_corpus, store_resume
from backend.app.models.job import CanonicalJob
from backend.app.studio.ats import assess
from backend.app.studio.documents import media_type, read_document
from backend.app.studio.facts import suggest_facts
from backend.app.studio.sections import read_structure


STATUSES = ("verified", "suggested", "deprecated", "needs_clarification")

KINDS = ("experience", "education", "project", "skill", "certification", "summary", "preference")

FACT_FIELDS = ("kind", "title", "organization", "start_date", "end_date", "bullets", "skills", "note")

MAX_FILE_BYTES = 5 * 1024 * 1024


class StudioError(ValueError):
    """A request Resume Studio turns down; the message says why."""


def sha256(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


# ----------------------------------------------------------------------
# Documents
# ----------------------------------------------------------------------


def upload(
    session: Session,
    *,
    filename: str,
    payload: bytes,
    kind: str,
    now: datetime,
    primary_if_first: bool = True,
) -> tuple[ResumeDocumentRecord, bool]:
    """Store a file as uploaded. A resume also yields suggested facts and
    a master version. The same file twice is stored once."""

    if kind not in ("resume", "template"):
        raise StudioError("Unknown document kind.")
    if not payload:
        raise StudioError("The file is empty.")
    if len(payload) > MAX_FILE_BYTES:
        raise StudioError("A file is at most 5 MB.")
    media = media_type(filename)
    if media is None or (kind == "template" and not filename.lower().endswith(".docx")):
        raise StudioError("Upload a PDF, DOCX or text file. A template must be a DOCX.")

    digest = sha256(payload)
    existing = session.scalar(
        select(ResumeDocumentRecord).where(
            ResumeDocumentRecord.sha256 == digest, ResumeDocumentRecord.kind == kind
        )
    )
    if existing is not None:
        return existing, False

    text, parser, report = read_document(payload=payload, filename=filename)
    document = ResumeDocumentRecord(
        kind=kind,
        filename=filename[:255],
        media_type=media,
        size_bytes=len(payload),
        sha256=digest,
        data=payload,
        extracted_text=text,
        parser=parser,
        report=report,
        created_at=now,
    )
    session.add(document)
    session.flush()

    if kind == "resume" and text:
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
            session.add(CareerFactEventRecord(fact_id=fact.id, action="created", from_status="",
                                              to_status="suggested", before=None, at=now))
        has_primary = session.scalar(
            select(func.count(ResumeVersionRecord.id)).where(ResumeVersionRecord.is_primary.is_(True))
        )
        create_version(
            session,
            label=filename.rsplit(".", 1)[0][:200],
            body_text=text,
            kind="master",
            document_id=document.id,
            now=now,
            primary=primary_if_first and not has_primary,
        )
    return document, True


# ----------------------------------------------------------------------
# Facts
# ----------------------------------------------------------------------


def _snapshot(fact: CareerFactRecord) -> dict:
    return {name: getattr(fact, name) for name in (*FACT_FIELDS, "status")}


def create_fact(session: Session, *, fields: dict, now: datetime) -> CareerFactRecord:
    """A fact the owner typed is theirs, so it starts verified."""

    kind = fields.get("kind", "")
    if kind not in KINDS:
        raise StudioError("Choose what kind of fact this is.")
    if not str(fields.get("title", "")).strip():
        raise StudioError("Give the fact a title.")
    fact = CareerFactRecord(
        kind=kind,
        title=str(fields.get("title", "")).strip()[:255],
        organization=str(fields.get("organization", "")).strip()[:255],
        start_date=str(fields.get("start_date", ""))[:10],
        end_date=str(fields.get("end_date", ""))[:10],
        bullets=[str(b).strip() for b in fields.get("bullets") or [] if str(b).strip()],
        skills=sorted({str(s).strip().lower() for s in fields.get("skills") or [] if str(s).strip()}),
        evidence="",
        status="verified",
        origin="user",
        note=str(fields.get("note", ""))[:2000],
        created_at=now,
        updated_at=now,
    )
    session.add(fact)
    session.flush()
    session.add(CareerFactEventRecord(fact_id=fact.id, action="created", from_status="",
                                      to_status="verified", before=None, at=now))
    return fact


def update_fact(session: Session, fact_id: int, *, changes: dict, now: datetime) -> CareerFactRecord:
    fact = session.get(CareerFactRecord, fact_id)
    if fact is None:
        raise StudioError("No such fact.")
    before = _snapshot(fact)
    status = changes.get("status")
    if status is not None and status not in STATUSES:
        raise StudioError("Unknown status.")
    edited = False
    for name in FACT_FIELDS:
        if name in changes and changes[name] is not None:
            value = changes[name]
            if name == "kind" and value not in KINDS:
                raise StudioError("Unknown kind.")
            if name == "skills":
                value = sorted({str(s).strip().lower() for s in value if str(s).strip()})
            if name == "bullets":
                value = [str(b).strip() for b in value if str(b).strip()]
            if getattr(fact, name) != value:
                setattr(fact, name, value)
                edited = True
    if edited:
        session.add(CareerFactEventRecord(fact_id=fact.id, action="edited", from_status=fact.status,
                                          to_status=fact.status, before=before, at=now))
    if status is not None and status != fact.status:
        session.add(CareerFactEventRecord(fact_id=fact.id, action="status", from_status=fact.status,
                                          to_status=status, before=None, at=now))
        fact.status = status
    fact.updated_at = now
    session.flush()
    return fact


def verified_skills(session: Session) -> frozenset[str] | None:
    """Skills the owner has confirmed. None until anything is verified,
    so an untouched knowledge base does not flood the checker."""

    rows = session.scalars(select(CareerFactRecord).where(CareerFactRecord.status == "verified")).all()
    if not rows:
        return None
    skills: set[str] = set()
    for fact in rows:
        skills.update(fact.skills or [])
        if fact.kind == "skill":
            skills.add(fact.title.lower())
    return frozenset(skills)


# ----------------------------------------------------------------------
# Versions
# ----------------------------------------------------------------------


def create_version(
    session: Session,
    *,
    label: str,
    body_text: str,
    kind: str = "master",
    parent_id: int | None = None,
    document_id: int | None = None,
    job_id: int | None = None,
    now: datetime,
    primary: bool = False,
) -> ResumeVersionRecord:
    if not body_text.strip():
        raise StudioError("A version needs some text.")
    version = ResumeVersionRecord(
        label=(label.strip() or "Resume")[:255],
        kind=kind,
        parent_id=parent_id,
        document_id=document_id,
        job_id=job_id,
        body_text=body_text,
        content_hash=sha256(body_text),
        status="approved" if kind == "master" else "draft",
        is_primary=False,
        created_at=now,
        approved_at=now if kind == "master" else None,
    )
    session.add(version)
    session.flush()
    if primary:
        make_primary(session, version.id, now=now)
    return version


def make_primary(session: Session, version_id: int, *, now: datetime) -> ResumeVersionRecord:
    """The version the job list scores against. Copies its text into the
    matcher's resume table and rescores, as an upload always has."""

    version = session.get(ResumeVersionRecord, version_id)
    if version is None:
        raise StudioError("No such version.")
    if version.status != "approved":
        raise StudioError("Approve a version before using it for matching.")
    for other in session.scalars(select(ResumeVersionRecord).where(ResumeVersionRecord.is_primary.is_(True))):
        other.is_primary = False
    version.is_primary = True
    record = store_resume(session, label=version.label, filename=f"version-{version.id}.txt",
                          raw_text=version.body_text, now=now)
    rescore_corpus(session, resume=record)
    session.flush()
    return version


# ----------------------------------------------------------------------
# The checker
# ----------------------------------------------------------------------


def _canonical(job: JobRecord) -> CanonicalJob:
    return CanonicalJob(
        source=job.source, company=job.company, external_id=job.external_id,
        requisition_id=job.requisition_id, title=job.title, location=job.location,
        description=job.description or "", official_url=job.official_url,
        posted_at=job.posted_at, updated_at=job.source_updated_at, employment_type=job.employment_type,
    )


def check(
    session: Session,
    *,
    version_id: int,
    job_id: int | None = None,
    pasted_text: str = "",
    pasted_title: str = "",
    pasted_company: str = "",
    now: datetime,
) -> ResumeAssessmentRecord:
    version = session.get(ResumeVersionRecord, version_id)
    if version is None:
        raise StudioError("No such version.")
    document = session.get(ResumeDocumentRecord, version.document_id) if version.document_id else None
    report = (document.report or {}) if document else {}

    if job_id is not None:
        job = session.get(JobRecord, job_id)
        if job is None:
            raise StudioError("No such job.")
        evaluation = session.scalar(select(JobEvaluationRecord).where(JobEvaluationRecord.job_id == job.id))
        verified = bool(getattr(evaluation, "requirements_verified", True)) if evaluation else True
        canonical = _canonical(job)
        text, source, title, company = canonical.description, "stored", job.title, job.company
        result = assess(resume_text=version.body_text, job=canonical, report=report,
                        profile=ACTIVE_PROFILE, verified=verified, kb_skills=verified_skills(session))
    else:
        if not pasted_text.strip():
            raise StudioError("Choose a job, or paste a job description.")
        text, source, title, company = pasted_text, "pasted", pasted_title, pasted_company
        result = assess(resume_text=version.body_text, job=None, job_text=pasted_text, report=report,
                        profile=ACTIVE_PROFILE, kb_skills=verified_skills(session))

    record = ResumeAssessmentRecord(
        version_id=version.id,
        job_id=job_id,
        job_source=source,
        job_title=title[:255],
        job_company=company[:255],
        job_text_hash=sha256(text),
        job_text=text if source == "pasted" else "",
        algorithm_version=result.algorithm_version,
        state=result.state,
        aggregate=result.aggregate,
        confidence=result.confidence,
        result=result.to_dict(),
        created_at=now,
    )
    session.add(record)
    session.flush()
    return record
