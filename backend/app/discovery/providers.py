"""Public discovery providers for ACE job-source discovery.

These providers discover possible external job-source accounts from
independent public feeds.

A discovery provider does NOT make a source trusted.

Its responsibility is only:

    public feed
        -> possible ATS/source identity
        -> SourceCandidate

The candidate must still pass ACE's normal source verification before it
is allowed into the persistent source catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import logging
import re
from typing import (
    Callable,
    Iterable,
)
from urllib.parse import (
    unquote,
    urlparse,
)

import httpx

from backend.app.discovery.detector import (
    detect_source_from_url,
)
from backend.app.discovery.types import (
    SourceCandidate,
)
from backend.app.scheduling.types import (
    SourceType,
)


logger = logging.getLogger(
    "ace.discovery.providers"
)


DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 20.0

DEFAULT_DISCOVERY_USER_AGENT = (
    "ACE-Job-Source-Discovery/1.0"
)


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryFeed:
    """One external feed from which ACE may discover source candidates."""

    name: str

    url: str

    def __post_init__(
        self,
    ) -> None:
        normalized_name = (
            self.name.strip()
        )

        normalized_url = (
            self.url.strip()
        )

        if not normalized_name:
            raise ValueError(
                "Discovery feed name "
                "must not be empty."
            )

        if not normalized_url:
            raise ValueError(
                "Discovery feed URL "
                "must not be empty."
            )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )

        object.__setattr__(
            self,
            "url",
            normalized_url,
        )


DEFAULT_PUBLIC_DISCOVERY_FEEDS = (
    DiscoveryFeed(
        name="simplify-new-grad",
        url=(
            "https://raw.githubusercontent.com/"
            "SimplifyJobs/"
            "New-Grad-Positions/"
            "dev/"
            "README.md"
        ),
    ),
)


TextFeedFetcher = Callable[
    [str],
    str,
]


class _HtmlTableParser(
    HTMLParser
):
    """Extract rows, text cells, and hyperlinks from HTML tables.

    The Simplify job feeds currently contain HTML tables embedded inside
    Markdown. ACE intentionally parses only the generic HTML structure
    required for source discovery rather than depending on the entire
    README format.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.rows: list[
            tuple[
                tuple[str, ...],
                tuple[str, ...],
            ]
        ] = []

        self._in_row = False
        self._in_cell = False

        self._cells: list[
            str
        ] = []

        self._hrefs: list[
            str
        ] = []

        self._cell_parts: list[
            str
        ] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        tag = tag.lower()

        if tag == "tr":
            self._in_row = True

            self._cells = []
            self._hrefs = []
            self._cell_parts = []

            return

        if (
            tag == "td"
            and self._in_row
        ):
            self._in_cell = True
            self._cell_parts = []

            return

        if (
            tag == "br"
            and self._in_cell
        ):
            self._cell_parts.append(
                " "
            )

            return

        if (
            tag == "a"
            and self._in_row
        ):
            for (
                attribute_name,
                attribute_value,
            ) in attrs:
                if (
                    attribute_name.lower()
                    == "href"
                    and attribute_value
                ):
                    self._hrefs.append(
                        attribute_value
                    )

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._in_cell:
            self._cell_parts.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        tag = tag.lower()

        if (
            tag == "td"
            and self._in_cell
        ):
            cell = (
                " ".join(
                    self._cell_parts
                )
            )

            cell = re.sub(
                r"\s+",
                " ",
                cell,
            ).strip()

            self._cells.append(
                cell
            )

            self._cell_parts = []
            self._in_cell = False

            return

        if (
            tag == "tr"
            and self._in_row
        ):
            self.rows.append(
                (
                    tuple(
                        self._cells
                    ),
                    tuple(
                        self._hrefs
                    ),
                )
            )

            self._cells = []
            self._hrefs = []
            self._cell_parts = []

            self._in_cell = False
            self._in_row = False


def _normalize_company_name(
    value: str,
) -> str:
    """Normalize a company label extracted from a public feed."""

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if (
        not value
        or value == "↳"
    ):
        return ""

    # Remove leading decorations such as:
    #
    #     🔥 Stripe
    #
    # while preserving ordinary Unicode company names.
    value = re.sub(
        r"^[^\w]+",
        "",
        value,
    ).strip()

    return value


def _humanize_account(
    account: str,
) -> str:
    """Produce a fallback display name from an ATS account token."""

    parts = re.split(
        r"[-_]+",
        account,
    )

    return " ".join(
        part.capitalize()
        for part in parts
        if part
    )


def greenhouse_account_from_url(
    url: str,
) -> str | None:
    """Extract a Greenhouse board account token from a public job URL.

    Supported examples include:

        https://job-boards.greenhouse.io/kikoff/jobs/123
        https://boards.greenhouse.io/example/jobs/456

    The returned account is normalized to lowercase.

    Branded company URLs that merely contain a Greenhouse job id are
    intentionally not guessed because the board token cannot be derived
    reliably from them.
    """

    value = url.strip()

    if not value:
        return None

    try:
        parsed = urlparse(
            value
        )
    except ValueError:
        return None

    hostname = (
        parsed.hostname
        or ""
    ).lower()

    is_greenhouse_board_host = (
        hostname.endswith(
            "greenhouse.io"
        )
        and (
            hostname.startswith(
                "boards."
            )
            or hostname.startswith(
                "job-boards."
            )
        )
    )

    if not is_greenhouse_board_host:
        return None

    path_parts = [
        unquote(
            part
        ).strip()
        for part in (
            parsed.path.split(
                "/"
            )
        )
        if part.strip()
    ]

    if not path_parts:
        return None

    account = (
        path_parts[
            0
        ]
        .strip()
        .lower()
    )

    if not account:
        return None

    return account


def extract_greenhouse_candidates(
    document: str,
    *,
    discovery_source: str,
) -> tuple[
    SourceCandidate,
    ...,
]:
    """Extract unique Greenhouse source candidates from one feed document."""

    parser = (
        _HtmlTableParser()
    )

    parser.feed(
        document
    )

    parser.close()

    candidates: list[
        SourceCandidate
    ] = []

    seen_accounts: set[
        str
    ] = set()

    last_company_name: (
        str | None
    ) = None

    for (
        cells,
        hrefs,
    ) in parser.rows:
        row_company = ""

        if cells:
            row_company = (
                _normalize_company_name(
                    cells[
                        0
                    ]
                )
            )

        if row_company:
            last_company_name = (
                row_company
            )

        for href in hrefs:
            account = (
                greenhouse_account_from_url(
                    href
                )
            )

            if account is None:
                continue

            if account in seen_accounts:
                continue

            seen_accounts.add(
                account
            )

            company_name = (
                last_company_name
                or _humanize_account(
                    account
                )
            )

            candidates.append(
                SourceCandidate(
                    source_type=(
                        SourceType.GREENHOUSE
                    ),
                    source_account=(
                        account
                    ),
                    company_name=(
                        company_name
                    ),
                    discovery_source=(
                        discovery_source
                    ),
                )
            )

    return tuple(
        candidates
    )


def extract_source_candidates(
    document: str,
    *,
    discovery_source: str,
) -> tuple[
    SourceCandidate,
    ...,
]:
    """Extract ATS-neutral source candidates from one feed document.

    Every hyperlink is passed through ACE's central ATS detector.

    This keeps discovery independent from Greenhouse, Lever, Ashby,
    SmartRecruiters, and future provider-specific URL formats.
    """

    parser = (
        _HtmlTableParser()
    )

    parser.feed(
        document
    )

    parser.close()

    candidates: list[
        SourceCandidate
    ] = []

    seen_identities: set[
        tuple[
            SourceType,
            str,
        ]
    ] = set()

    last_company_name: (
        str | None
    ) = None

    for (
        cells,
        hrefs,
    ) in parser.rows:
        row_company = ""

        if cells:
            row_company = (
                _normalize_company_name(
                    cells[
                        0
                    ]
                )
            )

        if row_company:
            last_company_name = (
                row_company
            )

        for href in hrefs:
            detected = (
                detect_source_from_url(
                    href
                )
            )

            if detected is None:
                continue

            identity = (
                detected.source_type,
                (
                    detected
                    .source_account
                    .casefold()
                ),
            )

            if identity in seen_identities:
                continue

            seen_identities.add(
                identity
            )

            company_name = (
                last_company_name
                or _humanize_account(
                    detected.source_account
                )
            )

            candidates.append(
                SourceCandidate(
                    source_type=(
                        detected.source_type
                    ),
                    source_account=(
                        detected.source_account
                    ),
                    company_name=(
                        company_name
                    ),
                    discovery_source=(
                        discovery_source
                    ),
                    source_host=(
                        detected.source_host
                    ),
                    evidence_url=href,
                )
            )

    return tuple(
        candidates
    )


def _fetch_public_text(
    url: str,
) -> str:
    """Fetch one public discovery document."""

    response = httpx.get(
        url,
        headers={
            "User-Agent": (
                DEFAULT_DISCOVERY_USER_AGENT
            ),
            "Accept": (
                "text/plain,"
                "text/markdown,"
                "text/html,"
                "application/xhtml+xml"
            ),
        },
        timeout=(
            DEFAULT_DISCOVERY_TIMEOUT_SECONDS
        ),
        follow_redirects=True,
    )

    response.raise_for_status()

    return response.text


class PublicJobFeedProvider:
    """Discover ATS source identities from public job-list feeds.

    The provider performs discovery only.

    Every returned candidate still has to pass
    DispatcherSourceVerifier before persistence.
    """

    def __init__(
        self,
        feeds: Iterable[
            DiscoveryFeed
        ] = (
            DEFAULT_PUBLIC_DISCOVERY_FEEDS
        ),
        *,
        fetch_text: (
            TextFeedFetcher
            | None
        ) = None,
        max_candidates: (
            int
            | None
        ) = None,
    ) -> None:
        normalized_feeds = tuple(
            feeds
        )

        if not normalized_feeds:
            raise ValueError(
                "At least one discovery "
                "feed is required."
            )

        if (
            max_candidates
            is not None
            and max_candidates <= 0
        ):
            raise ValueError(
                "max_candidates must "
                "be positive."
            )

        self._feeds = (
            normalized_feeds
        )

        self._fetch_text = (
            fetch_text
            or _fetch_public_text
        )

        self._max_candidates = (
            max_candidates
        )

    @property
    def feeds(
        self,
    ) -> tuple[
        DiscoveryFeed,
        ...,
    ]:
        return self._feeds

    def discover(
        self,
    ) -> tuple[
        SourceCandidate,
        ...,
    ]:
        """Fetch configured feeds and return unique ATS source candidates."""

        discovered: list[
            SourceCandidate
        ] = []

        seen_identities: set[
            tuple[
                SourceType,
                str,
            ]
        ] = set()

        successful_feed_count = 0

        feed_errors: list[
            str
        ] = []

        for feed in self._feeds:
            try:
                document = (
                    self._fetch_text(
                        feed.url
                    )
                )

            except (
                httpx.HTTPError,
                OSError,
            ) as exc:
                logger.warning(
                    (
                        "source_discovery_feed_failed "
                        "feed=%r url=%r "
                        "error_type=%s "
                        "error=%r"
                    ),
                    feed.name,
                    feed.url,
                    type(
                        exc
                    ).__name__,
                    str(
                        exc
                    ),
                )

                feed_errors.append(
                    (
                        f"{feed.name}: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                )

                continue

            successful_feed_count += 1

            feed_candidates = (
                extract_source_candidates(
                    document,
                    discovery_source=(
                        feed.name
                    ),
                )
            )

            for candidate in (
                feed_candidates
            ):
                identity = (
                    candidate.source_type,
                    (
                        candidate
                        .source_account
                        .casefold()
                    ),
                )

                if (
                    identity
                    in seen_identities
                ):
                    continue

                seen_identities.add(
                    identity
                )

                discovered.append(
                    candidate
                )

                if (
                    self._max_candidates
                    is not None
                    and len(
                        discovered
                    )
                    >= self._max_candidates
                ):
                    return tuple(
                        discovered
                    )

        if (
            successful_feed_count
            == 0
        ):
            detail = (
                "; ".join(
                    feed_errors
                )
                or "unknown error"
            )

            raise RuntimeError(
                (
                    "All configured source "
                    "discovery feeds failed: "
                    f"{detail}"
                )
            )

        return tuple(
            discovered
        )

# Backward-compatible alias.
#
# Existing callers may still import the old Greenhouse-specific class
# name while ACE transitions discovery to the provider-neutral name.
PublicGreenhouseFeedProvider = PublicJobFeedProvider
