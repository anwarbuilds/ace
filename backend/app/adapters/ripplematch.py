"""RippleMatch: early-career roles that exist nowhere else.

Found because a Plaid "Software Engineering, New Grad" posting was
reachable here and could not be found on Plaid's own careers site. That
was not ACE missing something: Plaid's Ashby board carried 110 live
postings at the time and none of them mentioned new grad, graduate,
university or campus. The role was never published there.

That is the shape of this source. RippleMatch is a university-recruiting
platform, and employers post early-career roles to it *instead of* their
own ATS, with the application handled by RippleMatch. Every one of those
roles is invisible to an adapter that only reads company boards, and
they are precisely the roles this user is looking for.

Why the apply link is not the employer's own
--------------------------------------------

ACE's standing invariant is that the apply link is always the employer's
own posting, never an aggregator. An aggregator lane was built once and
removed for failing exactly that test.

This is a deliberate, narrow exception, and the distinction is real: an
aggregator republishes a link to a posting that exists elsewhere, so its
link is a worse copy of one ACE could have had. RippleMatch is where the
employer chose to receive the application, and for these roles there is
no other posting to link to. Linking anywhere else would mean linking
nowhere.

It is still a weaker link than a company board, which is why the source
is registered under its own type rather than blended into the others.

How it is read
--------------

``sitemap.xml`` lists every public job page, which makes it the
authoritative snapshot for lifecycle: a posting absent from it is gone.
Each page then carries a complete ``JobPosting`` in JSON-LD -- title,
employer, location, date and the full description -- so the eligibility
gate runs on real requirement text rather than on a title alone.

The sitemap is served ``cache-control: no-cache`` with no ETag, so
conditional HTTP is impossible and this is an unconditional adapter.
Every page is fetched on each poll, which is why the source is polled
daily rather than every few minutes. The sitemap declares
``changefreq: daily`` itself, so a daily cadence is also what the
publisher asks for.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters.html_text import unescape_fully
from backend.app.models.job import CanonicalJob


LOGGER = logging.getLogger(
    "ace.adapters.ripplematch",
)


BASE_URL = "https://app.ripplematch.com"

SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

# A courtesy limit on somebody else's site, not a throughput target.
# The whole feed is a few hundred pages and this is polled once a day.
CONCURRENCY = 4

TIMEOUT_SECONDS = 20.0

# Long enough for a few hundred small pages at the concurrency above,
# and short enough that a wedged poll does not hold a scheduler slot
# for the rest of the day.
TOTAL_DEADLINE_SECONDS = 300.0

USER_AGENT = (
    "ACE/1.0 (personal job-search agent)"
)


_LOC = re.compile(
    r"<loc>([^<]+)</loc>",
)

_JOB_PATH = re.compile(
    r"/v2/public/job/([0-9a-zA-Z_-]+)",
)

_LD_JSON = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)

_BREAK = re.compile(
    r"<\s*(br|/p|/div|/li|/h[1-6])\s*/?\s*>",
    re.IGNORECASE,
)

_TAG = re.compile(
    r"<[^>]+>",
)

_WHITESPACE = re.compile(
    r"[ \t ]+",
)


def _to_text(
    html: str,
) -> str:
    """Flatten a JSON-LD description into readable plain text.

    The same treatment the Eightfold adapter gives its descriptions:
    block ends become newlines before tags are stripped, so paragraphs
    do not run together into one line and the phrase rules that read
    requirement text still see sentence boundaries.
    """

    if not html:
        return ""

    text = _BREAK.sub(
        "\n",
        html,
    )

    text = _TAG.sub(
        " ",
        text,
    )

    text = unescape_fully(
        text,
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


def _posted_at(
    value: str | None,
) -> datetime | None:
    """Parse the ISO date the posting states, or None.

    An unparseable date is dropped rather than guessed at. Freshness
    treats a missing date as unknown, which is the honest answer, and
    inventing "today" would make every posting look new forever.
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(
            tzinfo=timezone.utc,
        )

    return parsed


def _location_of(
    payload: dict,
) -> str:
    """Render the posting's location as one readable string."""

    location = payload.get(
        "jobLocation",
    )

    if isinstance(
        location,
        list,
    ):
        location = (
            location[0]
            if location
            else {}
        )

    address = (
        location or {}
    ).get(
        "address",
        {},
    )

    if not isinstance(
        address,
        dict,
    ):
        return ""

    parts = [
        address.get(
            "addressLocality",
        ),
        address.get(
            "addressRegion",
        ),
        address.get(
            "addressCountry",
        ),
    ]

    return ", ".join(
        str(part).strip()
        for part in parts
        if part and str(part).strip()
    )


def parse_job_page(
    html: str,
    *,
    job_id: str,
    url: str,
) -> CanonicalJob | None:
    """Turn one public job page into a CanonicalJob, or None.

    None rather than an exception for a page that carries no usable
    posting. One malformed page out of several hundred must not fail
    the whole poll, because a failed poll returns no snapshot and a
    missing snapshot is never treated as "everything closed".
    """

    blocks = _LD_JSON.findall(
        html,
    )

    for block in blocks:
        try:
            payload = json.loads(
                block.strip(),
            )
        except (
            ValueError,
            TypeError,
        ):
            continue

        if isinstance(
            payload,
            list,
        ):
            payload = next(
                (
                    item
                    for item in payload
                    if isinstance(item, dict)
                    and item.get("@type") == "JobPosting"
                ),
                None,
            )

        if not isinstance(
            payload,
            dict,
        ):
            continue

        if payload.get(
            "@type",
        ) != "JobPosting":
            continue

        title = str(
            payload.get(
                "title",
            )
            or ""
        ).strip()

        employer = (
            payload.get(
                "hiringOrganization",
            )
            or {}
        )

        company = str(
            employer.get(
                "name",
            )
            if isinstance(employer, dict)
            else ""
        ).strip()

        # Both are required. A posting with no title cannot be judged
        # by the gate, and one with no employer would appear in the
        # queue as a role at nobody.
        if not title or not company:
            return None

        return CanonicalJob(
            source="ripplematch",
            company=company,
            external_id=job_id,
            title=unescape_fully(
                title,
            ),
            location=_location_of(
                payload,
            ),
            description=_to_text(
                str(
                    payload.get(
                        "description",
                    )
                    or ""
                )
            ),
            official_url=url,
            posted_at=_posted_at(
                payload.get(
                    "datePosted",
                )
            ),
            employment_type=(
                str(
                    payload.get(
                        "employmentType",
                    )
                ).strip()
                or None
                if payload.get("employmentType")
                else None
            ),
        )

    return None


def parse_sitemap(
    xml: str,
) -> list[tuple[str, str]]:
    """Return every public job page as (job_id, url).

    The sitemap also lists company and marketing pages; only job paths
    are kept. Duplicate ids are collapsed, because emitting one posting
    twice would make the lifecycle diff see a job it already holds as a
    second, unrelated arrival.
    """

    seen: set[str] = set()

    found: list[tuple[str, str]] = []

    for url in _LOC.findall(
        xml,
    ):
        match = _JOB_PATH.search(
            url,
        )

        if match is None:
            continue

        job_id = match.group(
            1,
        )

        if job_id in seen:
            continue

        seen.add(
            job_id,
        )

        found.append(
            (
                job_id,
                url,
            )
        )

    return found


def fetch_ripplematch_jobs(
    *,
    source_account: str = "public",
    company_name: str = "",
    client: httpx.Client | None = None,
    concurrency: int = CONCURRENCY,
) -> list[CanonicalJob]:
    """Fetch every public RippleMatch posting.

    ``company_name`` is ignored: like the curated feed, this source
    spans many employers and each posting carries its own.

    The sitemap is the snapshot, so every live posting is returned and
    anything absent from it has genuinely gone. A page that cannot be
    read is skipped with a warning rather than failing the poll: one
    bad page out of hundreds must not produce an empty snapshot, which
    persistence would otherwise be asked to read as every job closing
    at once.
    """

    owned = client is None

    session = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    try:
        response = session.get(
            SITEMAP_URL,
        )

        response.raise_for_status()

        entries = parse_sitemap(
            response.text,
        )

        LOGGER.info(
            "ripplematch_sitemap_read entries=%d",
            len(
                entries,
            ),
        )

        def read(
            entry: tuple[str, str],
        ) -> CanonicalJob | None:
            job_id, url = entry

            try:
                page = session.get(
                    url,
                )

                page.raise_for_status()
            except httpx.HTTPError as error:
                LOGGER.warning(
                    "ripplematch_page_failed id=%s error=%s",
                    job_id,
                    error,
                )

                return None

            return parse_job_page(
                page.text,
                job_id=job_id,
                url=url,
            )

        jobs: list[CanonicalJob] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(
                1,
                concurrency,
            ),
        ) as pool:
            for job in pool.map(
                read,
                entries,
                timeout=TOTAL_DEADLINE_SECONDS,
            ):
                if job is not None:
                    jobs.append(
                        job,
                    )

        LOGGER.info(
            "ripplematch_fetch_complete listed=%d parsed=%d",
            len(
                entries,
            ),
            len(
                jobs,
            ),
        )

        return jobs
    finally:
        if owned:
            session.close()
