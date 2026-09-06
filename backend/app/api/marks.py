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


# Where an application stands. Ordered as it progresses, so the
# interface can show forward motion rather than a flat set of labels.
APPLICATION_STATUSES = (
    "applied",
    "screening",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "ghosted",
)


# Statuses that mean the loop is closed. A posting in one of these is
# finished business, and the interface can stop asking for attention.
CLOSED_STATUSES = frozenset(
    {
        "rejected",
        "withdrawn",
        "ghosted",
        "accepted",
    }
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
    applied_at: datetime | None = None,
    application_status: str | None = None,
    status_note: str | None = None,
    now: datetime | None = None,
) -> JobMarkRecord:
    """Create or update one job's mark.

    Only the fields passed are changed, so toggling "saved" never
    silently clears a review state set earlier.

    ``clear_review`` is separate from ``review_state=None`` because None
    is also the "leave it alone" signal, and the two must not collide.

    ``applied_at`` is separate from ``now`` because an imported
    application happened on its own date, while the row was written
    today. Collapsing the two would make every imported application
    look as though it happened at import time.
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

    if (
        application_status is not None
        and application_status
        not in APPLICATION_STATUSES
    ):
        raise ValueError(
            "unknown application status: "
            f"{application_status!r}"
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
        record.applied_at = (
            applied_at
            if applied_at is not None
            else stamp
        )

        # Applying is itself a status. Without this a job could be
        # marked applied yet show no state at all.
        if (
            record.application_status
            is None
            and application_status is None
        ):
            record.application_status = (
                "applied"
            )

            record.status_changed_at = (
                record.applied_at
            )

    elif applied is False:
        record.applied_at = None

        record.application_status = None

        record.status_changed_at = None

        record.status_note = None

    if application_status is not None:
        moved = (
            record.application_status
            != application_status
        )

        record.application_status = (
            application_status
        )

        if moved:
            record.status_changed_at = (
                stamp
            )

        # A status implies an application was sent. Recording one
        # without a date would leave "rejected" hanging on a posting
        # ACE believes was never applied to.
        if record.applied_at is None:
            record.applied_at = (
                applied_at
                if applied_at is not None
                else stamp
            )

    if status_note is not None:
        record.status_note = (
            status_note.strip()
            or None
        )

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
            JobMarkRecord
            .application_status,
        )
    ).all()

    saved = 0

    archived = 0

    applied = 0

    open_applications = 0

    by_status: dict[str, int] = {}

    for (
        is_saved,
        review_state,
        applied_at,
        status,
    ) in rows:
        if is_saved:
            saved += 1

        if review_state in REVIEW_STATES:
            archived += 1

        if applied_at is not None:
            applied += 1

        if status:
            by_status[status] = (
                by_status.get(
                    status,
                    0,
                )
                + 1
            )

            if (
                status
                not in CLOSED_STATUSES
            ):
                open_applications += 1

    return {
        "saved": saved,
        "archived": archived,
        "applied": applied,
        "open_applications": (
            open_applications
        ),
        "by_status": by_status,
    }
