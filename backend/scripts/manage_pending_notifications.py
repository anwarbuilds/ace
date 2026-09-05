"""Classify and safely retire ACE pending notification candidates.

Why this exists
---------------

ACE accumulated pending alert candidates before the freshness policy
existed. Most of them describe postings that are only "new" in the sense
that ACE had never polled their source before.

Draining that backlog would produce a flood of emails about roles that
opened months ago. Deleting it would destroy audit history.

This script reclassifies the backlog under the current freshness policy
instead.

Safety
------

The script is read-only by default. Nothing changes without --apply.

It never touches:

    - SENT rows        (real delivered history)
    - DEAD rows        (unless --requeue-dead is requested)
    - the jobs table
    - the source_states table

Stale candidates become SUPPRESSED, a terminal but fully preserved
state. Nothing is deleted.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.app.config import (
    get_settings,
)
from backend.app.db.models import (
    JobRecord,
    NotificationOutboxRecord,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.evaluation.freshness import (
    FreshnessPolicy,
    evaluate_freshness,
)
from backend.app.notifications.payload import (
    build_alert_payload,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


SUPPRESSION_STATUS = "SUPPRESSED"


@dataclass(
    frozen=True,
    slots=True,
)
class CandidateClassification:
    """One pending candidate judged against the freshness policy."""

    outbox_id: int

    company: str

    title: str

    observation_status: str

    posted_at: datetime | None

    posting_age_days: int | None

    keep: bool

    reason: str

    job_id: int | None


@dataclass(
    frozen=True,
    slots=True,
)
class BacklogReport:
    """Summary of one classification pass."""

    retained: tuple[
        CandidateClassification,
        ...,
    ]

    suppressed: tuple[
        CandidateClassification,
        ...,
    ]

    @property
    def total(self) -> int:
        """Return the number of pending candidates inspected."""

        return (
            len(self.retained)
            + len(self.suppressed)
        )


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Normalize an optional stored timestamp to aware UTC."""

    if value is None:
        return None

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


def classify_pending_candidates(
    session: Session,
    *,
    policy: FreshnessPolicy,
    now: datetime,
) -> BacklogReport:
    """Judge every PENDING, unassigned candidate against the policy.

    Backlog rows are treated as baseline observations, because that is
    exactly what they are: the product of ACE seeing a source for the
    first time. Applying the baseline rule is therefore the honest
    reading, not a stricter one.
    """

    rows = session.execute(
        select(
            NotificationOutboxRecord,
            JobRecord,
        )
        .outerjoin(
            JobRecord,
            (
                JobRecord.source
                == NotificationOutboxRecord.source
            )
            & (
                JobRecord.source_account
                == NotificationOutboxRecord.source_account
            )
            & (
                JobRecord.external_id
                == NotificationOutboxRecord.external_id
            ),
        )
        .where(
            NotificationOutboxRecord.status
            == "PENDING",
            NotificationOutboxRecord.digest_id
            .is_(None),
        )
        .order_by(
            NotificationOutboxRecord.id
        )
    ).all()

    retained: list[
        CandidateClassification
    ] = []

    suppressed: list[
        CandidateClassification
    ] = []

    for outbox_row, job_row in rows:
        posted_at = _as_utc(
            job_row.posted_at
            if job_row is not None
            else None
        )

        try:
            observation_status = (
                JobObservationStatus(
                    outbox_row.observation_status
                )
            )

        except ValueError:
            observation_status = (
                JobObservationStatus.NEW
            )

        decision = evaluate_freshness(
            observation_status=(
                observation_status
            ),
            is_baseline=True,
            posted_at=posted_at,
            observed_at=now,
            policy=policy,
        )

        classification = (
            CandidateClassification(
                outbox_id=outbox_row.id,
                company=(
                    job_row.company
                    if job_row is not None
                    else "unknown"
                ),
                title=(
                    job_row.title
                    if job_row is not None
                    else outbox_row.subject
                ),
                observation_status=(
                    outbox_row
                    .observation_status
                ),
                posted_at=posted_at,
                posting_age_days=(
                    decision.posting_age_days
                ),
                keep=decision.is_fresh,
                reason=(
                    decision.reason.value
                ),
                job_id=(
                    job_row.id
                    if job_row is not None
                    else None
                ),
            )
        )

        if decision.is_fresh:
            retained.append(
                classification
            )

        else:
            suppressed.append(
                classification
            )

    return BacklogReport(
        retained=tuple(
            retained
        ),
        suppressed=tuple(
            suppressed
        ),
    )


def suppress_candidates(
    session: Session,
    *,
    outbox_ids: Sequence[int],
    now: datetime,
    reason: str,
) -> int:
    """Move stale candidates to the terminal SUPPRESSED state."""

    if not outbox_ids:
        return 0

    result = session.execute(
        update(
            NotificationOutboxRecord
        )
        .where(
            NotificationOutboxRecord.id
            .in_(
                outbox_ids
            ),
            NotificationOutboxRecord.status
            == "PENDING",
        )
        .values(
            status=SUPPRESSION_STATUS,
            last_attempt_at=now,
            last_error=reason,
        )
    )

    return int(
        result.rowcount or 0
    )


def backfill_payloads(
    session: Session,
    *,
    outbox_ids: Sequence[int],
) -> int:
    """Give retained legacy rows a structured digest payload.

    Rows queued before structured payloads existed would otherwise
    render as a degraded digest entry. Backfilling from the persisted
    job record restores full detail: location, official URL, and role
    classification.
    """

    if not outbox_ids:
        return 0

    from backend.app.evaluation.types import (
        AlertDisposition,
        EvaluatedJob,
    )
    from backend.app.intelligence.eligibility import (
        evaluate_job,
    )
    from backend.app.models.job import (
        CanonicalJob,
    )

    rows = session.execute(
        select(
            NotificationOutboxRecord,
            JobRecord,
        )
        .join(
            JobRecord,
            (
                JobRecord.source
                == NotificationOutboxRecord.source
            )
            & (
                JobRecord.source_account
                == NotificationOutboxRecord.source_account
            )
            & (
                JobRecord.external_id
                == NotificationOutboxRecord.external_id
            ),
        )
        .where(
            NotificationOutboxRecord.id
            .in_(
                outbox_ids
            ),
            NotificationOutboxRecord.payload
            .is_(None),
        )
    ).all()

    updated = 0

    for outbox_row, job_row in rows:
        canonical = CanonicalJob(
            source=job_row.source,
            company=job_row.company,
            external_id=(
                job_row.external_id
            ),
            requisition_id=(
                job_row.requisition_id
            ),
            title=job_row.title,
            location=job_row.location,
            description=(
                job_row.description
            ),
            official_url=(
                job_row.official_url
            ),
            posted_at=_as_utc(
                job_row.posted_at
            ),
            updated_at=_as_utc(
                job_row.source_updated_at
            ),
        )

        try:
            observation_status = (
                JobObservationStatus(
                    outbox_row.observation_status
                )
            )

        except ValueError:
            observation_status = (
                JobObservationStatus.NEW
            )

        candidate = EvaluatedJob(
            job=canonical,
            observation_status=(
                observation_status
            ),
            eligibility=evaluate_job(
                canonical
            ),
            alert_disposition=(
                AlertDisposition.ALERT
            ),
        )

        outbox_row.payload = (
            build_alert_payload(
                candidate,
                source_account=(
                    outbox_row.source_account
                ),
                detected_at=_as_utc(
                    outbox_row.created_at
                )
                or datetime.now(
                    timezone.utc
                ),
            )
        )

        updated += 1

    return updated


def requeue_dead_candidates(
    session: Session,
    *,
    now: datetime,
) -> int:
    """Return DEAD candidates to PENDING for a future digest."""

    result = session.execute(
        update(
            NotificationOutboxRecord
        )
        .where(
            NotificationOutboxRecord.status
            == "DEAD"
        )
        .values(
            status="PENDING",
            digest_id=None,
            attempt_count=0,
            next_attempt_at=now,
            last_error=None,
        )
    )

    return int(
        result.rowcount or 0
    )


def _print_classification_table(
    title: str,
    entries: Sequence[
        CandidateClassification
    ],
    *,
    limit: int,
) -> None:
    """Print a bounded preview of one classification group."""

    print()

    print(
        f"{title} ({len(entries)})"
    )

    print(
        "-" * 100
    )

    if not entries:
        print(
            "  (none)"
        )

        return

    for entry in entries[:limit]:
        age = (
            "unknown"
            if entry.posting_age_days
            is None
            else f"{entry.posting_age_days}d"
        )

        print(
            f"  #{entry.outbox_id:<6} "
            f"{age:>8}  "
            f"{entry.observation_status:<9} "
            f"{entry.company[:24]:<24} "
            f"{entry.title[:40]:<40} "
            f"{entry.reason}"
        )

    if len(entries) > limit:
        print(
            f"  ... and "
            f"{len(entries) - limit} more"
        )


def build_parser() -> argparse.ArgumentParser:
    """Build maintenance CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Classify and safely retire "
            "stale ACE pending notification "
            "candidates."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Perform the changes. Without "
            "this flag the script only "
            "reports."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Explicitly request a read-only "
            "report. This is already the "
            "default."
        ),
    )

    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help=(
            "Override MAX_ALERT_POSTING_AGE_DAYS "
            "for this run."
        ),
    )

    parser.add_argument(
        "--alert-on-unknown-age",
        action="store_true",
        help=(
            "Retain candidates whose posting "
            "date is unknown."
        ),
    )

    parser.add_argument(
        "--no-backfill-payloads",
        action="store_true",
        help=(
            "Skip restoring structured digest "
            "payloads on retained legacy rows."
        ),
    )

    parser.add_argument(
        "--requeue-dead",
        action="store_true",
        help=(
            "Also return DEAD candidates to "
            "PENDING, for use after a "
            "resolved transport outage."
        ),
    )

    parser.add_argument(
        "--limit-preview",
        type=int,
        default=15,
        help=(
            "Rows to show per group in the "
            "report."
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Report on, and optionally retire, the pending backlog."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    if args.apply and args.dry_run:
        parser.error(
            (
                "--apply and --dry-run are "
                "mutually exclusive."
            )
        )

    settings = get_settings()

    max_age_days = (
        args.max_age_days
        if args.max_age_days is not None
        else (
            settings
            .max_alert_posting_age_days
        )
    )

    try:
        policy = FreshnessPolicy(
            max_posting_age_days=(
                max_age_days
            ),
            alert_on_unknown_posting_age=(
                args.alert_on_unknown_age
                or settings
                .alert_on_unknown_posting_age
            ),
        )

    except ValueError as exc:
        print(
            f"Invalid policy: {exc}",
            file=sys.stderr,
        )

        return 2

    now = datetime.now(
        timezone.utc
    )

    print(
        "ACE Pending Notification "
        "Maintenance"
    )

    print(
        "=" * 100
    )

    print(
        f"Mode:                  "
        f"{'APPLY' if args.apply else 'DRY RUN (read-only)'}"
    )

    print(
        f"Reference time:        "
        f"{now.isoformat()}"
    )

    print(
        f"Freshness threshold:   "
        f"{policy.max_posting_age_days} days"
    )

    print(
        f"Unknown age retained:  "
        f"{policy.alert_on_unknown_posting_age}"
    )

    with SessionLocal() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=policy,
                now=now,
            )
        )

    print()

    print(
        f"Pending candidates "
        f"inspected: {report.total}"
    )

    print(
        f"  retain (fresh):      "
        f"{len(report.retained)}"
    )

    print(
        f"  suppress (stale):    "
        f"{len(report.suppressed)}"
    )

    _print_classification_table(
        "RETAIN - will appear in the next digest",
        report.retained,
        limit=args.limit_preview,
    )

    _print_classification_table(
        "SUPPRESS - historical, will never be emailed",
        report.suppressed,
        limit=args.limit_preview,
    )

    if not args.apply:
        print()

        print(
            "=" * 100
        )

        print(
            (
                "DRY RUN. No changes were "
                "made."
            )
        )

        print(
            (
                "Re-run with --apply to "
                "suppress the stale candidates "
                "listed above."
            )
        )

        return 0

    with SessionLocal.begin() as session:
        suppressed_count = (
            suppress_candidates(
                session,
                outbox_ids=[
                    entry.outbox_id
                    for entry
                    in report.suppressed
                ],
                now=now,
                reason=(
                    "Suppressed by ACE "
                    "freshness policy "
                    f"(> {policy.max_posting_age_days} "
                    "days old at first "
                    "observation)."
                ),
            )
        )

        backfilled_count = 0

        if not args.no_backfill_payloads:
            backfilled_count = (
                backfill_payloads(
                    session,
                    outbox_ids=[
                        entry.outbox_id
                        for entry
                        in report.retained
                    ],
                )
            )

        requeued_count = 0

        if args.requeue_dead:
            requeued_count = (
                requeue_dead_candidates(
                    session,
                    now=now,
                )
            )

    print()

    print(
        "=" * 100
    )

    print(
        f"Suppressed:            "
        f"{suppressed_count}"
    )

    print(
        f"Payloads backfilled:   "
        f"{backfilled_count}"
    )

    print(
        f"DEAD requeued:         "
        f"{requeued_count}"
    )

    print(
        (
            "SENT rows, jobs, and "
            "source_states were not "
            "modified."
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
