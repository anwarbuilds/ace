"""Source-snapshot processing orchestration for ACE."""

from collections.abc import (
    Mapping,
    Sequence,
)
from datetime import (
    datetime,
    timezone,
)
from typing import Protocol

from backend.app.models.job import CanonicalJob
from backend.app.persistence.types import (
    JobObservationStatus,
    SnapshotResult,
)


class SnapshotRepository(Protocol):
    """Repository behavior required by the snapshot service."""

    def is_source_initialized(
        self,
        *,
        source: str,
        source_account: str,
    ) -> bool:
        """Return whether this source account already has a baseline."""

        ...

    def observe_jobs(
        self,
        *,
        source: str,
        source_account: str,
        jobs: Sequence[CanonicalJob],
        observed_at: datetime,
    ) -> Mapping[
        str,
        JobObservationStatus,
    ]:
        """Persist observed jobs and return observation statuses."""

        ...

    def mark_missing_jobs_inactive(
        self,
        *,
        source: str,
        source_account: str,
        observed_external_ids: Sequence[str],
        observed_at: datetime,
    ) -> int:
        """Close active jobs missing from the current snapshot."""

        ...

    def record_source_success(
        self,
        *,
        source: str,
        source_account: str,
        observed_at: datetime,
        job_count: int,
    ) -> None:
        """Record successful completion of a source snapshot."""

        ...


def process_snapshot(
    repository: SnapshotRepository,
    *,
    source: str,
    source_account: str,
    jobs: Sequence[CanonicalJob],
    observed_at: datetime | None = None,
) -> SnapshotResult:
    """Process one complete ATS source snapshot.

    The first successful source snapshot establishes a baseline.

    Baseline is lifecycle metadata only. Newly observed jobs from the
    first successful snapshot remain downstream evaluation candidates,
    just like NEW jobs observed on later snapshots.

    Empty snapshots are rejected because treating an unexpectedly empty
    provider response as authoritative could incorrectly close every
    currently active job.
    """

    normalized_source = source.strip()

    normalized_source_account = (
        source_account.strip()
    )

    if not normalized_source:
        raise ValueError(
            "source must not be empty"
        )

    if not normalized_source_account:
        raise ValueError(
            "source_account must not be empty"
        )

    if observed_at is None:
        observed_at = datetime.now(
            timezone.utc
        )

    if (
        observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "observed_at must be timezone-aware"
        )

    observed_at = observed_at.astimezone(
        timezone.utc
    )

    fetched_count = len(
        jobs
    )

    if fetched_count == 0:
        raise ValueError(
            (
                "Refusing to process an empty source "
                "snapshot as authoritative."
            )
        )

    unique_jobs_by_external_id: dict[
        str,
        CanonicalJob,
    ] = {}

    for job in jobs:
        if job.source != normalized_source:
            raise ValueError(
                (
                    "Snapshot contains a job from "
                    f"source {job.source!r}; "
                    f"expected {normalized_source!r}."
                )
            )

        unique_jobs_by_external_id[
            job.external_id
        ] = job

    unique_jobs = tuple(
        unique_jobs_by_external_id.values()
    )

    unique_count = len(
        unique_jobs
    )

    duplicate_count = (
        fetched_count
        - unique_count
    )

    is_baseline = (
        not repository.is_source_initialized(
            source=normalized_source,
            source_account=(
                normalized_source_account
            ),
        )
    )

    statuses = repository.observe_jobs(
        source=normalized_source,
        source_account=(
            normalized_source_account
        ),
        jobs=unique_jobs,
        observed_at=observed_at,
    )

    new_jobs: list[
        CanonicalJob
    ] = []

    updated_jobs: list[
        CanonicalJob
    ] = []

    reopened_jobs: list[
        CanonicalJob
    ] = []

    unchanged_count = 0

    for job in unique_jobs:
        status = statuses[
            job.external_id
        ]

        if (
            status
            == JobObservationStatus.NEW
        ):
            new_jobs.append(
                job
            )

        elif (
            status
            == JobObservationStatus.UPDATED
        ):
            updated_jobs.append(
                job
            )

        elif (
            status
            == JobObservationStatus.REOPENED
        ):
            reopened_jobs.append(
                job
            )

        elif (
            status
            == JobObservationStatus.UNCHANGED
        ):
            unchanged_count += 1

        else:
            raise RuntimeError(
                (
                    "Repository returned an "
                    f"unsupported job status: "
                    f"{status!r}"
                )
            )

    closed_count = (
        repository.mark_missing_jobs_inactive(
            source=normalized_source,
            source_account=(
                normalized_source_account
            ),
            observed_external_ids=[
                job.external_id
                for job in unique_jobs
            ],
            observed_at=observed_at,
        )
    )

    repository.record_source_success(
        source=normalized_source,
        source_account=(
            normalized_source_account
        ),
        observed_at=observed_at,
        job_count=unique_count,
    )

    evaluation_candidates: tuple[
        CanonicalJob,
        ...
    ] = tuple(
        [
            *new_jobs,
            *updated_jobs,
            *reopened_jobs,
        ]
    )

    return SnapshotResult(
        source=normalized_source,
        source_account=(
            normalized_source_account
        ),
        is_baseline=is_baseline,
        observed_at=observed_at,
        fetched_count=fetched_count,
        unique_count=unique_count,
        duplicate_count=duplicate_count,
        new_jobs=tuple(
            new_jobs
        ),
        updated_jobs=tuple(
            updated_jobs
        ),
        reopened_jobs=tuple(
            reopened_jobs
        ),
        unchanged_count=unchanged_count,
        closed_count=closed_count,
        evaluation_candidates=(
            evaluation_candidates
        ),
    )