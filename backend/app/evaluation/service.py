"""Evaluation orchestration for changed ACE jobs."""

from collections.abc import Sequence
from datetime import datetime

from backend.app.evaluation.freshness import (
    FreshnessPolicy,
    evaluate_freshness,
)
from backend.app.intelligence.eligibility import (
    EligibilityDecision,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.types import (
    JobObservationStatus,
    SnapshotResult,
)
from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
    EvaluationBatchResult,
    SuppressionCause,
)


ALERTABLE_ELIGIBILITY_STATUSES = frozenset(
    {
        EligibilityStatus.PASS,
        EligibilityStatus.STRETCH,
    }
)


def _is_eligible_for_alert(
    decision: EligibilityDecision,
) -> bool:
    """Return whether eligibility permits a notification."""

    return (
        decision.status
        in ALERTABLE_ELIGIBILITY_STATUSES
    )


def _evaluate_jobs(
    jobs: Sequence[CanonicalJob],
    *,
    observation_status: JobObservationStatus,
    is_baseline: bool,
    observed_at: datetime,
    policy: FreshnessPolicy,
) -> list[EvaluatedJob]:
    """Evaluate jobs sharing the same persistence observation status.

    Two independent policies apply, in order:

        1. eligibility  -- does this job belong to ACE at all?
        2. freshness    -- is it worth interrupting the user about now?

    Freshness is evaluated only for eligible jobs, so a rejected job is
    never mislabeled as merely stale.
    """

    evaluated_jobs: list[
        EvaluatedJob
    ] = []

    for job in jobs:
        decision = evaluate_job(
            job
        )

        if not _is_eligible_for_alert(
            decision
        ):
            evaluated_jobs.append(
                EvaluatedJob(
                    job=job,
                    observation_status=(
                        observation_status
                    ),
                    eligibility=decision,
                    alert_disposition=(
                        AlertDisposition
                        .SUPPRESS
                    ),
                    freshness=None,
                    suppression_cause=(
                        SuppressionCause
                        .NOT_ELIGIBLE
                    ),
                )
            )

            continue

        freshness = evaluate_freshness(
            observation_status=(
                observation_status
            ),
            is_baseline=is_baseline,
            posted_at=job.posted_at,
            observed_at=observed_at,
            policy=policy,
        )

        if freshness.is_fresh:
            evaluated_jobs.append(
                EvaluatedJob(
                    job=job,
                    observation_status=(
                        observation_status
                    ),
                    eligibility=decision,
                    alert_disposition=(
                        AlertDisposition
                        .ALERT
                    ),
                    freshness=freshness,
                    suppression_cause=None,
                )
            )

            continue

        evaluated_jobs.append(
            EvaluatedJob(
                job=job,
                observation_status=(
                    observation_status
                ),
                eligibility=decision,
                alert_disposition=(
                    AlertDisposition
                    .SUPPRESS
                ),
                freshness=freshness,
                suppression_cause=(
                    SuppressionCause
                    .NOT_FRESH
                ),
            )
        )

    return evaluated_jobs


def evaluate_snapshot(
    snapshot: SnapshotResult,
    *,
    freshness_policy: FreshnessPolicy | None = None,
) -> EvaluationBatchResult:
    """Evaluate changed jobs from one completed source snapshot.

    Only NEW, UPDATED, and REOPENED jobs are evaluated.

    Baseline status does not suppress evaluation. A first successful
    snapshot therefore evaluates its NEW jobs using the same eligibility
    rules as subsequent snapshots.

    Baseline status does, however, inform the freshness policy: a job
    that is NEW only because ACE had never polled the source before must
    additionally look recent before it may interrupt the user.

    UNCHANGED and CLOSED jobs do not enter normal job-alert evaluation.
    """

    policy = (
        freshness_policy
        if freshness_policy is not None
        else FreshnessPolicy()
    )

    evaluated_jobs: list[
        EvaluatedJob
    ] = []

    for jobs, observation_status in (
        (
            snapshot.new_jobs,
            JobObservationStatus.NEW,
        ),
        (
            snapshot.updated_jobs,
            JobObservationStatus.UPDATED,
        ),
        (
            snapshot.reopened_jobs,
            JobObservationStatus.REOPENED,
        ),
    ):
        evaluated_jobs.extend(
            _evaluate_jobs(
                jobs,
                observation_status=(
                    observation_status
                ),
                is_baseline=(
                    snapshot.is_baseline
                ),
                observed_at=(
                    snapshot.observed_at
                ),
                policy=policy,
            )
        )

    expected_candidate_ids = {
        job.external_id
        for job
        in snapshot.evaluation_candidates
    }

    evaluated_candidate_ids = {
        item.job.external_id
        for item
        in evaluated_jobs
    }

    if (
        expected_candidate_ids
        != evaluated_candidate_ids
    ):
        raise ValueError(
            (
                "Snapshot evaluation candidates "
                "do not match NEW / UPDATED / "
                "REOPENED jobs."
            )
        )

    alert_candidates = tuple(
        item
        for item in evaluated_jobs
        if item.is_alert_candidate
    )

    suppressed_jobs = tuple(
        item
        for item in evaluated_jobs
        if not item.is_alert_candidate
    )

    return EvaluationBatchResult(
        evaluated_jobs=tuple(
            evaluated_jobs
        ),
        alert_candidates=(
            alert_candidates
        ),
        suppressed_jobs=(
            suppressed_jobs
        ),
    )
