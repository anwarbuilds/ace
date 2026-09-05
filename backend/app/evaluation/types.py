"""Domain types produced by the ACE evaluation pipeline."""

from dataclasses import dataclass
from enum import Enum

from backend.app.evaluation.freshness import (
    FreshnessDecision,
)
from backend.app.intelligence.eligibility import (
    EligibilityDecision,
    EligibilityStatus,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.types import (
    JobObservationStatus,
)


class AlertDisposition(str, Enum):
    """Whether an evaluated job should continue toward notification."""

    ALERT = "ALERT"
    SUPPRESS = "SUPPRESS"


class SuppressionCause(str, Enum):
    """Why an evaluated job did not become an alert candidate.

    Suppression never removes a job from ACE. It only prevents the job
    from consuming the user's attention.
    """

    NOT_ELIGIBLE = "NOT_ELIGIBLE"

    NOT_FRESH = "NOT_FRESH"


@dataclass(frozen=True, slots=True)
class EvaluatedJob:
    """One changed job together with its eligibility evaluation."""

    job: CanonicalJob

    observation_status: JobObservationStatus

    eligibility: EligibilityDecision

    alert_disposition: AlertDisposition

    # Freshness is evaluated only for jobs that already passed the
    # eligibility gate. It stays None when eligibility already decided
    # the outcome.
    freshness: FreshnessDecision | None = None

    suppression_cause: SuppressionCause | None = None

    @property
    def is_alert_candidate(self) -> bool:
        """Return whether this job should continue to notification."""

        return (
            self.alert_disposition
            == AlertDisposition.ALERT
        )

    @property
    def is_suppressed_as_stale(self) -> bool:
        """Return whether freshness alone suppressed this job."""

        return (
            self.suppression_cause
            == SuppressionCause.NOT_FRESH
        )


@dataclass(frozen=True, slots=True)
class EvaluationBatchResult:
    """Result of evaluating changed jobs from one source snapshot."""

    evaluated_jobs: tuple[
        EvaluatedJob,
        ...,
    ]

    alert_candidates: tuple[
        EvaluatedJob,
        ...,
    ]

    suppressed_jobs: tuple[
        EvaluatedJob,
        ...,
    ]

    @property
    def stale_suppressed_jobs(
        self,
    ) -> tuple[
        EvaluatedJob,
        ...,
    ]:
        """Return eligible jobs held back only by the freshness policy.

        These are surfaced separately because they are healthy inventory
        for the web application, not rejected jobs.
        """

        return tuple(
            item
            for item in self.suppressed_jobs
            if item.is_suppressed_as_stale
        )

    @property
    def stale_suppressed_count(self) -> int:
        """Number of eligible jobs suppressed by freshness only."""

        return len(
            self.stale_suppressed_jobs
        )

    @property
    def evaluated_count(self) -> int:
        """Number of jobs evaluated."""

        return len(
            self.evaluated_jobs
        )

    @property
    def alert_candidate_count(self) -> int:
        """Number of jobs continuing toward notification."""

        return len(
            self.alert_candidates
        )

    @property
    def suppressed_count(self) -> int:
        """Number of evaluated jobs suppressed from notification."""

        return len(
            self.suppressed_jobs
        )

    @property
    def pass_count(self) -> int:
        """Number of evaluated jobs with PASS eligibility."""

        return sum(
            1
            for item in self.evaluated_jobs
            if (
                item.eligibility.status
                == EligibilityStatus.PASS
            )
        )

    @property
    def stretch_count(self) -> int:
        """Number of evaluated jobs with STRETCH eligibility."""

        return sum(
            1
            for item in self.evaluated_jobs
            if (
                item.eligibility.status
                == EligibilityStatus.STRETCH
            )
        )

    @property
    def reject_count(self) -> int:
        """Number of evaluated jobs with REJECT eligibility."""

        return sum(
            1
            for item in self.evaluated_jobs
            if (
                item.eligibility.status
                == EligibilityStatus.REJECT
            )
        )