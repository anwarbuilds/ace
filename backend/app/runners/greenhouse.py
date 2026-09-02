"""Live Greenhouse source runner for ACE.

This module bridges live Greenhouse ingestion with ACE's existing
source-snapshot persistence and evaluation workflow.

Network I/O is intentionally completed before the database transaction
begins. This avoids keeping a PostgreSQL transaction open while waiting
for an external HTTP request.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.service import (
    SnapshotRepository,
)
from backend.app.workflows.source_snapshot import (
    SourceSnapshotWorkflowResult,
    run_source_snapshot_workflow,
)


GreenhouseFetcher = Callable[
    [str, str],
    list[CanonicalJob],
]

Clock = Callable[
    [],
    datetime,
]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(
        timezone.utc
    )


@dataclass(frozen=True, slots=True)
class GreenhouseLiveSnapshot:
    """One live Greenhouse board observation before persistence."""

    board_token: str

    company_name: str

    detected_at: datetime

    jobs: tuple[
        CanonicalJob,
        ...,
    ]

    @property
    def source(self) -> str:
        """Return the canonical ACE source identifier."""

        return "greenhouse"

    @property
    def source_account(self) -> str:
        """Return the durable account identifier for this source."""

        return self.board_token

    @property
    def job_count(self) -> int:
        """Return the number of jobs returned by the live board."""

        return len(
            self.jobs
        )


def _require_non_empty(
    value: str,
    *,
    field_name: str,
) -> str:
    """Normalize and validate a required string value."""

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def _require_aware_datetime(
    value: datetime,
) -> datetime:
    """Validate and normalize a datetime to UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            (
                "ACE detection timestamps "
                "must be timezone-aware."
            )
        )

    return value.astimezone(
        timezone.utc
    )


def fetch_live_greenhouse_snapshot(
    *,
    board_token: str,
    company_name: str,
    fetcher: GreenhouseFetcher = fetch_greenhouse_jobs,
    clock: Clock = utc_now,
) -> GreenhouseLiveSnapshot:
    """Fetch one live Greenhouse board snapshot.

    The detection timestamp is captured after the external fetch
    completes. This timestamp represents when ACE successfully observed
    the returned source state.

    Database work is deliberately not performed here.
    """

    normalized_board_token = (
        _require_non_empty(
            board_token,
            field_name="board_token",
        )
    )

    normalized_company_name = (
        _require_non_empty(
            company_name,
            field_name="company_name",
        )
    )

    jobs = fetcher(
        normalized_board_token,
        normalized_company_name,
    )

    detected_at = (
        _require_aware_datetime(
            clock()
        )
    )

    return GreenhouseLiveSnapshot(
        board_token=(
            normalized_board_token
        ),
        company_name=(
            normalized_company_name
        ),
        detected_at=detected_at,
        jobs=tuple(
            jobs
        ),
    )


def process_live_greenhouse_snapshot(
    repository: SnapshotRepository,
    *,
    snapshot: GreenhouseLiveSnapshot,
) -> SourceSnapshotWorkflowResult:
    """Persist and evaluate one fetched live Greenhouse snapshot."""

    return run_source_snapshot_workflow(
        repository,
        source=snapshot.source,
        source_account=(
            snapshot.source_account
        ),
        jobs=snapshot.jobs,
        observed_at=(
            snapshot.detected_at
        ),
    )