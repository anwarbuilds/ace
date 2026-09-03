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
    durably enqueue notification candidates
        ↓
    COMMIT

External network fetching deliberately happens before the database
transaction.

SMTP delivery deliberately happens after this service returns and is
owned by the notification-delivery worker.
"""

from contextlib import (
    AbstractContextManager,
)
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import (
    Session,
)

from backend.app.notifications.outbox import (
    OutboxEnqueueResult,
    SqlAlchemyNotificationOutboxRepository,
    enqueue_alert_candidates,
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

    workflow: SourceSnapshotWorkflowResult

    outbox: OutboxEnqueueResult

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
        """Return the number of changed jobs evaluated."""

        return (
            self.workflow
            .evaluation
            .evaluated_count
        )

    @property
    def alert_candidate_count(
        self,
    ) -> int:
        """Return the number of notification-ready jobs."""

        return (
            self.workflow
            .evaluation
            .alert_candidate_count
        )

    @property
    def queued_notification_count(
        self,
    ) -> int:
        """Return newly persisted notification count."""

        return (
            self.outbox
            .queued_count
        )


def _empty_outbox_result() -> (
    OutboxEnqueueResult
):
    """Return the canonical result when no alerts require enqueueing."""

    return OutboxEnqueueResult(
        candidate_count=0,
        queued_count=0,
        duplicate_count=0,
    )


def _require_notification_recipient(
    recipient: str | None,
) -> str:
    """Require a recipient only when a poll produces alert candidates."""

    if recipient is None:
        raise ValueError(
            (
                "notification_recipient must "
                "be configured when alert "
                "candidates exist."
            )
        )

    normalized = recipient.strip()

    if not normalized:
        raise ValueError(
            (
                "notification_recipient must "
                "be configured when alert "
                "candidates exist."
            )
        )

    return normalized


def poll_source_once(
    *,
    source: SourceDefinition,
    fetcher: SourceSnapshotFetcher,
    transaction_factory: TransactionFactory,
    notification_recipient: str | None,
) -> SourcePollResult:
    """Fetch and transactionally process one configured source.

    Network fetching happens before opening the database transaction.

    Once the transaction begins, source reconciliation, deterministic
    evaluation, and durable notification enqueueing are treated as one
    atomic unit.

    If notification enqueueing fails, lifecycle persistence rolls back.

    If an alert candidate exists but notification configuration is
    missing, lifecycle persistence also rolls back. This prevents ACE
    from marking a job as already observed while silently losing the
    corresponding alert.

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
            )
        )

        alert_candidates = (
            workflow_result
            .evaluation
            .alert_candidates
        )

        if not alert_candidates:
            outbox_result = (
                _empty_outbox_result()
            )

        else:
            recipient = (
                _require_notification_recipient(
                    notification_recipient
                )
            )

            outbox_repository = (
                SqlAlchemyNotificationOutboxRepository(
                    session
                )
            )

            outbox_result = (
                enqueue_alert_candidates(
                    outbox_repository,
                    candidates=(
                        alert_candidates
                    ),
                    source_account=(
                        fetched_snapshot
                        .source_account
                    ),
                    recipient=recipient,
                    detected_at=(
                        fetched_snapshot
                        .detected_at
                    ),
                )
            )

    return SourcePollResult(
        fetched_snapshot=(
            fetched_snapshot
        ),
        workflow=workflow_result,
        outbox=outbox_result,
    )