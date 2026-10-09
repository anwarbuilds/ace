"""Avature: employer boards that live on the employer's own domain.

Found because a Two Sigma campus software engineering post in Houston
was never in ACE. The company had not been skipped by an adapter -- it
had never been probed, for the reason recorded in the coverage entry
for 2026-09-17. Once it was probed, the answer was that its board runs
on Avature, which ACE could not read.

Why this one is keyed on a URL
------------------------------

Every other adapter here keys on a tenant slug, because every other
provider hosts the board itself: ``jobs.ashbyhq.com/<slug>``,
``boards-api.greenhouse.io/v1/boards/<slug>``. Avature portals are
normally served from the employer's own domain -- Two Sigma's is
``careers.twosigma.com/careers`` -- with the Avature tenant visible
only in the sitemap reference in ``robots.txt``. There is no slug to
key on, so the source account is the portal base URL itself.

That also means the apply link is the employer's own posting, which is
the standing invariant and needs no exception here: this *is* the
company's board, however it is addressed.

How it is read
--------------

``{base}/OpenRoles?jobOffset=N`` lists ten roles a page, each as an
``article--result`` carrying the title, the location and the link to
its own page. Paging stops when a page introduces no new identifier,
which is what the portal does at the end rather than returning an empty
list.

A portal whose listing has another name is keyed on the listing page
itself: EA's is ``jobs.ea.com/en_US/careers/SearchJobs``, twenty roles
a page. The step between pages is however many the first page held.

The listing alone would pass the gate a title and nothing else, so each
posting's own page is then read for its description. Those pages carry
no JSON-LD -- unlike RippleMatch -- so the content region is flattened
to text, which is what the phrase rules that read requirement text
need. Only postings whose title the gate could pass are read: EA lists
365 roles, most of them art, finance and senior engineering, and a
posting the gate rejects on its title alone needs no description to be
rejected.

A posting's own page names every location it is open in; the listing
names one. Where the page names them, those are the location.

The listing is served ``no-store, no-cache`` with no ETag, and its
``Last-Modified`` is the moment of the request, so conditional HTTP is
impossible: this is an unconditional adapter, polled at the slower
cadence that implies.
"""

from __future__ import annotations

import concurrent.futures
import html
import logging
import re
from collections.abc import Callable
from urllib.parse import (
    urljoin,
    urlsplit,
)

import httpx

from backend.app.models.job import CanonicalJob


LOGGER = logging.getLogger(
    "ace.adapters.avature",
)


SOURCE = "avature"

# A courtesy limit on somebody else's site, not a throughput target.
CONCURRENCY = 4

TIMEOUT_SECONDS = 20.0

# Long enough for a few hundred small pages at the concurrency above,
# short enough that a wedged poll does not hold a scheduler slot all
# day.
TOTAL_DEADLINE_SECONDS = 300.0

# Two Sigma's portal pages ten at a time and EA's twenty; the step is
# taken from the first page. The cap is a guard against a portal that
# never stops paging, not an expectation: 200 pages is thousands of
# roles, far beyond any board seen here.
PAGE_SIZE = 10

MAX_PAGES = 200

USER_AGENT = (
    "ACE/1.0 (personal job-search agent)"
)


_WS = re.compile(
    r"\s+",
)

_ARTICLE = re.compile(
    r'<article\b[^>]*class="[^"]*article--result[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL,
)

_LINK = re.compile(
    r'href="([^"]*?/JobDetail/[^"]*?)"[^>]*>(.*?)</a>',
    re.DOTALL,
)

_LOCATION = re.compile(
    r'class="(?:paragraph_inner-span|list-item-location)"[^>]*>(.*?)</span>',
    re.DOTALL,
)

# "<strong>Locations</strong>: Hyderabad, Telangana, India&nbsp;<br>",
# one place a line.
_PAGE_LOCATIONS = re.compile(
    r"<strong>\s*Locations?\s*</strong>\s*:?(.*?)</div>",
    re.DOTALL | re.IGNORECASE,
)

_BREAK = re.compile(
    r"<br\s*/?>",
    re.IGNORECASE,
)

# The places after the first, one set each: "Location: Redwood City",
# "State: California", "Country: United States of America".
_DATA_SET = re.compile(
    r'<ul class="MultipleDataSetFields">(.*?)</ul>',
    re.DOTALL,
)

_DATA_VALUE = re.compile(
    r'class="MultipleDataSetFieldValue"[^>]*>(.*?)</span>',
    re.DOTALL,
)

_OFFSET = re.compile(
    r"jobOffset=(\d+)",
)

# A portal keyed on its listing page rather than its base.
_LISTING_PAGE = re.compile(
    r"/(?:SearchJobs|OpenRoles)/?$",
    re.IGNORECASE,
)

_CONTENT = re.compile(
    r'<div class="article__content"[^>]*>(.*?)'
    r'(?:<footer|<div class="article__footer)',
    re.DOTALL,
)

_SCRIPT = re.compile(
    r"<(script|style)\b.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

_TAG = re.compile(
    r"<[^>]+>",
)


def _text(
    markup: str,
) -> str:
    """Flatten a block of portal markup into readable plain text.

    Tags become newlines rather than disappearing, so the paragraphs
    and list items a posting is written in do not run together into one
    line. The phrase rules that read requirement text need sentence
    boundaries to survive.
    """

    if not markup:
        return ""

    without_code = _SCRIPT.sub(
        " ",
        markup,
    )

    flattened = _TAG.sub(
        "\n",
        without_code,
    )

    unescaped = html.unescape(
        flattened,
    )

    lines = [
        _WS.sub(
            " ",
            line,
        ).strip()
        for line in unescaped.split(
            "\n"
        )
    ]

    return "\n".join(
        line
        for line in lines
        if line
    ).strip()


def _inline(
    markup: str,
) -> str:
    """One line of text out of one inline element."""

    return _WS.sub(
        " ",
        html.unescape(
            _TAG.sub(
                " ",
                markup,
            )
        ),
    ).strip()


def parse_listing(
    markup: str,
    *,
    base_url: str,
) -> list[tuple[str, str, str, str]]:
    """Return ``(job_id, url, title, location)`` for one listing page.

    A posting with no link cannot be fetched or applied to, so it is
    dropped rather than carried as a job with nowhere to go.
    """

    found: list[
        tuple[str, str, str, str]
    ] = []

    for block in _ARTICLE.findall(
        markup,
    ):
        link = _LINK.search(
            block,
        )

        if link is None:
            continue

        url = urljoin(
            base_url,
            html.unescape(
                link.group(
                    1,
                )
            ),
        )

        job_id = urlsplit(
            url,
        ).path.rstrip(
            "/"
        ).rsplit(
            "/",
            1,
        )[-1]

        if not job_id:
            continue

        title = _inline(
            link.group(
                2,
            )
        )

        if not title:
            continue

        location = _LOCATION.search(
            block,
        )

        found.append(
            (
                job_id,
                url,
                title,
                _inline(
                    location.group(
                        1,
                    )
                )
                if location
                else "",
            )
        )

    return found


def parse_job_page(
    markup: str,
) -> str:
    """Return the posting's description as plain text.

    Empty rather than raising when the content region cannot be found.
    A posting whose description could not be read is still a real
    posting, and the gate treats missing requirement text as unknown
    rather than as disqualifying.
    """

    content = _CONTENT.search(
        markup,
    )

    if content is None:
        return ""

    return _text(
        content.group(
            1,
        )
    )


def parse_job_locations(
    markup: str,
) -> str:
    """Every location a posting's own page names, or empty."""

    field = _PAGE_LOCATIONS.search(
        markup,
    )

    if field is None:
        return ""

    body = field.group(
        1,
    )

    places = [
        _inline(
            line,
        ).strip(
            " ,;"
        )
        for line in _BREAK.split(
            _DATA_SET.sub(
                "<br>",
                body,
            )
        )
    ] + [
        ", ".join(
            value
            for value in (
                _inline(
                    found,
                )
                for found in _DATA_VALUE.findall(
                    data_set,
                )
            )
            if value
        )
        for data_set in _DATA_SET.findall(
            body,
        )
    ]

    return "; ".join(
        place
        for place in places
        if place
    )


def _page_step(
    markup: str,
    rows: int,
) -> int:
    """The portal's own page size: ten on Two Sigma's, twenty on EA's.

    Read from the first page's links to the pages after it, or from the
    page itself when it links nowhere.
    """

    offsets = [
        int(found)
        for found in _OFFSET.findall(
            markup,
        )
        if int(found) > 0
    ]

    return min(offsets) if offsets else max(
        rows,
        PAGE_SIZE,
    )


def _listing_url(
    base_url: str,
    offset: int,
) -> str:
    """The listing page at one offset."""

    if _LISTING_PAGE.search(
        urlsplit(
            base_url,
        ).path
    ):
        joined = base_url.rstrip(
            "/"
        )
    else:
        joined = urljoin(
            base_url.rstrip(
                "/"
            )
            + "/",
            "OpenRoles",
        )

    if not offset:
        return joined

    return f"{joined}?jobOffset={offset}"


def fetch_avature_jobs(
    *,
    source_account: str,
    company_name: str = "",
    client: httpx.Client | None = None,
    concurrency: int = CONCURRENCY,
    should_fetch_detail: Callable[[str], bool] | None = None,
) -> list[CanonicalJob]:
    """Fetch every public posting on one Avature portal.

    ``source_account`` is the portal base URL, for the reason given at
    the top of this module: an Avature portal is served from the
    employer's own domain and carries no slug to key on. It may also be
    the listing page itself, as EA's is.

    ``should_fetch_detail`` decides from a title whether the posting's
    own page is worth reading; a posting it turns down keeps the
    listing's title and location and no description.

    Paging stops when a page introduces no new identifier. The portal
    repeats the last page rather than returning an empty one, so
    "nothing new" is the end, and stopping on an empty page alone would
    never stop.

    A page that cannot be read is skipped with a warning rather than
    failing the poll: one bad posting out of dozens must not produce an
    empty snapshot, which persistence would otherwise be asked to read
    as every job closing at once.
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
        seen: set[str] = set()

        listed: list[
            tuple[str, str, str, str]
        ] = []

        offset = 0
        step = 0

        for _page in range(
            MAX_PAGES
        ):
            response = session.get(
                _listing_url(
                    source_account,
                    offset,
                ),
            )

            response.raise_for_status()

            rows = parse_listing(
                response.text,
                base_url=source_account,
            )

            fresh = [
                row
                for row in rows
                if row[0] not in seen
            ]

            if not fresh:
                break

            for row in fresh:
                seen.add(
                    row[0],
                )

            listed.extend(
                fresh,
            )

            step = step or _page_step(
                response.text,
                len(
                    rows,
                ),
            )

            offset += step

        LOGGER.info(
            "avature_listing_read account=%s listed=%d",
            source_account,
            len(
                listed,
            ),
        )

        def read(
            row: tuple[str, str, str, str],
        ) -> CanonicalJob | None:
            job_id, url, title, location = row

            if (
                should_fetch_detail is not None
                and not should_fetch_detail(
                    title,
                )
            ):
                return CanonicalJob(
                    source=SOURCE,
                    company=company_name,
                    external_id=job_id,
                    title=title,
                    location=location,
                    description="",
                    official_url=url,
                )

            try:
                page = session.get(
                    url,
                )

                page.raise_for_status()
            except httpx.HTTPError as error:
                LOGGER.warning(
                    "avature_page_failed id=%s error=%s",
                    job_id,
                    error,
                )

                return None

            return CanonicalJob(
                source=SOURCE,
                company=company_name,
                external_id=job_id,
                title=title,
                location=(
                    parse_job_locations(
                        page.text,
                    )
                    or location
                ),
                description=parse_job_page(
                    page.text,
                ),
                official_url=url,
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
                listed,
                timeout=TOTAL_DEADLINE_SECONDS,
            ):
                if job is not None:
                    jobs.append(
                        job,
                    )

        LOGGER.info(
            "avature_fetch_complete account=%s listed=%d parsed=%d",
            source_account,
            len(
                listed,
            ),
            len(
                jobs,
            ),
        )

        return jobs
    finally:
        if owned:
            session.close()
