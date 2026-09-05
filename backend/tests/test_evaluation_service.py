"""Tests for ACE evaluation orchestration."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.app.evaluation.service import (
    evaluate_snapshot,
)
from backend.app.evaluation.types import (
    AlertDisposition,
    SuppressionCause,
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


OBSERVED_AT = datetime(
    2026,
    9,
    5,
    16,
    0,
    tzinfo=timezone.utc,
)


# These tests exercise eligibility -> alert mapping, so their jobs are
# deliberately recent. Freshness behavior has its own dedicated module.
RECENTLY_POSTED_AT = (
    OBSERVED_AT
    - timedelta(
        days=2
    )
)


def make_job(
    external_id: str,
    *,
    title: str,
    location: str = "Seattle, Washington",
    description: str = "Build reliable software systems.",
    posted_at: datetime | None = (
        RECENTLY_POSTED_AT
    ),
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
        posted_at=posted_at,
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
    observed_at: datetime = OBSERVED_AT,
) -> SnapshotResult:
    """Build a representative persistence snapshot result."""

    # process_snapshot always reports NEW / UPDATED / REOPENED jobs as
    # evaluation candidates, including on a baseline snapshot. Baseline
    # is lifecycle metadata, not an evaluation filter.
    evaluation_candidates = (
        new_jobs
        + updated_jobs
        + reopened_jobs
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
        observed_at=observed_at,
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

# ----------------------------------------------------------------------
# Freshness integration
#
# The gate decides inclusion; freshness decides only whether an eligible
# job is worth interrupting the user about.
# ----------------------------------------------------------------------


def test_stale_baseline_job_is_evaluated_but_not_alerted() -> None:
    """Historical first-seen postings must not enter the outbox."""

    job = make_job(
        "20",
        title="Software Engineer",
        posted_at=(
            OBSERVED_AT
            - timedelta(
                days=336
            )
        ),
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            ),
            is_baseline=True,
        )
    )

    # Still evaluated: baseline suppression was deliberately removed.
    assert result.evaluated_count == 1

    assert result.alert_candidate_count == 0

    assert result.stale_suppressed_count == 1

    suppressed = result.suppressed_jobs[0]

    assert (
        suppressed.eligibility.status
        is EligibilityStatus.PASS
    )

    assert (
        suppressed.suppression_cause
        is SuppressionCause.NOT_FRESH
    )


def test_recent_baseline_job_still_alerts() -> None:
    """A newly discovered company with a fresh role must still alert."""

    job = make_job(
        "21",
        title="Software Engineer",
        posted_at=(
            OBSERVED_AT
            - timedelta(
                days=1
            )
        ),
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            ),
            is_baseline=True,
        )
    )

    assert result.alert_candidate_count == 1

    assert result.stale_suppressed_count == 0


def test_ineligible_job_is_not_labelled_stale() -> None:
    """Rejected jobs are distinguishable from merely-old ones."""

    job = make_job(
        "22",
        title="Senior Staff Engineer",
        posted_at=(
            OBSERVED_AT
            - timedelta(
                days=400
            )
        ),
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            ),
            is_baseline=True,
        )
    )

    assert result.alert_candidate_count == 0

    assert result.stale_suppressed_count == 0

    assert (
        result.suppressed_jobs[0]
        .suppression_cause
        is SuppressionCause.NOT_ELIGIBLE
    )


def test_non_baseline_new_job_alerts_despite_old_posting_date() -> None:
    """Appearing after a prior snapshot is evidence in itself."""

    job = make_job(
        "23",
        title="Software Engineer",
        posted_at=(
            OBSERVED_AT
            - timedelta(
                days=400
            )
        ),
    )

    result = evaluate_snapshot(
        make_snapshot(
            new_jobs=(
                job,
            ),
            is_baseline=False,
        )
    )

    assert result.alert_candidate_count == 1


def test_freshness_policy_is_configurable_per_call() -> None:
    """Evaluation honors an explicitly supplied policy."""

    job = make_job(
        "24",
        title="Software Engineer",
        posted_at=(
            OBSERVED_AT
            - timedelta(
                days=45
            )
        ),
    )

    snapshot = make_snapshot(
        new_jobs=(
            job,
        ),
        is_baseline=True,
    )

    assert (
        evaluate_snapshot(
            snapshot
        ).alert_candidate_count
        == 0
    )

    assert (
        evaluate_snapshot(
            snapshot,
            freshness_policy=(
                FreshnessPolicy(
                    max_posting_age_days=90
                )
            ),
        ).alert_candidate_count
        == 1
    )


def test_evaluation_uses_snapshot_observed_at_not_wall_clock() -> None:
    """Freshness compares against the snapshot's own reference instant."""

    job = make_job(
        "25",
        title="Software Engineer",
        posted_at=datetime(
            2020,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    snapshot = make_snapshot(
        new_jobs=(
            job,
        ),
        is_baseline=True,
        observed_at=datetime(
            2020,
            1,
            10,
            tzinfo=timezone.utc,
        ),
    )

    # Nine days old relative to the snapshot, ancient relative to now.
    assert (
        evaluate_snapshot(
            snapshot
        ).alert_candidate_count
        == 1
    )
