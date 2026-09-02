"""Domain types produced by the ACE evaluation pipeline."""

from dataclasses import dataclass
from enum import Enum

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


@dataclass(frozen=True, slots=True)
class EvaluatedJob:
    """One changed job together with its eligibility evaluation."""

    job: CanonicalJob

    observation_status: JobObservationStatus

    eligibility: EligibilityDecision

    alert_disposition: AlertDisposition

    @property
    def is_alert_candidate(self) -> bool:
        """Return whether this job should continue to notification."""

        return (
            self.alert_disposition
            == AlertDisposition.ALERT
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