"""Tests for ACE evaluation orchestration."""

from backend.app.evaluation.service import (
    evaluate_snapshot,
)
from backend.app.evaluation.types import (
    AlertDisposition,
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
    SnapshotResult,
)


def make_job(
    external_id: str,
    *,
    title: str,
    location: str = "Seattle, Washington",
    description: str = "Build reliable software systems.",
) -> CanonicalJob:
    """Create a normalized test job."""

    return CanonicalJob(
        source="greenhouse",
        company="Example Company",
        external_id=external_id,
        requisition_id=(
            f"REQ-{external_id}"
        ),
        title=title,
        location=location,
        description=description,
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
    )


def make_snapshot(
    *,
    new_jobs: tuple[
        CanonicalJob,
        ...,
    ] = (),
    updated_jobs: tuple[
        CanonicalJob,
        ...,
    ] = (),
    reopened_jobs: tuple[
        CanonicalJob,
        ...,
    ] = (),
    is_baseline: bool = False,
) -> SnapshotResult:
    """Build a representative persistence snapshot result."""

    evaluation_candidates = (
        ()
        if is_baseline
        else (
            new_jobs
            + updated_jobs
            + reopened_jobs
        )
    )

    unique_count = len(
        new_jobs
        + updated_jobs
        + reopened_jobs
    )

    return SnapshotResult(
        source="greenhouse",
        source_account="example",
        is_baseline=is_baseline,
        fetched_count=unique_count,
        unique_count=unique_count,
        duplicate_count=0,
        new_jobs=new_jobs,
        updated_jobs=updated_jobs,
        reopened_jobs=reopened_jobs,
        unchanged_count=0,
        closed_count=0,
        evaluation_candidates=(
            evaluation_candidates
        ),
    )


def test_primary_pass_job_becomes_alert_candidate() -> None:
    job = make_job(
        "1",
        title="Software Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            )
        )
    )

    assert result.evaluated_count == 1
    assert result.alert_candidate_count == 1
    assert result.suppressed_count == 0

    evaluated = result.alert_candidates[
        0
    ]

    assert (
        evaluated.observation_status.value
        == "NEW"
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

    assert (
        evaluated.alert_disposition
        == AlertDisposition.ALERT
    )


def test_primary_stretch_job_remains_alert_candidate() -> None:
    job = make_job(
        "2",
        title="Machine Learning Engineer",
        description=(
            "Build machine learning systems. "
            "Requires 3 years experience."
        ),
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            )
        )
    )

    assert result.alert_candidate_count == 1
    assert result.stretch_count == 1

    evaluated = result.alert_candidates[
        0
    ]

    assert (
        evaluated.eligibility.status
        == EligibilityStatus.STRETCH
    )

    assert (
        evaluated.eligibility.role_family
        == RoleFamily.AI_ML_ENGINEERING
    )

    assert (
        evaluated.eligibility.role_priority
        == RolePriority.PRIMARY
    )


def test_forward_deployed_pass_job_becomes_secondary_alert() -> None:
    job = make_job(
        "3",
        title="Forward Deployed Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            )
        )
    )

    evaluated = result.alert_candidates[
        0
    ]

    assert (
        evaluated.eligibility.status
        == EligibilityStatus.PASS
    )

    assert (
        evaluated.eligibility.role_family
        == RoleFamily.FORWARD_DEPLOYED_ENGINEERING
    )

    assert (
        evaluated.eligibility.role_priority
        == RolePriority.SECONDARY
    )


def test_rejected_job_is_suppressed() -> None:
    job = make_job(
        "4",
        title="Senior Software Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            )
        )
    )

    assert result.evaluated_count == 1
    assert result.alert_candidate_count == 0
    assert result.suppressed_count == 1
    assert result.reject_count == 1

    evaluated = result.suppressed_jobs[
        0
    ]

    assert (
        evaluated.eligibility.status
        == EligibilityStatus.REJECT
    )

    assert (
        evaluated.alert_disposition
        == AlertDisposition.SUPPRESS
    )


def test_updated_job_is_evaluated() -> None:
    job = make_job(
        "5",
        title="Software Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            updated_jobs=(
                job,
            )
        )
    )

    assert result.evaluated_count == 1
    assert (
        result.evaluated_jobs[
            0
        ].observation_status.value
        == "UPDATED"
    )


def test_reopened_job_is_evaluated() -> None:
    job = make_job(
        "6",
        title="AI Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            reopened_jobs=(
                job,
            )
        )
    )

    assert result.evaluated_count == 1
    assert (
        result.evaluated_jobs[
            0
        ].observation_status.value
        == "REOPENED"
    )


def test_baseline_snapshot_produces_no_evaluations() -> None:
    result = evaluate_snapshot(
        make_snapshot(
            is_baseline=True,
        )
    )

    assert result.evaluated_count == 0
    assert result.alert_candidate_count == 0
    assert result.suppressed_count == 0


def test_mixed_batch_reports_correct_counts() -> None:
    pass_job = make_job(
        "7",
        title="Software Engineer",
    )

    stretch_job = make_job(
        "8",
        title="Machine Learning Engineer",
        description=(
            "Requires 3 years experience."
        ),
    )

    reject_job = make_job(
        "9",
        title="Principal Software Engineer",
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                pass_job,
                stretch_job,
                reject_job,
            )
        )
    )

    assert result.evaluated_count == 3

    assert result.pass_count == 1
    assert result.stretch_count == 1
    assert result.reject_count == 1

    assert result.alert_candidate_count == 2
    assert result.suppressed_count == 1