"""Eightfold ATS adapter for ACE.

Built while investigating why Google, Meta, Microsoft and Netflix were
missing from the corpus. Netflix was the only one of the four with an
open, documented-shape JSON route, and it runs on Eightfold, which is a
multi-tenant platform. The adapter is therefore written against
Eightfold rather than against Netflix, so another tenant is a
configuration line rather than a new module.

Two Eightfold calls per poll cycle shape:

1. A paged search that returns titles, locations and URLs but an empty
   ``job_description``.
2. A per-posting detail call that returns the description.

That makes it a predicated-detail source like Workday: the gate is run
on the title first, and only titles that survive earn a detail request.
Fetching all of them would be several hundred requests per cycle to
learn nothing the title already settled.

Eightfold cannot use conditional HTTP: the search response embeds
per-request session fields, so the body differs even when the postings
do not.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import (
    datetime,
    timezone,
)
import re

import httpx

from backend.app.adapters.retry import request_with_retry
from backend.app.models.job import CanonicalJob


USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project; "
    "https://github.com/anwarbuilds/ace)"
)

REQUEST_TIMEOUT_SECONDS = 25.0

# Eightfold caps a page at 100 and rejects larger values.
PAGE_SIZE = 100

# A tenant with more open roles than this is almost certainly a
# misconfigured query rather than reality, and paging forever would
# hammer someone else's server.
MAX_POSTINGS = 3000

DETAIL_CONCURRENCY = 6


_TAG = re.compile(
    r"<[^>]+>"
)

_WHITESPACE = re.compile(
    r"[ \t\r\f\v]+"
)


def _clean_html(
    value: str,
) -> str:
    """Reduce an HTML description to readable text.

    The gate reads descriptions for citizenship, clearance and
    experience language, so markup has to go or a rule can match a tag
    attribute instead of prose.
    """

    if not value:
        return ""

    text = value.replace(
        "<br>",
        "\n",
    ).replace(
        "<br/>",
        "\n",
    ).replace(
        "</p>",
        "\n",
    ).replace(
        "</li>",
        "\n",
    )

    text = _TAG.sub(
        " ",
        text,
    )

    for entity, replacement in (
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ):
        text = text.replace(
            entity,
            replacement,
        )

    text = _WHITESPACE.sub(
        " ",
        text,
    )

    return "\n".join(
        line.strip()
        for line in text.split(
            "\n"
        )
    ).strip()


def _location_of(
    posting: dict,
) -> str:
    """Return one readable location for a posting.

    Eightfold ships "Los Gatos,California,United States of America"
    with no spaces, which the gate's location rules would read as one
    unknown token.
    """

    raw = (
        posting.get(
            "location"
        )
        or ""
    )

    if not raw:
        locations = (
            posting.get(
                "locations"
            )
            or []
        )

        raw = (
            locations[0]
            if locations
            else ""
        )

    parts = [
        part.strip()
        for part in str(
            raw
        ).split(
            ","
        )
        if part.strip()
    ]

    return ", ".join(
        parts
    )


def _updated_at(
    posting: dict,
) -> datetime | None:
    """Return the posting's update time, when it is trustworthy."""

    stamp = posting.get(
        "t_update"
    ) or posting.get(
        "t_create"
    )

    if not stamp:
        return None

    try:
        return datetime.fromtimestamp(
            int(
                stamp
            ),
            tz=timezone.utc,
        )
    except (
        ValueError,
        TypeError,
        OSError,
    ):
        return None


def fetch_eightfold_jobs(
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
    """Fetch one public Eightfold career site.

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

        descriptions = _fetch_descriptions(
            session,
            host=host,
            site_domain=site_domain,
            postings=wanted,
            concurrency=concurrency,
        )

        return [
            _to_canonical(
                posting,
                company=company,
                host=host,
                description=descriptions.get(
                    str(
                        posting.get(
                            "id"
                        )
                    ),
                    "",
                ),
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
    """Page through the tenant's open postings."""

    collected: list[dict] = []

    start = 0

    while start < MAX_POSTINGS:
        response = request_with_retry(
            lambda: session.get(
                f"https://{host}"
                "/api/apply/v2/jobs",
                params={
                    "domain": site_domain,
                    "start": start,
                    "num": PAGE_SIZE,
                },
            )
        )

        response.raise_for_status()

        payload = response.json()

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


def _fetch_descriptions(
    session: httpx.Client,
    *,
    host: str,
    site_domain: str,
    postings: list[dict],
    concurrency: int,
) -> dict[str, str]:
    """Fetch descriptions for the accepted postings, concurrently."""

    if not postings:
        return {}

    def load(
        posting: dict,
    ) -> tuple[str, str]:
        posting_id = str(
            posting.get(
                "id"
            )
        )

        try:
            response = request_with_retry(
                lambda: session.get(
                    f"https://{host}"
                    "/api/apply/v2/jobs/"
                    f"{posting_id}",
                    params={
                        "domain": site_domain,
                    },
                )
            )

            if response.status_code != 200:
                return (
                    posting_id,
                    "",
                )

            body = response.json()
        except (
            httpx.HTTPError,
            ValueError,
        ):
            # One unreadable posting must not fail the whole poll. It
            # simply arrives unverified, which the gate already handles.
            return (
                posting_id,
                "",
            )

        return (
            posting_id,
            _clean_html(
                str(
                    body.get(
                        "job_description"
                    )
                    or ""
                )
            ),
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


def _to_canonical(
    posting: dict,
    *,
    company: str,
    host: str,
    description: str,
) -> CanonicalJob:
    """Normalize one Eightfold posting."""

    posting_id = str(
        posting.get(
            "id"
        )
    )

    url = str(
        posting.get(
            "canonicalPositionUrl"
        )
        or f"https://{host}/careers/job/{posting_id}"
    )

    updated = _updated_at(
        posting
    )

    return CanonicalJob(
        source="eightfold",
        company=company,
        external_id=posting_id,
        requisition_id=(
            str(
                posting.get(
                    "display_job_id"
                )
            )
            if posting.get(
                "display_job_id"
            )
            else None
        ),
        title=str(
            posting.get(
                "name"
            )
            or ""
        ).strip(),
        location=_location_of(
            posting
        ),
        description=description,
        official_url=url,
        # Eightfold exposes a create and an update stamp but no posted
        # date, and t_create moves when a posting is edited, so it is
        # reported as updated rather than posted.
        posted_at=None,
        updated_at=updated,
    )
