"""Which companies are hiring, learned from an aggregator.

An aggregator is a bad source of jobs and a good source of names, and
ACE had been refusing both together.

The standing invariant is that an apply link is always the employer's
own posting. An aggregator lane was built once and deleted the next
day for failing exactly that: it linked to itself, so every posting it
found was one the user still had to go and find properly. That
reasoning is sound and nothing here changes it.

But the reason the link is bad has nothing to do with the *name*. When
JobRight lists a role at Algolia, the useful fact is not the role --
ACE cannot link to it -- it is that Algolia is hiring. Handed that
name, ACE reads Algolia's own Greenhouse board and gets all 33 of
their postings, each with a link to Algolia. The aggregator is a
tip-off, never a supplier.

That is what this module returns: company names, and nothing else. No
posting, no URL, no date. Anything more would be the deleted lane
coming back through a side door.

What it costs
-------------

JobRight's published list was one of three held-out benchmarks -- lists
ACE had never seen, used to measure what fraction of the market it
reaches. Discovering companies from JobRight means that list is no
longer held out, so it has been dropped from the benchmark. You cannot
feed from a source and also measure yourself against it; the number
would be ACE grading its own homework. Two independent lists remain.

How it reads
------------

robots.txt allows /jobs/*, which is where the category pages live.
Each lists a rotating page of roles and carries the employer of each
in the page's own embedded state, so one request yields around fifteen
names and a different fifteen tomorrow. The categories are the ones
this user is actually looking for; a category nobody here would apply
to is a page not worth fetching.
"""

from __future__ import annotations

import json
import logging
import re

import httpx


LOGGER = logging.getLogger(
    "ace.discovery.watchlist",
)


BASE_URL = "https://jobright.ai/jobs"

TIMEOUT_SECONDS = 25.0

USER_AGENT = (
    "ACE/1.0 (personal job-search agent)"
)


# The categories worth watching, which are the ones this user would
# apply to. Verified to answer 200 and to carry employers; a slug that
# stops existing drops out with a warning rather than failing the run.
WATCHED_CATEGORIES = (
    "software-engineering",
    "software-engineer",
    "backend-engineering",
    "frontend-engineering",
    "full-stack-engineer",
    "machine-learning-engineer",
    "ai-engineer",
    "data-engineer",
    "devops-engineer",
    "software-internet-ai",
    "entry-level",
)


# The employer of each listed role, carried in the page's own embedded
# state. Read with a pattern rather than by parsing the whole document
# because the surrounding structure is a framework's business and
# changes with its version; the field itself is the page's own data.
_COMPANY = re.compile(
    r'"companyName"\s*:\s*'
    r'("(?:[^"\\]|\\.){2,80}")',
)


def parse_companies(
    markup: str,
) -> set[str]:
    """Return every employer named on one category page.

    Decoded through json.loads so an escaped name arrives as the
    company wrote it: "Moody\\u2019s" is Moody's, and a probe for the
    literal backslash would find nobody.
    """

    found: set[str] = set()

    for raw in _COMPANY.findall(
        markup,
    ):
        try:
            name = json.loads(
                raw,
            )
        except ValueError:
            continue

        cleaned = str(
            name
        ).strip()

        if cleaned:
            found.add(
                cleaned,
            )

    return found


def fetch_watchlist(
    *,
    categories: tuple[str, ...] = WATCHED_CATEGORIES,
    client: httpx.Client | None = None,
) -> list[str]:
    """Return the distinct employers currently hiring in these
    categories.

    One page that fails is skipped rather than failing the run: this
    is a tip-off, and a partial tip-off is still worth acting on.
    Nothing downstream treats the result as authoritative -- every name
    is verified against the employer's own board before it becomes a
    source.
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
        names: set[str] = set()

        for category in categories:
            url = f"{BASE_URL}/{category}"

            try:
                response = session.get(
                    url,
                )

                response.raise_for_status()
            except httpx.HTTPError as error:
                LOGGER.warning(
                    "watchlist_category_failed "
                    "category=%s error=%s",
                    category,
                    error,
                )

                continue

            found = parse_companies(
                response.text,
            )

            LOGGER.info(
                "watchlist_category_read "
                "category=%s companies=%d",
                category,
                len(
                    found,
                ),
            )

            names |= found

        LOGGER.info(
            "watchlist_complete categories=%d companies=%d",
            len(
                categories,
            ),
            len(
                names,
            ),
        )

        return sorted(
            names,
        )
    finally:
        if owned:
            session.close()
