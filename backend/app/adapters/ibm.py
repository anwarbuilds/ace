"""IBM: its own careers search, the one source of IBM's openings ACE can read.

On 2026-10-08 the user found IBM's "2027 Entry-Level -- Software
Developer, AI & Marketing Platforms" in New York, posted two days
before, and it had never been in ACE. No IBM role ever had been: not
from IBM, and not from any feed.

IBM's careers site, careers.ibm.com, is an Avature portal behind an AWS
WAF JavaScript challenge. Every job page, every listing and every
per-locale sitemap answers 202 with an empty body and
``x-amzn-waf-action: challenge``. That is an access control, and ACE
does not get round access controls.

ibm.com/careers/search shows the same openings through IBM's own site
search, served by ``www-api.ibm.com/search/api/v2`` to any browser with
no challenge: every opening, with its title, its city, IBM's career
level and job category, the day it was posted, and the careers.ibm.com
link the user applies through. That is what this reads, asking for
exactly the fields IBM's own search page asks for; the API refuses any
other.

What it cannot see is the full description. The search returns a
two-line excerpt, and the posting's own page is behind the challenge.
The excerpt is kept, and IBM's career level is written into the
description so that "Entry Level" reaches the early-career rules.
Anything the gate wants from a full description stays unverified for
IBM.

How it is read
--------------
Newest first, a hundred at a time. Most polls read only until the
postings are three days old -- IBM posts and refreshes about two
hundred a day, so two to six requests -- and say so: a snapshot read
in part closes nothing. Every two hours the whole list is read, about
twenty-four requests for 2,400 openings, and that read is complete, so
an opening IBM has taken down is closed.

Locations
---------
IBM writes "City, CC" with a two-letter country code, and four of the
codes it uses -- CA, DE, CO, IN -- are also US states: 43 Canadian and
19 German openings would have read as Californian and Delawarean. The
code is written out as the country's name.

"Multiple Cities" carries no country at all: 361 openings, US ones among
them. When the title names US places -- "Site Reliability Engineer ELH -
OneIT - Durham, NC - 2027" -- those become the location. Otherwise it
stays "Multiple Cities", which the gate does not place in the US.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import (
    datetime,
    timezone,
)
from urllib.parse import (
    parse_qs,
    urlsplit,
)

import httpx

from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import (
    CanonicalJob,
    JobList,
)


LOGGER = logging.getLogger(
    "ace.adapters.ibm",
)

SOURCE = "ibm"

COMPANY = "IBM"

API = "https://www-api.ibm.com/search/api/v2"

# The search's own maximum.
PAGE_SIZE = 100

# 6,000 openings: a guard against a search that never stops paging, not
# an expectation.
MAX_PAGES = 60

# A posting refreshed or published within this many days is read on
# every poll.
RECENT_DAYS = 3

FULL_READ_SECONDS = 2 * 60 * 60

# A courtesy pause between pages of somebody else's search.
PAUSE_SECONDS = 0.5

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

# Exactly what IBM's search page asks for. Anything else is refused.
FIELDS = [
    "_id",
    "title",
    "url",
    "description",
    "language",
    "entitled",
    "field_keyword_17",
    "field_keyword_08",
    "field_keyword_18",
    "field_keyword_19",
    "dcdate",
]

# Every country IBM listed an opening in on 2026-10-08, and the
# neighbours it is likeliest to add, written the way the gate's list of
# countries reads them.
COUNTRIES = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "EG": "Egypt",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HK": "Hong Kong",
    "HR": "Croatia",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IT": "Italy",
    "JP": "Japan",
    "KE": "Kenya",
    "KR": "South Korea",
    "LK": "Sri Lanka",
    "LT": "Lithuania",
    "LV": "Latvia",
    "MA": "Morocco",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",
    "PE": "Peru",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RS": "Serbia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "TH": "Thailand",
    "TR": "Turkey",
    "TW": "Taiwan",
    "UA": "Ukraine",
    "UY": "Uruguay",
    "VN": "Vietnam",
    "ZA": "South Africa",
}

_US_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    "MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|"
    "UT|VT|VA|WA|WV|WI|WY"
)

# "Durham, NC", "Rochester, MN": a place and a state, as IBM's titles
# write them.
_US_PLACE = re.compile(
    r"\b([A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*){0,3}),\s*(" + _US_STATES + r")\b"
)

# IBM's own US sites, as its titles name them without a state.
_IBM_US_SITES = (
    (re.compile(r"\bRTP\b|\bResearch Triangle\b"), "Research Triangle Park, NC"),
    (re.compile(r"\bPoughkeepsie\b"), "Poughkeepsie, NY"),
    (re.compile(r"\bYorktown\b"), "Yorktown Heights, NY"),
    (re.compile(r"\bArmonk\b"), "Armonk, NY"),
    (re.compile(r"\bNew York\b"), "New York, NY"),
    (re.compile(r"\bAustin\b"), "Austin, TX"),
    (re.compile(r"\bTucson\b"), "Tucson, AZ"),
    (re.compile(r"\bUnited States\b|\bUSA\b"), "United States"),
)

_last_full_read: dict[str, float] = {}


def _location(
    raw: str,
    title: str,
) -> str:
    """IBM's "City, CC", written so the gate can place it."""

    text = " ".join(
        str(raw or "").split()
    )

    if not text or text.lower() == "multiple cities":
        places = [
            f"{place}, {state}"
            for place, state in _US_PLACE.findall(title)
        ]

        if not places:
            places = [
                site
                for pattern, site in _IBM_US_SITES
                if pattern.search(title)
            ]

        return "; ".join(places) if places else "Multiple Cities"

    city, _, code = text.rpartition(",")
    code = code.strip().upper()
    city = city.strip()

    if code == "US":
        return f"{city}, United States" if city else "United States"

    country = COUNTRIES.get(code)

    if country is None:
        LOGGER.warning(
            "ibm_unknown_country code=%s location=%r",
            code,
            text,
        )

        return text

    return f"{city}, {country}" if city else country


def _description(
    source: dict,
) -> str:
    excerpt = " ".join(
        str(source.get("description") or "").split()
    )

    details = [
        f"IBM career level: {source.get('field_keyword_18')}."
        if source.get("field_keyword_18")
        else "",
        f"Job category: {source.get('field_keyword_08')}."
        if source.get("field_keyword_08")
        else "",
        f"Work arrangement: {source.get('field_keyword_17')}."
        if source.get("field_keyword_17")
        else "",
    ]

    return "\n\n".join(
        part
        for part in [excerpt, " ".join(d for d in details if d)]
        if part
    )


def _posted_at(
    value: object,
) -> datetime | None:
    try:
        day = datetime.strptime(
            str(value),
            "%Y-%m-%d",
        )
    except ValueError:
        return None

    return day.replace(
        tzinfo=timezone.utc,
    )


def _job_id(
    url: str,
) -> str | None:
    found = parse_qs(
        urlsplit(url).query
    ).get("jobId")

    return found[0].strip() if found and found[0].strip() else None


def canonical_job(
    source: dict,
) -> CanonicalJob | None:
    """One search result as a CanonicalJob, or None when it has no id."""

    url = str(source.get("url") or "").strip()
    title = " ".join(str(source.get("title") or "").split())
    job_id = _job_id(url)

    if not job_id or not title:
        return None

    return CanonicalJob(
        source=SOURCE,
        company=COMPANY,
        external_id=job_id,
        requisition_id=job_id,
        title=title,
        location=_location(
            source.get("field_keyword_19"),
            title,
        ),
        description=_description(
            source
        ),
        official_url=url,
        posted_at=_posted_at(
            source.get("dcdate")
        ),
    )


def fetch_ibm_jobs(
    *,
    source_account: str = "careers.ibm.com",
    client: httpx.Client | None = None,
    now: datetime | None = None,
    full: bool | None = None,
    pause_seconds: float = PAUSE_SECONDS,
) -> JobList:
    """Read IBM's openings, in full every two hours and newest otherwise."""

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
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
    )

    jobs: list[CanonicalJob] = []
    seen: set[str] = set()
    complete = False

    try:
        for page in range(MAX_PAGES):
            body = {
                "appId": "careers",
                "scopes": ["careers2"],
                "query": {"bool": {"must": []}},
                "size": PAGE_SIZE,
                "from": page * PAGE_SIZE,
                # Newest first, and ties in a fixed order, so pages do
                # not overlap or skip.
                "sort": [{"dcdate": "desc"}, {"_id": "asc"}],
                "lang": "zz",
                "localeSelector": {},
                "p": page + 1,
                "sm": {"query": "", "lang": "zz"},
                "_source": FIELDS,
            }

            response = request_with_retry(
                lambda: http.post(
                    API,
                    json=body,
                )
            )

            response.raise_for_status()

            payload = response.json()

            hits = (payload.get("hits") or {}).get("hits") or []

            oldest = None

            for hit in hits:
                source = hit.get("_source") or {}
                job = canonical_job(source)

                if job is None or job.external_id in seen:
                    continue

                seen.add(job.external_id)
                jobs.append(job)

                if job.posted_at is not None:
                    oldest = job.posted_at

            if len(hits) < PAGE_SIZE:
                complete = True
                break

            if (
                not full
                and oldest is not None
                and (moment - oldest).days > RECENT_DAYS
            ):
                break

            time.sleep(pause_seconds)

    finally:
        if owns_client:
            http.close()

    if complete:
        _last_full_read[source_account] = clock

    return JobList(
        jobs,
        complete=complete,
    )
