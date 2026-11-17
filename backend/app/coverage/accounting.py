"""Honest counting: every board and every company in exactly one group (REC-05).

A count is only honest when its parts add up to the whole it claims. Each board
ACE knows sits in one group, checked in this order so none can count twice:

1. switched off (ACE stopped reading it on purpose),
2. turned ace away (its site's robots rules refuse the paths ACE reads),
3. not read yet (added, no read finished),
4. not read lately (no good read in two days),
5. working.

There is no "working, empty" group: ACE refuses an empty answer as a read
(it could otherwise close every open job on the board), so a board that
answers with nothing has no good read and lands in "not read lately".

Companies are the lead ledger's own states, one per company. Jobs are counted
on their own. A company, a board and a job are never added together. Public
lists ACE reads (Simplify, RippleMatch) are many employers' feeds, not boards,
so they are named apart. Nothing here makes a request.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
from backend.app.coverage.host_policy import read_targets, refused_hosts
from backend.app.coverage.leads import (
    AGENCY,
    CHECKING,
    DORMANT,
    NOREADER,
    POLLING,
    REFUSED,
    STATE_LABELS,
    STATE_MEANINGS,
    WAITING,
)
from backend.app.db.models import EmployerLead, JobEvaluationRecord, JobRecord, JobSourceRecord, SourceState
from backend.app.discovery.feed_links import board_key


STALE_AFTER = timedelta(days=2)

OFF = "off"
REFUSED_BOARD = "refused"
UNREAD = "unread"
STALE = "stale"
WORKING = "working"

BOARD_GROUPS = (
    (WORKING, "Working", "Read fine in the last two days."),
    (
        STALE,
        "Not read lately",
        "Switched on, but no good read in two days. A board that answers with no jobs counts here, "
        "because ace never trusts an empty answer.",
    ),
    (UNREAD, "Not read yet", "Added, and its first read has not finished."),
    (
        REFUSED_BOARD,
        "Turned ace away",
        "Its site's robots rules ask readers to stay off the pages ace reads. Boards read before keep being "
        "read until you decide.",
    ),
    (OFF, "Switched off", "ace stopped reading it on purpose: a duplicate, an agency, a dead board or your Undo."),
)

COMPANY_ORDER = (POLLING, WAITING, DORMANT, CHECKING, NOREADER, REFUSED, AGENCY)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def board_group(*, enabled: bool, refused: bool, last_success_at: datetime | None, has_state: bool,
                now: datetime) -> str:
    """The one group a board belongs to, in the order the module names."""

    if not enabled:
        return OFF
    if refused:
        return REFUSED_BOARD
    if not has_state:
        return UNREAD
    last = _aware(last_success_at)
    if last is None or now - last > STALE_AFTER:
        return STALE
    return WORKING


def counting_report(session: Session, *, now: datetime) -> dict:
    states = {board_key(row.source, row.source_account): row for row in session.scalars(sa.select(SourceState))}
    refused = refused_hosts(session)

    groups = dict.fromkeys((key for key, _, _ in BOARD_GROUPS), 0)
    feeds = 0
    for source_type, account, host, enabled in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.source_host,
            JobSourceRecord.enabled,
        )
    ):
        if source_type in MULTI_EMPLOYER_SOURCES:
            feeds += bool(enabled)
            continue
        state = states.get(board_key(source_type, account))
        hosts = {target.host for target in read_targets(source_type, account, host)} if enabled else set()
        groups[
            board_group(
                enabled=bool(enabled),
                refused=bool(hosts & refused),
                last_success_at=state.last_success_at if state else None,
                has_state=state is not None,
                now=now,
            )
        ] += 1

    lead_counts = dict(
        session.execute(sa.select(EmployerLead.state, sa.func.count()).group_by(EmployerLead.state)).all()
    )
    companies = [
        {"key": state, "label": STATE_LABELS[state], "meaning": STATE_MEANINGS[state], "count": int(lead_counts.get(state, 0))}
        for state in COMPANY_ORDER
    ]

    open_jobs = session.scalar(
        sa.select(sa.func.count()).select_from(JobRecord).where(JobRecord.is_active.is_(True))
    ) or 0
    passing = session.scalar(
        sa.select(sa.func.count())
        .select_from(JobRecord)
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .where(JobRecord.is_active.is_(True), JobEvaluationRecord.eligibility_status == "PASS")
    ) or 0

    boards = [
        {"key": key, "label": label, "meaning": meaning, "count": groups[key]}
        for key, label, meaning in BOARD_GROUPS
    ]
    return {
        "counted_at": now.isoformat(),
        "boards": {"total": sum(groups.values()), "groups": boards},
        "companies": {"total": sum(item["count"] for item in companies), "groups": companies},
        "jobs": {"open": int(open_jobs), "passing": int(passing)},
        "feeds": feeds,
    }
