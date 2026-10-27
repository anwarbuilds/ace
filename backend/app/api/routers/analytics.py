"""Read-only Analytics projection. No mailbox access, status writes or guessed attribution.

Analytics replaced the Career Dashboard (removed 2026-10-26). This projection
has bounded submission-date filters, local calendar weeks, undo-aware outcomes,
the employers that rejected the owner and official petition series, without
changing any durable business logic.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Annotated
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.routers.inbox import _identities, _stale_query, PENDING
from backend.app.db.models import ApplicationEventRecord, CompanyPetitionReportRecord, GmailMessageRecord, JobEvaluationRecord, GmailConnectionRecord
from backend.app.inbox.reconcile import _MARKING_GRACE

router = APIRouter()
POSITIVE = {"recruiter_reply", "online_assessment", "screening", "interview", "interviewing", "offer", "accepted"}
STAGE_KIND = {"screening": "recruiter_reply", "interviewing": "interview", "offer": "offer", "accepted": "accepted", "rejected": "rejection"}
IN_PROGRESS = {"applied", "screening", "interviewing", "offer"}


def _latest_first(stamp: datetime | None) -> tuple[bool, float]:
    """Sort key: dated newest first, undated last."""
    return (stamp is None, -stamp.timestamp() if stamp else 0.0)


def aware(stamp: datetime) -> datetime:
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def analytics_read(session: Session, *, days: str = "all", family: str | None = None,
                   start: date | None = None, end: date | None = None, tz: str = "UTC",
                   company: str | None = None, now: datetime | None = None, records: bool = False,
                   status: str | None = None, evidence: str | None = None, eligible: bool = False,
                   timed: bool = False, offset: int = 0, limit: int = 50, q: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    explicit_dates = start is not None or end is not None
    include_undated = days == "all" and not explicit_dates
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Choose a valid display timezone.")
    identities = _identities(session)  # Same identities as Inbox and application marks.
    job_ids = [int(a.key.split(":")[1]) for a in identities if a.key.startswith("job:")]
    families = dict(session.execute(select(JobEvaluationRecord.job_id, JobEvaluationRecord.role_family).where(JobEvaluationRecord.job_id.in_(job_ids))).all()) if job_ids else {}
    role = {a.key: families.get(int(a.key.split(":")[1]), "Unknown") if a.key.startswith("job:") else "Unknown" for a in identities}
    today = now.astimezone(zone).date()
    dated = {a.key: aware(a.submitted_at).astimezone(zone).date() for a in identities if a.submitted_at}
    if start is None:
        start = min(today, min(dated.values(), default=today)) if days == "all" else today - timedelta(days=int(days) - 1)
    end = end or today
    if start > end or end > today or (end - start).days > 36600:
        raise HTTPException(422, "Choose a valid date range ending today or earlier, up to 100 years.")
    eligible_family = [a for a in identities if not family or role[a.key] == family]
    selected = [a for a in eligible_family if a.key in dated and start <= dated[a.key] <= end]
    # All-time keeps undated external history visible; it never invents a chart date.
    if include_undated:
        selected += [a for a in eligible_family if a.key not in dated]
    keys = {a.key for a in selected}
    # Restrict event reads to selected application keys, including corresponding undos.
    raw_events = session.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.application_key.in_(keys))).all() if keys else []
    undone = {e.undo_of_id for e in raw_events if e.undo_of_id}
    message_ids = {e.gmail_message_id for e in raw_events if e.gmail_message_id}
    messages = {m.id: m for m in session.scalars(select(GmailMessageRecord).where(GmailMessageRecord.id.in_(message_ids)))} if message_ids else {}
    # One message can substantiate only one identity. Exclude conflicts even
    # when the competing application falls outside the selected date range.
    # Inbox's own audit entries (key "email:<id>") are not applications; every
    # imported email has one, so counting them excluded every email outcome.
    message_targets = defaultdict(set)
    if message_ids:
        linked_events = session.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.gmail_message_id.in_(message_ids))).all()
        linked_ids = {e.id for e in linked_events}
        linked_undos = set(session.scalars(select(ApplicationEventRecord.undo_of_id).where(ApplicationEventRecord.undo_of_id.in_(linked_ids))))
        for linked in linked_events:
            if linked.id not in linked_undos and linked.kind != "undo" and linked.application_key.startswith(("job:", "external:")):
                message_targets[linked.gmail_message_id].add(linked.application_key)
    # First outcomes drive response timing; latest outcomes drive company
    # recency, evidence links and the current cohort partition.
    events: dict[str, dict[str, datetime | None]] = defaultdict(dict)
    latest_events: dict[str, dict[str, datetime | None]] = defaultdict(dict)
    excluded: Counter = Counter()
    excluded_by_key: dict[str, list[dict]] = defaultdict(list)
    pre_mark = 0

    def exclude(e, reason: str) -> None:
        excluded[reason] += 1
        if e.gmail_message_id:
            excluded_by_key[e.application_key].append({"message_id": e.gmail_message_id, "reason": reason})

    # The email behind each counted event, so a record can open it in Inbox.
    emails: dict[str, dict[str, int]] = defaultdict(dict)
    actors: dict[str, set[str]] = defaultdict(set)
    selected_by_key = {a.key: a for a in selected}
    for e in raw_events:
        if e.id in undone or e.kind == "undo":
            continue
        kind = e.kind
        message = messages.get(e.gmail_message_id)
        if kind == "manual_correction":
            kind = STAGE_KIND.get(e.new_status, "unknown")
            if message and message.classification == "online_assessment" and e.new_status == "screening":
                kind = "online_assessment"
        if kind not in POSITIVE | {"rejection"}:
            continue
        if e.actor not in {"owner", "verified_automation"}:
            exclude(e, "unconfirmed_actor")
            continue
        if e.gmail_message_id:
            if not message:
                exclude(e, "missing_email")
                continue
            if len(message_targets[e.gmail_message_id]) != 1:
                exclude(e, "conflicting_targets")
                continue
            if message.selected_application_key != e.application_key or message.decision not in {"manual", "automatic"}:
                exclude(e, "email_not_confirmed_for_application")
                continue
        app = selected_by_key[e.application_key]
        stamp = aware(e.occurred_at) if e.occurred_at else None
        if stamp and stamp > now:
            exclude(e, "future_timestamp")
            continue
        if stamp and app.submitted_at and stamp < aware(app.submitted_at):
            # Inbox accepts a quick response received just before the owner
            # marks Applied. Retain that confirmed email, never a negative lag.
            if not message or aware(app.submitted_at) - stamp > _MARKING_GRACE:
                exclude(e, "before_application_window")
                continue
            pre_mark += 1
        previous = events[e.application_key].get(kind)
        if kind not in events[e.application_key] or (stamp and (previous is None or stamp < previous)):
            events[e.application_key][kind] = stamp
        latest = latest_events[e.application_key].get(kind)
        if kind not in latest_events[e.application_key] or (stamp and (latest is None or stamp >= latest)):
            latest_events[e.application_key][kind] = stamp
            if e.gmail_message_id:
                emails[e.application_key][kind] = e.gmail_message_id
            else:
                emails[e.application_key].pop(kind, None)
        actors[e.application_key].add(e.actor)
    # Existing explicit owner stages remain useful even before the event ledger.
    # They are counted once per application and never given an invented timestamp.
    for a in selected:
        kind = STAGE_KIND.get(a.current_status)
        if a.current_status == "screening":
            # A recorded assessment already explains the screening stage; it
            # must not manufacture a separate recruiter-reply event.
            if POSITIVE.intersection(events[a.key]):
                continue
            kind = "screening"
        if kind and kind not in events[a.key]:
            events[a.key][kind] = None
            latest_events[a.key][kind] = None
            actors[a.key].add("recorded_status")
    positive = {key for key, kinds in events.items() if POSITIVE.intersection(kinds)}
    rejected = {key for key, kinds in events.items() if "rejection" in kinds}
    assessed = {key for key, kinds in events.items() if "online_assessment" in kinds}
    interviewed = {key for key, kinds in events.items() if {"interview", "interviewing"}.intersection(kinds)}
    mature = {a.key for a in selected if a.submitted_at and aware(a.submitted_at) <= now - timedelta(days=30)}
    # A reconsidered rejection must not override a later interview or offer.
    # Equal-time conflicts remain conservative; historical evidence keeps both.
    def polarity(a) -> str | None:
        kinds = events.get(a.key, {})
        if not kinds:
            return None
        dated_outcomes = [(stamp, kind == "rejection", kind) for kind, stamp in latest_events[a.key].items() if stamp]
        latest = max(dated_outcomes, default=None)
        stage = STAGE_KIND.get(a.current_status)
        status_kind = "screening" if a.current_status == "screening" and "screening" in kinds else stage
        # An undated current stage remains authoritative without inventing
        # when it happened or letting an older dated event erase it.
        if status_kind in kinds and latest_events[a.key].get(status_kind) is None:
            return "rejection" if stage == "rejection" else "positive"
        if stage and a.status_changed_at and (latest is None or aware(a.status_changed_at) > latest[0]):
            return "rejection" if stage == "rejection" else "positive"
        if latest:
            return "rejection" if latest[1] else "positive"
        return "rejection" if "rejection" in kinds else "positive"

    polarities = {a.key: polarity(a) for a in selected}
    confirmed_negative = {key for key in mature if polarities[key] == "rejection"}
    confirmed_positive = {key for key in mature if polarities[key] == "positive"}
    no_outcome = mature - positive - rejected
    withdrawn = {a.key for a in selected if a.current_status == "withdrawn"}
    pending = no_outcome - withdrawn
    unknown = no_outcome & withdrawn
    # A Gmail sync or a single event never proves exhaustive response coverage.
    # No coverage attestation exists in the current schema, so rates remain null.
    def group(apps: list) -> dict:
        group_keys = {a.key for a in apps}
        return {"submitted": len(apps), "eligible": len(group_keys & mature),
                "responses": len(group_keys & positive), "rejections": len(group_keys & rejected),
                "assessments": len(group_keys & assessed), "interviews": len(group_keys & interviewed), "rate": None}
    groups: dict[str, list] = defaultdict(list)
    employers: dict[str, list] = defaultdict(list)
    for a in selected:
        groups[role[a.key]].append(a)
        employers[a.company].append(a)
    company_rows = []
    for name, apps in sorted(employers.items(), key=lambda item: (-len(item[1]), item[0])):
        stamps = [(stamp, kind) for a in apps for kind, stamp in latest_events.get(a.key, {}).items() if stamp]
        latest = max(stamps, default=None)
        company_rows.append({"name": name, **group(apps), "latest": latest[1] if latest else "Not recorded", "latest_at": latest[0].isoformat() if latest else None})
    # Every employer with a recorded rejection in this selection, newest
    # dated rejection first. A status recorded without an email has no date;
    # it is never given one. Roles are the rejected applications' titles.
    rejected_companies = []
    for name, apps in employers.items():
        refused = sorted((a for a in apps if a.key in rejected),
                         key=lambda a: (*_latest_first(latest_events[a.key].get("rejection")), a.title.casefold()))
        if refused:
            stamps = [latest_events[a.key]["rejection"] for a in refused if latest_events[a.key].get("rejection")]
            rejected_companies.append({"name": name, "rejections": len(refused), "applications": len(apps),
                                       "latest": max(stamps, default=None), "dated": len(stamps),
                                       "roles": list(dict.fromkeys(a.title for a in refused)),
                                       "in_progress": sum(a.current_status in IN_PROGRESS and (a.key not in rejected or polarities[a.key] == "positive") for a in apps)})
    rejected_companies.sort(key=lambda row: (*_latest_first(row["latest"]), -row["rejections"], row["name"].casefold()))
    newest_rejection = max((row["latest"] for row in rejected_companies if row["latest"]), default=None)
    monday = today - timedelta(days=today.weekday())
    daily = Counter(dated[a.key].isoformat() for a in selected if a.key in dated)
    weekly = Counter(dated[a.key].isoformat() for a in eligible_family if a.key in dated and monday <= dated[a.key] <= today)
    # Cap chart points by calendar-month aggregation for long histories.
    granularity = "daily" if (end - start).days < 100 else "monthly"
    chart: Counter = Counter()
    cursor = start
    while cursor <= end:
        chart[cursor.isoformat() if granularity == "daily" else cursor.strftime("%Y-%m")] += daily[cursor.isoformat()]
        cursor += timedelta(days=1)
    timing = Counter()
    lags = []
    timed_keys = set()
    for a in selected:
        stamps = [stamp for stamp in events.get(a.key, {}).values() if stamp]
        if a.submitted_at and stamps and min(stamps) >= aware(a.submitted_at):
            lag = (min(stamps) - aware(a.submitted_at)).total_seconds() / 86400
            timed_keys.add(a.key)
            lags.append(lag)
            timing["0 to 7 days" if lag <= 7 else "8 to 14 days" if lag <= 14 else "15 to 30 days" if lag <= 30 else "30+ days"] += 1
    review_counts = dict(session.execute(select(GmailMessageRecord.decision, func.count()).group_by(GmailMessageRecord.decision)).all())
    stale = sum(session.scalar(select(func.count()).select_from(_stale_query(connection_id).subquery())) or 0
                for connection_id in session.scalars(select(GmailConnectionRecord.id)))
    ambiguous = sum(len(candidate_keys or []) > 1 for candidate_keys in session.scalars(
        select(GmailMessageRecord.candidate_keys).where(GmailMessageRecord.decision == "review")))
    reports = session.scalars(select(CompanyPetitionReportRecord).where(CompanyPetitionReportRecord.ace_company.in_(employers), CompanyPetitionReportRecord.entity_verified.is_(True))).all() if employers else []
    # Exact entity + metric + year reconciliation; newer revisions replace old
    # releases instead of adding duplicate totals. DOL stays a separate metric.
    latest_reports = {}
    for r in sorted(reports, key=lambda r: (aware(r.last_checked_at), r.id)):
        parsed = urlparse(r.source_uri)
        if parsed.scheme != "https" or parsed.hostname not in {"uscis.gov", "www.uscis.gov", "dol.gov", "www.dol.gov", "flag.dol.gov"}:
            continue
        if r.metric_definition == "USCIS I-129 petition decisions" and parsed.hostname not in {"uscis.gov", "www.uscis.gov"}:
            continue
        latest_reports[(r.ace_company, r.legal_entity, r.period, r.metric_definition)] = r
    reports = list(latest_reports.values())
    selected_company = company if company in employers else next((r.ace_company for r in reports), next(iter(employers), ""))
    report_items = []
    annual: dict[str, Counter] = defaultdict(Counter)
    incomplete_years = set()
    for r in reports:
        if r.ace_company != selected_company:
            continue
        official = r.metric_definition == "USCIS I-129 petition decisions"
        total = (r.petition_approvals or 0) + (r.petition_denials or 0)
        complete = official and r.petition_approvals is not None and r.petition_denials is not None and r.petition_approvals >= 0 and r.petition_denials >= 0
        report_items.append({"entity": r.legal_entity, "period": r.period, "source": r.source_name, "url": r.source_uri, "metric": r.metric_definition,
                             "version": r.report_version, "checked_at": aware(r.last_checked_at).isoformat(), "approvals": r.petition_approvals,
                             "denials": r.petition_denials, "rate": r.petition_approvals / total if complete and total else None})
        if official and r.period.startswith("FY ") and r.period[3:].isdigit():
            if complete:
                annual[r.period]["approvals"] += r.petition_approvals
                annual[r.period]["denials"] += r.petition_denials
            else:
                incomplete_years.add(r.period)
    for period in incomplete_years:
        annual.pop(period, None)
    result = {"as_of": now.isoformat(), "timezone": tz, "start": start.isoformat(), "end": end.isoformat(), "days": "custom" if explicit_dates else days, "family": family,
            "available_families": sorted(set(role.values())), "total_submitted": len(identities), "submitted": len(selected), "undated": sum(a.key not in dated for a in eligible_family),
            "week_total": sum(weekly.values()), "positive": len(positive), "assessments": len(assessed), "interviews": len(interviewed),
            "has_outcome_evidence": bool(positive or rejected), "statuses": dict(Counter(a.current_status for a in selected)),
            "daily": [{"date": day, "count": count} for day, count in sorted(chart.items())], "granularity": granularity,
            "week": [{"date": (monday + timedelta(days=i)).isoformat(), "count": weekly[(monday + timedelta(days=i)).isoformat()]} for i in range(7)],
            "cohort": {"eligible": len(mature), "positive": len(confirmed_positive), "rejected": len(confirmed_negative), "pending": len(pending), "unknown": len(unknown), "rate": None, "coverage": "No complete observation coverage is recorded. Pending applications may have unrecorded responses."},
            "timing": [{"label": label, "count": timing[label]} for label in ("0 to 7 days", "8 to 14 days", "15 to 30 days", "30+ days")],
            "median_days": median(lags) if lags else None, "timing_sample": len(lags),
            "evidence": {"positive": len(positive), "rejected": len(rejected), "manual": sum("owner" in value for value in actors.values()), "automatic": sum("verified_automation" in value for value in actors.values()),
                         "recorded_status": sum("recorded_status" in value for value in actors.values())},
            "review": {"needs_review": review_counts.get("review", 0), "exact_preview": review_counts.get("exact_preview", 0),
                       "deferred": review_counts.get("deferred", 0), "ambiguous": ambiguous},
            "inbox_audit": {"stored_messages": sum(review_counts.values()),
                            "recorded_messages": sum(review_counts.get(key, 0) for key in ("manual", "automatic")),
                            "pending_messages": sum(review_counts.get(key, 0) for key in PENDING),
                            "ignored_messages": review_counts.get("ignored", 0), "stale_messages": stale,
                            "pre_mark_email_outcomes": pre_mark, "excluded_events": dict(excluded),
                            "event_scope": "selected_applications"},
            "roles": [{"family": key, **group(apps)} for key, apps in sorted(groups.items(), key=lambda item: -len(item[1]))],
            "attribution": {"resume": "Not recorded", "channel": "Not recorded", "combinations": []},
            "companies": company_rows, "selected_company": selected_company,
            "rejected_companies": [{**{key: value for key, value in row.items() if key != "latest"},
                                    "latest_at": row["latest"].isoformat() if row["latest"] else None} for row in rejected_companies],
            "rejection_summary": {"applications": sum(row["rejections"] for row in rejected_companies),
                                  "companies": len(rejected_companies),
                                  "dated": sum(row["dated"] for row in rejected_companies),
                                  "latest_at": newest_rejection.isoformat() if newest_rejection else None},
            "verified_companies": [{"name": name, **group(employers[name]), "reports": sum(r.ace_company == name for r in reports)} for name in employers if any(r.ace_company == name for r in reports)],
            "reports": sorted(report_items, key=lambda r: r["period"], reverse=True),
            "annual": [{"period": period, **counts, "rate": counts["approvals"] / sum(counts.values()) if sum(counts.values()) else None} for period, counts in sorted(annual.items())]}


    if records:
        from backend.app.api.marks import APPLICATION_STATUSES
        if status and status not in APPLICATION_STATUSES:
            raise HTTPException(422, "Choose a supported application status.")
        evidence_keys = {"positive": positive, "rejection": rejected, "online_assessment": assessed,
                         "interview": interviewed, "response": positive | rejected}
        if evidence and evidence not in evidence_keys:
            raise HTTPException(422, "Choose a supported outcome evidence type.")
        dated_responses = timed_keys
        # Every word must appear in the company, role, job ID or record key.
        words = (q or "").casefold().split()[:8]

        def found(a) -> bool:
            text = f"{a.company} {a.title} {a.requisition_id or ''} {a.key}".casefold()
            return all(word in text for word in words)

        matching = [a for a in selected if (not company or a.company == company)
                    and (not status or a.current_status == status)
                    and (not evidence or a.key in evidence_keys[evidence])
                    and (not eligible or a.key in mature) and (not timed or a.key in dated_responses)
                    and (not words or found(a))]
        matching.sort(key=lambda a: (aware(a.submitted_at) if a.submitted_at else datetime.min.replace(tzinfo=timezone.utc), a.key), reverse=True)
        if evidence == "rejection":
            # Rejected applications read newest rejection first; undated last.
            matching.sort(key=lambda a: _latest_first(latest_events[a.key].get("rejection")))
        result["record_total"] = len(matching)
        result["record_offset"] = offset
        result["record_limit"] = limit
        result["record_query"] = " ".join(words)
        result["records"] = [{"key": a.key, "company": a.company, "title": a.title, "requisition_id": a.requisition_id,
                               "family": role[a.key], "submitted_at": aware(a.submitted_at).isoformat() if a.submitted_at else None,
                               "status": a.current_status, "event_types": sorted(events.get(a.key, {})),
                               "evidence": [{"kind": kind, "at": stamp.isoformat() if stamp else None,
                                             "message_id": emails.get(a.key, {}).get(kind),
                                             **({"predates_mark": True} if stamp and a.submitted_at and stamp < aware(a.submitted_at) else {})}
                                            for kind, stamp in sorted(latest_events.get(a.key, {}).items())],
                               "excluded_evidence": excluded_by_key.get(a.key, [])[:25],
                               "href": f"/app/jobs/{a.key.split(':')[1]}" if a.key.startswith("job:") else None}
                              for a in matching[offset:offset + limit]]
        result["not_listed"] = {"applications": [], "emails": [], "application_total": 0, "email_total": 0}
        if words and not matching:
            other = [a for a in identities if found(a)]
            other.sort(key=lambda a: (aware(a.submitted_at) if a.submitted_at else datetime.min.replace(tzinfo=timezone.utc), a.key), reverse=True)
            mail_query = select(GmailMessageRecord)
            for word in words:
                pattern = "%" + re.sub(r"([\\%_])", r"\\\1", word) + "%"
                mail_query = mail_query.where(or_(*(column.ilike(pattern, escape="\\") for column in
                                                    (GmailMessageRecord.sender, GmailMessageRecord.subject, GmailMessageRecord.snippet))))
            email_total = session.scalar(select(func.count()).select_from(mail_query.subquery())) or 0
            related_mail = session.scalars(mail_query.order_by(GmailMessageRecord.received_at.desc(), GmailMessageRecord.id.desc()).limit(25))
            result["not_listed"] = {
                "applications": [{"key": a.key, "company": a.company, "title": a.title, "status": a.current_status,
                                  "submitted_at": aware(a.submitted_at).isoformat() if a.submitted_at else None,
                                  "outside_range": (not include_undated if a.key not in dated else not start <= dated[a.key] <= end),
                                  "href": f"/app/jobs/{a.key.split(':')[1]}" if a.key.startswith("job:") else "/app/applications"}
                                 for a in other[:25]],
                "emails": [{"id": m.id, "subject": m.subject, "decision": m.decision, "classification": m.classification,
                            "received_at": aware(m.received_at).isoformat()} for m in related_mail],
                "application_total": len(other), "email_total": email_total,
            }
    return result


@router.get("/api/analytics")
def analytics(days: str = Query("all", pattern="^(14|30|90|all|custom)$"), family: str | None = None,
              start: date | None = None, end: date | None = None, tz: str = "UTC", company: str | None = None,
              records: bool = False, status: str | None = None, evidence: str | None = None,
              eligible: bool = False, timed: bool = False, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
              q: Annotated[str | None, Query(max_length=100)] = None,
              session: Session = Depends(get_session)) -> dict:
    if days == "custom" and (start is None or end is None):
        raise HTTPException(422, "Choose both dates.")
    return analytics_read(session, days=days, family=family, start=start, end=end, tz=tz, company=company, records=records, status=status, evidence=evidence, eligible=eligible, timed=timed, offset=offset, limit=limit, q=q)
