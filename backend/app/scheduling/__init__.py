"""Scheduling primitives for ACE automatic source monitoring."""

from backend.app.scheduling.catalog import (
    SqlAlchemySourceCatalogRepository,
    build_source_registry_from_records,
    load_source_registry,
)
from backend.app.scheduling.dispatcher import (
    GreenhouseSourceFetcher,
    SourceDispatcher,
    SourceFetchHandler,
    UnsupportedSourceTypeError,
    build_default_source_dispatcher,
)
from backend.app.scheduling.registry import (
    SourceRegistry,
    build_default_source_registry,
)
from backend.app.scheduling.runtime import (
    SchedulerCycleResult,
    SchedulerRuntime,
    SourcePollFailure,
    SourcePollSuccess,
    SourcePoller,
)
from backend.app.scheduling.service import (
    SourcePollResult,
    SourceSnapshotFetcher,
    TransactionFactory,
    poll_source_once,
)
from backend.app.scheduling.types import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    FetchedSourceSnapshot,
    SourceDefinition,
    SourceType,
)


__all__ = [
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "FetchedSourceSnapshot",
    "GreenhouseSourceFetcher",
    "SchedulerCycleResult",
    "SchedulerRuntime",
    "SourceDefinition",
    "SourceDispatcher",
    "SourceFetchHandler",
    "SourcePollFailure",
    "SourcePollResult",
    "SourcePollSuccess",
    "SourcePoller",
    "SourceRegistry",
    "SourceSnapshotFetcher",
    "SourceType",
    "SqlAlchemySourceCatalogRepository",
    "TransactionFactory",
    "UnsupportedSourceTypeError",
    "build_default_source_dispatcher",
    "build_default_source_registry",
    "build_source_registry_from_records",
    "load_source_registry",
    "poll_source_once",
]