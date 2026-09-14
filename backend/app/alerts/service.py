"""One email per pull, once the pull is finished.

ACE deleted its entire email subsystem on 2026-09-06 -- outbox,
digests, SMTP, delivery worker, roughly 4,000 lines -- because the web
application was the only surface being watched. This is not that system
returning. The reason changed: alerts exist now so an application can be
started from a phone, away from the laptop, which a web page you have to
be sitting in front of cannot do.

So it stays deliberately small. No outbox, no delivery worker, no retry
schedule. One HTTPS call when a pull finishes, and a timestamp saying it
happened.

Why a pull is the unit
----------------------

A pull is a fifteen-minute bucket in ``poll_sessions``: every quarter
hour with any activity is exactly one row. That is already how the
interface groups arrivals, and it is what a person means by "this
morning's pull".

Alerting per job would send twenty emails on an ordinary day and, on the
two days new sources were registered, 140 and 185. Alerting per
scheduler cycle would be worse: a cycle runs every few seconds.

A bucket is only alerted once it has closed, because a bucket still
being written to is a pull still arriving, and half a pull is not worth
an email.
"""

from __future__ import annotations

import logging
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    PollSessionRecord,
)
from backend.app.mail.sender import send as send_mail
from backend.app.persistence.sessions import (
    SESSION_BUCKET,
    _as_utc,
)


LOGGER = logging.getLogger(
    "ace.alerts",
)


# Listed in full up to this many; beyond it the email says how many
# more rather than running to several screens on a phone. The two
# source-expansion days produced 140 and 185 qualifying jobs in a day,
# and a single pull on such a day can hold dozens.
MAX_LISTED = 25


# A pull older than this is not worth an email. Protects against a
# scheduler that was stopped for a week coming back and mailing every
# quarter hour it missed.
MAX_AGE = timedelta(
    hours=12,
)


def pending_pulls(
    session: Session,
    *,
    now: datetime | None = None,
) -> list[PollSessionRecord]:
    """Closed pulls that found something and have not been alerted.

    Ordered oldest first, so a backlog arrives in the order it
    happened rather than newest-first.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    rows = session.scalars(
        select(
            PollSessionRecord,
        ).where(
            PollSessionRecord.notified_at.is_(
                None,
            ),
            PollSessionRecord.qualifying_discovered > 0,
        ).order_by(
            PollSessionRecord.started_at,
        )
    ).all()

    ready = []

    for row in rows:
        closed_at = _as_utc(
            row.started_at,
        ) + SESSION_BUCKET

        # Still being written to: the pull is still arriving.
        if closed_at > moment:
            continue

        ready.append(
            row,
        )

    return ready


def qualifying_jobs(
    session: Session,
    pull: PollSessionRecord,
) -> list[tuple[JobRecord, JobEvaluationRecord]]:
    """The gate-passing jobs this pull discovered, best signal first."""

    rows = session.execute(
        select(
            JobRecord,
            JobEvaluationRecord,
        ).join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        ).where(
            JobRecord.first_seen_session_id == pull.id,
            JobEvaluationRecord.eligibility_status == "PASS",
        ).order_by(
            # The same order the queue leads with: roles that announce
            # themselves as new grad, then the ones ACE could actually
            # read, then everything else.
            JobEvaluationRecord.is_new_grad.desc(),
            JobEvaluationRecord.requirements_verified.desc(),
            JobRecord.company,
        )
    ).all()

    return [
        (
            row[0],
            row[1],
        )
        for row in rows
    ]


def _experience(
    evaluation: JobEvaluationRecord,
) -> str:
    """How the row states experience, in the interface's three states."""

    if evaluation.is_early_career:
        return "Early career"

    if evaluation.required_experience_years is not None:
        return (
            f"{evaluation.required_experience_years} yrs max"
        )

    return "Experience not stated"


def render(
    pull: PollSessionRecord,
    jobs: list[tuple[JobRecord, JobEvaluationRecord]],
) -> tuple[str, str]:
    """Return the subject and body for one pull."""

    count = len(
        jobs,
    )

    subject = (
        f"ACE: {count} new "
        + (
            "opportunity"
            if count == 1
            else "opportunities"
        )
    )

    lines = [
        f"{count} new "
        + (
            "role"
            if count == 1
            else "roles"
        )
        + " passed your filters.",
        "",
    ]

    for job, evaluation in jobs[:MAX_LISTED]:
        lines.append(
            f"{job.company} - {job.title}",
        )

        lines.append(
            "  "
            + " | ".join(
                part
                for part in (
                    job.location,
                    _experience(
                        evaluation,
                    ),
                )
                if part
            ),
        )

        # The employer's own posting, never an aggregator or a link
        # back into ACE. Tapping it on a phone has to land on the
        # application form, which is the entire point of the email.
        lines.append(
            "  " + job.official_url,
        )

        lines.append(
            "",
        )

    if count > MAX_LISTED:
        lines.append(
            f"and {count - MAX_LISTED} more, "
            "in the queue.",
        )

        lines.append(
            "",
        )

    settings = get_settings()

    lines.append(
        settings.public_base_url.rstrip(
            "/",
        )
        + "/",
    )

    return subject, "\n".join(
        lines,
    )


def send_pending(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Alert every finished pull that has not been alerted. Returns how
    many emails were sent.

    Marks a pull notified whether or not the send succeeded. The
    alternative is retrying, and a pull that could not be delivered
    once is stale by the time a retry would land: the jobs are still in
    the queue, which is the durable surface. An alert is a nudge, not a
    record.
    """

    settings = get_settings()

    if not settings.alert_email:
        return 0

    moment = now or datetime.now(
        timezone.utc,
    )

    sent = 0

    for pull in pending_pulls(
        session,
        now=moment,
    ):
        age = moment - _as_utc(
            pull.started_at,
        )

        jobs = qualifying_jobs(
            session,
            pull,
        )

        if age > MAX_AGE or not jobs:
            # Too old to be useful, or the qualifying count was
            # recorded but the jobs have since been re-evaluated away.
            # Marked so it is not reconsidered every cycle.
            pull.notified_at = moment
            continue

        subject, body = render(
            pull,
            jobs,
        )

        delivered = send_mail(
            to=settings.alert_email,
            subject=subject,
            text=body,
        )

        pull.notified_at = moment

        if delivered:
            sent += 1

        LOGGER.info(
            "alert_pull id=%s jobs=%s delivered=%s",
            pull.id,
            len(
                jobs,
            ),
            delivered,
        )

    return sent
