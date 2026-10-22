"""Decision intelligence from persisted ACE records and explicit event coverage."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import secrets
from statistics import median
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.marks import mark_counts
from backend.app.auth.guard import current_owner
from backend.app.config import get_settings
from backend.app.db.models import (
    ApplicationEventRecord,
    CompanyPetitionReportRecord,
    ExternalApplicationRecord,
    GmailMessageRecord,
    JobEvaluationRecord,
    JobMarkRecord,
    JobRecord,
    PollSessionRecord,
)
from backend.app.matching.skills import extract_skills

router = APIRouter()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _action_candidates(session: Session) -> list[dict]:
    """Small, evidence-linked task set. No status is inferred from silence."""
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for job_id, company, title, applied_at, status in session.execute(
        select(JobMarkRecord.job_id, JobRecord.company, JobRecord.title, JobMarkRecord.applied_at, JobMarkRecord.application_status)
        .join(JobRecord, JobRecord.id == JobMarkRecord.job_id)
        .where(JobMarkRecord.applied_at.is_not(None))
    ):
        if status not in {"accepted", "rejected", "withdrawn"} and applied_at and _aware(applied_at) <= now - timedelta(days=7):
            rows.append({"key": f"job:{job_id}", "kind": "follow_up", "title": f"Review {company} application", "reason": "Submitted at least 7 days ago with no confirmed terminal outcome", "href": f"/app/jobs/{job_id}", "evidence_at": _aware(applied_at).isoformat()})
    for app in session.scalars(select(ExternalApplicationRecord)):
        if app.application_status not in {"accepted", "rejected", "withdrawn"} and app.applied_at and _aware(app.applied_at) <= now - timedelta(days=7):
            rows.append({"key": f"external:{app.id}", "kind": "follow_up", "title": f"Review {app.company} application", "reason": "External submission at least 7 days ago with no confirmed terminal outcome", "href": "/app/applications", "evidence_at": _aware(app.applied_at).isoformat()})
    for email in session.scalars(select(GmailMessageRecord).where(GmailMessageRecord.decision.in_(("review", "exact_preview"))).order_by(GmailMessageRecord.received_at.desc()).limit(20)):
        rows.append({"key": f"email:{email.id}", "kind": "email_review", "title": f"Review email: {email.subject}", "reason": email.decision_reason, "href": "/app/applications/inbox", "evidence_at": _aware(email.received_at).isoformat()})
    for pull in session.scalars(select(PollSessionRecord).where(PollSessionRecord.started_at >= now - timedelta(days=1), PollSessionRecord.qualifying_discovered > 0).order_by(PollSessionRecord.started_at.desc()).limit(6)):
        rows.append({"key": f"pull:{pull.id}", "kind": "fresh_opportunities", "title": f"Review {pull.qualifying_discovered} qualifying roles", "reason": "New roles in a recorded Pull window", "href": "/app/pulls", "evidence_at": _aware(pull.started_at).isoformat()})
    return sorted(rows, key=lambda row: row["evidence_at"], reverse=True)[:50]


@router.get("/api/intelligence/actions")
def actions(request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    rows = _action_candidates(session)
    keys = {f"action:{row['key']}" for row in rows}
    events = session.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.application_key.in_(keys)).order_by(ApplicationEventRecord.recorded_at, ApplicationEventRecord.id)).all() if keys else []
    state = {event.application_key: event.new_status for event in events if event.kind == "action_state"}
    return {"as_of": datetime.now(timezone.utc).isoformat(), "items": [{**row, "state": state.get(f"action:{row['key']}", "open")} for row in rows]}


class ActionUpdate(BaseModel):
    key: str
    state: str


@router.post("/api/intelligence/actions")
def update_action(body: ActionUpdate, request: Request, session: Session = Depends(get_session)) -> dict:
    current_owner(request)
    if body.state not in {"open", "completed", "dismissed"} or body.key not in {row["key"] for row in _action_candidates(session)}:
        raise HTTPException(422, "Action is unavailable. Refresh the action center.")
    latest = session.scalar(select(ApplicationEventRecord).where(ApplicationEventRecord.application_key == f"action:{body.key}", ApplicationEventRecord.kind == "action_state").order_by(ApplicationEventRecord.id.desc()).limit(1))
    event = ApplicationEventRecord(application_key=f"action:{body.key}", kind="action_state", previous_status=latest.new_status if latest else "open", new_status=body.state,
                                   actor="owner", reason="Owner changed action center state", occurred_at=datetime.now(timezone.utc),
                                   dedupe_key=f"action:{body.key}:{secrets.token_hex(16)}")
    session.add(event)
    session.commit()
    return {"key": body.key, "state": body.state}


@router.get("/api/intelligence")
def intelligence(days: int = Query(90, ge=7, le=365), family: str | None = Query(None), session: Session = Depends(get_session)) -> dict:
    now = datetime.now(timezone.utc)
    zone = ZoneInfo(get_settings().display_timezone)
    since = now.astimezone(zone).date() - timedelta(days=days - 1)
    marks = mark_counts(session)
    marked = session.execute(
        select(JobMarkRecord.job_id, JobRecord.company, JobEvaluationRecord.role_family, JobMarkRecord.applied_at, JobMarkRecord.application_status)
        .join(JobRecord, JobRecord.id == JobMarkRecord.job_id)
        .outerjoin(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobMarkRecord.applied_at.is_not(None))
    ).all()
    external = session.execute(select(ExternalApplicationRecord.id, ExternalApplicationRecord.company, ExternalApplicationRecord.applied_at, ExternalApplicationRecord.application_status)).all()
    applications = [
        (f"job:{id}", company, role or "Unknown", at, status or "applied")
        for id, company, role, at, status in marked
    ] + [
        (f"external:{id}", company, "Unknown", at, status or "applied")
        for id, company, at, status in external
    ]
    if family:
        filtered = [a for a in applications if a[2] == family]
    else:
        filtered = applications
    filtered_keys = {row[0] for row in filtered}
    status = Counter(row[4] for row in filtered)
    daily: Counter = Counter()
    cohorts: dict[str, Counter] = defaultdict(Counter)
    roles: dict[str, Counter] = defaultdict(Counter)
    companies: dict[str, Counter] = defaultdict(Counter)
    undated = 0
    for key, company, role, at, stage in filtered:
        roles[role]["submitted"] += 1
        companies[company]["submitted"] += 1
        if stage == "rejected":
            roles[role]["currently_rejected"] += 1
        if at is None:
            undated += 1
            continue
        day = _aware(at).astimezone(zone).date()
        cohorts[day.strftime("%Y-%m")][stage] += 1
        if day >= since:
            daily[day.isoformat()] += 1
    events = session.execute(
        select(ApplicationEventRecord.application_key, ApplicationEventRecord.kind, ApplicationEventRecord.occurred_at)
    ).all()
    event_keys: dict[str, set[str]] = defaultdict(set)
    for key, kind, _ in events:
        if key in filtered_keys:
            event_keys[kind].add(key)
    response_kinds = ("recruiter_reply", "online_assessment", "screening", "interview", "interviewing", "offer", "accepted")
    responded = set().union(*(event_keys[k] for k in response_kinds))
    submitted_at = {key: _aware(at) for key, _, _, at, _ in filtered if at is not None}
    mature = {key for key, at in submitted_at.items() if at <= now - timedelta(days=30)}
    first_response: dict[str, datetime] = {}
    for key, kind, occurred in events:
        if key in submitted_at and kind in response_kinds and occurred is not None:
            stamp = _aware(occurred)
            if stamp >= submitted_at[key] and (key not in first_response or stamp < first_response[key]):
                first_response[key] = stamp
    response_days = [(stamp - submitted_at[key]).total_seconds() / 86400 for key, stamp in first_response.items()]
    complete_coverage = len({key for key, _, _ in events if key in filtered_keys}) >= len(filtered)
    pending = sum(n for s, n in status.items() if s not in {"rejected", "withdrawn", "accepted"})
    source_query = (
        select(JobEvaluationRecord.role_family, func.count(JobRecord.id))
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.first_seen_at >= now - timedelta(days=days), JobEvaluationRecord.eligibility_status == "PASS")
        .group_by(JobEvaluationRecord.role_family)
    )
    if family:
        source_query = source_query.where(JobEvaluationRecord.role_family == family)
    source_rows = session.execute(source_query).all()
    available_families = session.scalars(
        select(JobEvaluationRecord.role_family)
        .where(JobEvaluationRecord.eligibility_status == "PASS")
        .distinct()
        .order_by(JobEvaluationRecord.role_family)
    ).all()
    open_rows = session.execute(
        select(JobEvaluationRecord.role_family, func.count(JobRecord.id))
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.is_active.is_(True), JobEvaluationRecord.eligibility_status == "PASS")
        .group_by(JobEvaluationRecord.role_family)
    ).all()
    open_by_family = {role: count for role, count in open_rows}
    company_open_rows = session.execute(
        select(JobRecord.company, func.count(JobRecord.id))
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.is_active.is_(True), JobEvaluationRecord.eligibility_status == "PASS")
        .group_by(JobRecord.company)
    ).all()
    for company, count in company_open_rows:
        companies[company]["open_qualified"] = count
    for role, counts in roles.items():
        keys = {row[0] for row in filtered if row[2] == role}
        counts["recorded_responses"] = len(keys & responded)
        counts["recorded_interviews"] = len(keys & (event_keys["interview"] | event_keys["interviewing"]))
        counts["open_qualified"] = open_by_family.get(role, 0)
    today = now.astimezone(zone).date()
    submitted_today = daily[today.isoformat()]
    qualified_today_query = (
        select(func.count(JobRecord.id))
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.first_seen_at >= datetime.combine(today, datetime.min.time(), zone).astimezone(timezone.utc),
               JobEvaluationRecord.eligibility_status == "PASS")
    )
    if family:
        qualified_today_query = qualified_today_query.where(JobEvaluationRecord.role_family == family)
    qualified_today = session.scalar(qualified_today_query) or 0
    email_review = session.scalar(
        select(func.count(GmailMessageRecord.id)).where(GmailMessageRecord.decision.in_(("review", "exact_preview")))
    ) or 0
    skills_query = (
        select(JobRecord.title, JobRecord.description)
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.first_seen_at >= now - timedelta(days=days), JobEvaluationRecord.eligibility_status == "PASS")
        .order_by(JobRecord.first_seen_at.desc())
        .limit(101)
    )
    if family:
        skills_query = skills_query.where(JobEvaluationRecord.role_family == family)
    skill_rows = session.execute(skills_query).all()
    skill_counts: Counter = Counter()
    for title, description in skill_rows[:100]:
        skill_counts.update(extract_skills(f"{title}\n{description or ''}"))
    verified_companies = session.scalar(select(func.count(func.distinct(CompanyPetitionReportRecord.ace_company))).where(CompanyPetitionReportRecord.entity_verified.is_(True))) or 0
    return {
        "as_of": now.isoformat(),
        "source": "ACE persisted applications, events and observed employer postings",
        "window_days": days,
        "family": family,
        "coverage": "recorded_events" if complete_coverage else "partial",
        "total_submitted": marks["applications_total"],
        "filtered_submitted": len(filtered),
        "with_posting": marks["applications_with_posting"],
        "without_posting": marks["applications_without_posting"],
        "current_pending": pending,
        "current_status": dict(status),
        "confirmed_rejections": status.get("rejected", 0),
        "historical_events": {kind: len(keys) for kind, keys in event_keys.items()},
        "meaningful_responses_recorded": len(responded),
        "recruiter_response_rate": {"numerator": len(mature & responded), "denominator": len(mature), "value": len(mature & responded) / len(mature) if mature and complete_coverage else None, "status": "recorded" if complete_coverage else "partial"},
        "interview_conversion": {"numerator": len(event_keys["interview"] | event_keys["interviewing"]), "denominator": len(filtered), "value": len(event_keys["interview"] | event_keys["interviewing"]) / len(filtered) if filtered and complete_coverage else None, "status": "recorded" if complete_coverage else "partial"},
        "median_days_to_first_response": {"value": median(response_days) if response_days else None, "sample_size": len(response_days), "status": "recorded" if response_days else "unavailable"},
        "undated": undated,
        "today": {"submitted": submitted_today, "qualified_observed": qualified_today, "email_review": email_review},
        "available_families": available_families,
        "daily": [{"date": (since + timedelta(days=i)).isoformat(), "submitted": daily[(since + timedelta(days=i)).isoformat()]} for i in range(days)],
        "cohorts": [{"month": month, "statuses": dict(counts), "sample_size": sum(counts.values())} for month, counts in sorted(cohorts.items(), reverse=True)],
        "roles": [{"family": role, **counts} for role, counts in sorted(roles.items(), key=lambda x: -x[1]["submitted"])],
        "companies": [{"name": company, **counts} for company, counts in sorted(companies.items(), key=lambda x: (-x[1]["submitted"], -x[1].get("open_qualified", 0)))[:20]],
        "observed_qualified_by_family": [{"family": role or "Unknown", "count": n} for role, n in source_rows],
        "observed_skill_demand": {"items": [{"skill": skill, "count": count} for skill, count in skill_counts.most_common(12)], "sample_size": min(len(skill_rows), 100), "status": "partial" if len(skill_rows) > 100 else "fresh_sample"},
        "verified_petition_companies": verified_companies,
        "metric_definitions": {
            "total_submitted": "Applied job marks plus external application records, regardless of current status.",
            "current_pending": "Submitted records without a confirmed accepted, rejected or withdrawn current status. No reply remains pending.",
            "meaningful_responses_recorded": "Distinct applications with a recorded recruiter, assessment, interview or offer event. Historical coverage begins with the event ledger.",
            "observed_qualified": "Unique ACE postings first seen in this period that passed the eligibility gate. This is not a national hiring rate.",
            "observed_skill_demand": "Skills explicitly named in the newest 100 qualifying ACE posting descriptions, or all such postings if fewer. Coverage is partial when more exist.",
        },
    }
