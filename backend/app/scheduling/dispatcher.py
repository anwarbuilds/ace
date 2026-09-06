"""Provider dispatch for ACE scheduled source fetching.

This layer converts provider-specific source execution into a common
FetchedSourceSnapshot.

It intentionally performs no database, evaluation, outbox, or email
work. Those responsibilities belong to later orchestration layers.
"""

from collections.abc import (
    Callable,
    Mapping,
)
from datetime import timedelta
from typing import Protocol

from backend.app.adapters.ashby import (
    fetch_ashby_jobs,
)
from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
)
from backend.app.adapters.lever import (
    fetch_lever_jobs,
)
from backend.app.adapters.smartrecruiters import (
    fetch_smartrecruiters_jobs,
)
from backend.app.adapters.eightfold import (
    fetch_eightfold_jobs,
)
from backend.app.adapters.amazon import (
    fetch_amazon_jobs,
)
from backend.app.adapters.simplify import (
    fetch_simplify_jobs,
)
from backend.app.adapters.workday import (
    fetch_workday_jobs,
)
from backend.app.adapters.http_cache import (
    CacheValidators,
)
from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.runners.prefilter import (
    build_detail_predicate,
)
from backend.app.runners.clock import (
    Clock,
    utc_now,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
    SourceType,
)


ValidatorLookup = Callable[
    [
        "SourceDefinition",
    ],
    CacheValidators,
]


class SourceFetchHandler(Protocol):
    """Callable capable of fetching one configured source."""

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch and normalize one source snapshot."""


class ConditionalFetchResult(Protocol):
    """What a conditional adapter returns.

    Three values rather than one: the jobs, whether the provider said
    nothing had changed, and the validators to replay next poll.
    """


class GreenhouseFetcher(Protocol):
    """Callable capable of fetching one Greenhouse board."""

    def __call__(
        self,
        board_token: str,
        company_name: str,
        *,
        validators: CacheValidators | None = None,
    ) -> tuple[
        list[CanonicalJob],
        bool,
        CacheValidators,
    ]:
        """Fetch and normalize one Greenhouse board."""


class AshbyFetcher(Protocol):
    """Callable capable of fetching one Ashby source."""

    def __call__(
        self,
        board_name: str,
        company_name: str,
        *,
        validators: CacheValidators | None = None,
    ) -> tuple[
        list[CanonicalJob],
        bool,
        CacheValidators,
    ]:
        """Fetch and normalize one Ashby board."""


class SmartRecruitersFetcher(Protocol):
    """Callable capable of fetching one SmartRecruiters source."""

    def __call__(
        self,
        company_identifier: str,
        company_name: str,
        should_fetch_detail=None,
        *,
        validators: CacheValidators | None = None,
    ) -> tuple[
        list[CanonicalJob],
        bool,
        CacheValidators,
    ]:
        """Fetch and normalize one SmartRecruiters company."""


class LeverFetcher(Protocol):
    """Callable capable of fetching one Lever source."""

    def __call__(
        self,
        *,
        source_account: str,
        company_name: str,
        source_host: str | None,
        validators: CacheValidators | None = None,
    ) -> tuple[
        list[CanonicalJob],
        bool,
        CacheValidators,
    ]:
        """Fetch and normalize one Lever board."""


class WorkdayFetcher(Protocol):
    """Callable capable of fetching one Workday tenant."""

    def __call__(
        self,
        *,
        source_account: str,
        company_name: str,
        source_host: str | None,
        should_fetch_detail,
    ) -> list[CanonicalJob]:
        """Fetch and normalize one Workday tenant."""


class AmazonFetcher(Protocol):
    """Callable capable of fetching Amazon postings."""

    def __call__(
        self,
        *,
        company_name: str,
    ) -> list[CanonicalJob]:
        """Fetch and normalize recent Amazon postings."""


class EightfoldFetcher(Protocol):
    """Callable capable of fetching one Eightfold career site."""

    def __call__(
        self,
        tenant_host: str,
        company_name: str,
        *,
        domain: str | None = None,
        should_fetch_detail=None,
    ) -> list[CanonicalJob]:
        """Fetch and normalize one Eightfold tenant."""


class SimplifyFetcher(Protocol):
    """Callable capable of fetching one curated listing feed."""

    def __call__(
        self,
        *,
        source_account: str,
        company_name: str,
        validators: CacheValidators | None = None,
    ) -> tuple[
        list[CanonicalJob],
        bool,
        CacheValidators,
    ]:
        """Fetch a feed, reporting whether it changed."""


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
        validator_lookup: (
            ValidatorLookup | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

    def _validators(
        self,
        source: SourceDefinition,
    ):
        """Return the validators remembered for this source."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if self._validator_lookup is None:
            return CacheValidators()

        return self._validator_lookup(
            source
        )

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

        jobs, unchanged, validators = (
            self._fetcher(
                source.source_account,
                source.company_name,
                validators=self._validators(
                    source
                ),
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            unchanged=unchanged,
            etag=validators.etag,
            last_modified=(
                validators.last_modified
            ),
        )


class AshbySourceFetcher:
    """Dispatch adapter for Ashby-backed source definitions."""

    def __init__(
        self,
        *,
        fetcher: AshbyFetcher = (
            fetch_ashby_jobs
        ),
        clock: Clock = utc_now,
        validator_lookup: (
            ValidatorLookup | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

    def _validators(
        self,
        source: SourceDefinition,
    ):
        """Return the validators remembered for this source."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if self._validator_lookup is None:
            return CacheValidators()

        return self._validator_lookup(
            source
        )

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one configured Ashby source."""

        if (
            source.source_type
            != SourceType.ASHBY
        ):
            raise ValueError(
                (
                    "AshbySourceFetcher "
                    "requires an ASHBY "
                    "SourceDefinition."
                )
            )

        jobs, unchanged, validators = (
            self._fetcher(
                source.source_account,
                source.company_name,
                validators=self._validators(
                    source
                ),
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            unchanged=unchanged,
            etag=validators.etag,
            last_modified=(
                validators.last_modified
            ),
        )


class SmartRecruitersSourceFetcher:
    """Dispatch adapter for SmartRecruiters-backed sources."""

    def __init__(
        self,
        *,
        fetcher: SmartRecruitersFetcher = (
            fetch_smartrecruiters_jobs
        ),
        clock: Clock = utc_now,
        validator_lookup: (
            ValidatorLookup | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

    def _validators(
        self,
        source: SourceDefinition,
    ):
        """Return the validators remembered for this source."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if self._validator_lookup is None:
            return CacheValidators()

        return self._validator_lookup(
            source
        )

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one configured SmartRecruiters source."""

        if (
            source.source_type
            != SourceType.SMARTRECRUITERS
        ):
            raise ValueError(
                (
                    "SmartRecruitersSourceFetcher "
                    "requires a SMARTRECRUITERS "
                    "SourceDefinition."
                )
            )

        jobs, unchanged, validators = (
            self._fetcher(
                source.source_account,
                source.company_name,
                should_fetch_detail=(
                    build_detail_predicate(
                        source=(
                            "smartrecruiters"
                        ),
                        company_name=(
                            source.company_name
                        ),
                    )
                ),
                validators=self._validators(
                    source
                ),
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            unchanged=unchanged,
            etag=validators.etag,
            last_modified=(
                validators.last_modified
            ),
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
        validator_lookup: (
            ValidatorLookup | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

    def _validators(
        self,
        source: SourceDefinition,
    ):
        """Return the validators remembered for this source."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if self._validator_lookup is None:
            return CacheValidators()

        return self._validator_lookup(
            source
        )

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

        jobs, unchanged, validators = (
            self._fetcher(
                source_account=(
                    source.source_account
                ),
                company_name=(
                    source.company_name
                ),
                source_host=(
                    source.source_host
                ),
                validators=self._validators(
                    source
                ),
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=(
                self._clock()
            ),
            jobs=tuple(
                jobs
            ),
            unchanged=unchanged,
            etag=validators.etag,
            last_modified=(
                validators.last_modified
            ),
        )


class WorkdaySourceFetcher:
    """Dispatch adapter for Workday-backed source definitions."""

    def __init__(
        self,
        *,
        fetcher: WorkdayFetcher = (
            fetch_workday_jobs
        ),
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one Workday tenant.

        The detail predicate is supplied here rather than inside the
        adapter, keeping provider code free of eligibility knowledge.
        """

        if (
            source.source_type
            != SourceType.WORKDAY
        ):
            raise ValueError(
                (
                    "WorkdaySourceFetcher "
                    "requires a WORKDAY "
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
            should_fetch_detail=(
                build_detail_predicate(
                    source="workday",
                    company_name=(
                        source.company_name
                    ),
                )
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class AmazonSourceFetcher:
    """Dispatch adapter for Amazon's public search endpoint.

    Amazon is a search index rather than an employer board, so the
    source_account carries no provider identity; it exists only to give
    the catalog a stable key.
    """

    def __init__(
        self,
        *,
        fetcher: AmazonFetcher = (
            fetch_amazon_jobs
        ),
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch recent Amazon postings."""

        if (
            source.source_type
            != SourceType.AMAZON
        ):
            raise ValueError(
                (
                    "AmazonSourceFetcher "
                    "requires an AMAZON "
                    "SourceDefinition."
                )
            )

        jobs = self._fetcher(
            company_name=(
                source.company_name
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class EightfoldSourceFetcher:
    """Dispatch adapter for Eightfold-hosted career sites.

    Descriptions live behind a per-posting request, so the gate is run
    on titles first and only survivors earn one. On Netflix that is 79
    of 501, which is the difference between one poll and five hundred
    extra requests against someone else's server.
    """

    def __init__(
        self,
        *,
        fetcher: EightfoldFetcher = (
            fetch_eightfold_jobs
        ),
        clock: Clock = utc_now,
        predicate_factory=None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._predicate_factory = (
            predicate_factory
        )

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one Eightfold tenant."""

        if (
            source.source_type
            != SourceType.EIGHTFOLD
        ):
            raise ValueError(
                (
                    "EightfoldSourceFetcher "
                    "requires an EIGHTFOLD "
                    "SourceDefinition."
                )
            )

        predicate = None

        if self._predicate_factory is not None:
            predicate = (
                self._predicate_factory(
                    source=(
                        SourceType.EIGHTFOLD
                        .value
                    ),
                    company_name=(
                        source.company_name
                    ),
                )
            )

        jobs = self._fetcher(
            source.source_host
            or source.source_account,
            source.company_name,
            domain=source.source_account,
            should_fetch_detail=predicate,
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class SimplifySourceFetcher:
    """Dispatch adapter for the curated new-grad feed.

    This lane spans many employers rather than one, so company identity
    comes from each entry rather than from the source definition.

    These feeds are the catalog's largest download, so the HTTP
    validators from the previous poll are replayed and an unchanged feed
    costs one 304 with no body.
    """

    def __init__(
        self,
        *,
        fetcher: SimplifyFetcher = (
            fetch_simplify_jobs
        ),
        clock: Clock = utc_now,
        validator_lookup: (
            ValidatorLookup | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

    def _validators(
        self,
        source: SourceDefinition,
    ):
        """Return the validators remembered for this source."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if self._validator_lookup is None:
            return CacheValidators()

        return self._validator_lookup(
            source
        )

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one curated listing feed."""

        if (
            source.source_type
            != SourceType.SIMPLIFY
        ):
            raise ValueError(
                (
                    "SimplifySourceFetcher "
                    "requires a SIMPLIFY "
                    "SourceDefinition."
                )
            )

        jobs, unchanged, validators = (
            self._fetcher(
                source_account=(
                    source.source_account
                ),
                company_name=(
                    source.company_name
                ),
                validators=(
                    self._validators(
                        source
                    )
                ),
            )
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            unchanged=unchanged,
            etag=validators.etag,
            last_modified=(
                validators.last_modified
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


# How long a source may go without an unconditional fetch. Bounds how
# long a stale validator could hide real changes.
FULL_REFETCH_INTERVAL = timedelta(
    hours=6
)


def _stored_validators(
    source: SourceDefinition,
):
    """Load the HTTP validators remembered for one source.

    Read in its own short session, outside any poll transaction, so a
    lookup can never hold a connection while the network is slow.

    Returns nothing when the source is due a full fetch, which forces an
    unconditional request and re-establishes the truth.
    """

    from backend.app.adapters.http_cache import (
        CacheValidators,
    )
    from backend.app.db.session import (
        SessionLocal,
    )
    from backend.app.persistence.repository import (
        JobRepository,
    )

    with SessionLocal() as session:
        etag, last_modified = (
            JobRepository(
                session
            ).get_http_validators(
                source=(
                    source.source_type.value
                ),
                source_account=(
                    source.source_account
                ),
                force_full_fetch_after=(
                    FULL_REFETCH_INTERVAL
                ),
            )
        )

    return CacheValidators(
        etag=etag,
        last_modified=last_modified,
    )


def build_default_source_dispatcher() -> (
    SourceDispatcher
):
    """Build the production dispatcher for currently supported sources."""

    return SourceDispatcher(
        {
            SourceType.ASHBY: (
                AshbySourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
            SourceType.GREENHOUSE: (
                GreenhouseSourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
            SourceType.LEVER: (
                LeverSourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
            SourceType.SMARTRECRUITERS: (
                SmartRecruitersSourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
            SourceType.WORKDAY: (
                WorkdaySourceFetcher()
            ),
            SourceType.AMAZON: (
                AmazonSourceFetcher()
            ),
            SourceType.EIGHTFOLD: (
                EightfoldSourceFetcher(
                    predicate_factory=(
                        build_detail_predicate
                    )
                )
            ),
            SourceType.SIMPLIFY: (
                SimplifySourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
        }
    )