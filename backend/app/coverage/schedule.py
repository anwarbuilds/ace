"""Is reading on schedule? Each hiring site's boards against their plan (FRS-02).

Every board has a planned gap between reads. For the boards that are working
(a good read in the last two days, the Scoreboard's "Working" group), this
says how long ago each was last read, per hiring site: typical, 19 in 20 and
99 in 100, and how many are late (more than one and a half planned gaps, the
rule the "Can ace keep up?" box uses). Above it, how many boards are due right
now and how long the longest has waited.

It is a picture of now, taken from what the scheduler already records (each
board's last read, a 304 "unchanged" answer included). Nothing here makes a
request or changes a board. Boards not read in two days are counted on the
Scoreboard as "Not read lately", not here, so one dead board cannot hide in a
site's typical time.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.accounting import STALE_AFTER
from backend.app.coverage.capacity import ON_TIME_INTERVALS, _percentile
from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
from backend.app.coverage.sources_view import site_label
from backend.app.db.models import JobSourceRecord, SourceState
from backend.app.discovery.feed_links import board_key


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def plan_label(seconds: int) -> str:
    if seconds <= 900:
        return f"Every {max(1, round(seconds / 60))} min"
    if seconds < 3600:
        return f"Every {round(seconds / 60)} min"
    if seconds == 3600:
        return "Hourly"
    if seconds < 86400:
        return f"Every {round(seconds / 3600)} h"
    return "Daily"


def schedule_report(session: Session, *, now: datetime) -> dict:
    states = {board_key(row.source, row.source_account): row for row in session.scalars(sa.select(SourceState))}

    ages: dict[str, list[float]] = defaultdict(list)
    plans: dict[str, Counter] = defaultdict(Counter)
    late: Counter = Counter()
    due = 0
    longest_wait = 0.0
    working = 0

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
        state = states.get(board_key(source_type, account))
        if state is None:
            continue
        reads = [value for value in (_aware(state.last_success_at), _aware(state.last_unchanged_at)) if value]
        if not reads:
            continue
        age = (now - max(reads)).total_seconds()
        if age > STALE_AFTER.total_seconds():
            continue
        working += 1
        interval = max(int(interval or 0), 60)
        site = site_label(source_type)
        ages[site].append(max(age, 0.0))
        plans[site][interval] += 1
        if age > interval * ON_TIME_INTERVALS:
            late[site] += 1
        if age > interval:
            due += 1
            longest_wait = max(longest_wait, age - interval)

    sites = []
    for site, values in ages.items():
        common = [seconds for seconds, _ in plans[site].most_common()]
        sites.append(
            {
                "site": site,
                "boards": len(values),
                "plan": plan_label(min(common)) if len(common) == 1 else f"{plan_label(min(common))} to {plan_label(max(common)).lower()}",
                "typical_minutes": round(_percentile(values, 0.5) / 60, 1),
                "p95_minutes": round(_percentile(values, 0.95) / 60, 1),
                "p99_minutes": round(_percentile(values, 0.99) / 60, 1),
                "late": late[site],
            }
        )
    sites.sort(key=lambda row: (-row["boards"], row["site"]))
    return {
        "measured_at": now.isoformat(),
        "working_boards": working,
        "due_now": due,
        "longest_wait_minutes": round(longest_wait / 60, 1),
        "late": sum(late.values()),
        "late_after": ON_TIME_INTERVALS,
        "sites": sites,
    }


__all__ = ["plan_label", "schedule_report"]
