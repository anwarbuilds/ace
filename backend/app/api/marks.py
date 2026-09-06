"""Durable saved, reviewed, dismissed and applied marks.

These are the one kind of job data ACE cannot recompute. Evaluations and
scores are derived and can be rebuilt from the corpus; a mark is a
judgement a person made by hand. That makes it authoritative, and it is
why re-scoring must never touch this table.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import JobMarkRecord


REVIEW_STATES = (
    "reviewed",
    "dismissed",
)


def get_mark(
    session: Session,
    *,
    job_id: int,
) -> JobMarkRecord | None:
    """Return the stored mark for one job, if any."""

    return session.get(
        JobMarkRecord,
        job_id,
    )


def set_mark(
    session: Session,
    *,
    job_id: int,
    saved: bool | None = None,
    review_state: str | None = None,
    clear_review: bool = False,
    applied: bool | None = None,
    now: datetime | None = None,
) -> JobMarkRecord:
    """Create or update one job's mark.

    Only the fields passed are changed, so toggling "saved" never
    silently clears a review state set earlier.

    ``clear_review`` is separate from ``review_state=None`` because None
    is also the "leave it alone" signal, and the two must not collide.
    """

    if (
        review_state is not None
        and review_state
        not in REVIEW_STATES
    ):
        raise ValueError(
            "unknown review state: "
            f"{review_state!r}"
        )

    stamp = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    record = session.get(
        JobMarkRecord,
        job_id,
    )

    if record is None:
        record = JobMarkRecord(
            job_id=job_id,
            is_saved=False,
        )

        session.add(
            record
        )

    if saved is not None:
        record.is_saved = saved

    if clear_review:
        record.review_state = None
    elif review_state is not None:
        record.review_state = (
            review_state
        )

    if applied is True:
        record.applied_at = stamp
    elif applied is False:
        record.applied_at = None

    record.updated_at = stamp

    session.flush()

    return record


def mark_counts(
    session: Session,
) -> dict:
    """Return how many jobs carry each mark.

    Counted over every stored job rather than the current page, which is
    the whole point of moving these out of the browser.
    """

    rows = session.execute(
        select(
            JobMarkRecord.is_saved,
            JobMarkRecord.review_state,
            JobMarkRecord.applied_at,
        )
    ).all()

    saved = 0

    archived = 0

    applied = 0

    for (
        is_saved,
        review_state,
        applied_at,
    ) in rows:
        if is_saved:
            saved += 1

        if review_state in REVIEW_STATES:
            archived += 1

        if applied_at is not None:
            applied += 1

    return {
        "saved": saved,
        "archived": archived,
        "applied": applied,
    }
