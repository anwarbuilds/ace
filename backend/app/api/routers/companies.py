"""Companies, as a directory: who is hiring for you, and where you applied.

One row per employer with an open qualifying role or an application, so
the web app can offer a page per company the way a shop offers one per
brand. Counts only; the roles themselves come from /api/jobs?company=.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.db.models import JobEvaluationRecord, JobMarkRecord, JobRecord
from backend.app.intelligence.companies import classify_company


router = APIRouter()


@router.get("/api/companies")
def companies(session: Session = Depends(get_session)) -> dict:
    open_role = case(
        (
            (JobRecord.is_active.is_(True)) & (JobEvaluationRecord.eligibility_status == "PASS"),
            1,
        ),
        else_=0,
    )
    applied = case((JobMarkRecord.applied_at.is_not(None), 1), else_=0)
    rows = session.execute(
        select(
            JobRecord.company,
            func.sum(open_role),
            func.sum(applied),
            func.max(case((open_role == 1, JobRecord.first_seen_at), else_=None)),
        )
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .outerjoin(JobMarkRecord, JobMarkRecord.job_id == JobRecord.id)
        .group_by(JobRecord.company)
    ).all()
    items = [
        {
            "name": name,
            "tier": classify_company(name).value,
            "open_roles": int(open_n or 0),
            "applied": int(applied_n or 0),
            "newest_role_at": newest.isoformat() if newest else None,
        }
        for name, open_n, applied_n, newest in rows
        if (open_n or 0) or (applied_n or 0)
    ]
    items.sort(key=lambda c: c["name"].lower())
    return {"items": items}
