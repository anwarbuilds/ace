"""Amazon Jobs adapter for ACE.

Amazon publishes a public JSON search endpoint behind amazon.jobs:

    GET https://www.amazon.jobs/search.json

Unlike an ATS board it is a search index over roughly ten thousand US
postings, most of them warehouse, retail and corporate roles.

What is read, and why all of it
-------------------------------

The adapter used to walk the whole US index newest first and stop at a
45-day horizon or 25 pages, whichever came first. Both limits lost
roles the user wants. Amazon keeps its new-graduate postings open for
months -- "Software Development Engineer - 2026 (US)" was posted in
February -- so the horizon hid them; and 2,500 postings cover only a
few weeks of the whole index, so everything older fell out of each
snapshot and was marked closed while still open.

It now reads a few job categories in full, with no horizon: software
development, machine learning science, and systems/quality/security
engineering. Every Amazon role that has ever passed the gate was in the
first. Software development was 1,701 US postings on 2026-10-04 --
eighteen requests.

A snapshot is authoritative: whatever it lacks is closed. So a category
that does not finish inside its page budget raises rather than return
part of itself.

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
    timezone,
)
import html
import re
from typing import Any

import httpx

from backend.app.adapters.html_text import (
    unescape_fully,
)
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

# The categories read, by amazon.jobs's own slugs.
AMAZON_CATEGORIES = (
    "software-development",
    "machine-learning-science",
    "systems-quality-security-engineering",
)

# Pages per category before giving up on it. Software development, the
# largest, needed eighteen on 2026-10-04.
MAX_PAGES_PER_CATEGORY = 60


class IncompleteAmazonRead(RuntimeError):
    """A category did not finish inside its page budget.

    Raised rather than returning part of it, because a snapshot is
    authoritative and everything it lacks would be marked closed.
    """

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


def _canonical_job(
    posting: Any,
    *,
    company_name: str,
    seen_ids: set[str],
) -> CanonicalJob | None:
    """One search result as a canonical job, or None to skip it.

    Skipped: anything malformed, untitled, or already seen -- the same
    posting can be filed under two of the categories read.
    """

    if not isinstance(
        posting,
        dict,
    ):
        return None

    external_id = _external_id(
        posting
    )

    if (
        external_id is None
        or external_id in seen_ids
    ):
        return None

    title = str(
        posting.get(
            "title"
        )
        or ""
    ).strip()

    if not title:
        return None

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

    return CanonicalJob(
        source=AMAZON_SOURCE,
        company=company_name,
        external_id=external_id,
        requisition_id=external_id,
        title=title,
        location=build_location(
            posting
        ),
        description=build_description(
            posting
        ),
        official_url=official_url,
        posted_at=parse_posted_date(
            posting.get(
                "posted_date"
            )
        ),
        updated_at=None,
    )


def fetch_amazon_jobs(
    *,
    company_name: str = "Amazon",
    client: httpx.Client | None = None,
    categories: tuple[str, ...] = AMAZON_CATEGORIES,
    max_pages_per_category: int = (
        MAX_PAGES_PER_CATEGORY
    ),
    country_code: str = "USA",
) -> list[CanonicalJob]:
    """Fetch every US Amazon posting in the categories ACE reads."""

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
        for category in categories:
            offset = 0

            for _ in range(
                max_pages_per_category
            ):
                response = request_with_retry(
                    lambda offset=offset: http.get(
                        AMAZON_SEARCH_URL,
                        params={
                            "base_query": "",
                            "offset": offset,
                            "result_limit": (
                                AMAZON_PAGE_SIZE
                            ),
                            # A stable order, so paging neither repeats
                            # nor skips while the walk is under way.
                            "sort": "recent",
                            "normalized_country_code[]": (
                                country_code
                            ),
                            "category[]": category,
                        },
                    )
                )

                response.raise_for_status()

                body = response.json()

                postings = body.get(
                    "jobs"
                )

                if not isinstance(
                    postings,
                    list,
                ) or not postings:
                    break

                for posting in postings:
                    job = _canonical_job(
                        posting,
                        company_name=company_name,
                        seen_ids=seen_ids,
                    )

                    if job is not None:
                        jobs.append(
                            job
                        )

                offset += len(
                    postings
                )

                hits = body.get(
                    "hits"
                )

                if len(
                    postings
                ) < AMAZON_PAGE_SIZE or (
                    isinstance(
                        hits,
                        int,
                    )
                    and offset >= hits
                ):
                    break

            else:
                raise IncompleteAmazonRead(
                    (
                        f"Amazon category {category!r} did not "
                        f"finish in {max_pages_per_category} "
                        "pages; refusing to treat part of it as "
                        "the whole."
                    )
                )

    finally:
        if owns_client:
            http.close()

    return jobs
