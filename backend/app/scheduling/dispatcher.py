"""Provider dispatch for ACE scheduled source fetching.

This layer converts provider-specific source execution into a common
FetchedSourceSnapshot.

It intentionally performs no database, evaluation, outbox, or email
work. Those responsibilities belong to later orchestration layers.
"""

from collections.abc import (
    Callable,
    Mapping,
    Sequence,
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
from backend.app.adapters.eightfold_pcsx import (
    fetch_eightfold_pcsx_jobs,
)
from backend.app.coverage.benchmark import (
    company_keys,
)
from backend.app.adapters.amazon import (
    fetch_amazon_jobs,
)
from backend.app.adapters.avature import (
    fetch_avature_jobs,
)
from backend.app.adapters.bytedance import (
    fetch_bytedance_jobs,
)
from backend.app.adapters.oracle_recruiting import (
    fetch_oracle_recruiting_jobs,
)
from backend.app.adapters.workable import (
    fetch_workable_jobs,
)
from backend.app.adapters.ibm import (
    fetch_ibm_jobs,
)
from backend.app.adapters.atlassian import (
    fetch_atlassian_jobs,
)
from backend.app.adapters.apple import (
    fetch_apple_jobs,
)
from backend.app.adapters.shopify import (
    fetch_shopify_jobs,
)
from backend.app.verification.employer_page import (
    EmployerPageVerifier,
)
from backend.app.adapters.ripplematch import (
    fetch_ripplematch_jobs,
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


class EightfoldPcsxFetcher(Protocol):
    """Callable capable of fetching one Eightfold PCSX career site."""

    def __call__(
        self,
        tenant_host: str,
        company_name: str,
        *,
        domain: str | None = None,
        should_fetch_detail=None,
    ) -> list[CanonicalJob]:
        """Fetch and normalize one Eightfold PCSX tenant."""


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
            # A tenant too large for Workday's search to return whole,
            # and with no facet to split it by, is read in part.
            complete=getattr(
                jobs,
                "complete",
                True,
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


class RippleMatchSourceFetcher:
    """Dispatch adapter for RippleMatch's public postings.

    Like the curated feed, this source spans many employers rather than
    one tenant, so ``source_account`` exists only to give the catalog a
    stable key and ``company_name`` is ignored -- each posting carries
    its own employer.

    Unconditional: the sitemap is served ``cache-control: no-cache``
    with no validator to replay, so there is nothing to send back and
    claiming otherwise would add a contract the source does not honour.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_ripplematch_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch every public RippleMatch posting."""

        if (
            source.source_type
            != SourceType.RIPPLEMATCH
        ):
            raise ValueError(
                (
                    "RippleMatchSourceFetcher "
                    "requires a RIPPLEMATCH "
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
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class ByteDanceSourceFetcher:
    """Dispatch adapter for ByteDance's and TikTok's own careers sites.

    ``source_account`` names the portal -- "bytedance" or "tiktok" --
    and the adapter knows each portal's API host and posting URL.
    Unconditional: the API is a POST search with no validators.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_bytedance_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch every posting on one portal."""

        if (
            source.source_type
            != SourceType.BYTEDANCE
        ):
            raise ValueError(
                (
                    "ByteDanceSourceFetcher "
                    "requires a BYTEDANCE "
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
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class OracleRecruitingSourceFetcher:
    """Dispatch adapter for Oracle Recruiting Cloud career sites.

    ``source_account`` is ``{host}/{siteNumber}``. Descriptions are
    fetched only for titles the gate could pass, and kept between polls
    in the shared reading store.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_oracle_recruiting_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch every posting on one career site."""

        if (
            source.source_type
            != SourceType.ORACLE_RECRUITING
        ):
            raise ValueError(
                (
                    "OracleRecruitingSourceFetcher "
                    "requires an ORACLE_RECRUITING "
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
            should_fetch_detail=(
                build_detail_predicate(
                    source="oracle_recruiting",
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


class WorkableSourceFetcher:
    """Dispatch adapter for apply.workable.com boards.

    ``source_account`` is the board's slug. Descriptions are fetched
    only for titles the gate could pass, and kept between polls in the
    shared reading store.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_workable_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch every posting on one board."""

        if (
            source.source_type
            != SourceType.WORKABLE
        ):
            raise ValueError(
                (
                    "WorkableSourceFetcher "
                    "requires a WORKABLE "
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
            should_fetch_detail=(
                build_detail_predicate(
                    source="workable",
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


class AtlassianSourceFetcher:
    """Dispatch adapter for the job list Atlassian's careers site loads.

    One request for the whole board, made conditional with the validators
    remembered from the last poll, so an unchanged list costs nothing.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_atlassian_jobs,
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

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch Atlassian's openings."""

        from backend.app.adapters.http_cache import (
            CacheValidators,
        )

        if (
            source.source_type
            != SourceType.ATLASSIAN
        ):
            raise ValueError(
                (
                    "AtlassianSourceFetcher "
                    "requires an ATLASSIAN "
                    "SourceDefinition."
                )
            )

        jobs, unchanged, validators = self._fetcher(
            validators=(
                self._validator_lookup(source)
                if self._validator_lookup is not None
                else CacheValidators()
            ),
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


class IbmSourceFetcher:
    """Dispatch adapter for IBM's careers search.

    Read newest first, in full every two hours and otherwise only as far
    as the last few days; a partial read is reported as one, so it
    closes nothing.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_ibm_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch IBM's openings."""

        if (
            source.source_type
            != SourceType.IBM
        ):
            raise ValueError(
                (
                    "IbmSourceFetcher "
                    "requires an IBM "
                    "SourceDefinition."
                )
            )

        jobs = self._fetcher(
            source_account=(
                source.source_account
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            complete=getattr(
                jobs,
                "complete",
                True,
            ),
        )


class AppleSourceFetcher:
    """Dispatch adapter for Apple's careers search.

    Read newest first, in full every four hours and otherwise only as
    far as the last two days; a partial read is reported as one, so it
    closes nothing. A posting's own page is read once: what ACE already
    holds for it is handed back to the reader.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_apple_jobs,
        known_lookup: (
            Callable[
                [SourceDefinition],
                dict[str, tuple[str, str]],
            ]
            | None
        ) = None,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._known_lookup = known_lookup
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch Apple's openings."""

        if (
            source.source_type
            != SourceType.APPLE
        ):
            raise ValueError(
                (
                    "AppleSourceFetcher "
                    "requires an APPLE "
                    "SourceDefinition."
                )
            )

        jobs = self._fetcher(
            source_account=(
                source.source_account
            ),
            should_fetch_detail=(
                build_detail_predicate(
                    source="apple",
                    company_name=(
                        source.company_name
                    ),
                )
            ),
            known=(
                self._known_lookup(source)
                if self._known_lookup is not None
                else None
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
            complete=getattr(
                jobs,
                "complete",
                True,
            ),
        )


class ShopifySourceFetcher:
    """Dispatch adapter for Shopify's careers page.

    One page carries every posting, so every read is complete. A
    posting's own page is read once: what ACE already holds for it is
    handed back to the reader.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_shopify_jobs,
        known_lookup: (
            Callable[
                [SourceDefinition],
                dict[str, tuple[str, str]],
            ]
            | None
        ) = None,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._known_lookup = known_lookup
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch Shopify's openings."""

        if (
            source.source_type
            != SourceType.SHOPIFY
        ):
            raise ValueError(
                (
                    "ShopifySourceFetcher "
                    "requires a SHOPIFY "
                    "SourceDefinition."
                )
            )

        jobs = self._fetcher(
            should_fetch_detail=(
                build_detail_predicate(
                    source="shopify",
                    company_name=(
                        source.company_name
                    ),
                )
            ),
            known=(
                self._known_lookup(source)
                if self._known_lookup is not None
                else None
            ),
        )

        return FetchedSourceSnapshot(
            source_definition=source,
            detected_at=self._clock(),
            jobs=tuple(
                jobs
            ),
        )


class AvatureSourceFetcher:
    """Dispatch adapter for Avature-hosted employer boards.

    ``source_account`` is the portal base URL rather than a tenant
    slug. Avature portals are served from the employer's own domain --
    Two Sigma's is ``careers.twosigma.com/careers`` -- and carry no
    slug to key on, so the URL is the only stable identifier there is.

    ``company_name`` is used, unlike the multi-employer lanes: one
    portal is one employer, and the postings do not name them.

    Unconditional: the listing is served ``no-store, no-cache`` and its
    ``Last-Modified`` is the moment of the request, so there is no
    validator worth replaying.
    """

    def __init__(
        self,
        *,
        fetcher=fetch_avature_jobs,
        clock: Clock = utc_now,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock

    def __call__(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch every public posting on one Avature portal."""

        if (
            source.source_type
            != SourceType.AVATURE
        ):
            raise ValueError(
                (
                    "AvatureSourceFetcher "
                    "requires an AVATURE "
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
            should_fetch_detail=(
                build_detail_predicate(
                    source="avature",
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


class EightfoldPcsxSourceFetcher:
    """Dispatch adapter for Eightfold PCSX-hosted career sites.

    Amdocs is the tenant that led to this: their board answers with a
    403 under the classic Eightfold route, because it runs the newer
    product line under /api/pcsx/ with different response shapes
    entirely. Same predicated-detail approach as the classic adapter.
    """

    def __init__(
        self,
        *,
        fetcher: EightfoldPcsxFetcher = (
            fetch_eightfold_pcsx_jobs
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
        """Fetch one Eightfold PCSX tenant."""

        if (
            source.source_type
            != SourceType.EIGHTFOLD_PCSX
        ):
            raise ValueError(
                (
                    "EightfoldPcsxSourceFetcher "
                    "requires an "
                    "EIGHTFOLD_PCSX "
                    "SourceDefinition."
                )
            )

        predicate = None

        if self._predicate_factory is not None:
            predicate = (
                self._predicate_factory(
                    source=(
                        SourceType
                        .EIGHTFOLD_PCSX
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
        verifier: (
            Callable[
                [Sequence[CanonicalJob]],
                list[CanonicalJob],
            ]
            | None
        ) = None,
        read_directly_factory: (
            Callable[
                [],
                Callable[[str], bool],
            ]
            | None
        ) = None,
    ) -> None:
        self._fetcher = fetcher
        self._clock = clock
        self._validator_lookup = (
            validator_lookup
        )

        # Reads each posting's employer page so the gate judges it on
        # what the employer says, not on the feed's placeholder.
        self._verifier = verifier

        # Answers, per poll, whether ACE already reads the board a
        # posting is on -- so only those postings leave the feed lane.
        self._read_directly_factory = read_directly_factory

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
                read_directly=(
                    self._read_directly_factory()
                    if self._read_directly_factory
                    is not None
                    else None
                ),
            )
        )

        if (
            not unchanged
            and jobs
            and self._verifier is not None
        ):
            jobs = self._verifier(
                jobs
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


def _registered_board_check() -> Callable[[str], bool]:
    """Whether ACE reads the board a posting link names.

    Registered and switched on -- not merely readable. Loaded once per
    feed poll, in a short session of its own.
    """

    from sqlalchemy import select

    from backend.app.db.models import (
        JobSourceRecord,
    )
    from backend.app.db.session import (
        SessionLocal,
    )
    from backend.app.discovery.detector import (
        detect_source_from_url,
    )

    with SessionLocal() as session:
        registered = {
            (
                source_type,
                source_account.lower(),
            )
            for source_type, source_account in session.execute(
                select(
                    JobSourceRecord.source_type,
                    JobSourceRecord.source_account,
                ).where(
                    JobSourceRecord.enabled.is_(True),
                )
            ).all()
        }

    def read_directly(
        url: str,
    ) -> bool:
        detected = detect_source_from_url(
            url
        )

        return detected is not None and (
            detected.source_type.value,
            detected.source_account.lower(),
        ) in registered

    return read_directly


def _title_could_pass(
    job: CanonicalJob,
) -> bool:
    """Whether a feed posting's page is worth reading at all.

    The same title test the Workday detail fetch uses: a posting the
    gate rejects on its title alone is rejected whatever its page says.
    """

    return build_detail_predicate(
        source=job.source,
        company_name=job.company,
    )(
        job.title
    )


def _stored_descriptions(
    source: SourceDefinition,
) -> dict[str, tuple[str, str]]:
    """What ACE already holds for each posting of one source.

    Each posting's location and description, by its identifier, for a
    reader that would otherwise fetch every posting's own page on every
    poll. Read in its own short session, like the validators.
    """

    from sqlalchemy import (
        select,
    )

    from backend.app.db.models import (
        JobRecord,
    )
    from backend.app.db.session import (
        SessionLocal,
    )

    with SessionLocal() as session:
        rows = session.execute(
            select(
                JobRecord.external_id,
                JobRecord.location,
                JobRecord.description,
            ).where(
                JobRecord.source
                == source.source_type.value,
                JobRecord.source_account
                == source.source_account,
                JobRecord.description != "",
            )
        ).all()

    return {
        external_id: (
            location,
            description,
        )
        for external_id, location, description in rows
    }


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
            SourceType.EIGHTFOLD_PCSX: (
                EightfoldPcsxSourceFetcher(
                    predicate_factory=(
                        build_detail_predicate
                    )
                )
            ),
            SourceType.RIPPLEMATCH: (
                RippleMatchSourceFetcher()
            ),
            SourceType.AVATURE: (
                AvatureSourceFetcher()
            ),
            SourceType.BYTEDANCE: (
                ByteDanceSourceFetcher()
            ),
            SourceType.ORACLE_RECRUITING: (
                OracleRecruitingSourceFetcher()
            ),
            SourceType.WORKABLE: (
                WorkableSourceFetcher()
            ),
            SourceType.IBM: (
                IbmSourceFetcher()
            ),
            SourceType.ATLASSIAN: (
                AtlassianSourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    )
                )
            ),
            SourceType.APPLE: (
                AppleSourceFetcher(
                    known_lookup=(
                        _stored_descriptions
                    )
                )
            ),
            SourceType.SHOPIFY: (
                ShopifySourceFetcher(
                    known_lookup=(
                        _stored_descriptions
                    )
                )
            ),
            SourceType.SIMPLIFY: (
                SimplifySourceFetcher(
                    validator_lookup=(
                        _stored_validators
                    ),
                    verifier=EmployerPageVerifier(
                        worth_reading=(
                            _title_could_pass
                        ),
                    ),
                    read_directly_factory=(
                        _registered_board_check
                    ),
                )
            ),
        }
    )