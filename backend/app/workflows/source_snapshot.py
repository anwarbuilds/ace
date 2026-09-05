"""End-to-end source snapshot workflow for ACE.

This module coordinates persistence and evaluation without owning the
database transaction itself.

Transaction ownership remains with the caller so that adapters, workers,
scheduled jobs, API handlers, and tests can choose the appropriate
transaction boundary.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.app.evaluation.service import (
    evaluate_snapshot,
)
from backend.app.evaluation.types import (
    EvaluationBatchResult,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.service import (
    SnapshotRepository,
    process_snapshot,
)
from backend.app.persistence.types import (
    SnapshotResult,
)


@dataclass(frozen=True, slots=True)
class SourceSnapshotWorkflowResult:
    """Complete result of processing one source snapshot."""

    snapshot: SnapshotResult

    evaluation: EvaluationBatchResult

    @property
    def alert_candidate_count(self) -> int:
        """Return the number of jobs continuing toward notification."""

        return self.evaluation.alert_candidate_count

    @property
    def suppressed_count(self) -> int:
        """Return the number of evaluated jobs suppressed from alerts."""

        return self.evaluation.suppressed_count

    @property
    def stale_suppressed_count(self) -> int:
        """Return eligible jobs held back only by freshness policy."""

        return (
            self.evaluation
            .stale_suppressed_count
        )


def run_source_snapshot_workflow(
    repository: SnapshotRepository,
    *,
    source: str,
    source_account: str,
    jobs: Sequence[CanonicalJob],
    observed_at: datetime | None = None,
    freshness_policy: FreshnessPolicy | None = None,
) -> SourceSnapshotWorkflowResult:
    """Persist and evaluate one complete source snapshot.

    Processing order is deliberately:

        normalize upstream
            ↓
        persist full snapshot
            ↓
        detect source lifecycle changes
            ↓
        evaluate only changed jobs
            ↓
        apply alert freshness policy

    Persistence determines WHAT changed.

    Evaluation determines whether changed jobs are relevant and eligible.

    Freshness determines whether an eligible change is worth an
    interruption. Jobs suppressed by freshness remain fully persisted.

    Notification is intentionally not performed here.
    """

    snapshot = process_snapshot(
        repository,
        source=source,
        source_account=source_account,
        jobs=jobs,
        observed_at=observed_at,
    )

    evaluation = evaluate_snapshot(
        snapshot,
        freshness_policy=(
            freshness_policy
        ),
    )

    return SourceSnapshotWorkflowResult(
        snapshot=snapshot,
        evaluation=evaluation,
    )