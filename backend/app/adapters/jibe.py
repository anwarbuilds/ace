"""Jibe: iCIMS's careers sites, read from the job API they load.

AMD and Susquehanna (SIG) were on ACE's list of top employers with no
board ACE read. Both take applications through iCIMS, which ACE has no
reader for, and both show their openings on an iCIMS Jibe careers site
-- careers.amd.com, careers.sig.com -- that fills itself from
``/api/jobs``: every opening with its title, its place, the day it was
posted and its whole description. Both sites' robots.txt allow it and
ask for five seconds between requests, which this keeps.

The account is the address job pages live under, "careers.sig.com" or
"careers.amd.com/careers-home"; the API is on the same host.

How it is read
--------------
Newest first, a hundred at a time. Most polls read only until the
postings are three days old -- usually one page -- and say so: a
snapshot read in part closes nothing. When the first page has not
changed since the last poll (its ETag answers 304) nothing more is read.
Every four hours the whole list is read, and that read is complete, so
an opening taken down is closed: AMD's 1,300 openings are thirteen
pages, a little over a minute at the pace the site asks for.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import (
    datetime,
    timezone,
)

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


LOGGER = logging.getLogger(
    "ace.adapters.jibe",
)

SOURCE = "jibe"

# The API's own maximum.
PAGE_SIZE = 100

# 10,000 openings: a guard, not an expectation.
MAX_PAGES = 100

RECENT_DAYS = 3

FULL_READ_SECONDS = 4 * 60 * 60

# Both sites' robots.txt: "crawl-delay: 5".
CRAWL_DELAY_SECONDS = 5.0

TIMEOUT_SECONDS = 60.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

_TAG = re.compile(
    r"<[^>]+>",
)

_BLANK_LINES = re.compile(
    r"\n\s*\n+",
)

_last_full_read: dict[str, float] = {}

_first_page_etag: dict[str, str] = {}


def _text(
    value: object,
) -> str:
    if not value:
        return ""

    flattened = _TAG.sub(
        "\n",
        unescape_fully(
            str(value)
        ),
    )

    return _BLANK_LINES.sub(
        "\n",
        "\n".join(
            " ".join(line.split())
            for line in flattened.split("\n")
        ),
    ).strip()


def _when(
    value: object,
) -> datetime | None:
    text = str(value or "").strip()

    if not text:
        return None

    # "2026-10-09T01:42:00+0000"
    text = re.sub(
        r"([+-]\d{2})(\d{2})$",
        r"\1:\2",
        text,
    )

    try:
        moment = datetime.fromisoformat(
            text
        )
    except ValueError:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(
            tzinfo=timezone.utc,
        )

    return moment


def _location(
    data: dict,
) -> str:
    parts: list[str] = []

    for part in (
        data.get("city"),
        data.get("state"),
        data.get("country"),
    ):
        text = " ".join(
            str(part or "").split()
        )

        if text and text not in parts:
            parts.append(
                text
            )

    return ", ".join(
        parts
    ) or str(data.get("full_location") or "").strip() or "Unknown"


def canonical_job(
    data: dict,
    *,
    source_account: str,
    company_name: str,
) -> CanonicalJob | None:
    """One opening as a CanonicalJob, or None without an id or title."""

    slug = str(data.get("slug") or data.get("req_id") or "").strip()
    title = " ".join(
        str(data.get("title") or "").split()
    )

    if not slug or not title:
        return None

    description = "\n\n".join(
        part
        for part in (
            _text(data.get("description")),
            _text(data.get("responsibilities")),
            _text(data.get("qualifications")),
        )
        if part
    )

    posted = _when(
        data.get("posted_date")
    )

    return CanonicalJob(
        source=SOURCE,
        company=company_name,
        external_id=slug,
        requisition_id=str(data.get("req_id") or slug),
        title=title,
        location=_location(
            data
        ),
        description=description,
        official_url=(
            f"https://{source_account.strip('/')}/jobs/{slug}?lang=en-us"
        ),
        posted_at=posted,
        updated_at=_when(
            data.get("update_date")
        ),
        employment_type=(
            str(data.get("employment_type") or "").strip().lower()
            or None
        ),
    )


def fetch_jibe_jobs(
    *,
    source_account: str,
    company_name: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    full: bool | None = None,
    crawl_delay_seconds: float = CRAWL_DELAY_SECONDS,
) -> JobList:
    """Read one Jibe site's openings, in full every four hours."""

    moment = now or datetime.now(
        timezone.utc
    )

    clock = time.monotonic()

    if full is None:
        last = _last_full_read.get(
            source_account
        )

        full = last is None or clock - last >= FULL_READ_SECONDS

    host = source_account.split(
        "/",
        1,
    )[0]

    owns_client = client is None

    http = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    jobs: list[CanonicalJob] = []
    seen: set[str] = set()
    complete = False

    try:
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                time.sleep(
                    crawl_delay_seconds
                )

            headers = {}

            if page == 1 and not full and source_account in _first_page_etag:
                headers["If-None-Match"] = _first_page_etag[
                    source_account
                ]

            response = request_with_retry(
                lambda: http.get(
                    f"https://{host}/api/jobs",
                    params={
                        "page": page,
                        "limit": PAGE_SIZE,
                        "sortBy": "posted_date",
                        "descending": "true",
                        "internal": "false",
                    },
                    headers=headers,
                )
            )

            if response.status_code == 304:
                # Nothing new at the top of the list since the last poll.
                break

            response.raise_for_status()

            if page == 1 and response.headers.get("etag"):
                _first_page_etag[source_account] = response.headers[
                    "etag"
                ]

            rows = response.json().get("jobs") or []

            oldest = None

            for row in rows:
                job = canonical_job(
                    (row or {}).get("data") or {},
                    source_account=source_account,
                    company_name=company_name,
                )

                if job is None or job.external_id in seen:
                    continue

                seen.add(
                    job.external_id
                )

                jobs.append(
                    job
                )

                if job.posted_at is not None:
                    oldest = job.posted_at

            if len(rows) < PAGE_SIZE:
                complete = True
                break

            if (
                not full
                and oldest is not None
                and (moment - oldest).days >= RECENT_DAYS
            ):
                break

    finally:
        if owns_client:
            http.close()

    if complete:
        if not jobs:
            # An empty list is never taken as every posting closing.
            raise ValueError(
                f"{source_account} listed no openings."
            )

        _last_full_read[source_account] = clock

    LOGGER.info(
        "jibe_read account=%s jobs=%d complete=%s",
        source_account,
        len(jobs),
        complete,
    )

    return JobList(
        jobs,
        complete=complete,
    )
