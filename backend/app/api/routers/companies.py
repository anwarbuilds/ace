"""Companies, as a directory: who is hiring for you, and where you applied.

One row per employer with an open qualifying role or an application, so
the web app can offer a page per company the way a shop offers one per
brand. Counts only; the roles themselves come from /api/jobs?company=.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.db.models import CompanyPetitionReportRecord, JobEvaluationRecord, JobMarkRecord, JobRecord
from backend.app.intelligence.companies import classify_company


router = APIRouter()


@router.get("/api/company-intelligence/batch")
def company_intelligence_batch(name: list[str] = Query(default=[]), session: Session = Depends(get_session)) -> dict:
    """Compact verified evidence for the visible Pull rows, never fuzzy joined."""
    names = list(dict.fromkeys(value[:255] for value in name if value))[:30]
    if not names:
        return {"items": {}}
    rows = session.scalars(
        select(CompanyPetitionReportRecord)
        .where(CompanyPetitionReportRecord.ace_company.in_(names), CompanyPetitionReportRecord.entity_verified.is_(True))
        .order_by(CompanyPetitionReportRecord.period.desc())
    ).all()
    items = {}
    for row in rows:
        items.setdefault(row.ace_company, {
            "period": row.period, "source": row.source_name, "source_uri": row.source_uri,
            "metric_definition": row.metric_definition, "approvals": row.petition_approvals,
            "denials": row.petition_denials, "last_checked_at": row.last_checked_at.isoformat(),
        })
    return {"items": items}


@router.get("/api/company-intelligence")
def company_intelligence(name: str = Query(..., min_length=1, max_length=255), session: Session = Depends(get_session)) -> dict:
    """Only explicitly resolved official legal-entity evidence is shown."""
    reports = session.scalars(
        select(CompanyPetitionReportRecord)
        .where(CompanyPetitionReportRecord.ace_company == name, CompanyPetitionReportRecord.entity_verified.is_(True))
        .order_by(CompanyPetitionReportRecord.period.desc())
        .limit(20)
    ).all()
    return {
        "company": name,
        "petition_history": [
            {
                "legal_entity": r.legal_entity,
                "source": r.source_name,
                "source_uri": r.source_uri,
                "metric_definition": r.metric_definition,
                "period": r.period,
                "report_version": r.report_version,
                "approvals": r.petition_approvals,
                "denials": r.petition_denials,
                "approval_rate": (
                    r.petition_approvals / (r.petition_approvals + r.petition_denials)
                    if r.metric_definition == "USCIS I-129 petition decisions"
                    and r.petition_approvals is not None and r.petition_denials is not None
                    and r.petition_approvals + r.petition_denials > 0 else None
                ),
                "first_seen_at": r.first_seen_at.isoformat(),
                "last_checked_at": r.last_checked_at.isoformat(),
            }
            for r in reports
        ],
        "hiring_sponsorship_rate": None,
        "status": "verified" if reports else "unavailable",
    }


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
