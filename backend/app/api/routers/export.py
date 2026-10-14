"""Everything the owner entered by hand, in one file they can keep.

Marks, statuses, notes, answers, history, standalone applications and
resume versions are the data ace cannot recompute. Jobs and scores are
not included: they are rebuilt from the boards.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.db.models import (
    ApplicationAnswerRecord,
    ExternalApplicationRecord,
    HistoryEntryRecord,
    JobMarkRecord,
    JobRecord,
    ResumeRecord,
)


router = APIRouter()

EXPORT_FORMAT = "ace-owner-export/1"


def _iso(
    moment: datetime | None,
) -> str | None:
    return None if moment is None else moment.isoformat()


@router.get(
    "/api/export.json"
)
def export_owner_data(
    session: Session = Depends(
        get_session
    ),
) -> JSONResponse:
    """Return every hand-entered record, as a download."""

    marks = [
        {
            "job": {
                "source": job.source,
                "source_account": job.source_account,
                "external_id": job.external_id,
                "company": job.company,
                "title": job.title,
                "official_url": job.official_url,
            },
            "is_saved": mark.is_saved,
            "review_state": mark.review_state,
            "applied_at": _iso(mark.applied_at),
            "application_status": mark.application_status,
            "status_changed_at": _iso(mark.status_changed_at),
            "status_note": mark.status_note,
        }
        for mark, job in session.execute(
            select(
                JobMarkRecord,
                JobRecord,
            )
            .join(
                JobRecord,
                JobRecord.id == JobMarkRecord.job_id,
            )
            .order_by(
                JobMarkRecord.job_id
            )
        ).all()
    ]

    body = {
        "format": EXPORT_FORMAT,
        "exported_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "marks": marks,
        "answers": [
            {
                "label": row.label,
                "value": row.value,
            }
            for row in session.scalars(
                select(ApplicationAnswerRecord).order_by(
                    ApplicationAnswerRecord.sort_order,
                    ApplicationAnswerRecord.id,
                )
            )
        ],
        "history": [
            {
                "kind": row.kind,
                "employer": row.employer,
                "job_title": row.job_title,
                "location": row.location,
                "is_current": row.is_current,
                "start_month": row.start_month,
                "start_year": row.start_year,
                "end_month": row.end_month,
                "end_year": row.end_year,
                "description": row.description,
            }
            for row in session.scalars(
                select(HistoryEntryRecord).order_by(
                    HistoryEntryRecord.kind,
                    HistoryEntryRecord.sort_order,
                )
            )
        ],
        "external_applications": [
            {
                "company": row.company,
                "title": row.title,
                "applied_at": _iso(row.applied_at),
                "application_status": row.application_status,
                "url": row.url,
            }
            for row in session.scalars(
                select(ExternalApplicationRecord).order_by(
                    ExternalApplicationRecord.id
                )
            )
        ],
        "resumes": [
            {
                "label": row.label,
                "filename": row.filename,
                "uploaded_at": _iso(row.uploaded_at),
                "is_active": row.is_active,
                "raw_text": row.raw_text,
            }
            for row in session.scalars(
                select(ResumeRecord).order_by(
                    ResumeRecord.uploaded_at
                )
            )
        ],
    }

    return JSONResponse(
        body,
        headers={
            "Content-Disposition": (
                'attachment; filename="ace-export.json"'
            ),
        },
    )
