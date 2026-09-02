"""Tests for the ACE source-snapshot application workflow."""

from collections.abc import (
    Mapping,
    Sequence,
)
from datetime import (
    datetime,
    timezone,
)

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
from backend.app.workflows.source_snapshot import (
    run_source_snapshot_workflow,
)


OBSERVED_AT = datetime(
    2026,
    8,
    29,
    12,
    0,
    tzinfo=timezone.utc,
)


class FakeRepository:
    """Deterministic repository for workflow-level unit tests."""

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
    title: str,
    location: str = "Seattle, Washington",
    description: str = "Build reliable software systems.",
) -> CanonicalJob:
    """Create one normalized synthetic job."""

    return CanonicalJob(
        source="greenhouse",
        company="ACE Synthetic Company",
        external_id=external_id,
        requisition_id=(
            f"ACE-{external_id}"
        ),
        title=title,
        location=location,
        description=description,
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
    )


def test_baseline_is_persisted_but_not_evaluated() -> None:
    job = make_job(
        "1",
        title="Software Engineer",
    )

    repository = FakeRepository(
        initialized=False,
        statuses={
            "1": JobObservationStatus.NEW,
        },
    )

    result = run_source_snapshot_workflow(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            job,
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.snapshot.is_baseline is True

    assert result.snapshot.new_count == 1

    assert (
        result.snapshot.evaluation_candidate_count
        == 0
    )

    assert (
        result.evaluation.evaluated_count
        == 0
    )

    assert result.alert_candidate_count == 0

    assert (
        repository.recorded_job_count
        == 1
    )


def test_new_software_engineer_flows_to_alert_candidate() -> None:
    job = make_job(
        "2",
        title="Software Engineer",
    )

    repository = FakeRepository(
        initialized=True,
        statuses={
            "2": JobObservationStatus.NEW,
        },
    )

    result = run_source_snapshot_workflow(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            job,
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.snapshot.new_count == 1

    assert (
        result.evaluation.evaluated_count
        == 1
    )

    assert result.alert_candidate_count == 1

    evaluated = (
        result.evaluation.alert_candidates[
            0
        ]
    )

    assert (
        evaluated.observation_status
        == JobObservationStatus.NEW
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


def test_new_senior_software_engineer_is_suppressed() -> None:
    job = make_job(
        "3",
        title="Senior Software Engineer",
    )

    repository = FakeRepository(
        initialized=True,
        statuses={
            "3": JobObservationStatus.NEW,
        },
    )

    result = run_source_snapshot_workflow(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            job,
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.snapshot.new_count == 1

    assert (
        result.evaluation.evaluated_count
        == 1
    )

    assert result.alert_candidate_count == 0
    assert result.suppressed_count == 1

    evaluated = (
        result.evaluation.suppressed_jobs[
            0
        ]
    )

    assert (
        evaluated.eligibility.status
        == EligibilityStatus.REJECT
    )


def test_mixed_lifecycle_changes_preserve_observation_status() -> None:
    new_job = make_job(
        "4",
        title="Software Engineer",
    )

    updated_job = make_job(
        "5",
        title="Machine Learning Engineer",
        description=(
            "Build production machine learning "
            "systems. Requires 3 years experience."
        ),
    )

    reopened_job = make_job(
        "6",
        title="Forward Deployed Engineer",
    )

    unchanged_job = make_job(
        "7",
        title="Software Engineer",
    )

    repository = FakeRepository(
        initialized=True,
        statuses={
            "4": JobObservationStatus.NEW,
            "5": JobObservationStatus.UPDATED,
            "6": JobObservationStatus.REOPENED,
            "7": JobObservationStatus.UNCHANGED,
        },
    )

    result = run_source_snapshot_workflow(
        repository,
        source="greenhouse",
        source_account="example",
        jobs=[
            new_job,
            updated_job,
            reopened_job,
            unchanged_job,
        ],
        observed_at=OBSERVED_AT,
    )

    assert result.snapshot.new_count == 1
    assert result.snapshot.updated_count == 1
    assert result.snapshot.reopened_count == 1
    assert result.snapshot.unchanged_count == 1

    assert (
        result.snapshot.evaluation_candidate_count
        == 3
    )

    assert (
        result.evaluation.evaluated_count
        == 3
    )

    statuses = {
        item.job.external_id:
        item.observation_status
        for item
        in result.evaluation.evaluated_jobs
    }

    assert statuses == {
        "4": JobObservationStatus.NEW,
        "5": JobObservationStatus.UPDATED,
        "6": JobObservationStatus.REOPENED,
    }

    assert result.alert_candidate_count == 3
    assert result.suppressed_count == 0

    assert (
        result.evaluation.pass_count
        == 2
    )

    assert (
        result.evaluation.stretch_count
        == 1
    )

    assert (
        result.evaluation.reject_count
        == 0
    )