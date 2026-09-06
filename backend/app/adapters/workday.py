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

import httpx

from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import CanonicalJob


WORKDAY_SOURCE = "workday"

# Workday silently caps a page at twenty regardless of the requested
# limit, so asking for more only wastes the round trip.
WORKDAY_PAGE_SIZE = 20

REQUEST_TIMEOUT_SECONDS = 25.0

# Bounds so one pathological tenant cannot hang a scheduler cycle.
DEFAULT_MAX_PAGES = 150

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

    decoded = html.unescape(
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
    ) -> list[dict[str, Any]]:
        """Fetch one page of listings."""

        response = request_with_retry(
            lambda: http.post(
                list_url,
                json={
                    "appliedFacets": {},
                    "limit": (
                        WORKDAY_PAGE_SIZE
                    ),
                    "offset": offset,
                    "searchText": "",
                },
            )
        )

        response.raise_for_status()

        postings = response.json().get(
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
        first_page = fetch_page(
            0
        )

        if not first_page:
            return []

        # The first response carries the total, so every remaining page
        # offset is known up front and can be fetched concurrently.
        total = 0

        probe = http.post(
            list_url,
            json={
                "appliedFacets": {},
                "limit": WORKDAY_PAGE_SIZE,
                "offset": 0,
                "searchText": "",
            },
        )

        if probe.status_code == 200:
            raw_total = probe.json().get(
                "total"
            )

            if isinstance(
                raw_total,
                int,
            ):
                total = raw_total

        page_count = min(
            max_pages,
            max(
                1,
                -(-total // WORKDAY_PAGE_SIZE)
                if total
                else 1,
            ),
        )

        pages: list[
            list[dict[str, Any]]
        ] = [
            first_page,
        ]

        remaining_offsets = [
            index * WORKDAY_PAGE_SIZE
            for index in range(
                1,
                page_count,
            )
        ]

        if remaining_offsets:
            with ThreadPoolExecutor(
                max_workers=concurrency
            ) as pool:
                pages.extend(
                    pool.map(
                        fetch_page,
                        remaining_offsets,
                    )
                )

        listings: list[
            dict[str, Any]
        ] = []

        for page in pages:
            for posting in page:
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

            location = str(
                posting.get(
                    "locationsText"
                )
                or ""
            ).strip()

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

    return jobs
