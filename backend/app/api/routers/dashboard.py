"""The analysis page in one request: open roles by company tier and by
role family, how the resume scores across them, applications by status,
and arrivals per day.

Read over the same qualifying set the Opportunities list shows (active,
passing the gate, opened within the usual window), so every number here
can be clicked through to the rows behind it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.queries import MATCH_HIGH_MIN, MATCH_MEDIUM_MIN, QUALIFYING_STATUSES
from backend.app.config import get_settings
from backend.app.db.models import (
    JobEvaluationRecord,
    JobMarkRecord,
    JobRecord,
    JobResumeScoreRecord,
)
from backend.app.intelligence.companies import classify_company
from backend.app.matching.service import get_active_resume
from backend.app.persistence.openings import OLD_OPENING_DAYS, opened_within


router = APIRouter()

TIERS = ("BIG_TECH", "TOP_TIER", "ESTABLISHED", "OTHER")

DAYS = 14


def _band(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score >= MATCH_HIGH_MIN:
        return "high"
    if score >= MATCH_MEDIUM_MIN:
        return "medium"
    return "minimal"


def _empty() -> dict:
    return {"open": 0, "applied": 0, "high": 0, "medium": 0, "minimal": 0, "unscored": 0}


@router.get("/api/dashboard")
def dashboard(session: Session = Depends(get_session)) -> dict:
    now = datetime.now(timezone.utc)
    zone = ZoneInfo(get_settings().display_timezone)
    resume = get_active_resume(session)

    rows = session.execute(
        select(
            JobRecord.company,
            JobEvaluationRecord.role_family,
            JobResumeScoreRecord.score,
            JobRecord.first_seen_at,
            JobMarkRecord.applied_at,
        )
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .outerjoin(
            JobResumeScoreRecord,
            and_(
                JobResumeScoreRecord.job_id == JobRecord.id,
                JobResumeScoreRecord.resume_id == (resume.id if resume else -1),
            ),
        )
        .outerjoin(JobMarkRecord, JobMarkRecord.job_id == JobRecord.id)
        .where(
            JobRecord.is_active.is_(True),
            JobEvaluationRecord.eligibility_status.in_(QUALIFYING_STATUSES),
            opened_within(OLD_OPENING_DAYS, now=now),
        )
    ).all()

    tiers = {t: _empty() for t in TIERS}
    families: dict[str, dict] = defaultdict(_empty)
    companies: dict[str, dict] = {}
    scores: Counter = Counter()
    daily: Counter = Counter()
    first_day = (now.astimezone(zone) - timedelta(days=DAYS - 1)).date()

    for company, family, score, first_seen, applied_at in rows:
        tier = classify_company(company).value
        band = _band(score)
        for bucket in (tiers[tier], families[family or "OTHER"]):
            bucket["open"] += 1
            bucket[band] += 1
            if applied_at:
                bucket["applied"] += 1
        scores[band] += 1
        c = companies.setdefault(company, {"name": company, "tier": tier, "open": 0, "best": None, "applied": 0})
        c["open"] += 1
        if score is not None and (c["best"] is None or score > c["best"]):
            c["best"] = score
        if applied_at:
            c["applied"] += 1
        if first_seen is not None:
            seen = first_seen if first_seen.tzinfo else first_seen.replace(tzinfo=timezone.utc)
            day = seen.astimezone(zone).date()
            if day >= first_day:
                daily[day] += 1

    statuses = Counter(
        status or "applied"
        for (status,) in session.execute(
            select(JobMarkRecord.application_status).where(JobMarkRecord.applied_at.is_not(None))
        )
    )

    return {
        "total_open": len(rows),
        "resume": {"label": resume.label} if resume else None,
        "scores": {k: scores.get(k, 0) for k in ("high", "medium", "minimal", "unscored")},
        "tiers": [{"tier": t, **tiers[t]} for t in TIERS],
        "families": sorted(
            ({"family": f, **v} for f, v in families.items()), key=lambda x: -x["open"]
        ),
        "top_companies": sorted(
            companies.values(), key=lambda c: (-(c["best"] or -1), -c["open"], c["name"])
        )[:12],
        "applications": dict(statuses),
        "daily": [
            {"date": (first_day + timedelta(days=i)).isoformat(), "found": daily.get(first_day + timedelta(days=i), 0)}
            for i in range(DAYS)
        ],
        "thresholds": {"high": MATCH_HIGH_MIN, "medium": MATCH_MEDIUM_MIN},
    }
