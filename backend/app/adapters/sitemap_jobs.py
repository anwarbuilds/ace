"""Careers sites that list every posting in a sitemap and describe each
posting's own page with schema.org JobPosting.

Meta, Intuit, Arm and Synopsys were on ACE's list of top employers with
no board ACE could read. Their careers searches are closed to it --
Meta's loads through a token-guarded GraphQL call, and Intuit's, Arm's
and Synopsys's Radancy sites disallow ``/search-jobs/`` in robots.txt --
but each publishes a sitemap of every open posting, which robots.txt
names or leaves open, and each posting's own page carries a JobPosting
in JSON-LD: title, places, the day it was posted, the whole description.
That is what this reads.

- Meta: ``www.metacareers.com/jobsearch/sitemap.xml``, the sitemap its
  robots.txt names, about 1,100 postings at ``/profile/job_details/<id>/``.
  The sitemap carries no titles, so every posting's page is read --
  once, and again after a month -- at most ``MAX_READS_PER_POLL`` a poll,
  so the first pass spreads over a few hours.
- Radancy (Intuit, Arm, Synopsys): ``/sitemap.xml``, with postings at
  ``/job/<city>/<title>/<org>/<id>``. The title in the address decides
  whether the page is worth reading at all, as it does for every board
  that lists before it describes.

The sitemap is the whole board, so a read is complete: a posting that
leaves it is closed. A posting not yet read is left out rather than
guessed at; it was never stored, so leaving it out closes nothing.

Each reading is kept in the shared reading store under the posting's
address plus ``#jobposting``, so it never stands in for the employer-page
reading a feed posting at the same address might need.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

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
from backend.app.verification.employer_page import (
    READ,
    UNREACHABLE,
    Reading,
    ReadingStore,
)


LOGGER = logging.getLogger(
    "ace.adapters.sitemap_jobs",
)

SOURCE = "jobposting_sitemap"

# A courtesy limit on somebody else's site.
MAX_READS_PER_POLL = 120

PAUSE_SECONDS = 1.0

# Requirements rarely change once posted, and a posting that closes
# leaves the sitemap.
REREAD_AFTER = timedelta(
    days=30,
)

# A page that could not be read is tried again sooner.
RETRY_AFTER = timedelta(
    days=1,
)

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

READING_SUFFIX = "#jobposting"

_URL_ENTRY = re.compile(
    r"<url>(.*?)</url>",
    re.DOTALL,
)

_LOC = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>",
)

_JSON_LD = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)

_TAG = re.compile(
    r"<[^>]+>",
)

_BLANK_LINES = re.compile(
    r"\n\s*\n+",
)


@dataclass(frozen=True)
class Site:
    """Where one site keeps its sitemap and its postings."""

    sitemap: str

    # Matches a posting's address; group "id" is its identifier, and
    # "slug" and "city", where present, its title and place.
    posting: re.Pattern

    titled: bool


def site_for(
    host: str,
) -> Site:
    """The layout of one careers site, by its host."""

    host = host.strip().strip("/").lower()

    if host.endswith("metacareers.com"):
        return Site(
            sitemap=f"https://{host}/jobsearch/sitemap.xml",
            posting=re.compile(
                rf"^https://{re.escape(host)}/profile/job_details/"
                r"(?P<id>\d+)/?$"
            ),
            titled=False,
        )

    # Radancy: "/job/<city>/<title>/<org id>/<job id>".
    return Site(
        sitemap=f"https://{host}/sitemap.xml",
        posting=re.compile(
            rf"^https://{re.escape(host)}/job/(?P<city>[^/]+)/"
            r"(?P<slug>[^/]+)/\d+/(?P<id>\d+)/?$"
        ),
        titled=True,
    )


@dataclass(frozen=True)
class Listed:
    """One posting as the sitemap names it."""

    url: str

    external_id: str

    title: str

    city: str


def _words(
    slug: str,
) -> str:
    return " ".join(
        part.capitalize()
        for part in slug.replace("_", "-").split("-")
        if part
    )


def parse_sitemap(
    markup: str,
    site: Site,
) -> list[Listed]:
    """Every posting a sitemap lists."""

    listed: list[Listed] = []
    seen: set[str] = set()

    for entry in _URL_ENTRY.findall(markup) or [markup]:
        for url in _LOC.findall(entry):
            url = unescape_fully(url).strip()

            found = site.posting.match(url)

            if found is None:
                continue

            groups = found.groupdict()
            external_id = groups["id"]

            if external_id in seen:
                continue

            seen.add(
                external_id
            )

            listed.append(
                Listed(
                    url=url,
                    external_id=external_id,
                    title=_words(groups.get("slug") or ""),
                    city=_words(groups.get("city") or ""),
                )
            )

    return listed


def _text(
    value: object,
) -> str:
    if isinstance(value, list):
        value = "\n".join(
            str(item)
            for item in value
        )

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


def _postings_in(
    value: Any,
) -> list[dict]:
    if isinstance(value, list):
        return [
            found
            for item in value
            for found in _postings_in(item)
        ]

    if isinstance(value, dict):
        kind = value.get("@type")

        if kind == "JobPosting" or (
            isinstance(kind, list) and "JobPosting" in kind
        ):
            return [value]

        return _postings_in(
            value.get("@graph")
        )

    return []


def parse_posting_page(
    markup: str,
) -> dict | None:
    """The JobPosting a page describes itself with, or None."""

    for block in _JSON_LD.findall(
        markup
    ):
        try:
            data = json.loads(
                block.strip()
            )
        except ValueError:
            continue

        postings = _postings_in(
            data
        )

        if postings:
            return postings[0]

    return None


def _name(
    value: object,
) -> str:
    if isinstance(value, dict):
        value = value.get("name")

    return " ".join(
        str(value or "").split()
    )


def _places(
    posting: dict,
) -> list[str]:
    located = posting.get("jobLocation") or []

    if isinstance(located, dict):
        located = [located]

    places: list[str] = []

    for place in located:
        if not isinstance(place, dict):
            continue

        address = place.get("address") or {}

        if isinstance(address, list):
            address = address[0] if address else {}

        parts: list[str] = []

        for part in (
            address.get("addressLocality"),
            address.get("addressRegion"),
            _name(address.get("addressCountry")),
        ):
            text = " ".join(
                str(part or "").split()
            )

            if text and text not in parts:
                parts.append(
                    text
                )

        place_text = ", ".join(parts) or _name(place)

        if place_text and place_text not in places:
            places.append(
                place_text
            )

    if str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        required = posting.get("applicantLocationRequirements") or []

        if isinstance(required, dict):
            required = [required]

        countries = [
            _name(country)
            for country in required
            if _name(country)
        ]

        places.append(
            "Remote - " + (", ".join(countries) if countries else "anywhere")
        )

    return places


def _posted(
    value: object,
) -> datetime | None:
    text = str(value or "").strip()

    if not text:
        return None

    try:
        moment = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(
            tzinfo=timezone.utc,
        )

    return moment


def canonical_job(
    posting: dict,
    listed: Listed,
    *,
    company_name: str,
) -> CanonicalJob | None:
    """One posting's JobPosting as a CanonicalJob."""

    title = " ".join(
        unescape_fully(
            str(posting.get("title") or "")
        ).split()
    ) or listed.title

    if not title:
        return None

    description = "\n\n".join(
        part
        for part in (
            _text(posting.get("description")),
            _text(posting.get("responsibilities")),
            _text(posting.get("qualifications")),
            _text(posting.get("experienceRequirements")),
        )
        if part
    )

    employment = posting.get("employmentType")

    if isinstance(employment, list):
        employment = ", ".join(
            str(item)
            for item in employment
        )

    return CanonicalJob(
        source=SOURCE,
        company=company_name,
        external_id=listed.external_id,
        requisition_id=listed.external_id,
        title=title,
        location="; ".join(_places(posting)) or listed.city or "Unknown",
        description=description,
        official_url=listed.url,
        posted_at=_posted(
            posting.get("datePosted")
        ),
        employment_type=(
            str(employment or "").strip().lower() or None
        ),
    )


def _due(
    reading: Reading,
    checked_at: datetime,
    moment: datetime,
) -> bool:
    age = moment - checked_at

    return age >= (
        REREAD_AFTER
        if reading.status == READ
        else RETRY_AFTER
    )


def fetch_sitemap_jobs(
    *,
    host: str,
    company_name: str,
    client: httpx.Client | None = None,
    should_fetch_detail: Callable[[str], bool] | None = None,
    store: ReadingStore | None = None,
    now: Callable[[], datetime] | None = None,
    max_reads: int = MAX_READS_PER_POLL,
    pause_seconds: float = PAUSE_SECONDS,
) -> JobList:
    """Read one careers site's sitemap and the postings worth reading."""

    site = site_for(
        host
    )

    store = store or ReadingStore()

    clock = now or (
        lambda: datetime.now(timezone.utc)
    )

    owns_client = client is None

    http = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    try:
        response = request_with_retry(
            lambda: http.get(
                site.sitemap
            )
        )

        response.raise_for_status()

        listed = parse_sitemap(
            response.text,
            site,
        )

        if not listed:
            # An empty or unreadable sitemap is never taken as every
            # posting closing at once.
            raise ValueError(
                f"{host}'s sitemap listed no postings."
            )

        moment = clock()

        keys = {
            entry.external_id: entry.url + READING_SUFFIX
            for entry in listed
        }

        stored = store.load(
            list(keys.values())
        )

        wanted = [
            entry
            for entry in listed
            if not site.titled
            or should_fetch_detail is None
            or should_fetch_detail(entry.title)
        ]

        wanted_ids = {
            entry.external_id
            for entry in wanted
        }

        due = [
            entry
            for entry in wanted
            if keys[entry.external_id] not in stored
            or _due(
                *stored[keys[entry.external_id]],
                moment,
            )
        ][:max_reads]

        fresh: dict[str, Reading] = {}

        for index, entry in enumerate(due):
            if index:
                time.sleep(
                    pause_seconds
                )

            try:
                page = request_with_retry(
                    lambda: http.get(
                        entry.url
                    )
                )

                page.raise_for_status()

                posting = parse_posting_page(
                    page.text
                )
            except (httpx.HTTPError, ValueError) as error:
                LOGGER.warning(
                    "sitemap_posting_failed host=%s id=%s error=%s",
                    host,
                    entry.external_id,
                    error,
                )

                posting = None

            fresh[keys[entry.external_id]] = (
                Reading(
                    READ,
                    json.dumps(
                        posting,
                        separators=(",", ":"),
                    ),
                )
                if posting is not None
                else Reading(
                    UNREACHABLE,
                )
            )

        store.save(
            fresh,
            moment=moment,
        )

    finally:
        if owns_client:
            http.close()

    readings = {
        key: reading
        for key, (reading, _checked) in stored.items()
    }

    for key, reading in fresh.items():
        # An earlier good reading survives a failed one, as it does in
        # the store.
        if reading.status == READ or key not in readings:
            readings[key] = reading

    jobs: list[CanonicalJob] = []

    for entry in listed:
        reading = readings.get(
            keys[entry.external_id]
        )

        posting = None

        if reading is not None and reading.status == READ and reading.description:
            try:
                posting = json.loads(
                    reading.description
                )
            except ValueError:
                posting = None

        if posting is not None:
            job = canonical_job(
                posting,
                entry,
                company_name=company_name,
            )
        elif site.titled and entry.external_id not in wanted_ids:
            # Rejected on the title in its address: kept, so the board
            # is whole, without a page anyone needed to read.
            job = CanonicalJob(
                source=SOURCE,
                company=company_name,
                external_id=entry.external_id,
                requisition_id=entry.external_id,
                title=entry.title,
                location=entry.city or "Unknown",
                description="",
                official_url=entry.url,
            )
        else:
            # Worth reading and not read yet: left out until it is.
            job = None

        if job is not None:
            jobs.append(
                job
            )

    LOGGER.info(
        "sitemap_read host=%s listed=%d read_now=%d jobs=%d",
        host,
        len(listed),
        len(fresh),
        len(jobs),
    )

    return JobList(
        jobs,
        complete=True,
    )
