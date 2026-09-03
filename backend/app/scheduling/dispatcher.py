"""Provider dispatch for ACE scheduled source fetching.

This layer converts provider-specific source execution into a common
FetchedSourceSnapshot.

It intentionally performs no database, evaluation, outbox, or email
work. Those responsibilities belong to later orchestration layers.
"""

from collections.abc import Mapping
from typing import Protocol

from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
)
from backend.app.adapters.lever import (
    fetch_lever_jobs,
)
from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.runners.greenhouse import (
    Clock,
    GreenhouseFetcher,
    fetch_live_greenhouse_snapshot,
    utc_now,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
    SourceType,
)


class SourceFetchHandler(Protocol):
    """Callable capable of fetching one configured source."""

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch and normalize one source snapshot."""


class LeverFetcher(Protocol):
    """Callable capable of fetching one Lever source."""

    def __call__(
        self,
        *,
        source_account: str,
        company_name: str,
        source_host: str | None,
    ) -> list[CanonicalJob]:
        """Fetch and normalize one Lever board."""


class UnsupportedSourceTypeError(
    LookupError
):
    """Raised when no fetch handler exists for a source type."""


class GreenhouseSourceFetcher:
    """Dispatch adapter for Greenhouse-backed source definitions."""

    def __init__(
        self,
        *,
        fetcher: GreenhouseFetcher = (
            fetch_greenhouse_jobs
        ),
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one Greenhouse source through the existing runner."""

        if (
            source.source_type
            != SourceType.GREENHOUSE
        ):
            raise ValueError(
                (
                    "GreenhouseSourceFetcher "
                    "requires a GREENHOUSE "
                    "SourceDefinition."
                )
            )

        live_snapshot = (
            fetch_live_greenhouse_snapshot(
                board_token=(
                    source.source_account
                ),
                company_name=(
                    source.company_name
                ),
                fetcher=self._fetcher,
                clock=self._clock,
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=(
                live_snapshot.detected_at
            ),
            jobs=live_snapshot.jobs,
        )


class LeverSourceFetcher:
    """Dispatch adapter for Lever-backed source definitions."""

    def __init__(
        self,
        *,
        fetcher: LeverFetcher = (
            fetch_lever_jobs
        ),
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one Lever source using its configured region host."""

        if (
            source.source_type
            != SourceType.LEVER
        ):
            raise ValueError(
                (
                    "LeverSourceFetcher "
                    "requires a LEVER "
                    "SourceDefinition."
                )
            )

        jobs = self._fetcher(
            source_account=(
                source.source_account
            ),
            company_name=(
                source.company_name
            ),
            source_host=(
                source.source_host
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=(
                self._clock()
            ),
            jobs=tuple(
                jobs
            ),
        )


class SourceDispatcher:
    """Dispatch configured sources to provider-specific fetch handlers."""

    def __init__(
        self,
        handlers: Mapping[
            SourceType,
            SourceFetchHandler,
        ],
    ) -> None:
        self._handlers = dict(
            handlers
        )

    @property
    def supported_source_types(
        self,
    ) -> frozenset[
        SourceType
    ]:
        """Return source types currently supported by this dispatcher."""

        return frozenset(
            self._handlers
        )

    def fetch(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one configured source using its registered handler."""

        try:
            handler = self._handlers[
                source.source_type
            ]

        except KeyError as exc:
            raise UnsupportedSourceTypeError(
                (
                    "No source fetch handler "
                    "registered for "
                    f"{source.source_type.value!r}."
                )
            ) from exc

        result = handler(
            source
        )

        if (
            result.source_definition
            != source
        ):
            raise ValueError(
                (
                    "Source fetch handler returned "
                    "a snapshot for a different "
                    "source definition."
                )
            )

        return result


def build_default_source_dispatcher() -> (
    SourceDispatcher
):
    """Build the production dispatcher for currently supported sources."""

    return SourceDispatcher(
        {
            SourceType.GREENHOUSE: (
                GreenhouseSourceFetcher()
            ),
            SourceType.LEVER: (
                LeverSourceFetcher()
            ),
        }
    )