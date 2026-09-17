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

The listing alone would pass the gate a title and nothing else, so each
posting's own page is then read for its description. Those pages carry
no JSON-LD -- unlike RippleMatch -- so the content region is flattened
to text, which is what the phrase rules that read requirement text
need.

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

# The portal pages ten at a time. The cap is a guard against a portal
# that never stops paging, not an expectation: 200 pages is 2,000
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
    r'class="paragraph_inner-span"[^>]*>(.*?)</span>',
    re.DOTALL,
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


def _listing_url(
    base_url: str,
    offset: int,
) -> str:
    """The listing page at one offset."""

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
) -> list[CanonicalJob]:
    """Fetch every public posting on one Avature portal.

    ``source_account`` is the portal base URL, for the reason given at
    the top of this module: an Avature portal is served from the
    employer's own domain and carries no slug to key on.

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

        for page in range(
            MAX_PAGES
        ):
            response = session.get(
                _listing_url(
                    source_account,
                    page * PAGE_SIZE,
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
                location=location,
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
