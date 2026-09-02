"""Tests for the ACE live Greenhouse runner."""

from collections.abc import (
    Mapping,
    Sequence,
)
from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.app.intelligence.eligibility import (
    EligibilityStatus,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.types import (
    JobObservationStatus,
)
from backend.app.runners.greenhouse import (
    fetch_live_greenhouse_snapshot,
    process_live_greenhouse_snapshot,
)


DETECTED_AT = datetime(
    2026,
    9,
    2,
    18,
    0,
    tzinfo=timezone.utc,
)


def make_job(
    external_id: str = "1",
    *,
    title: str = "Software Engineer",
) -> CanonicalJob:
    """Create one normalized synthetic Greenhouse job."""

    return CanonicalJob(
        source="greenhouse",
        company="Example Company",
        external_id=external_id,
        requisition_id=(
            f"REQ-{external_id}"
        ),
        title=title,
        location=(
            "Seattle, Washington"
        ),
        description=(
            "Build reliable software systems."
        ),
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
        posted_at=DETECTED_AT,
        updated_at=DETECTED_AT,
    )


class FakeRepository:
    """Minimal repository used for runner workflow tests."""

    def __init__(
        self,
        *,
        initialized: bool,
        statuses: Mapping[
            str,
            JobObservationStatus,
        ],
    ) -> None:
        self.initialized = initialized

        self.statuses = dict(
            statuses
        )

        self.observed_source: (
            str | None
        ) = None

        self.observed_source_account: (
            str | None
        ) = None

        self.recorded_job_count: (
            int | None
        ) = None

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
        self.observed_source = (
            source
        )

        self.observed_source_account = (
            source_account
        )

        return {
            job.external_id:
            self.statuses[
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
        return 0

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


def test_fetch_live_snapshot_fetches_before_detection_time() -> None:
    events: list[str] = []

    job = make_job()

    def fake_fetcher(
        board_token: str,
        company_name: str,
    ) -> list[CanonicalJob]:
        events.append(
            "fetch"
        )

        assert (
            board_token
            == "databricks"
        )

        assert (
            company_name
            == "Databricks"
        )

        return [
            job,
        ]

    def fake_clock() -> datetime:
        events.append(
            "clock"
        )

        return DETECTED_AT

    result = (
        fetch_live_greenhouse_snapshot(
            board_token=" databricks ",
            company_name=" Databricks ",
            fetcher=fake_fetcher,
            clock=fake_clock,
        )
    )

    assert events == [
        "fetch",
        "clock",
    ]

    assert (
        result.source
        == "greenhouse"
    )

    assert (
        result.source_account
        == "databricks"
    )

    assert (
        result.company_name
        == "Databricks"
    )

    assert (
        result.detected_at
        == DETECTED_AT
    )

    assert result.job_count == 1

    assert result.jobs == (
        job,
    )


@pytest.mark.parametrize(
    (
        "board_token",
        "company_name",
    ),
    [
        (
            "",
            "Databricks",
        ),
        (
            "   ",
            "Databricks",
        ),
        (
            "databricks",
            "",
        ),
        (
            "databricks",
            "   ",
        ),
    ],
)
def test_fetch_live_snapshot_rejects_blank_identity(
    board_token: str,
    company_name: str,
) -> None:
    def fake_fetcher(
        board_token: str,
        company_name: str,
    ) -> list[CanonicalJob]:
        raise AssertionError(
            "Fetcher must not be called."
        )

    with pytest.raises(
        ValueError
    ):
        fetch_live_greenhouse_snapshot(
            board_token=board_token,
            company_name=company_name,
            fetcher=fake_fetcher,
        )


def test_fetch_live_snapshot_rejects_naive_detection_time() -> None:
    def fake_fetcher(
        board_token: str,
        company_name: str,
    ) -> list[CanonicalJob]:
        return [
            make_job(),
        ]

    def naive_clock() -> datetime:
        return datetime(
            2026,
            9,
            2,
            18,
            0,
        )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        fetch_live_greenhouse_snapshot(
            board_token="databricks",
            company_name="Databricks",
            fetcher=fake_fetcher,
            clock=naive_clock,
        )


def test_process_live_snapshot_uses_board_as_persistent_source_account() -> None:
    job = make_job()

    repository = FakeRepository(
        initialized=True,
        statuses={
            "1": (
                JobObservationStatus.NEW
            ),
        },
    )

    live_snapshot = (
        fetch_live_greenhouse_snapshot(
            board_token="databricks",
            company_name="Databricks",
            fetcher=(
                lambda _board, _company: [
                    job,
                ]
            ),
            clock=lambda: DETECTED_AT,
        )
    )

    result = (
        process_live_greenhouse_snapshot(
            repository,
            snapshot=live_snapshot,
        )
    )

    assert (
        repository.observed_source
        == "greenhouse"
    )

    assert (
        repository.observed_source_account
        == "databricks"
    )

    assert (
        repository.recorded_job_count
        == 1
    )

    assert (
        result.snapshot.new_count
        == 1
    )

    assert (
        result.alert_candidate_count
        == 1
    )

    evaluated = (
        result.evaluation.alert_candidates[
            0
        ]
    )

    assert (
        evaluated.eligibility.status
        == EligibilityStatus.PASS
    )

    assert (
        evaluated.eligibility.role_family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        evaluated.eligibility.role_priority
        == RolePriority.PRIMARY
    )