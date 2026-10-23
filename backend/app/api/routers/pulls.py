"""The Pulls page in one request: is ace looking, what did it find, and
what did each fifteen minute window check.

Sources are polled continuously, each on its own interval. A window is
how the record is read, not when anything runs: every quarter hour in
which the scheduler finished an attempt has one row in poll_sessions.

What each number means, so none is passed off as another:

- sources_enabled: boards configured and switched on. Not a check.
- sources_polled: enabled boards with a source state, matching the legacy
  Sources polling figure. It is not a 24-hour freshness count.
- sources_succeeded: distinct boards read successfully in the window,
  each once however often it was read (poll_sessions.boards_checked).
- sources_attempted, poll_attempts, failed_checks: recorded from
  migration 0040 on; null before it, and reported as not recorded.
- postings_observed: postings held by the boards read successfully, each
  board at its latest read. Most were seen before; it is not "new".
- new_postings: identities first seen in the window.
- new_qualifying: of those, the ones that passed the gate and were
  opened recently, counted when they arrived. A later close does not
  lower it; qualifying_open_now says how many are still open.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.queries import (
    QUALIFYING_STATUSES,
    _as_utc,
    last_poll_completed_at,
)
from backend.app.config import get_settings
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    PollSessionRecord,
    SourceState,
)
from backend.app.persistence.openings import OLD_OPENING_DAYS, opened_within
from backend.app.persistence.sessions import SESSION_BUCKET


router = APIRouter()

# Most boards are read every five minutes, so a quarter hour with no
# successful read anywhere is late, and three quarters is stopped. The
# second matches the stale threshold in /api/system.
DELAYED_AFTER = timedelta(minutes=15)
STALLED_AFTER = timedelta(minutes=45)

SUMMARY_SPAN = timedelta(hours=24)

State = Literal["live", "delayed", "stalled", "unknown"]
Outcome = Literal["opportunities", "new_postings", "quiet"]
Filter = Literal["all", "opportunities", "quiet"]


class PullStatus(BaseModel):
    state: State
    last_success_at: str | None
    age_seconds: int | None
    delayed_after_seconds: int
    stalled_after_seconds: int
    sources_enabled: int
    sources_polled: int


class PullSummary(BaseModel):
    """The last 24 hours, ending now."""

    window_start: str
    window_end: str
    new_postings: int
    new_qualifying: int
    # Distinct enabled boards whose latest successful read falls in the
    # span, which is every board read successfully in it.
    sources_succeeded: int
    sources_enabled: int
    windows: int
    windows_with_failures: int | None


class PullBucket(BaseModel):
    id: int
    start: str
    end: str
    last_activity_at: str | None
    outcome: Outcome
    new_postings: int
    new_qualifying: int
    qualifying_open_now: int
    sources_succeeded: int
    postings_observed: int
    sources_attempted: int | None
    poll_attempts: int | None
    failed_checks: int | None
    telemetry: Literal["full", "partial"]
    alert_status: str | None


class PullDay(BaseModel):
    date: str
    new_postings: int
    new_qualifying: int
    counts: dict[str, int]


class PullsResponse(BaseModel):
    timezone: str
    today: str
    date: str
    prev_date: str | None
    next_date: str | None
    filter: Filter
    status: PullStatus
    summary: PullSummary
    day: PullDay
    buckets: list[PullBucket]


def _iso(moment: datetime | None) -> str | None:
    moment = _as_utc(moment)
    return None if moment is None else moment.isoformat()


def pull_state(last_success: datetime | None, now: datetime) -> State:
    """Live, delayed or stalled, from when a board last answered.

    Never from whether this request was served: the website can be up
    while the scheduler is not.
    """

    if last_success is None:
        return "unknown"
    age = now - last_success
    if age <= DELAYED_AFTER:
        return "live"
    if age <= STALLED_AFTER:
        return "delayed"
    return "stalled"


def bucket_outcome(new_postings: int, new_qualifying: int) -> Outcome:
    if new_qualifying > 0:
        return "opportunities"
    if new_postings > 0:
        return "new_postings"
    return "quiet"


def day_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The instants a local calendar day starts and ends, in UTC.

    Through the zone, so a day is 23 or 25 hours across a clock change.
    """

    start = datetime.combine(day, time(0), tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _zone(name: str | None) -> ZoneInfo:
    fallback = get_settings().display_timezone
    for candidate in (name, fallback, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def _serialize(row: PollSessionRecord, open_now: int) -> PullBucket:
    start = _as_utc(row.started_at)
    recorded = row.sources_attempted is not None
    return PullBucket(
        id=row.id,
        start=start.isoformat(),
        end=(start + SESSION_BUCKET).isoformat(),
        last_activity_at=_iso(row.last_activity_at),
        outcome=bucket_outcome(row.jobs_discovered or 0, row.qualifying_discovered or 0),
        new_postings=row.jobs_discovered or 0,
        new_qualifying=row.qualifying_discovered or 0,
        qualifying_open_now=open_now,
        sources_succeeded=row.boards_checked or 0,
        postings_observed=row.postings_checked or 0,
        sources_attempted=row.sources_attempted,
        poll_attempts=row.poll_attempts,
        failed_checks=row.failed_checks,
        telemetry="full" if recorded else "partial",
        alert_status=row.alert_status,
    )


def build_pulls(
    session: Session,
    *,
    zone: ZoneInfo,
    day: date | None = None,
    filter: Filter = "all",
    now: datetime | None = None,
) -> PullsResponse:
    now = _as_utc(now) or datetime.now(timezone.utc)
    today = now.astimezone(zone).date()
    day = min(day or today, today)
    start, end = day_bounds(day, zone)

    enabled = int(
        session.scalar(
            select(func.count()).select_from(JobSourceRecord).where(JobSourceRecord.enabled.is_(True))
        )
        or 0
    )
    polled = int(
        session.scalar(
            select(func.count())
            .select_from(JobSourceRecord)
            .join(
                SourceState,
                (JobSourceRecord.source_type == SourceState.source)
                & (JobSourceRecord.source_account == SourceState.source_account),
            )
            .where(JobSourceRecord.enabled.is_(True))
        )
        or 0
    )

    last_success = last_poll_completed_at(session)

    status = PullStatus(
        state=pull_state(last_success, now),
        last_success_at=_iso(last_success),
        age_seconds=None if last_success is None else max(0, int((now - last_success).total_seconds())),
        delayed_after_seconds=int(DELAYED_AFTER.total_seconds()),
        stalled_after_seconds=int(STALLED_AFTER.total_seconds()),
        sources_enabled=enabled,
        sources_polled=polled,
    )

    # The last 24 hours. Windows are summed for arrivals (each identity
    # is first seen in exactly one window); boards are counted from
    # source state, because summing per window distinct counts would
    # count a board once per window it was read in.
    span_start = now - SUMMARY_SPAN
    span = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(PollSessionRecord.jobs_discovered), 0),
            func.coalesce(func.sum(PollSessionRecord.qualifying_discovered), 0),
            func.count(PollSessionRecord.failed_checks),
            func.count().filter(PollSessionRecord.failed_checks > 0),
        ).where(PollSessionRecord.last_activity_at >= span_start)
    ).one()

    succeeded = int(
        session.scalar(
            select(func.count())
            .select_from(SourceState)
            .join(
                JobSourceRecord,
                (JobSourceRecord.source_type == SourceState.source)
                & (JobSourceRecord.source_account == SourceState.source_account),
            )
            .where(
                JobSourceRecord.enabled.is_(True),
                SourceState.last_success_at >= span_start,
            )
        )
        or 0
    )

    summary = PullSummary(
        window_start=span_start.isoformat(),
        window_end=now.isoformat(),
        new_postings=int(span[1]),
        new_qualifying=int(span[2]),
        sources_succeeded=succeeded,
        sources_enabled=enabled,
        windows=int(span[0]),
        # Only over windows that recorded failures at all.
        windows_with_failures=int(span[4]) if span[3] else None,
    )

    rows = list(
        session.scalars(
            select(PollSessionRecord)
            .where(PollSessionRecord.started_at >= start, PollSessionRecord.started_at < end)
            .order_by(PollSessionRecord.started_at.desc(), PollSessionRecord.id.desc())
        ).all()
    )

    open_now: dict[int, int] = {}
    if rows:
        open_now = dict(
            session.execute(
                select(JobRecord.first_seen_session_id, func.count())
                .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
                .where(
                    JobRecord.first_seen_session_id.in_([r.id for r in rows]),
                    JobRecord.is_active.is_(True),
                    JobEvaluationRecord.eligibility_status.in_(QUALIFYING_STATUSES),
                    opened_within(OLD_OPENING_DAYS, now=now),
                )
                .group_by(JobRecord.first_seen_session_id)
            ).all()
        )

    buckets = [_serialize(r, int(open_now.get(r.id, 0))) for r in rows]

    counts = {
        "all": len(buckets),
        "opportunities": sum(1 for b in buckets if b.new_qualifying > 0),
        "quiet": sum(1 for b in buckets if b.new_qualifying == 0),
    }

    shown = [
        b
        for b in buckets
        if filter == "all"
        or (filter == "opportunities" and b.new_qualifying > 0)
        or (filter == "quiet" and b.new_qualifying == 0)
    ]

    earliest = _as_utc(session.scalar(select(func.min(PollSessionRecord.started_at))))
    prev_date = None
    if earliest is not None and earliest < start:
        # The nearest earlier day with any activity, so paging back
        # never lands on an empty day in a gap.
        before = _as_utc(
            session.scalar(select(func.max(PollSessionRecord.started_at)).where(PollSessionRecord.started_at < start))
        )
        if before is not None:
            prev_date = before.astimezone(zone).date().isoformat()

    next_date = None
    if day < today:
        after = _as_utc(
            session.scalar(select(func.min(PollSessionRecord.started_at)).where(PollSessionRecord.started_at >= end))
        )
        next_date = (after.astimezone(zone).date() if after is not None else today).isoformat()

    return PullsResponse(
        timezone=zone.key,
        today=today.isoformat(),
        date=day.isoformat(),
        prev_date=prev_date,
        next_date=next_date,
        filter=filter,
        status=status,
        summary=summary,
        day=PullDay(
            date=day.isoformat(),
            new_postings=sum(b.new_postings for b in buckets),
            new_qualifying=sum(b.new_qualifying for b in buckets),
            counts=counts,
        ),
        buckets=shown,
    )


@router.get("/api/pulls", response_model=PullsResponse)
def get_pulls(
    day: date | None = Query(default=None, alias="date", description="Local calendar day, YYYY-MM-DD."),
    filter: Filter = Query(default="all"),
    tz: str | None = Query(default=None, max_length=64, description="IANA time zone for day boundaries."),
    session: Session = Depends(get_session),
) -> PullsResponse:
    if tz is not None:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(status_code=422, detail={"reason": "bad_timezone", "message": "Unknown time zone."})
    return build_pulls(session, zone=_zone(tz), day=day, filter=filter)
