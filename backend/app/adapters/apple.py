"""Apple: its own careers search, read from the pages it serves.

Apple was on ACE's list of top employers with no board ACE read: its
careers site, jobs.apple.com, is its own. It publishes no robots.txt --
the path redirects to apple.com's page-not-found -- and every search
page is rendered on the server with its results embedded as JSON
(``window.__staticRouterHydrationData``), the same rows the page shows,
twenty a page. That is what this reads. The site's own JSON API asks for
a session token, and ACE does not use it.

Which openings
--------------
The search is narrowed to the United States and to the teams whose work
is software and machine learning: Apple's sub-teams under Software and
Services and under Machine Learning and AI, and the software ones under
Hardware. On 2026-10-08 that was 1,439 rows of Apple's 4,440 US
openings; the rest were retail stores, AppleCare and corporate
functions. A row is one posting in one place, so a posting open in three
cities is three rows, merged here into one job.

The site splits its team list on a literal "+". An encoded one reads as
a single unknown team, and the search quietly falls back to every team.

How it is read
--------------
Newest first. Most polls read only until the postings are two days old
-- a page or a few -- and say so: a snapshot read in part closes
nothing. Every four hours the whole list is read, about seventy pages,
and that read is complete, so an opening Apple has taken down is closed.

Descriptions
------------
The list carries a summary only. A posting's own page carries the rest
-- the description, the minimum and preferred qualifications ("3+ years
of ..."), every location with its state, and Apple's level -- and is
read only for a title the gate could pass, and only once: a posting ACE
already holds keeps the description it was first read with.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Mapping
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
    "ace.adapters.apple",
)

SOURCE = "apple"

COMPANY = "Apple"

SEARCH = "https://jobs.apple.com/en-us/search"

DETAILS = "https://jobs.apple.com/en-us/details/{id}/{slug}"

# The site's own page size.
PAGE_SIZE = 20

# 3,000 rows: a guard against a search that never stops paging, not an
# expectation.
MAX_PAGES = 150

# A posting published within this many days is read on every poll.
RECENT_DAYS = 2

FULL_READ_SECONDS = 4 * 60 * 60

# Courtesy pauses on somebody else's site.
PAGE_PAUSE_SECONDS = 1.0

DETAIL_PAUSE_SECONDS = 0.5

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

# As Apple's own careers pages link to them, 2026-10-08. Left out:
# product design, program management, trust and safety, privacy and
# security policy, and AI data operations.
TEAMS = (
    # Software and Services
    "apps-and-frameworks-SFTWR-AF",
    "camera-and-photos-SFTWR-CP",
    "cloud-and-back-end-infrastructure-SFTWR-CLD",
    "devops-and-site-reliability-SFTWR-DSR",
    "gpu-and-graphics-SFTWR-GPUG",
    "information-systems-and-technology-SFTWR-ISTECH",
    "machine-learning-and-ai-SFTWR-MCHLN",
    "operating-systems-SFTWR-COS",
    "security-and-privacy-SFTWR-SEC",
    "software-quality-automation-tools-and-validation-SFTWR-SQAT",
    "spatial-computing-SFTWR-SC",
    "user-experience-engineering-SFTWR-UEE",
    "video-media-and-audio-technologies-SFTWR-VMAT",
    "wireless-software-SFTWR-WSFT",
    # Machine Learning and AI
    "computer-vision-MLAI-CV",
    "data-science-engineering-and-generation-MLAI-DSEG",
    "deep-learning-generative-ai-and-foundation-models-MLAI-DLRL",
    "information-systems-and-technology-MLAI-IST",
    "machine-learning-compute-and-infrastructure-MLAI-MLI",
    "mapping-and-motion-MLAI-MM",
    "natural-language-processing-and-speech-technologies-MLAI-NLP",
    "responsible-ai-and-safety-MLAI-RAIS",
    "search-and-knowledge-MLAI-SK",
    # Hardware's software teams
    "embedded-systems-firmware-development-HRDWR-ESFD",
    "machine-learning-and-ai-HRDWR-MCHLN",
    "software-quality-automation-tools-and-validation-HRDWR-SQATV",
)

_HYDRATION = re.compile(
    r"window\.__staticRouterHydrationData\s*=\s*JSON\.parse\((\".*?\")\);",
    re.DOTALL,
)

_TAG = re.compile(
    r"<[^>]+>",
)

_BLANK_LINES = re.compile(
    r"\n\s*\n+",
)

_last_full_read: dict[str, float] = {}


def _page_url(
    page: int,
) -> str:
    return (
        f"{SEARCH}?location=united-states-USA&sort=newest&page={page}"
        f"&team={'+'.join(TEAMS)}"
    )


def _loader_data(
    markup: str,
) -> dict:
    """The JSON a server-rendered page carries."""

    found = _HYDRATION.search(
        markup
    )

    if found is None:
        raise ValueError(
            "Apple's page carried no hydration data."
        )

    return json.loads(
        json.loads(
            found.group(1)
        )
    ).get("loaderData") or {}


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

    lines = [
        " ".join(line.split())
        for line in flattened.split("\n")
    ]

    return _BLANK_LINES.sub(
        "\n",
        "\n".join(lines),
    ).strip()


def _posted_at(
    value: object,
) -> datetime | None:
    text = str(value or "").strip()

    if not text:
        return None

    # "2026-10-09T01:57:37.474065956Z": more fractional digits than
    # Python reads.
    text = re.sub(
        r"(\.\d{6})\d+",
        r"\1",
        text,
    ).replace(
        "Z",
        "+00:00",
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


def _row_place(
    row: dict,
) -> list[str]:
    places = [
        f"{location.get('name')}, United States"
        for location in row.get("locations") or []
        if location.get("name")
    ]

    if row.get("homeOffice"):
        places.append(
            "Remote, United States"
        )

    return places


def _detail_place(
    location: dict,
) -> str:
    parts: list[str] = []

    for part in (
        location.get("city") or location.get("name"),
        location.get("stateProvince"),
        location.get("countryName"),
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
    )


def parse_search_page(
    markup: str,
) -> tuple[list[dict], int]:
    """The rows of one search page, and how many rows the search holds."""

    search = _loader_data(
        markup
    ).get("search") or {}

    teams = (search.get("filters") or {}).get("teams") or []

    if len(teams) != len(TEAMS):
        # A team Apple has renamed or retired is dropped from the
        # filter, and its postings are not read.
        LOGGER.warning(
            "apple_team_filter teams_recognised=%d of=%d",
            len(teams),
            len(TEAMS),
        )

    return (
        list(
            search.get("searchResults") or []
        ),
        int(
            search.get("totalRecords") or 0
        ),
    )


def parse_job_page(
    markup: str,
) -> tuple[str, str] | None:
    """A posting's own page as its locations and its description."""

    data = (
        _loader_data(
            markup
        ).get("jobDetails")
        or {}
    ).get("jobsData")

    if not data:
        return None

    places = [
        _detail_place(location)
        for location in data.get("locations") or []
    ]

    if data.get("homeOffice"):
        places.append(
            "Remote, United States"
        )

    sections = [
        _text(data.get("jobSummary")),
        _text(data.get("description")),
    ]

    for heading, key in (
        ("Minimum Qualifications", "minimumQualifications"),
        ("Preferred Qualifications", "preferredQualifications"),
    ):
        body = _text(
            data.get(key)
        )

        if body:
            sections.append(
                f"{heading}\n{body}"
            )

    low = _text(data.get("lowJobTitle"))
    high = _text(data.get("highJobTitle"))

    if low or high:
        sections.append(
            "Apple job level: "
            + (f"{low} to {high}" if low and high and low != high else low or high)
            + "."
        )

    return (
        "; ".join(
            place
            for place in places
            if place
        ),
        "\n\n".join(
            section
            for section in sections
            if section
        ),
    )


def fetch_apple_jobs(
    *,
    source_account: str = "jobs.apple.com",
    client: httpx.Client | None = None,
    now: datetime | None = None,
    full: bool | None = None,
    should_fetch_detail: Callable[[str], bool] | None = None,
    known: Mapping[str, tuple[str, str]] | None = None,
    page_pause_seconds: float = PAGE_PAUSE_SECONDS,
    detail_pause_seconds: float = DETAIL_PAUSE_SECONDS,
) -> JobList:
    """Read Apple's software and machine-learning openings in the US.

    ``known`` is what ACE already holds for a posting -- its location
    and description -- so a posting's own page is read once, not on
    every poll.
    """

    moment = now or datetime.now(
        timezone.utc
    )

    clock = time.monotonic()

    if full is None:
        last = _last_full_read.get(
            source_account
        )

        full = last is None or clock - last >= FULL_READ_SECONDS

    owns_client = client is None

    http = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    # One posting, however many rows it came as.
    postings: dict[str, dict] = {}
    complete = False

    try:
        for page in range(1, MAX_PAGES + 1):
            response = request_with_retry(
                lambda: http.get(
                    _page_url(page)
                )
            )

            response.raise_for_status()

            rows, total = parse_search_page(
                response.text
            )

            oldest = None

            for row in rows:
                position = str(row.get("positionId") or "").strip()
                title = " ".join(
                    str(row.get("postingTitle") or "").split()
                )

                if not position or not title:
                    continue

                posted = _posted_at(
                    row.get("postDateInGMT")
                )

                # "200683887-0836": the identifier the site's own links
                # use. The bare number redirects to it.
                row_id = str(row.get("id") or "").strip()

                posting = postings.setdefault(
                    position,
                    {
                        "path": (
                            row_id
                            if row_id.startswith(position)
                            else position
                        ),
                        "title": title,
                        "slug": str(
                            row.get("transformedPostingTitle") or ""
                        ).strip(),
                        "posted": posted,
                        "places": [],
                    },
                )

                for place in _row_place(row):
                    if place not in posting["places"]:
                        posting["places"].append(
                            place
                        )

                if posted is not None:
                    oldest = posted

            if len(rows) < PAGE_SIZE or page * PAGE_SIZE >= total:
                complete = True
                break

            if (
                not full
                and oldest is not None
                and (moment - oldest).days >= RECENT_DAYS
            ):
                break

            time.sleep(
                page_pause_seconds
            )

        jobs: list[CanonicalJob] = []

        for position, posting in postings.items():
            location = "; ".join(
                posting["places"]
            ) or "United States"
            description = ""

            held = (known or {}).get(
                position
            )

            if held and held[1]:
                location, description = held
            elif should_fetch_detail is None or should_fetch_detail(
                posting["title"]
            ):
                try:
                    page_response = request_with_retry(
                        lambda: http.get(
                            DETAILS.format(
                                id=posting["path"],
                                slug=posting["slug"] or "role",
                            )
                        )
                    )

                    page_response.raise_for_status()

                    detail = parse_job_page(
                        page_response.text
                    )
                except (httpx.HTTPError, ValueError) as error:
                    LOGGER.warning(
                        "apple_detail_failed id=%s error=%s",
                        position,
                        error,
                    )

                    detail = None

                if detail is not None:
                    location = detail[0] or location
                    description = detail[1]

                time.sleep(
                    detail_pause_seconds
                )

            jobs.append(
                CanonicalJob(
                    source=SOURCE,
                    company=COMPANY,
                    external_id=position,
                    requisition_id=position,
                    title=posting["title"],
                    location=location,
                    description=description,
                    official_url=DETAILS.format(
                        id=posting["path"],
                        slug=posting["slug"] or "role",
                    ),
                    posted_at=posting["posted"],
                )
            )

    finally:
        if owns_client:
            http.close()

    if complete:
        _last_full_read[source_account] = clock

    LOGGER.info(
        "apple_read jobs=%d complete=%s",
        len(jobs),
        complete,
    )

    return JobList(
        jobs,
        complete=complete,
    )
