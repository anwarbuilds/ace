"""Google: the first page of its own careers searches, newest first.

Google was the largest employer ACE could not read. Its careers search,
google.com/about/careers/applications/jobs/results, is rendered on the
server with every result's whole posting embedded in the page -- title,
places, about the job, responsibilities, minimum and preferred
qualifications, when it was created and last updated -- twenty to a
page.

google.com's robots.txt forbids paging through those results (any
address with ``page=``) and allows the first page of any search, and
each posting's own page. So ACE never reads past the first page.
Instead it asks a few narrow searches, each sorted newest first, often
enough that fewer than twenty new or updated postings can arrive between
two polls: the first page of each is everything that changed.

The searches, all in the United States:

- every early-career posting, in any field (about a hundred);
- mid-level postings matching "software engineer" -- Google's
  "Software Engineer III" asks about two years;
- mid-level postings matching "machine learning".

What it cannot see, it does not claim: every read is partial, so a
posting that leaves the first page is never closed for it. ACE hides
openings older than thirty days in any case.
"""

from __future__ import annotations

import json
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
    "ace.adapters.google",
)

SOURCE = "google"

RESULTS = "https://www.google.com/about/careers/applications/jobs/results"

POSTING = RESULTS + "/{id}-{slug}"

# Each the first page only: robots.txt disallows "page=".
SEARCHES = (
    {
        "location": "United States",
        "target_level": "EARLY",
        "sort_by": "date",
    },
    {
        "location": "United States",
        "target_level": "MID",
        "q": "software engineer",
        "sort_by": "date",
    },
    {
        "location": "United States",
        "target_level": "MID",
        "q": "machine learning",
        "sort_by": "date",
    },
)

PAUSE_SECONDS = 2.0

TIMEOUT_SECONDS = 60.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

_DATA_BLOCK = re.compile(
    r"AF_initDataCallback\((\{.*?\})\);</script>",
    re.DOTALL,
)

_DATA = re.compile(
    r"data:(.*), sideChannel:",
    re.DOTALL,
)

_TAG = re.compile(
    r"<[^>]+>",
)

_BLANK_LINES = re.compile(
    r"\n\s*\n+",
)


def _text(
    value: object,
) -> str:
    """One of the page's [null, "<html>"] fields as plain text."""

    if isinstance(value, list):
        value = value[1] if len(value) > 1 else None

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
    """[seconds, nanos] since the epoch."""

    if not isinstance(value, list) or not value:
        return None

    try:
        return datetime.fromtimestamp(
            int(value[0]),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OverflowError):
        return None


def _slug(
    title: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "-",
        title.casefold(),
    ).strip("-") or "role"


def _field(
    row: list,
    index: int,
):
    return row[index] if len(row) > index else None


def parse_results(
    markup: str,
) -> list[list]:
    """The result rows a search page carries."""

    for block in _DATA_BLOCK.findall(
        markup
    ):
        if "'ds:1'" not in block and '"ds:1"' not in block:
            continue

        found = _DATA.search(
            block
        )

        if found is None:
            break

        data = json.loads(
            found.group(1)
        )

        rows = data[0] if data and isinstance(data[0], list) else []

        return [
            row
            for row in rows
            if isinstance(row, list)
        ]

    raise ValueError(
        "Google's results page carried no results data."
    )


def canonical_job(
    row: list,
) -> CanonicalJob | None:
    """One result as a CanonicalJob, or None without an id or title."""

    job_id = str(_field(row, 0) or "").strip()
    title = " ".join(
        str(_field(row, 1) or "").split()
    )

    if not job_id or not title:
        return None

    places = [
        str(place[0]).strip()
        for place in _field(row, 9) or []
        if isinstance(place, list) and place and place[0]
    ]

    description = "\n\n".join(
        part
        for part in (
            _text(_field(row, 10)),
            _text(_field(row, 3)),
            _text(_field(row, 4)),
        )
        if part
    )

    return CanonicalJob(
        source=SOURCE,
        company=str(_field(row, 7) or "Google").strip() or "Google",
        external_id=job_id,
        requisition_id=job_id,
        title=title,
        location="; ".join(places) or "United States",
        description=description,
        official_url=POSTING.format(
            id=job_id,
            slug=_slug(title),
        ),
        # When the posting was created, not when it was last touched:
        # a requisition reopened today after a year is a year-old
        # opening.
        posted_at=_when(
            _field(row, 12)
        ),
        updated_at=_when(
            _field(row, 14)
        ),
    )


def fetch_google_jobs(
    *,
    client: httpx.Client | None = None,
    searches: tuple[dict, ...] = SEARCHES,
    pause_seconds: float = PAUSE_SECONDS,
) -> JobList:
    """Read the first page of each search. Always a partial read."""

    owns_client = client is None

    http = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    jobs: dict[str, CanonicalJob] = {}

    try:
        for index, search in enumerate(searches):
            if "page" in search:
                raise ValueError(
                    "Google's robots.txt disallows paging its results."
                )

            if index:
                time.sleep(
                    pause_seconds
                )

            response = request_with_retry(
                lambda: http.get(
                    RESULTS,
                    params=search,
                )
            )

            response.raise_for_status()

            for row in parse_results(
                response.text
            ):
                job = canonical_job(
                    row
                )

                if job is not None:
                    jobs.setdefault(
                        job.external_id,
                        job,
                    )

    finally:
        if owns_client:
            http.close()

    LOGGER.info(
        "google_read jobs=%d searches=%d",
        len(jobs),
        len(searches),
    )

    return JobList(
        list(jobs.values()),
        complete=False,
    )
