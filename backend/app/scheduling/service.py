"""Transactional single-source polling orchestration for ACE.

This module coordinates one complete source poll while preserving clear
failure and transaction boundaries.

Execution order:

    external source fetch
        ↓
    BEGIN database transaction
        ↓
    persist source/job lifecycle
        ↓
    evaluate changed jobs
        ↓
    materialize evaluation for the web read model
        ↓
    COMMIT

External network fetching deliberately happens before the database
transaction.

ACE has no delivery step. The web application is the only surface, so a
poll's job ends once the database reflects what the source published.
"""

from contextlib import (
    AbstractContextManager,
)
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import (
    Session,
)

from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.app.persistence.evaluations import (
    record_job_evaluations,
)
from backend.app.persistence.repository import (
    JobRepository,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
)
from backend.app.workflows.source_snapshot import (
    SourceSnapshotWorkflowResult,
    run_source_snapshot_workflow,
)


class SourceSnapshotFetcher(Protocol):
    """Provider-neutral source-fetch contract used by the poll service."""

    def fetch(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one configured source."""


class TransactionFactory(Protocol):
    """Factory capable of creating one managed database transaction."""

    def begin(
        self,
    ) -> AbstractContextManager[
        Session
    ]:
        """Return a context manager owning one database transaction."""


@dataclass(
    frozen=True,
    slots=True,
)
class SourcePollResult:
    """Complete result of one ACE source poll."""

    fetched_snapshot: FetchedSourceSnapshot

    workflow: SourceSnapshotWorkflowResult | None

    @property
    def source_definition(
        self,
    ) -> SourceDefinition:
        """Return the source configuration used for this poll."""

        return (
            self.fetched_snapshot
            .source_definition
        )

    @property
    def fetched_count(
        self,
    ) -> int:
        """Return the number of upstream jobs fetched."""

        return (
            self.fetched_snapshot
            .job_count
        )

    @property
    def evaluated_count(
        self,
    ) -> int:
        """Return the number of changed jobs evaluated.

        Zero for an unchanged snapshot: there was nothing to evaluate.
        """

        if self.workflow is None:
            return 0

        return (
            self.workflow
            .evaluation
            .evaluated_count
        )

    @property
    def alert_candidate_count(
        self,
    ) -> int:
        """Return the number of jobs that passed every rule."""

        if self.workflow is None:
            return 0

        return (
            self.workflow
            .evaluation
            .alert_candidate_count
        )


    @property
    def stale_suppressed_count(
        self,
    ) -> int:
        """Return eligible jobs held back only by freshness policy."""

        if self.workflow is None:
            return 0

        return (
            self.workflow
            .stale_suppressed_count
        )




def poll_source_once(
    *,
    source: SourceDefinition,
    fetcher: SourceSnapshotFetcher,
    transaction_factory: TransactionFactory,
    freshness_policy: FreshnessPolicy | None = None,
) -> SourcePollResult:
    """Fetch and transactionally process one configured source.

    Network fetching happens before opening the database transaction.

    Once the transaction begins, source reconciliation, deterministic
    evaluation, and the materialized read model are treated as one
    atomic unit.

    The snapshot's own detected_at is used as the deterministic
    freshness reference instant, so a poll's alert decisions do not
    depend on how long the transaction itself takes.

    SMTP delivery is intentionally not performed here.
    """

    fetched_snapshot = (
        fetcher.fetch(
            source
        )
    )

    with (
        transaction_factory.begin()
        as session
    ):
        job_repository = (
            JobRepository(
                session
            )
        )

        # A provider that answered "not modified" is byte-identical to
        # last time, so there is nothing to diff. Only the success
        # markers move.
        if fetched_snapshot.unchanged:
            job_repository.record_source_unchanged(
                source=(
                    fetched_snapshot.source
                ),
                source_account=(
                    fetched_snapshot
                    .source_account
                ),
                observed_at=(
                    fetched_snapshot
                    .detected_at
                ),
            )

            return SourcePollResult(
                fetched_snapshot=(
                    fetched_snapshot
                ),
                workflow=None,
            )

        workflow_result = (
            run_source_snapshot_workflow(
                job_repository,
                source=(
                    fetched_snapshot
                    .source
                ),
                source_account=(
                    fetched_snapshot
                    .source_account
                ),
                jobs=(
                    fetched_snapshot
                    .jobs
                ),
                observed_at=(
                    fetched_snapshot
                    .detected_at
                ),
                freshness_policy=(
                    freshness_policy
                ),
            )
        )

        # Materialize eligibility for the web application inside the
        # same transaction that persisted the lifecycle, so the read
        # model can never disagree with what ACE actually decided.
        record_job_evaluations(
            session,
            source=(
                fetched_snapshot.source
            ),
            source_account=(
                fetched_snapshot
                .source_account
            ),
            evaluated_jobs=(
                workflow_result
                .evaluation
                .evaluated_jobs
            ),
            evaluated_at=(
                fetched_snapshot
                .detected_at
            ),
        )

        job_repository.record_http_validators(
            source=(
                fetched_snapshot.source
            ),
            source_account=(
                fetched_snapshot
                .source_account
            ),
            etag=fetched_snapshot.etag,
            last_modified=(
                fetched_snapshot
                .last_modified
            ),
            observed_at=(
                fetched_snapshot
                .detected_at
            ),
        )

    return SourcePollResult(
        fetched_snapshot=(
            fetched_snapshot
        ),
        workflow=workflow_result,
    )