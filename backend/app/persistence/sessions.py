"""Discovery-run recording for ACE.

A person opening the web application wants to see "what arrived since I
last looked", grouped so it is scannable. A scheduler cycle is the wrong
unit for that: measured over 25 minutes, 38 of roughly 65 cycles polled
a single source, so cycle-level grouping would produce dozens of runs
holding one job each.

A session is therefore a *discovery run*. It opens when a cycle finds
new jobs and extends while further discoveries arrive close behind it,
which reproduces what someone means by "this morning's pull" without
inventing a fixed schedule the scheduler does not actually have.

Cycles that find nothing create no session, so the list stays
meaningful.

Claiming rather than threading
------------------------------

Jobs are attached to a session after the cycle, by claiming those first
seen inside its window. The alternative -- passing a session id down
through the scheduler, poll service, workflow, snapshot service and
repository -- would thread a presentation concern through five layers of
domain code to record something none of them care about.

This is safe because the scheduler is the only writer of new jobs, and
cycles do not overlap.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import (
    func,
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    PollSessionRecord,
)


# Discoveries arriving within this gap belong to the same run. Long
# enough to absorb a staggered sweep across 128 sources, short enough
# that a morning pull and an afternoon one stay separate.
SESSION_MERGE_WINDOW = timedelta(
    minutes=20
)


def _as_utc(
    value: datetime,
) -> datetime:
    """Normalize a stored timestamp to aware UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def unclaimed_job_ids(
    session: Session,
    *,
    since: datetime,
) -> list[int]:
    """Return jobs first seen since ``since`` that no run owns yet."""

    return list(
        session.scalars(
            select(
                JobRecord.id
            ).where(
                JobRecord.first_seen_session_id
                .is_(None),
                JobRecord.first_seen_at
                >= since,
            )
        ).all()
    )


def _open_session(
    session: Session,
    *,
    now: datetime,
    merge_window: timedelta,
) -> PollSessionRecord:
    """Return the run to extend, or start a new one."""

    recent = session.scalars(
        select(
            PollSessionRecord
        )
        .order_by(
            PollSessionRecord
            .last_activity_at.desc()
        )
        .limit(1)
    ).first()

    if recent is not None:
        last_activity = _as_utc(
            recent.last_activity_at
        )

        if (
            now - last_activity
            <= merge_window
        ):
            return recent

    record = PollSessionRecord(
        started_at=now,
        last_activity_at=now,
        jobs_discovered=0,
        qualifying_discovered=0,
    )

    session.add(
        record
    )

    session.flush()

    return record


def record_discoveries(
    session: Session,
    *,
    since: datetime,
    now: datetime | None = None,
    merge_window: timedelta = (
        SESSION_MERGE_WINDOW
    ),
) -> PollSessionRecord | None:
    """Attach jobs discovered since ``since`` to a discovery run.

    Returns:
        The run the jobs were attached to, or None when the cycle
        discovered nothing. A run is never created empty.
    """

    reference = (
        _as_utc(
            now
        )
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    job_ids = unclaimed_job_ids(
        session,
        since=since,
    )

    if not job_ids:
        return None

    run = _open_session(
        session,
        now=reference,
        merge_window=merge_window,
    )

    session.execute(
        update(
            JobRecord
        )
        .where(
            JobRecord.id.in_(
                job_ids
            )
        )
        .values(
            first_seen_session_id=run.id
        )
    )

    qualifying = session.scalar(
        select(
            func.count()
        )
        .select_from(
            JobEvaluationRecord
        )
        .where(
            JobEvaluationRecord.job_id.in_(
                job_ids
            ),
            JobEvaluationRecord
            .eligibility_status
            == "PASS",
        )
    )

    run.jobs_discovered = (
        run.jobs_discovered
        + len(job_ids)
    )

    run.qualifying_discovered = (
        run.qualifying_discovered
        + int(
            qualifying or 0
        )
    )

    run.last_activity_at = reference

    session.flush()

    return run
