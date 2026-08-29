"""Shared persistence-domain types for ACE."""

from dataclasses import dataclass
from enum import Enum

from backend.app.models.job import CanonicalJob


class JobObservationStatus(str, Enum):
    """Result of comparing an observed job with persistent state."""

    NEW = "NEW"
    UPDATED = "UPDATED"
    REOPENED = "REOPENED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    """Summary of processing one complete source snapshot."""

    source: str
    source_account: str

    is_baseline: bool

    fetched_count: int
    unique_count: int
    duplicate_count: int

    new_jobs: tuple[CanonicalJob, ...]
    updated_jobs: tuple[CanonicalJob, ...]
    reopened_jobs: tuple[CanonicalJob, ...]

    unchanged_count: int
    closed_count: int

    evaluation_candidates: tuple[CanonicalJob, ...]

    @property
    def new_count(self) -> int:
        """Number of previously unseen jobs."""

        return len(self.new_jobs)

    @property
    def updated_count(self) -> int:
        """Number of jobs whose meaningful content changed."""

        return len(self.updated_jobs)

    @property
    def reopened_count(self) -> int:
        """Number of previously closed jobs that appeared again."""

        return len(self.reopened_jobs)

    @property
    def evaluation_candidate_count(self) -> int:
        """Number of changed jobs requiring downstream reevaluation."""

        return len(self.evaluation_candidates)