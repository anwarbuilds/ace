"""Real PostgreSQL smoke test for the ACE source-snapshot workflow."""

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
from backend.app.evaluation.types import (
    EvaluationBatchResult,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.repository import (
    JobRepository,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)
from backend.app.workflows.source_snapshot import (
    SourceSnapshotWorkflowResult,
    run_source_snapshot_workflow,
)


SOURCE = "greenhouse"
SOURCE_ACCOUNT = "ace-module4-smoke"

BASE_TIME = datetime(
    2026,
    8,
    29,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_job(
    external_id: str,
    *,
    title: str,
    description: str = "Build reliable software systems.",
    location: str = "Seattle, Washington",
) -> CanonicalJob:
    """Create one synthetic normalized job."""

    return CanonicalJob(
        source=SOURCE,
        company="ACE Module 4 Synthetic Company",
        external_id=external_id,
        requisition_id=(
            f"ACE-M4-{external_id}"
        ),
        title=title,
        location=location,
        description=description,
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
        posted_at=BASE_TIME,
        updated_at=BASE_TIME,
    )


def cleanup() -> None:
    """Remove only Module 4 synthetic smoke-test data."""

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


def run_snapshot(
    jobs: list[CanonicalJob],
    *,
    observed_at: datetime,
) -> SourceSnapshotWorkflowResult:
    """Persist and evaluate one complete synthetic source snapshot."""

    with SessionLocal.begin() as session:
        repository = JobRepository(
            session
        )

        return run_source_snapshot_workflow(
            repository,
            source=SOURCE,
            source_account=SOURCE_ACCOUNT,
            jobs=jobs,
            observed_at=observed_at,
        )


def format_relative_age(
    timestamp: datetime | None,
    *,
    reference_time: datetime,
) -> str:
    """Return a human-readable age for a timestamp."""

    if timestamp is None:
        return "Unknown"

    delta = (
        reference_time
        - timestamp
    )

    total_seconds = max(
        0,
        int(
            delta.total_seconds()
        ),
    )

    if total_seconds < 60:
        unit = (
            "second"
            if total_seconds == 1
            else "seconds"
        )

        return (
            f"{total_seconds} "
            f"{unit} ago"
        )

    total_minutes = (
        total_seconds // 60
    )

    if total_minutes < 60:
        unit = (
            "minute"
            if total_minutes == 1
            else "minutes"
        )

        return (
            f"{total_minutes} "
            f"{unit} ago"
        )

    total_hours = (
        total_minutes // 60
    )

    if total_hours < 24:
        unit = (
            "hour"
            if total_hours == 1
            else "hours"
        )

        return (
            f"{total_hours} "
            f"{unit} ago"
        )

    total_days = (
        total_hours // 24
    )

    unit = (
        "day"
        if total_days == 1
        else "days"
    )

    return (
        f"{total_days} "
        f"{unit} ago"
    )


def format_timestamp(
    timestamp: datetime | None,
) -> str:
    """Return a stable human-readable UTC timestamp."""

    if timestamp is None:
        return "Unknown"

    normalized = timestamp.astimezone(
        timezone.utc
    )

    return normalized.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def print_snapshot_summary(
    label: str,
    result: SourceSnapshotWorkflowResult,
) -> None:
    """Print persistence and evaluation summaries."""

    snapshot = result.snapshot
    evaluation = result.evaluation

    print()
    print(label)
    print("=" * 80)

    print("Persistence")
    print("-" * 80)

    print(
        f"Baseline:               "
        f"{snapshot.is_baseline}"
    )

    print(
        f"Fetched:                "
        f"{snapshot.fetched_count}"
    )

    print(
        f"Unique:                 "
        f"{snapshot.unique_count}"
    )

    print(
        f"NEW:                    "
        f"{snapshot.new_count}"
    )

    print(
        f"UPDATED:                "
        f"{snapshot.updated_count}"
    )

    print(
        f"REOPENED:               "
        f"{snapshot.reopened_count}"
    )

    print(
        f"UNCHANGED:              "
        f"{snapshot.unchanged_count}"
    )

    print(
        f"CLOSED:                 "
        f"{snapshot.closed_count}"
    )

    print(
        f"Evaluation candidates:  "
        f"{snapshot.evaluation_candidate_count}"
    )

    print()
    print("Evaluation")
    print("-" * 80)

    print(
        f"Evaluated:              "
        f"{evaluation.evaluated_count}"
    )

    print(
        f"PASS:                   "
        f"{evaluation.pass_count}"
    )

    print(
        f"STRETCH:                "
        f"{evaluation.stretch_count}"
    )

    print(
        f"REJECT:                 "
        f"{evaluation.reject_count}"
    )

    print(
        f"Alert candidates:       "
        f"{evaluation.alert_candidate_count}"
    )

    print(
        f"Suppressed:             "
        f"{evaluation.suppressed_count}"
    )


def print_alert_candidates(
    evaluation: EvaluationBatchResult,
    *,
    reference_time: datetime,
) -> None:
    """Print jobs that would continue toward the notification layer."""

    print()
    print("Alert candidates")
    print("=" * 80)

    if not evaluation.alert_candidates:
        print("None")
        return

    for item in evaluation.alert_candidates:
        print("-" * 80)

        print(
            f"Change:      "
            f"{item.observation_status.value}"
        )

        print(
            f"Company:     "
            f"{item.job.company}"
        )

        print(
            f"Title:       "
            f"{item.job.title}"
        )

        print(
            f"Location:    "
            f"{item.job.location}"
        )

        print(
            f"Role family: "
            f"{item.eligibility.role_family.value}"
        )

        print(
            f"Priority:    "
            f"{item.eligibility.role_priority.value}"
        )

        print(
            f"Eligibility: "
            f"{item.eligibility.status.value}"
        )

        print(
            f"Posted:      "
            f"{format_relative_age(
                item.job.posted_at,
                reference_time=reference_time,
            )}"
        )

        print(
            f"Posted at:   "
            f"{format_timestamp(
                item.job.posted_at
            )}"
        )

        print(
            f"Updated at:  "
            f"{format_timestamp(
                item.job.updated_at
            )}"
        )

        print(
            f"Official URL:"
            f" {item.job.official_url}"
        )


def print_suppressed_jobs(
    evaluation: EvaluationBatchResult,
    *,
    reference_time: datetime,
) -> None:
    """Print changed jobs blocked from notification."""

    print()
    print("Suppressed jobs")
    print("=" * 80)

    if not evaluation.suppressed_jobs:
        print("None")
        return

    for item in evaluation.suppressed_jobs:
        print("-" * 80)

        print(
            f"Change:      "
            f"{item.observation_status.value}"
        )

        print(
            f"Company:     "
            f"{item.job.company}"
        )

        print(
            f"Title:       "
            f"{item.job.title}"
        )

        print(
            f"Location:    "
            f"{item.job.location}"
        )

        print(
            f"Posted:      "
            f"{format_relative_age(
                item.job.posted_at,
                reference_time=reference_time,
            )}"
        )

        print(
            f"Posted at:   "
            f"{format_timestamp(
                item.job.posted_at
            )}"
        )

        print(
            f"Updated at:  "
            f"{format_timestamp(
                item.job.updated_at
            )}"
        )

        print(
            f"Eligibility: "
            f"{item.eligibility.status.value}"
        )

        print(
            "Reasons:"
        )

        for reason in item.eligibility.reasons:
            print(
                f"  - {reason}"
            )

        print(
            f"Official URL:"
            f" {item.job.official_url}"
        )


def verify_second_pass(
    result: SourceSnapshotWorkflowResult,
) -> None:
    """Assert expected real end-to-end workflow behavior."""

    snapshot = result.snapshot
    evaluation = result.evaluation

    assert snapshot.is_baseline is False

    assert snapshot.fetched_count == 6
    assert snapshot.unique_count == 6

    assert snapshot.new_count == 4
    assert snapshot.updated_count == 1
    assert snapshot.reopened_count == 0
    assert snapshot.unchanged_count == 1
    assert snapshot.closed_count == 0

    assert (
        snapshot.evaluation_candidate_count
        == 5
    )

    assert evaluation.evaluated_count == 5

    assert evaluation.pass_count == 3
    assert evaluation.stretch_count == 1
    assert evaluation.reject_count == 1

    assert (
        evaluation.alert_candidate_count
        == 4
    )

    assert evaluation.suppressed_count == 1

    evaluated_by_id = {
        item.job.external_id: item
        for item in evaluation.evaluated_jobs
    }

    assert (
        evaluated_by_id[
            "B"
        ].observation_status
        == JobObservationStatus.UPDATED
    )

    assert (
        evaluated_by_id[
            "C"
        ].observation_status
        == JobObservationStatus.NEW
    )

    assert (
        evaluated_by_id[
            "D"
        ].observation_status
        == JobObservationStatus.NEW
    )

    assert (
        evaluated_by_id[
            "E"
        ].observation_status
        == JobObservationStatus.NEW
    )

    assert (
        evaluated_by_id[
            "F"
        ].observation_status
        == JobObservationStatus.NEW
    )

    updated_job = evaluated_by_id[
        "B"
    ]

    assert (
        updated_job.eligibility.status
        == EligibilityStatus.PASS
    )

    assert (
        updated_job.eligibility.role_family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        updated_job.eligibility.role_priority
        == RolePriority.PRIMARY
    )

    software_job = evaluated_by_id[
        "C"
    ]

    assert (
        software_job.eligibility.status
        == EligibilityStatus.PASS
    )

    assert (
        software_job.eligibility.role_family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    senior_job = evaluated_by_id[
        "D"
    ]

    assert (
        senior_job.eligibility.status
        == EligibilityStatus.REJECT
    )

    ml_job = evaluated_by_id[
        "E"
    ]

    assert (
        ml_job.eligibility.status
        == EligibilityStatus.STRETCH
    )

    assert (
        ml_job.eligibility.role_family
        == RoleFamily.AI_ML_ENGINEERING
    )

    assert (
        ml_job.eligibility.role_priority
        == RolePriority.PRIMARY
    )

    fde_job = evaluated_by_id[
        "F"
    ]

    assert (
        fde_job.eligibility.status
        == EligibilityStatus.PASS
    )

    assert (
        fde_job.eligibility.role_family
        == RoleFamily.FORWARD_DEPLOYED_ENGINEERING
    )

    assert (
        fde_job.eligibility.role_priority
        == RolePriority.SECONDARY
    )


def main() -> None:
    """Exercise persistence and evaluation together against PostgreSQL."""

    cleanup()

    try:
        baseline_job_a = make_job(
            "A",
            title="Software Engineer",
        )

        baseline_job_b = make_job(
            "B",
            title="Software Engineer",
            description=(
                "Build reliable backend systems."
            ),
        )

        baseline_result = run_snapshot(
            [
                baseline_job_a,
                baseline_job_b,
            ],
            observed_at=BASE_TIME,
        )

        print_snapshot_summary(
            "Pass 1 — Baseline",
            baseline_result,
        )

        assert (
            baseline_result.snapshot.is_baseline
            is True
        )

        assert (
            baseline_result.snapshot.new_count
            == 2
        )

        assert (
            baseline_result.snapshot.evaluation_candidate_count
            == 0
        )

        assert (
            baseline_result.evaluation.evaluated_count
            == 0
        )

        assert (
            baseline_result.alert_candidate_count
            == 0
        )

        unchanged_job_a = (
            baseline_job_a
        )

        updated_job_b = make_job(
            "B",
            title="Software Engineer",
            description=(
                "Build reliable distributed "
                "backend systems."
            ),
        )

        new_software_job = make_job(
            "C",
            title="Software Engineer",
        )

        new_senior_job = make_job(
            "D",
            title="Senior Software Engineer",
        )

        new_ml_job = make_job(
            "E",
            title="Machine Learning Engineer",
            description=(
                "Build production machine "
                "learning systems. "
                "Requires 3 years experience."
            ),
        )

        new_fde_job = make_job(
            "F",
            title="Forward Deployed Engineer",
        )

        second_observed_at = (
            BASE_TIME
            + timedelta(minutes=15)
        )

        second_result = run_snapshot(
            [
                unchanged_job_a,
                updated_job_b,
                new_software_job,
                new_senior_job,
                new_ml_job,
                new_fde_job,
            ],
            observed_at=second_observed_at,
        )

        print_snapshot_summary(
            "Pass 2 — Persistence + Evaluation",
            second_result,
        )

        print_alert_candidates(
            second_result.evaluation,
            reference_time=second_observed_at,
        )

        print_suppressed_jobs(
            second_result.evaluation,
            reference_time=second_observed_at,
        )

        verify_second_pass(
            second_result
        )

        with SessionLocal() as session:
            repository = JobRepository(
                session
            )

            persisted_count = (
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

        assert persisted_count == 6
        assert active_count == 6

        print()
        print("=" * 80)

        print(
            "Module 4 end-to-end "
            "workflow smoke test passed."
        )

        print(
            f"Persistent records: "
            f"{persisted_count}"
        )

        print(
            f"Active records:     "
            f"{active_count}"
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()