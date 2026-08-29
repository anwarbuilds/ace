"""Unit tests for ACE source-snapshot processing."""

from collections.abc import (
    Mapping,
    Sequence,
)
from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.app.models.job import CanonicalJob
from backend.app.persistence.service import (
    process_snapshot,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


OBSERVED_AT = datetime(
    2026,
    8,
    28,
    12,
    0,
    tzinfo=timezone.utc,
)


class FakeRepository:
    """Deterministic repository for snapshot-service unit tests."""

    def __init__(
        self,
        *,
        initialized: bool,
        statuses: Mapping[
            str,
            JobObservationStatus,
        ],
        closed_count: int = 0,
    ) -> None:
        self.initialized = initialized

        self.statuses = dict(
            statuses
        )

        self.closed_count = (
            closed_count
        )

        self.observed_jobs: list[
            CanonicalJob
        ] = []

        self.recorded_job_count: (
            int | None
        ) = None

        self.observed_external_ids: tuple[
            str,
            ...
        ] = ()

    def is_source_initialized(
        self,
        *,
        source: str,
        source_account: str,
    ) -> bool:
        return self.initialized

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
        self.observed_jobs.extend(
            jobs
        )

        return {
            job.external_id: self.statuses[
                job.external_id
            ]
            for job in jobs
        }

    def mark_missing_jobs_inactive(
        self,
        *,
        source: str,
        source_account: str,
        observed_external_ids: Sequence[str],
        observed_at: datetime,
    ) -> int:
        self.observed_external_ids = tuple(
            observed_external_ids
        )

        return self.closed_count

    def record_source_success(
        self,
        *,
        source: str,
        source_account: str,
        observed_at: datetime,
        job_count: int,
    ) -> None:
        self.recorded_job_count = (
            job_count
        )


def make_job(
    external_id: str,
    *,
    source: str = "greenhouse",
) -> CanonicalJob:
    """Create a normalized test job."""

    return CanonicalJob(
        source=source,
        company="Example Company",
        external_id=external_id,
        title="Software Engineer",
        location="Seattle, Washington",
        description="Build software.",
        official_url=(
            f"https://example.com/jobs/"
            f"{external_id}"
        ),
    )


def test_baseline_stores_jobs_but_suppresses_evaluation_candidates() -> None:
    repository = FakeRepository(
        initialized=False,
        statuses={
            "1": JobObservationStatus.NEW,
            "2": JobObservationStatus.NEW,
        },
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
            make_job("2"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.is_baseline is True
    assert result.new_count == 2

    assert (
        result.evaluation_candidate_count
        == 0
    )

    assert (
        repository.recorded_job_count
        == 2
    )


def test_new_job_after_baseline_becomes_evaluation_candidate() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": JobObservationStatus.UNCHANGED,
            "2": JobObservationStatus.NEW,
        },
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
            make_job("2"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.is_baseline is False
    assert result.new_count == 1
    assert result.unchanged_count == 1

    assert [
        job.external_id
        for job in result.evaluation_candidates
    ] == [
        "2"
    ]


def test_updated_job_becomes_evaluation_candidate() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": JobObservationStatus.UPDATED,
        },
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.updated_count == 1

    assert [
        job.external_id
        for job in result.evaluation_candidates
    ] == [
        "1"
    ]


def test_reopened_job_becomes_evaluation_candidate() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": JobObservationStatus.REOPENED,
        },
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.reopened_count == 1

    assert [
        job.external_id
        for job in result.evaluation_candidates
    ] == [
        "1"
    ]


def test_missing_jobs_are_reported_as_closed() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": JobObservationStatus.UNCHANGED,
        },
        closed_count=2,
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.closed_count == 2


def test_empty_snapshot_is_rejected() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={},
    )

    with pytest.raises(
        ValueError,
        match="empty source snapshot",
    ):
        process_snapshot(
            repository,
            source="greenhouse",
            source_account="example",
            jobs=[],
            observed_at=OBSERVED_AT,
        )


def test_duplicate_external_ids_are_processed_once() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": JobObservationStatus.UNCHANGED,
        },
    )

    result = process_snapshot(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            make_job("1"),
            make_job("1"),
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.fetched_count == 2
    assert result.unique_count == 1
    assert result.duplicate_count == 1

    assert len(
        repository.observed_jobs
    ) == 1


def test_snapshot_rejects_jobs_from_another_source() -> None:
    repository = FakeRepository(
        initialized=True,
        statuses={},
    )

    with pytest.raises(
        ValueError,
        match="expected 'greenhouse'",
    ):
        process_snapshot(
            repository,
            source="greenhouse",
            source_account="example",
            jobs=[
                make_job(
                    "1",
                    source="another-source",
                )
            ],
            observed_at=OBSERVED_AT,
        )