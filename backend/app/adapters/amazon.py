"""Amazon Jobs adapter for ACE.

Amazon publishes a public JSON search endpoint behind amazon.jobs:

    GET https://www.amazon.jobs/search.json

Unlike an ATS board it is a search index over roughly ten thousand US
postings, so fetching everything would be both slow and pointless.

Recency paging
--------------

The endpoint supports ``sort=recent``. Because ACE only alerts on
postings inside its freshness window, the adapter walks pages newest
first and stops as soon as a page is entirely older than the configured
horizon. A ten-day horizon typically costs two or three requests
instead of one hundred.

The horizon is deliberately wider than the alert freshness window so
that lifecycle tracking still sees a job for a while after it stops
being alert-worthy.

Description assembly
--------------------

Amazon splits requirements across three fields. All three are joined,
because the eligibility gate reads experience, citizenship and language
requirements that appear in the qualification sections rather than the
main description.
"""

from __future__ import annotations

from datetime import (
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


AMAZON_SOURCE = "amazon"

AMAZON_SEARCH_URL = (
    "https://www.amazon.jobs/search.json"
)

AMAZON_JOB_BASE_URL = "https://www.amazon.jobs"

AMAZON_PAGE_SIZE = 100

REQUEST_TIMEOUT_SECONDS = 30.0

# Wider than the alert freshness window so lifecycle tracking still sees
# a posting after it stops being alert-worthy.
DEFAULT_HORIZON_DAYS = 45

DEFAULT_MAX_PAGES = 25

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _clean_html(
    value: str | None,
) -> str:
    """Convert Amazon posting HTML into normalized plain text."""

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


def parse_posted_date(
    value: object,
) -> datetime | None:
    """Parse Amazon's posting date.

    Amazon renders dates as "September  4, 2026", occasionally with
    doubled spacing, so whitespace is collapsed before parsing.
    """

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if not normalized:
        return None

    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(
                normalized,
                fmt,
            )

        except ValueError:
            continue

        return parsed.replace(
            tzinfo=timezone.utc
        )

    return None


def build_description(
    posting: dict[str, Any],
) -> str:
    """Join Amazon's three requirement sections into one description.

    The eligibility gate reads experience, citizenship and language
    requirements that live in the qualification sections rather than the
    main description, so all three must travel together.
    """

    parts = [
        _clean_html(
            posting.get(
                "description"
            )
        ),
        _clean_html(
            posting.get(
                "basic_qualifications"
            )
        ),
        _clean_html(
            posting.get(
                "preferred_qualifications"
            )
        ),
    ]

    return " ".join(
        part
        for part in parts
        if part
    ).strip()


def build_location(
    posting: dict[str, Any],
) -> str:
    """Return the most specific location Amazon supplies."""

    for key in (
        "normalized_location",
        "location",
    ):
        value = posting.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():
            return value.strip()

    city = str(
        posting.get(
            "city"
        )
        or ""
    ).strip()

    state = str(
        posting.get(
            "state"
        )
        or ""
    ).strip()

    joined = ", ".join(
        part
        for part in (
            city,
            state,
        )
        if part
    )

    return joined or "United States"


def _external_id(
    posting: dict[str, Any],
) -> str | None:
    """Return the durable identity of one Amazon posting."""

    for key in (
        "id_icims",
        "id",
    ):
        value = posting.get(
            key
        )

        if value is None:
            continue

        normalized = str(
            value
        ).strip()

        if normalized:
            return normalized

    return None


def fetch_amazon_jobs(
    *,
    company_name: str = "Amazon",
    client: httpx.Client | None = None,
    now: datetime | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    max_pages: int = DEFAULT_MAX_PAGES,
    country_code: str = "USA",
) -> list[CanonicalJob]:
    """Fetch recent US Amazon postings.

    Pages are walked newest first and stop as soon as an entire page
    predates the horizon, so a routine poll costs a handful of requests
    rather than the full index.
    """

    reference = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    cutoff = reference - timedelta(
        days=horizon_days
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
            follow_redirects=True,
        )
    )

    jobs: list[CanonicalJob] = []

    seen_ids: set[str] = set()

    try:
        for page in range(
            max_pages
        ):
            response = request_with_retry(
                lambda offset=(
                    page * AMAZON_PAGE_SIZE
                ): http.get(
                AMAZON_SEARCH_URL,
                params={
                    "base_query": "",
                    "offset": offset,
                    "result_limit": (
                        AMAZON_PAGE_SIZE
                    ),
                    "sort": "recent",
                    "normalized_country_code[]": (
                        country_code
                    ),
                },
                )
            )

            response.raise_for_status()

            postings = response.json().get(
                "jobs"
            )

            if not isinstance(
                postings,
                list,
            ) or not postings:
                break

            page_had_recent = False

            for posting in postings:
                if not isinstance(
                    posting,
                    dict,
                ):
                    continue

                external_id = _external_id(
                    posting
                )

                if external_id is None:
                    continue

                if external_id in seen_ids:
                    continue

                title = str(
                    posting.get(
                        "title"
                    )
                    or ""
                ).strip()

                if not title:
                    continue

                posted_at = parse_posted_date(
                    posting.get(
                        "posted_date"
                    )
                )

                if (
                    posted_at is not None
                    and posted_at >= cutoff
                ):
                    page_had_recent = True

                elif posted_at is None:
                    # An unparseable date is unknown, not old.
                    page_had_recent = True

                else:
                    continue

                seen_ids.add(
                    external_id
                )

                job_path = str(
                    posting.get(
                        "job_path"
                    )
                    or ""
                ).strip()

                official_url = (
                    f"{AMAZON_JOB_BASE_URL}"
                    f"{job_path}"
                    if job_path.startswith(
                        "/"
                    )
                    else AMAZON_JOB_BASE_URL
                )

                jobs.append(
                    CanonicalJob(
                        source=AMAZON_SOURCE,
                        company=company_name,
                        external_id=(
                            external_id
                        ),
                        requisition_id=(
                            external_id
                        ),
                        title=title,
                        location=(
                            build_location(
                                posting
                            )
                        ),
                        description=(
                            build_description(
                                posting
                            )
                        ),
                        official_url=(
                            official_url
                        ),
                        posted_at=posted_at,
                        updated_at=None,
                    )
                )

            # Results are newest first, so a page with nothing inside
            # the horizon means every later page is older still.
            if not page_had_recent:
                break

            if len(
                postings
            ) < AMAZON_PAGE_SIZE:
                break

    finally:
        if owns_client:
            http.close()

    return jobs
