"""Real PostgreSQL lifecycle smoke test for ACE persistence."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import delete

from backend.app.db.models import (
    JobRecord,
    SourceState,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.repository import (
    JobRepository,
)
from backend.app.persistence.service import (
    process_snapshot,
)
from backend.app.persistence.types import (
    SnapshotResult,
)


SOURCE = "greenhouse"
SOURCE_ACCOUNT = "ace-module3-smoke"

BASE_TIME = datetime(
    2026,
    8,
    28,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_job(
    external_id: str,
    *,
    description: str = "Build reliable software.",
) -> CanonicalJob:
    """Create one synthetic normalized job."""

    return CanonicalJob(
        source=SOURCE,
        company="ACE Synthetic Company",
        external_id=external_id,
        requisition_id=(
            f"ACE-{external_id}"
        ),
        title="Software Engineer",
        location="Seattle, Washington",
        description=description,
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
        posted_at=BASE_TIME,
        updated_at=BASE_TIME,
    )


def cleanup() -> None:
    """Remove only synthetic Module 3 smoke-test records."""

    with SessionLocal.begin() as session:
        session.execute(
            delete(
                JobRecord
            ).where(
                JobRecord.source == SOURCE,
                JobRecord.source_account
                == SOURCE_ACCOUNT,
            )
        )

        session.execute(
            delete(
                SourceState
            ).where(
                SourceState.source == SOURCE,
                SourceState.source_account
                == SOURCE_ACCOUNT,
            )
        )


def persist(
    jobs: list[CanonicalJob],
    *,
    observed_at: datetime,
) -> SnapshotResult:
    """Persist one complete synthetic snapshot."""

    with SessionLocal.begin() as session:
        repository = JobRepository(
            session
        )

        return process_snapshot(
            repository,
            source=SOURCE,
            source_account=SOURCE_ACCOUNT,
            jobs=jobs,
            observed_at=observed_at,
        )


def print_result(
    label: str,
    result: SnapshotResult,
) -> None:
    """Print one lifecycle result."""

    print()
    print(label)
    print("=" * 80)

    print(
        f"Baseline:               "
        f"{result.is_baseline}"
    )

    print(
        f"NEW:                    "
        f"{result.new_count}"
    )

    print(
        f"UPDATED:                "
        f"{result.updated_count}"
    )

    print(
        f"REOPENED:               "
        f"{result.reopened_count}"
    )

    print(
        f"UNCHANGED:              "
        f"{result.unchanged_count}"
    )

    print(
        f"CLOSED:                 "
        f"{result.closed_count}"
    )

    print(
        f"Evaluation candidates:  "
        f"{result.evaluation_candidate_count}"
    )


def main() -> None:
    """Exercise NEW, UPDATED, CLOSED, and REOPENED transitions."""

    cleanup()

    try:
        job_a = make_job(
            "A"
        )

        job_b = make_job(
            "B"
        )

        job_c = make_job(
            "C"
        )

        baseline = persist(
            [
                job_a,
                job_b,
            ],
            observed_at=BASE_TIME,
        )

        print_result(
            "Pass 1 — baseline",
            baseline,
        )

        assert baseline.is_baseline is True
        assert baseline.new_count == 2
        assert (
            baseline.evaluation_candidate_count
            == 0
        )

        updated_job_b = make_job(
            "B",
            description=(
                "Build reliable distributed "
                "software systems."
            ),
        )

        second_pass = persist(
            [
                job_a,
                updated_job_b,
                job_c,
            ],
            observed_at=(
                BASE_TIME
                + timedelta(minutes=15)
            ),
        )

        print_result(
            "Pass 2 — NEW + UPDATED",
            second_pass,
        )

        assert second_pass.is_baseline is False
        assert second_pass.new_count == 1
        assert second_pass.updated_count == 1
        assert second_pass.unchanged_count == 1
        assert (
            second_pass.evaluation_candidate_count
            == 2
        )

        third_pass = persist(
            [
                job_a,
                job_c,
            ],
            observed_at=(
                BASE_TIME
                + timedelta(minutes=30)
            ),
        )

        print_result(
            "Pass 3 — CLOSED",
            third_pass,
        )

        assert third_pass.closed_count == 1
        assert third_pass.unchanged_count == 2
        assert (
            third_pass.evaluation_candidate_count
            == 0
        )

        fourth_pass = persist(
            [
                job_a,
                updated_job_b,
                job_c,
            ],
            observed_at=(
                BASE_TIME
                + timedelta(minutes=45)
            ),
        )

        print_result(
            "Pass 4 — REOPENED",
            fourth_pass,
        )

        assert fourth_pass.reopened_count == 1
        assert fourth_pass.unchanged_count == 2
        assert (
            fourth_pass.evaluation_candidate_count
            == 1
        )

        with SessionLocal() as session:
            repository = JobRepository(
                session
            )

            total_count = (
                repository.count_jobs_for_source(
                    source=SOURCE,
                    source_account=(
                        SOURCE_ACCOUNT
                    ),
                )
            )

            active_count = (
                repository.count_active_jobs_for_source(
                    source=SOURCE,
                    source_account=(
                        SOURCE_ACCOUNT
                    ),
                )
            )

        print()
        print("=" * 80)
        print(
            "Lifecycle smoke test passed."
        )

        print(
            f"Persistent records: "
            f"{total_count}"
        )

        print(
            f"Active records:     "
            f"{active_count}"
        )

        assert total_count == 3
        assert active_count == 3

    finally:
        cleanup()


if __name__ == "__main__":
    main()