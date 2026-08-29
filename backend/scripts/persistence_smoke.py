"""Live Databricks -> PostgreSQL persistence smoke test."""

from collections.abc import Sequence

from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
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
SOURCE_ACCOUNT = "databricks"
COMPANY_NAME = "Databricks"


def _print_result(
    label: str,
    result: SnapshotResult,
) -> None:
    """Print a readable persistence summary."""

    print()
    print(label)
    print("=" * 80)

    print(
        f"Baseline:               "
        f"{result.is_baseline}"
    )

    print(
        f"Fetched:                "
        f"{result.fetched_count}"
    )

    print(
        f"Unique:                 "
        f"{result.unique_count}"
    )

    print(
        f"Duplicates:             "
        f"{result.duplicate_count}"
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


def _persist_once(
    jobs: Sequence[CanonicalJob],
) -> SnapshotResult:
    """Process one complete source snapshot atomically."""

    with SessionLocal.begin() as session:
        repository = JobRepository(
            session
        )

        return process_snapshot(
            repository,
            source=SOURCE,
            source_account=SOURCE_ACCOUNT,
            jobs=jobs,
        )


def main() -> None:
    """Fetch Databricks and validate persistent snapshot behavior."""

    print(
        "Fetching live Databricks jobs..."
    )

    jobs = fetch_greenhouse_jobs(
        board_token=SOURCE_ACCOUNT,
        company_name=COMPANY_NAME,
    )

    first_result = _persist_once(
        jobs
    )

    _print_result(
        "Persistence pass 1",
        first_result,
    )

    second_result = _persist_once(
        jobs
    )

    _print_result(
        "Persistence pass 2",
        second_result,
    )

    with SessionLocal() as session:
        repository = JobRepository(
            session
        )

        stored_count = (
            repository.count_jobs_for_source(
                source=SOURCE,
                source_account=SOURCE_ACCOUNT,
            )
        )

        active_count = (
            repository.count_active_jobs_for_source(
                source=SOURCE,
                source_account=SOURCE_ACCOUNT,
            )
        )

    print()
    print(
        f"Persisted Databricks jobs: "
        f"{stored_count}"
    )

    print(
        f"Active Databricks jobs:    "
        f"{active_count}"
    )


if __name__ == "__main__":
    main()