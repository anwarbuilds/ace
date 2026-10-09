"""Shopify: the openings its own careers page carries.

Shopify was on ACE's list of top employers with no board ACE read. Its
postings live in Ashby, but on a board ACE cannot name: no public Ashby
board answers to Shopify. Its careers page, www.shopify.com/careers,
which robots.txt leaves open, is rendered on the server with every
listed posting in it -- title, Ashby's locations, employment type, the
day it was published -- as React Router loader data (see
``turbo_stream``). One request reads the whole board.

A posting's own page, ``/careers/<slug>_<id>``, carries its full
description. It is read only for a title the gate could pass, and only
once: a posting ACE already holds keeps the description it was first
read with. The site finds a posting by the identifier after the
underscore, whatever the slug says.

Most of Shopify's engineering roles are remote across the "Americas",
which the gate reads as open to the US.

robots.txt disallows ``/careers/search`` and ``/careers/portal``; neither
is read.
"""

from __future__ import annotations

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
from backend.app.adapters.turbo_stream import (
    loader_data,
)
from backend.app.models.job import (
    CanonicalJob,
)


LOGGER = logging.getLogger(
    "ace.adapters.shopify",
)

SOURCE = "shopify"

COMPANY = "Shopify"

CAREERS = "https://www.shopify.com/careers"

POSTING = "https://www.shopify.com/careers/{slug}_{id}"

LISTING_ROUTE = "($locale)/careers"

POSTING_ROUTE = "($locale)/careers/$posting"

DETAIL_PAUSE_SECONDS = 1.0

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _slug(
    title: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "-",
        title.casefold(),
    ).strip("-") or "role"


def _when(
    value: object,
) -> datetime | None:
    text = str(value or "").strip()

    if not text:
        return None

    try:
        moment = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(
            tzinfo=timezone.utc,
        )

    return moment


def _place(
    location: dict,
) -> str:
    """One Ashby location as the gate can place it."""

    address = (location.get("address") or {}).get("postalAddress") or {}

    parts: list[str] = []

    for part in (
        location.get("externalName") or location.get("name"),
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ):
        text = " ".join(
            str(part or "").split()
        )

        if text and text not in parts:
            parts.append(
                text
            )

    place = ", ".join(
        parts
    )

    if place and location.get("isRemote"):
        return f"Remote - {place}"

    return place


def parse_careers_page(
    markup: str,
) -> list[dict]:
    """Every listed posting on the careers page."""

    route = loader_data(
        markup
    ).get(LISTING_ROUTE) or {}

    places = {
        location.get("id"): location
        for location in route.get("atsLocations") or []
        if isinstance(location, dict)
    }

    postings: list[dict] = []

    for item in route.get("jobPostingsWithJobs") or []:
        posting = (item or {}).get("jobPosting") or {}

        posting_id = str(posting.get("id") or "").strip()
        title = " ".join(
            str(posting.get("title") or "").split()
        )

        if not posting_id or not title or posting.get("isListed") is False:
            continue

        ids = posting.get("locationIds") or {}

        located = [
            _place(places[location_id])
            for location_id in [
                ids.get("primaryLocationId"),
                *(ids.get("secondaryLocationIds") or []),
            ]
            if location_id in places
        ]

        location = "; ".join(
            dict.fromkeys(
                place
                for place in located
                if place
            )
        ) or str(posting.get("locationName") or "").strip() or "Unknown"

        postings.append(
            {
                "id": posting_id,
                "title": title,
                "location": location,
                "posted": _when(posting.get("publishedDate")),
                "updated": _when(posting.get("updatedAt")),
                "employment_type": (
                    str(posting.get("employmentType") or "").strip().lower()
                    or None
                ),
            }
        )

    return postings


def parse_posting_page(
    markup: str,
) -> str:
    """A posting's own page as its description, or empty."""

    posting = (
        loader_data(
            markup
        ).get(POSTING_ROUTE)
        or {}
    ).get("jobPosting") or {}

    plain = str(posting.get("descriptionPlain") or "")

    if plain.strip():
        return unescape_fully(
            plain
        ).strip()

    return re.sub(
        r"\s+",
        " ",
        re.sub(
            r"<[^>]+>",
            " ",
            unescape_fully(
                str(posting.get("descriptionHtml") or "")
            ),
        ),
    ).strip()


def fetch_shopify_jobs(
    *,
    client: httpx.Client | None = None,
    should_fetch_detail: Callable[[str], bool] | None = None,
    known: Mapping[str, tuple[str, str]] | None = None,
    detail_pause_seconds: float = DETAIL_PAUSE_SECONDS,
) -> list[CanonicalJob]:
    """Read every Shopify opening.

    ``known`` is what ACE already holds for a posting -- its location
    and description -- so a posting's own page is read once.
    """

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
                CAREERS
            )
        )

        response.raise_for_status()

        postings = parse_careers_page(
            response.text
        )

        if not postings:
            # An empty or unreadable page is never taken as every
            # posting closing at once.
            raise ValueError(
                "Shopify's careers page listed no postings."
            )

        jobs: list[CanonicalJob] = []

        for posting in postings:
            url = POSTING.format(
                slug=_slug(posting["title"]),
                id=posting["id"],
            )

            description = ""

            held = (known or {}).get(
                posting["id"]
            )

            if held and held[1]:
                description = held[1]
            elif should_fetch_detail is None or should_fetch_detail(
                posting["title"]
            ):
                try:
                    page = request_with_retry(
                        lambda: http.get(
                            url
                        )
                    )

                    page.raise_for_status()

                    description = parse_posting_page(
                        page.text
                    )
                except (httpx.HTTPError, ValueError) as error:
                    LOGGER.warning(
                        "shopify_posting_failed id=%s error=%s",
                        posting["id"],
                        error,
                    )

                time.sleep(
                    detail_pause_seconds
                )

            jobs.append(
                CanonicalJob(
                    source=SOURCE,
                    company=COMPANY,
                    external_id=posting["id"],
                    requisition_id=posting["id"],
                    title=posting["title"],
                    location=posting["location"],
                    description=description,
                    official_url=url,
                    posted_at=posting["posted"],
                    updated_at=posting["updated"],
                    employment_type=posting["employment_type"],
                )
            )

    finally:
        if owns_client:
            http.close()

    return jobs
