"""Resume Studio over HTTP: documents, facts, versions, the checker."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.db.models import (
    CareerFactEventRecord,
    CareerFactRecord,
    ResumeAssessmentRecord,
    ResumeDocumentRecord,
    ResumeVersionRecord,
)
from backend.app.studio import service
from backend.app.studio.ats import ALGORITHM_VERSION, WEIGHTS
from backend.app.studio.sections import read_structure


router = APIRouter(prefix="/api/studio")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bad(error: service.StudioError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _document(d: ResumeDocumentRecord, *, text: bool = False) -> dict:
    out = {
        "id": d.id, "kind": d.kind, "filename": d.filename, "media_type": d.media_type,
        "size_bytes": d.size_bytes, "parser": d.parser, "report": d.report or {},
        "created_at": _iso(d.created_at),
    }
    if text:
        out["extracted_text"] = d.extracted_text
        structure = read_structure(d.extracted_text)
        out["structure"] = {
            "sections": [{"kind": s.kind, "heading": s.heading, "line": s.start + 1} for s in structure.sections],
            "emails": structure.emails, "phones": structure.phones, "links": structure.links,
            "dates": [{"text": x.text, "line": x.line + 1} for x in structure.dates],
            "bullets": len(structure.bullets),
        }
    return out


def _fact(f: CareerFactRecord) -> dict:
    return {
        "id": f.id, "kind": f.kind, "title": f.title, "organization": f.organization,
        "start_date": f.start_date, "end_date": f.end_date, "bullets": f.bullets or [],
        "skills": f.skills or [], "evidence": f.evidence, "status": f.status, "origin": f.origin,
        "source_document_id": f.source_document_id, "note": f.note,
        "created_at": _iso(f.created_at), "updated_at": _iso(f.updated_at),
    }


def _version(v: ResumeVersionRecord, *, text: bool = False) -> dict:
    out = {
        "id": v.id, "label": v.label, "kind": v.kind, "parent_id": v.parent_id,
        "document_id": v.document_id, "job_id": v.job_id, "status": v.status,
        "is_primary": v.is_primary, "content_hash": v.content_hash,
        "created_at": _iso(v.created_at), "approved_at": _iso(v.approved_at),
    }
    if text:
        out["body_text"] = v.body_text
    return out


def _assessment(a: ResumeAssessmentRecord, *, full: bool = False) -> dict:
    out = {
        "id": a.id, "version_id": a.version_id, "job_id": a.job_id, "job_source": a.job_source,
        "job_title": a.job_title, "job_company": a.job_company, "algorithm_version": a.algorithm_version,
        "state": a.state, "aggregate": a.aggregate, "confidence": a.confidence,
        "components": (a.result or {}).get("components", {}), "created_at": _iso(a.created_at),
    }
    if full:
        out["result"] = a.result
    return out


@router.get("")
def overview(session: Session = Depends(get_session)) -> dict:
    counts = {
        (kind, status): n
        for kind, status, n in session.execute(
            select(CareerFactRecord.kind, CareerFactRecord.status, func.count()).group_by(
                CareerFactRecord.kind, CareerFactRecord.status
            )
        )
    }
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for (kind, status), n in counts.items():
        by_status[status] = by_status.get(status, 0) + n
        if status != "deprecated":
            by_kind[kind] = by_kind.get(kind, 0) + n
    primary = session.scalar(select(ResumeVersionRecord).where(ResumeVersionRecord.is_primary.is_(True)))
    return {
        "primary": _version(primary) if primary else None,
        "facts": {"by_status": by_status, "by_kind": by_kind},
        "documents": [_document(d) for d in session.scalars(
            select(ResumeDocumentRecord).order_by(ResumeDocumentRecord.created_at.desc()))],
        "versions": [_version(v) for v in session.scalars(
            select(ResumeVersionRecord).order_by(ResumeVersionRecord.created_at.desc()))],
        "recent": [_assessment(a) for a in session.scalars(
            select(ResumeAssessmentRecord).order_by(ResumeAssessmentRecord.created_at.desc()).limit(6))],
        "checker": {"algorithm_version": ALGORITHM_VERSION, "weights": WEIGHTS},
    }


@router.post("/documents")
def upload_document(
    file: UploadFile = File(...),
    kind: str = Form("resume"),
    session: Session = Depends(get_session),
) -> dict:
    payload = file.file.read(service.MAX_FILE_BYTES + 1)
    try:
        document, created = service.upload(session, filename=file.filename or "resume",
                                           payload=payload, kind=kind, now=_now())
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return {"document": _document(document), "created": created}


@router.get("/documents/{document_id}")
def get_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    document = session.get(ResumeDocumentRecord, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="No such document.")
    return _document(document, text=True)


@router.get("/documents/{document_id}/file")
def download_document(document_id: int, session: Session = Depends(get_session)) -> Response:
    document = session.get(ResumeDocumentRecord, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="No such document.")
    safe = "".join(c for c in document.filename if c.isalnum() or c in "._ ") or "resume"
    return Response(document.data, media_type=document.media_type,
                    headers={"Content-Disposition": f'attachment; filename="{safe}"'})


class FactBody(BaseModel):
    kind: str | None = None
    title: str | None = None
    organization: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] | None = None
    skills: list[str] | None = None
    note: str | None = None
    status: str | None = None


@router.get("/facts")
def list_facts(
    status: str | None = Query(None),
    kind: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    statement = select(CareerFactRecord).order_by(
        CareerFactRecord.kind, CareerFactRecord.start_date.desc(), CareerFactRecord.id
    )
    if status:
        statement = statement.where(CareerFactRecord.status == status)
    if kind:
        statement = statement.where(CareerFactRecord.kind == kind)
    return {"items": [_fact(f) for f in session.scalars(statement)]}


@router.post("/facts")
def create_fact(body: FactBody, session: Session = Depends(get_session)) -> dict:
    try:
        fact = service.create_fact(session, fields=body.model_dump(exclude_none=True), now=_now())
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return _fact(fact)


@router.patch("/facts/{fact_id}")
def update_fact(fact_id: int, body: FactBody, session: Session = Depends(get_session)) -> dict:
    try:
        fact = service.update_fact(session, fact_id, changes=body.model_dump(exclude_none=True), now=_now())
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return _fact(fact)


@router.get("/facts/{fact_id}/history")
def fact_history(fact_id: int, session: Session = Depends(get_session)) -> dict:
    events = session.scalars(
        select(CareerFactEventRecord).where(CareerFactEventRecord.fact_id == fact_id)
        .order_by(CareerFactEventRecord.at, CareerFactEventRecord.id)
    )
    return {"items": [{"action": e.action, "from_status": e.from_status, "to_status": e.to_status,
                       "before": e.before, "at": _iso(e.at)} for e in events]}


class VersionBody(BaseModel):
    label: str = ""
    body_text: str = ""
    parent_id: int | None = None


@router.get("/versions/{version_id}")
def get_version(version_id: int, session: Session = Depends(get_session)) -> dict:
    version = session.get(ResumeVersionRecord, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="No such version.")
    return _version(version, text=True)


@router.post("/versions")
def create_version(body: VersionBody, session: Session = Depends(get_session)) -> dict:
    """A corrected copy: the owner fixes what extraction got wrong."""

    parent = session.get(ResumeVersionRecord, body.parent_id) if body.parent_id else None
    try:
        version = service.create_version(
            session, label=body.label or (parent.label + ", corrected" if parent else "Resume"),
            body_text=body.body_text, kind="master", parent_id=body.parent_id,
            document_id=parent.document_id if parent else None, now=_now(),
        )
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return _version(version, text=True)


@router.post("/versions/{version_id}/primary")
def make_primary(version_id: int, session: Session = Depends(get_session)) -> dict:
    try:
        version = service.make_primary(session, version_id, now=_now())
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return _version(version)


class CheckBody(BaseModel):
    version_id: int
    job_id: int | None = None
    job_text: str = ""
    job_title: str = ""
    job_company: str = ""


@router.post("/check")
def run_check(body: CheckBody, session: Session = Depends(get_session)) -> dict:
    try:
        record = service.check(
            session, version_id=body.version_id, job_id=body.job_id, pasted_text=body.job_text,
            pasted_title=body.job_title, pasted_company=body.job_company, now=_now(),
        )
    except service.StudioError as error:
        raise _bad(error) from None
    session.commit()
    return _assessment(record, full=True)


@router.get("/assessments")
def assessments(
    version_id: int | None = Query(None),
    job_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    statement = select(ResumeAssessmentRecord).order_by(ResumeAssessmentRecord.created_at.desc()).limit(limit)
    if version_id:
        statement = statement.where(ResumeAssessmentRecord.version_id == version_id)
    if job_id:
        statement = statement.where(ResumeAssessmentRecord.job_id == job_id)
    return {"items": [_assessment(a) for a in session.scalars(statement)]}


@router.get("/assessments/{assessment_id}")
def assessment(assessment_id: int, session: Session = Depends(get_session)) -> dict:
    record = session.get(ResumeAssessmentRecord, assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such assessment.")
    return _assessment(record, full=True)
