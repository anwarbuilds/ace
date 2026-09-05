"""Rebuild the materialized ACE job-evaluation table.

The web application reads eligibility from job_evaluations. That table
is derived data: it can be rebuilt from the jobs table at any time.

Run this when:

    - the table is first created
    - eligibility rules change (ELIGIBILITY_RULE_VERSION)
    - a job's content changed while evaluation was unavailable

Only jobs whose stored evaluation is missing or stale are recomputed,
unless --all is given.

The script is read-only by default. Nothing is written without --apply.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
)
from backend.app.intelligence.eligibility import (
    ELIGIBILITY_RULE_VERSION,
    evaluate_job,
)
from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.persistence.evaluations import (
    record_job_evaluations,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


DEFAULT_BATCH_SIZE = 500


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Normalize a stored timestamp to aware UTC."""

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


def _to_canonical(
    record: JobRecord,
) -> CanonicalJob:
    """Rebuild the canonical job from its persisted record."""

    return CanonicalJob(
        source=record.source,
        company=record.company,
        external_id=record.external_id,
        requisition_id=(
            record.requisition_id
        ),
        title=record.title,
        location=record.location,
        description=record.description,
        official_url=(
            record.official_url
        ),
        posted_at=_as_utc(
            record.posted_at
        ),
        updated_at=_as_utc(
            record.source_updated_at
        ),
    )


def _stale_filter(
    *,
    rebuild_all: bool,
):
    """Return the predicate selecting jobs needing evaluation."""

    if rebuild_all:
        return None

    return (
        (
            JobEvaluationRecord.job_id
            .is_(None)
        )
        | (
            JobEvaluationRecord.content_hash
            != JobRecord.content_hash
        )
        | (
            JobEvaluationRecord.rule_version
            != ELIGIBILITY_RULE_VERSION
        )
    )


def count_pending(
    session: Session,
    *,
    rebuild_all: bool,
) -> int:
    """Count jobs whose evaluation is missing or stale."""

    statement = (
        select(
            func.count()
        )
        .select_from(
            JobRecord
        )
        .outerjoin(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
    )

    predicate = _stale_filter(
        rebuild_all=rebuild_all
    )

    if predicate is not None:
        statement = statement.where(
            predicate
        )

    return int(
        session.scalar(
            statement
        )
        or 0
    )


def load_batch(
    session: Session,
    *,
    rebuild_all: bool,
    after_id: int,
    batch_size: int,
) -> list[JobRecord]:
    """Load the next batch of jobs requiring evaluation."""

    statement = (
        select(
            JobRecord
        )
        .outerjoin(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .where(
            JobRecord.id > after_id
        )
        .order_by(
            JobRecord.id
        )
        .limit(
            batch_size
        )
    )

    predicate = _stale_filter(
        rebuild_all=rebuild_all
    )

    if predicate is not None:
        statement = statement.where(
            predicate
        )

    return list(
        session.scalars(
            statement
        ).all()
    )


def build_parser() -> argparse.ArgumentParser:
    """Build backfill CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the materialized ACE "
            "job-evaluation table."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write evaluations. Without "
            "this flag the script only "
            "reports."
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        dest="rebuild_all",
        help=(
            "Re-evaluate every job, not "
            "only missing or stale ones."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "Jobs to evaluate per "
            "transaction."
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Rebuild missing or stale job evaluations."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    if args.batch_size < 1:
        print(
            "--batch-size must be at least 1.",
            file=sys.stderr,
        )

        return 2

    now = datetime.now(
        timezone.utc
    )

    print(
        "ACE Job Evaluation Backfill"
    )

    print(
        "=" * 80
    )

    print(
        f"Mode:          "
        f"{'APPLY' if args.apply else 'DRY RUN (read-only)'}"
    )

    print(
        f"Rule version:  "
        f"{ELIGIBILITY_RULE_VERSION}"
    )

    print(
        f"Scope:         "
        f"{'all jobs' if args.rebuild_all else 'missing or stale only'}"
    )

    with SessionLocal() as session:
        pending = count_pending(
            session,
            rebuild_all=(
                args.rebuild_all
            ),
        )

        total_jobs = int(
            session.scalar(
                select(
                    func.count()
                ).select_from(
                    JobRecord
                )
            )
            or 0
        )

    print(
        f"Jobs total:    {total_jobs}"
    )

    print(
        f"To evaluate:   {pending}"
    )

    if not args.apply:
        print()

        print(
            (
                "DRY RUN. No changes were "
                "made. Re-run with --apply."
            )
        )

        return 0

    if pending == 0:
        print()

        print(
            "Nothing to do."
        )

        return 0

    written = 0

    after_id = 0

    while True:
        with SessionLocal.begin() as session:
            records = load_batch(
                session,
                rebuild_all=(
                    args.rebuild_all
                ),
                after_id=after_id,
                batch_size=(
                    args.batch_size
                ),
            )

            if not records:
                break

            after_id = records[-1].id

            by_source: dict[
                tuple[str, str],
                list[EvaluatedJob],
            ] = {}

            for record in records:
                canonical = _to_canonical(
                    record
                )

                candidate = EvaluatedJob(
                    job=canonical,
                    observation_status=(
                        JobObservationStatus
                        .UNCHANGED
                    ),
                    eligibility=evaluate_job(
                        canonical
                    ),
                    alert_disposition=(
                        AlertDisposition
                        .SUPPRESS
                    ),
                )

                by_source.setdefault(
                    (
                        record.source,
                        record.source_account,
                    ),
                    [],
                ).append(
                    candidate
                )

            for (
                source,
                source_account,
            ), candidates in (
                by_source.items()
            ):
                written += (
                    record_job_evaluations(
                        session,
                        source=source,
                        source_account=(
                            source_account
                        ),
                        evaluated_jobs=(
                            candidates
                        ),
                        evaluated_at=now,
                    )
                )

        print(
            f"  evaluated {written} / "
            f"{pending}"
        )

    print()

    print(
        "=" * 80
    )

    print(
        f"Evaluations written: {written}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
