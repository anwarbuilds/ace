"""Eightfold's newer "PCSX" API surface.

Found while chasing down why an Amdocs new-grad posting the user found
by hand was not in ACE. Amdocs runs Eightfold, which ACE already reads,
and the existing adapter's own docstring says another tenant is "a
configuration line rather than a new module". That held for Netflix. It
did not hold here: Amdocs's classic ``/api/apply/v2/jobs`` endpoint
returns 403 with a bare ``{"message": "Not authorized for PCSX"}``,
because the tenant runs Eightfold's newer product line under
``/api/pcsx/``, a different route with a different response shape.

The real endpoint was found by driving a headless browser against the
live search widget and watching the network panel rather than guessing
URLs, because guessing had already produced three wrong ones.

Response shape, for the next tenant that needs this
-----------------------------------------------------

Every PCSX response wraps its payload:

    {"status": 200, "error": {...}, "data": {...}, "metadata": null}

``GET /api/pcsx/search?domain=<tenant>&query=&start=0`` returns
``data.positions`` (id, name, a location string with no country code)
and ``data.count``. ``GET /api/pcsx/position_details?position_id=<id>
&domain=<tenant>`` returns the same posting with ``jobDescription``
(HTML) and ``standardizedLocations`` (clean "City, ST, US" strings,
better than the search response's raw location line).

Same predicated-detail shape as the classic adapter: title first, detail
only for postings the gate's title-only pass would not already reject.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters.eightfold import _clean_html
from backend.app.adapters.retry import request_with_retry
from backend.app.models.job import CanonicalJob


USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project; "
    "https://github.com/anwarbuilds/ace)"
)

REQUEST_TIMEOUT_SECONDS = 25.0

# Observed cap on the live search widget; unconfirmed against the
# server, so treated as a page size rather than trusted blindly.
PAGE_SIZE = 50

# A tenant with more open roles than this is almost certainly a
# misconfigured query rather than reality, and paging forever would
# hammer someone else's server.
MAX_POSTINGS = 3000

DETAIL_CONCURRENCY = 6


def fetch_eightfold_pcsx_jobs(
    tenant_host: str,
    company_name: str,
    *,
    domain: str | None = None,
    client: httpx.Client | None = None,
    should_fetch_detail: (
        Callable[[str], bool] | None
    ) = None,
    concurrency: int = DETAIL_CONCURRENCY,
) -> list[CanonicalJob]:
    """Fetch one Eightfold PCSX career site.

    Returns every posting, with descriptions filled in only for titles
    the caller's predicate accepted. A posting whose detail was skipped
    still appears: the snapshot is authoritative for lifecycle, and
    omitting a posting would tell ACE it had closed.
    """

    host = tenant_host.strip().strip(
        "/"
    )

    if not host:
        raise ValueError(
            "tenant_host must not be empty."
        )

    company = company_name.strip()

    if not company:
        raise ValueError(
            "company_name must not be empty."
        )

    site_domain = (
        domain or ""
    ).strip() or host

    owns_client = client is None

    session = (
        client
        if client is not None
        else httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
    )

    try:
        postings = _fetch_postings(
            session,
            host=host,
            site_domain=site_domain,
        )

        wanted = [
            posting
            for posting in postings
            if should_fetch_detail is None
            or should_fetch_detail(
                str(
                    posting.get(
                        "name"
                    )
                    or ""
                )
            )
        ]

        details = _fetch_details(
            session,
            host=host,
            site_domain=site_domain,
            postings=wanted,
            concurrency=concurrency,
        )

        return [
            _to_canonical(
                posting,
                detail=details.get(
                    str(
                        posting.get(
                            "id"
                        )
                    )
                ),
                company=company,
                host=host,
            )
            for posting in postings
            if posting.get(
                "id"
            )
            and posting.get(
                "name"
            )
        ]
    finally:
        if owns_client:
            session.close()


def _fetch_postings(
    session: httpx.Client,
    *,
    host: str,
    site_domain: str,
) -> list[dict]:
    """Page through the tenant's open postings.

    ``query=""`` is a real, deliberate parameter: the live search
    widget sends it empty on first load and returns every open role
    rather than nothing, which is the behaviour a listing poll needs.
    """

    collected: list[dict] = []

    start = 0

    while start < MAX_POSTINGS:
        response = request_with_retry(
            lambda: session.get(
                f"https://{host}"
                "/api/pcsx/search",
                params={
                    "domain": site_domain,
                    "query": "",
                    "start": start,
                    "num": PAGE_SIZE,
                },
            )
        )

        response.raise_for_status()

        payload = _unwrap(
            response.json()
        )

        page = (
            payload.get(
                "positions"
            )
            or []
        )

        if not page:
            break

        collected.extend(
            page
        )

        total = payload.get(
            "count"
        )

        start += len(
            page
        )

        if (
            isinstance(
                total,
                int,
            )
            and start >= total
        ):
            break

    return collected


def _fetch_details(
    session: httpx.Client,
    *,
    host: str,
    site_domain: str,
    postings: list[dict],
    concurrency: int,
) -> dict[str, dict]:
    """Fetch full detail records for the accepted postings, concurrently."""

    if not postings:
        return {}

    def load(
        posting: dict,
    ) -> tuple[str, dict]:
        posting_id = str(
            posting.get(
                "id"
            )
        )

        try:
            response = request_with_retry(
                lambda: session.get(
                    f"https://{host}"
                    "/api/pcsx/position_details",
                    params={
                        "position_id": posting_id,
                        "domain": site_domain,
                    },
                )
            )

            if response.status_code != 200:
                return (
                    posting_id,
                    {},
                )

            return (
                posting_id,
                _unwrap(
                    response.json()
                ),
            )
        except (
            httpx.HTTPError,
            ValueError,
        ):
            # One unreadable posting must not fail the whole poll. It
            # simply arrives unverified, which the gate already handles.
            return (
                posting_id,
                {},
            )

    with ThreadPoolExecutor(
        max_workers=max(
            1,
            concurrency,
        )
    ) as pool:
        return dict(
            pool.map(
                load,
                postings,
            )
        )


def _unwrap(
    payload: object,
) -> dict:
    """Return the ``data`` object every PCSX response wraps its
    payload in.

    A response with no ``data`` key, or a non-dict payload entirely,
    is treated as an empty result rather than raised: a malformed
    response from one tenant must not take the whole poll down.
    """

    if not isinstance(
        payload,
        dict,
    ):
        return {}

    data = payload.get(
        "data"
    )

    return (
        data
        if isinstance(
            data,
            dict,
        )
        else {}
    )


def _location_of(
    posting: dict,
    detail: dict,
) -> str:
    """Return one readable location for a posting.

    The detail call's ``standardizedLocations`` is "City, ST, US" and
    is preferred when present. The search response's own ``location``
    is a raw internal string like "USA-TX, Plano, 2900 W Plano Pkwy
    (CU)", worse but the only thing available for a posting whose
    detail was never fetched: still readable, since the gate's location
    rules look for real place names rather than a specific format.
    """

    standardized = detail.get(
        "standardizedLocations"
    )

    if isinstance(
        standardized,
        list,
    ) and standardized:
        return ", ".join(
            str(
                item
            )
            for item in standardized
            if item
        )

    raw = (
        detail.get(
            "location"
        )
        or posting.get(
            "location"
        )
        or ""
    )

    return str(
        raw
    ).strip()


def _posted_at(
    detail: dict,
) -> datetime | None:
    """Return the posting's post time, when it is trustworthy.

    ``postedTs`` is Unix seconds. A stamp implausibly far in the future
    or the epoch itself is a malformed value rather than a real date.
    """

    stamp = detail.get(
        "postedTs"
    )

    try:
        moment = datetime.fromtimestamp(
            int(
                stamp
            ),
            tz=timezone.utc,
        )
    except (
        ValueError,
        TypeError,
        OSError,
        OverflowError,
    ):
        return None

    if moment.year < 2000:
        return None

    return moment


def _to_canonical(
    posting: dict,
    *,
    detail: dict | None,
    company: str,
    host: str,
) -> CanonicalJob:
    """Normalize one Eightfold PCSX posting."""

    detail = detail or {}

    posting_id = str(
        posting.get(
            "id"
        )
    )

    url = str(
        detail.get(
            "publicUrl"
        )
        or posting.get(
            "publicUrl"
        )
        or f"https://{host}/careers/job/{posting_id}"
    )

    display_id = (
        detail.get(
            "displayJobId"
        )
        or posting.get(
            "displayJobId"
        )
    )

    return CanonicalJob(
        source="eightfold_pcsx",
        company=company,
        external_id=posting_id,
        requisition_id=(
            str(
                display_id
            )
            if display_id
            else None
        ),
        title=str(
            posting.get(
                "name"
            )
            or ""
        ).strip(),
        location=_location_of(
            posting,
            detail,
        ),
        description=_clean_html(
            str(
                detail.get(
                    "jobDescription"
                )
                or ""
            )
        ),
        official_url=url,
        posted_at=_posted_at(
            detail
        ),
        # No reliable update stamp is exposed on this API surface.
        updated_at=None,
    )
