"""Workday CXS adapter for ACE.

Workday hosts each employer on its own tenant:

    https://{tenant}.{wd}.myworkdayjobs.com/{site}

The public JSON API behind that page is:

    POST /wday/cxs/{tenant}/{site}/jobs      list, 20 per page
    GET  /wday/cxs/{tenant}/{site}{path}     one posting, with description

Two properties of that API shape the adapter.

Listing is expensive, detail is not
-----------------------------------

Workday caps a page at twenty postings regardless of the requested
limit, so a two-thousand-posting tenant costs one hundred list requests
(about 85 seconds) before any description is read.

Server-side ``searchText`` cannot be used to narrow this. It behaves as
a fuzzy OR: searching "software engineer" against a 2000-posting tenant
still returns 1719 results, so filtering there would be both ineffective
and lossy.

Detail requests are therefore filtered instead, through an injected
predicate. On a real tenant only 72 of 2000 titles survive ACE's gate,
turning ~300 seconds of detail fetching into ~11.

Shallow postings
----------------

Every listed posting is emitted, including those whose detail was
skipped, because the snapshot is authoritative for lifecycle: omitting
them would mark 1900 live jobs closed on every poll.

Skipped postings carry an empty description. That is safe because the
predicate only skips what the gate already rejects on title alone, and
it is self-healing: if the rules later change so the title qualifies,
the next poll fetches the detail, the content hash changes, and the job
is re-evaluated in full.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
import html
import re
from typing import Any
from urllib.parse import unquote

import httpx

from backend.app.adapters.html_text import (
    unescape_fully,
)
from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import (
    CanonicalJob,
    JobList,
)


WORKDAY_SOURCE = "workday"

# Workday silently caps a page at twenty regardless of the requested
# limit, so asking for more only wastes the round trip.
WORKDAY_PAGE_SIZE = 20

REQUEST_TIMEOUT_SECONDS = 25.0

# Workday's search returns at most this many results, and reports this
# as its total, however many postings the tenant has.
WORKDAY_RESULT_CAP = 2000

# List pages per poll, all searches together. Bounds one pathological
# tenant; NVIDIA read whole in slices is about 150.
DEFAULT_MAX_PAGES = 400

DEFAULT_MAX_DETAIL_FETCHES = 400

# Offset pagination means every page after the first can be requested
# independently once the total is known. Some tenants answer a list page
# in five seconds, so fetching them one at a time made a 600-posting
# employer cost nearly three minutes.
#
# Kept deliberately small: this is a courtesy limit on someone else's
# careers site, not a throughput target.
DEFAULT_CONCURRENCY = 4

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _postings(
    body: dict[str, Any],
) -> list[dict[str, Any]]:
    postings = body.get(
        "jobPostings"
    )

    if not isinstance(
        postings,
        list,
    ):
        return []

    return [
        posting
        for posting in postings
        if isinstance(
            posting,
            dict,
        )
    ]


def _total(
    body: dict[str, Any],
) -> int:
    total = body.get(
        "total"
    )

    return (
        total
        if isinstance(
            total,
            int,
        )
        else 0
    )


# Facets tried first when splitting a capped tenant. Job family is a
# true partition -- every posting has exactly one -- and usually the
# finest one that is.
PREFERRED_PARTITIONS = (
    "jobFamilyGroup",
    "Location_Country",
    "workerSubType",
    "timeType",
)


def _partition(
    body: dict[str, Any],
) -> tuple[str, list[str]] | None:
    """A facet whose every value fits under the cap, and its values.

    It must account for at least as many postings as the capped total,
    or some postings carry no value of it and would be missed. Nested
    facets (location hierarchies) are not used: their values overlap.
    """

    candidates: dict[str, tuple[int, int, list[str]]] = {}

    for facet in body.get(
        "facets"
    ) or []:
        if not isinstance(
            facet,
            dict,
        ):
            continue

        parameter = facet.get(
            "facetParameter"
        )

        values = facet.get(
            "values"
        ) or []

        if not parameter or not values or any(
            "facetParameter" in value
            for value in values
            if isinstance(
                value,
                dict,
            )
        ):
            continue

        counts = [
            value.get("count") or 0
            for value in values
            if isinstance(
                value,
                dict,
            )
        ]

        ids = [
            str(value.get("id"))
            for value in values
            if isinstance(
                value,
                dict,
            )
            and value.get("id")
        ]

        if len(ids) != len(counts):
            continue

        candidates[parameter] = (
            sum(counts),
            max(counts),
            ids,
        )

    ordered = [
        name
        for name in PREFERRED_PARTITIONS
        if name in candidates
    ] + sorted(
        name
        for name in candidates
        if name not in PREFERRED_PARTITIONS
    )

    for name in ordered:
        covered, largest, ids = candidates[name]

        if (
            largest < WORKDAY_RESULT_CAP
            and covered >= WORKDAY_RESULT_CAP
        ):
            return name, ids

    return None


class WorkdaySourceError(RuntimeError):
    """Raised when a Workday source is misconfigured."""


def parse_source_account(
    source_account: str,
) -> tuple[str, str]:
    """Split a Workday source account into tenant and site.

    Workday identity needs both parts, so ACE stores them as
    ``tenant/site``:

        nvidia/NVIDIAExternalCareerSite
    """

    normalized = source_account.strip().strip(
        "/"
    )

    parts = [
        part
        for part in normalized.split(
            "/"
        )
        if part
    ]

    if len(parts) != 2:
        raise WorkdaySourceError(
            (
                "Workday source_account must be "
                "'tenant/site', received "
                f"{source_account!r}."
            )
        )

    return (
        parts[0],
        parts[1],
    )


def _require_host(
    source_host: str | None,
) -> str:
    """Require the tenant host.

    The Workday data-centre number differs per tenant (wd1, wd5, wd101)
    and cannot be derived, so it must be configured.
    """

    normalized = (
        source_host or ""
    ).strip().lower()

    if not normalized:
        raise WorkdaySourceError(
            (
                "Workday sources require "
                "source_host, for example "
                "'nvidia.wd5.myworkdayjobs.com'."
            )
        )

    return normalized.rstrip(
        "/"
    )


def _clean_html(
    value: str | None,
) -> str:
    """Convert Workday description HTML into normalized plain text."""

    if not value:
        return ""

    decoded = unescape_fully(
        value
    )

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        decoded,
    )

    return re.sub(
        r"\s+",
        " ",
        without_tags,
    ).strip()


RELATIVE_POSTED_PATTERN = re.compile(
    r"posted\s+(?P<count>\d+)\+?\s*"
    r"(?P<unit>day|days|month|months|hour|hours)\s*ago",
    re.IGNORECASE,
)


def parse_posted_on(
    value: object,
    *,
    reference: datetime,
) -> datetime | None:
    """Parse Workday's relative posting label.

    Workday reports list-level recency as prose: "Posted Today",
    "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago".

    The detail endpoint carries a real ``startDate``, which is preferred
    wherever available. This exists for postings whose detail was
    skipped.
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip().lower()

    if not text:
        return None

    if "today" in text:
        return reference

    if "yesterday" in text:
        return reference - timedelta(
            days=1
        )

    match = RELATIVE_POSTED_PATTERN.search(
        text
    )

    if match is None:
        return None

    count = int(
        match.group(
            "count"
        )
    )

    unit = match.group(
        "unit"
    ).lower()

    if unit.startswith(
        "hour"
    ):
        return reference - timedelta(
            hours=count
        )

    if unit.startswith(
        "month"
    ):
        return reference - timedelta(
            days=count * 30
        )

    return reference - timedelta(
        days=count
    )


def parse_start_date(
    value: object,
) -> datetime | None:
    """Parse the detail endpoint's ISO ``startDate``."""

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    try:
        parsed = date.fromisoformat(
            normalized[:10]
        )

    except ValueError:
        return None

    return datetime(
        parsed.year,
        parsed.month,
        parsed.day,
        tzinfo=timezone.utc,
    )


def _external_id(
    posting: dict[str, Any],
) -> str | None:
    """Return the durable identity of one listed posting.

    ``externalPath`` embeds the requisition id and is stable for the
    life of the posting, which makes it the natural identity.
    """

    path = posting.get(
        "externalPath"
    )

    if not isinstance(
        path,
        str,
    ):
        return None

    normalized = path.strip()

    return normalized or None


def _requisition_id(
    posting: dict[str, Any],
) -> str | None:
    """Extract a requisition id from a listing's bullet fields."""

    bullets = posting.get(
        "bulletFields"
    )

    if not isinstance(
        bullets,
        list,
    ):
        return None

    for bullet in bullets:
        if not isinstance(
            bullet,
            str,
        ):
            continue

        candidate = bullet.strip()

        # Requisition ids look like JR0286800; the other bullet is
        # usually a marketing label such as "Spotlight Job".
        if re.fullmatch(
            r"[A-Z]{1,4}[-_]?\d{3,}",
            candidate,
        ):
            return candidate

    return None


_LOCATION_COUNT = re.compile(
    r"^\s*(\d+)\s+locations?\s*$",
    re.IGNORECASE,
)


def _listed_location(
    locations_text: str,
    external_path: str,
) -> str:
    """The listing's location, or the one the posting's own path names.

    Some tenants list no location at all -- Accenture, Parsons, Levi's --
    and every tenant lists a posting open in several places as "2
    Locations". Unless its detail was read, that was all ACE stored, and
    the gate cannot place "2 Locations" in the US: on 2026-10-07, 44,000
    postings were stored that way and 166 were rejected for nothing but
    their location, Accenture's Seattle "AI Native Software Engineer"
    among them. The posting's path always names its primary location,
    "/job/Seattle-1191-2nd-Avenue-Corp/...", and the detail, when it is
    read, still replaces this with every location in full.
    """

    count = _LOCATION_COUNT.match(
        locations_text
    )

    if locations_text and not count:
        return locations_text

    segments = external_path.split(
        "/"
    )

    primary = ""

    if (
        len(segments) >= 4
        and segments[1] == "job"
    ):
        primary = " ".join(
            unquote(
                segments[2]
            )
            .replace(
                "-",
                " ",
            )
            .split()
        )

    if not primary:
        return locations_text

    if count and int(count.group(1)) > 1:
        return (
            f"{primary} + "
            f"{int(count.group(1)) - 1} more"
        )

    return primary


def _detail_location(
    info: dict[str, Any],
) -> str:
    """Join the primary and additional locations of one posting."""

    parts: list[str] = []

    primary = info.get(
        "location"
    )

    if isinstance(
        primary,
        str,
    ) and primary.strip():
        parts.append(
            primary.strip()
        )

    additional = info.get(
        "additionalLocations"
    )

    if isinstance(
        additional,
        list,
    ):
        for item in additional:
            if isinstance(
                item,
                str,
            ) and item.strip():
                parts.append(
                    item.strip()
                )

    return "; ".join(
        parts
    )


def _public_url(
    *,
    host: str,
    site: str,
    external_path: str,
) -> str:
    """Build the employer-facing posting URL."""

    return (
        f"https://{host}/{site}"
        f"{external_path}"
    )


def fetch_workday_jobs(
    *,
    source_account: str,
    company_name: str,
    source_host: str | None,
    should_fetch_detail: (
        Callable[[str], bool] | None
    ) = None,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_detail_fetches: int = (
        DEFAULT_MAX_DETAIL_FETCHES
    ),
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[CanonicalJob]:
    """Fetch and normalize one Workday tenant's public postings.

    ``should_fetch_detail`` receives a posting title and decides whether
    the expensive detail request is worth making. Composition wires this
    to ACE's eligibility gate so the adapter itself stays free of
    eligibility knowledge.
    """

    tenant, site = parse_source_account(
        source_account
    )

    host = _require_host(
        source_host
    )

    reference = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    owns_client = client is None

    http = (
        client
        if client is not None
        else httpx.Client(
            timeout=(
                REQUEST_TIMEOUT_SECONDS
            ),
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "application/json"
                ),
            },
        )
    )

    list_url = (
        f"https://{host}/wday/cxs/"
        f"{tenant}/{site}/jobs"
    )

    jobs: list[CanonicalJob] = []

    seen_paths: set[str] = set()

    def fetch_page(
        offset: int,
        facets: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of listings, as the whole response body."""

        response = request_with_retry(
            lambda: http.post(
                list_url,
                json={
                    "appliedFacets": facets or {},
                    "limit": (
                        WORKDAY_PAGE_SIZE
                    ),
                    "offset": offset,
                    "searchText": "",
                },
            )
        )

        response.raise_for_status()

        body = response.json()

        return (
            body
            if isinstance(
                body,
                dict,
            )
            else {}
        )

    def read_search(
        facets: dict[str, list[str]] | None,
        first: dict[str, Any],
        budget: list[int],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Every posting one search returns, and whether that was all.

        ``first`` is the search's first page, already fetched; the rest
        are requested concurrently once its total is known. Pages past
        what is left of ``budget`` are not requested, and the search is
        then reported as read in part.
        """

        total = _total(
            first
        )

        page_count = max(
            1,
            -(-min(total, WORKDAY_RESULT_CAP) // WORKDAY_PAGE_SIZE),
        )

        allowed = max(
            1,
            min(
                page_count,
                budget[0],
            ),
        )

        budget[0] -= allowed

        pages = [
            _postings(
                first
            ),
        ]

        offsets = [
            index * WORKDAY_PAGE_SIZE
            for index in range(
                1,
                allowed,
            )
        ]

        if offsets:
            with ThreadPoolExecutor(
                max_workers=concurrency
            ) as pool:
                pages.extend(
                    pool.map(
                        lambda offset: _postings(
                            fetch_page(
                                offset,
                                facets,
                            )
                        ),
                        offsets,
                    )
                )

        return (
            [
                posting
                for page in pages
                for posting in page
            ],
            allowed == page_count,
        )

    def fetch_detail(
        external_path: str,
    ) -> dict[str, Any] | None:
        """Fetch one posting's detail record."""

        response = http.get(
            (
                f"https://{host}/wday/cxs/"
                f"{tenant}/{site}"
                f"{external_path}"
            )
        )

        if response.status_code != 200:
            return None

        info = response.json().get(
            "jobPostingInfo"
        )

        return (
            info
            if isinstance(
                info,
                dict,
            )
            else None
        )

    try:
        first = fetch_page(
            0
        )

        if not _postings(
            first
        ):
            return []

        budget = [
            max_pages,
        ]

        everything: list[dict[str, Any]] | None = None

        complete = True

        # Workday's search stops at 2,000 results however many the
        # tenant has: NVIDIA reported a total of 2,000 while its own
        # job-family counts came to 2,679. Such a tenant is read in
        # slices that each fit -- one per value of a facet that
        # partitions the board -- and the slices together are the
        # whole board.
        capped = _total(
            first
        ) >= WORKDAY_RESULT_CAP

        partition = (
            _partition(
                first
            )
            if capped
            else None
        )

        if partition is not None:
            parameter, values = partition

            everything = []

            for value_id in values:
                facets = {
                    parameter: [
                        value_id,
                    ],
                }

                part, whole = read_search(
                    facets,
                    fetch_page(
                        0,
                        facets,
                    ),
                    budget,
                )

                if not whole:
                    everything = None

                    break

                everything.extend(
                    part
                )

        if everything is None:
            # Not capped, or capped with no facet that splits it.
            everything, whole = read_search(
                None,
                first,
                budget,
            )

            # Part of a board is still worth reading, but it is not
            # evidence that anything left it.
            complete = whole and not capped

        listings: list[
            dict[str, Any]
        ] = []

        for posting in everything:
            path = _external_id(
                posting
            )

            if (
                path is None
                or path in seen_paths
            ):
                continue

            seen_paths.add(
                path
            )

            listings.append(
                posting
            )

        # Decide which postings deserve the expensive detail request
        # before making any of them.
        wanted: list[str] = []

        for posting in listings:
            title = str(
                posting.get(
                    "title"
                )
                or ""
            ).strip()

            if not title:
                continue

            if (
                should_fetch_detail is None
                or should_fetch_detail(
                    title
                )
            ):
                path = _external_id(
                    posting
                )

                if path is not None:
                    wanted.append(
                        path
                    )

        wanted = wanted[
            :max_detail_fetches
        ]

        details: dict[
            str,
            dict[str, Any],
        ] = {}

        if wanted:
            with ThreadPoolExecutor(
                max_workers=concurrency
            ) as pool:
                for path, info in zip(
                    wanted,
                    pool.map(
                        fetch_detail,
                        wanted,
                    ),
                ):
                    if info is not None:
                        details[path] = info

        for posting in listings:
            external_path = _external_id(
                posting
            )

            if external_path is None:
                continue

            title = str(
                posting.get(
                    "title"
                )
                or ""
            ).strip()

            if not title:
                continue

            official_url = _public_url(
                host=host,
                site=site,
                external_path=(
                    external_path
                ),
            )

            description = ""

            location = _listed_location(
                str(
                    posting.get(
                        "locationsText"
                    )
                    or ""
                ).strip(),
                external_path,
            )

            posted_at = parse_posted_on(
                posting.get(
                    "postedOn"
                ),
                reference=reference,
            )

            requisition_id = (
                _requisition_id(
                    posting
                )
            )

            info = details.get(
                external_path
            )

            if info is not None:
                description = _clean_html(
                    info.get(
                        "jobDescription"
                    )
                )

                detail_location = (
                    _detail_location(
                        info
                    )
                )

                if detail_location:
                    location = (
                        detail_location
                    )

                posted_at = (
                    parse_start_date(
                        info.get(
                            "startDate"
                        )
                    )
                    or posted_at
                )

                requisition_id = (
                    str(
                        info.get(
                            "jobReqId"
                        )
                        or ""
                    ).strip()
                    or requisition_id
                )

                external_official = info.get(
                    "externalUrl"
                )

                if isinstance(
                    external_official,
                    str,
                ) and external_official.startswith(
                    "http"
                ):
                    official_url = (
                        external_official.strip()
                    )

            jobs.append(
                CanonicalJob(
                    source=WORKDAY_SOURCE,
                    company=company_name,
                    external_id=(
                        external_path
                    ),
                    requisition_id=(
                        requisition_id
                    ),
                    title=title,
                    location=location,
                    description=description,
                    official_url=(
                        official_url
                    ),
                    posted_at=posted_at,
                    updated_at=None,
                )
            )

    finally:
        if owns_client:
            http.close()

    return JobList(
        jobs,
        complete=complete,
    )
