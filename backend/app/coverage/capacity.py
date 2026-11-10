"""Can ace keep up? The capacity block on Coverage, Sources (OPS-05).

Three numbers, read from what the scheduler already records; nothing here
makes a request or writes anything:

- reads in the last full hour, from the quarter-hour windows the scheduler
  logs (``poll_sessions``), against the reads the boards ask for (one per
  planned interval);
- boards read on time: a last good read within one and a half planned
  intervals;
- how fast new jobs reach the owner: the typical time from the employer's
  posted time to ace first seeing the job, and the time nine in ten beat,
  over jobs first seen in the last day on boards ace was already reading
  and whose posted time is a real time of day (T4).

A posted time at exactly midnight UTC is a date without a time (Workday's
list, Oracle), so it says nothing about minutes and is left out, as is a
posted time after ace saw the job, or more than two days old (a posting
taken down and put up again keeps its first date).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
    PollSessionRecord,
    SourceState,
)
from backend.app.persistence.sessions import bucket_start

# A board's last good read within this many planned intervals is on time.
ON_TIME_INTERVALS = 1.5

# Reads at least this share of what the boards ask for: ace keeps up.
KEEPING_UP_SHARE = 0.9

# Fewer new jobs than this in a day say too little about speed.
MIN_JOBS_FOR_SPEED = 20

SPEED_WINDOW = timedelta(hours=24)

# A posted time older than this is a reposting's first date, not news.
OLDEST_POSTED = timedelta(days=2)

# A job posted this soon after ace first read its board may have been
# there before the first read.
FIRST_READ_GRACE = timedelta(hours=1)

# Clocks differ a little; a posted time just after ace saw the job is
# still the same moment.
CLOCK_SLACK = timedelta(minutes=5)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _is_date_only(value: datetime) -> bool:
    value = value.astimezone(timezone.utc)
    return (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0)


def _reads(session: Session, *, now: datetime) -> tuple[int, datetime, datetime]:
    """Reads in the last four complete quarter-hour windows."""

    end = bucket_start(now.astimezone(timezone.utc))
    start = end - timedelta(hours=1)
    total = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(PollSessionRecord.poll_attempts), 0)).where(
            PollSessionRecord.started_at >= start,
            PollSessionRecord.started_at < end,
        )
    )
    return int(total or 0), start, end


def _boards(session: Session, *, now: datetime) -> tuple[float, int, int]:
    """Reads the boards ask for an hour, boards counted, boards on time."""

    states = {
        (row.source, row.source_account): row
        for row in session.scalars(sa.select(SourceState))
    }

    asked = 0.0
    boards = 0
    on_time = 0

    for source_type, account, interval in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.poll_interval_seconds,
        ).where(
            JobSourceRecord.enabled.is_(True),
            JobSourceRecord.source_type.not_in(sorted(MULTI_EMPLOYER_SOURCES)),
        )
    ):
        interval = max(int(interval or 0), 1)
        boards += 1
        asked += 3600 / interval

        state = states.get((source_type, account))
        if state is None:
            continue

        last = max(
            value
            for value in (_aware(state.last_success_at), _aware(state.last_unchanged_at))
            if value is not None
        )

        if now - last <= timedelta(seconds=interval * ON_TIME_INTERVALS):
            on_time += 1

    return asked, boards, on_time


def _speed(session: Session, *, now: datetime) -> dict:
    """Minutes from posted to first seen, typical and nine in ten."""

    since = now - SPEED_WINDOW

    rows = session.execute(
        sa.select(
            JobRecord.posted_at,
            JobRecord.first_seen_at,
            SourceState.initialized_at,
        )
        .join(
            SourceState,
            sa.and_(
                SourceState.source == JobRecord.source,
                SourceState.source_account == JobRecord.source_account,
            ),
        )
        .where(
            JobRecord.first_seen_at >= since,
            JobRecord.posted_at.is_not(None),
            JobRecord.posted_at >= now - OLDEST_POSTED,
            JobRecord.source.not_in(sorted(MULTI_EMPLOYER_SOURCES)),
        )
    )

    minutes = []

    for posted, seen, first_read in rows:
        posted = _aware(posted)
        seen = _aware(seen)
        first_read = _aware(first_read)

        if _is_date_only(posted):
            continue
        if posted < first_read + FIRST_READ_GRACE:
            continue
        if posted > seen + CLOCK_SLACK:
            continue

        minutes.append(max((seen - posted).total_seconds() / 60, 0.0))

    if len(minutes) < MIN_JOBS_FOR_SPEED:
        return {"jobs": len(minutes), "typical_minutes": None, "nine_in_ten_minutes": None}

    return {
        "jobs": len(minutes),
        "typical_minutes": round(median(minutes), 1),
        "nine_in_ten_minutes": round(_percentile(minutes, 0.9), 1),
    }


def capacity_report(session: Session, *, now: datetime) -> dict:
    now = _aware(now)

    reads, start, end = _reads(session, now=now)
    asked, boards, on_time = _boards(session, now=now)
    speed = _speed(session, now=now)

    keeping_up = asked > 0 and reads >= asked * KEEPING_UP_SHARE

    return {
        "reads_last_hour": reads,
        "reads_window_start": start.isoformat(),
        "reads_window_end": end.isoformat(),
        "reads_asked_per_hour": round(asked),
        "boards": boards,
        "boards_on_time": on_time,
        "new_jobs": speed,
        "keeping_up": keeping_up,
        "status_label": "ace is keeping up." if keeping_up else "ace is behind: some boards are read later than planned.",
    }


__all__ = ["capacity_report"]
