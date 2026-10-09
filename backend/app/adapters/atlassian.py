"""Atlassian: the job list its own careers site loads.

Atlassian was on ACE's list of top employers and had no board ACE read:
its careers site is its own, with applications taken by an iCIMS portal
ACE has no reader for. The careers page fills itself from
``www.atlassian.com/endpoint/careers/listings``, one JSON document with
every opening -- title, type, every location, and the full overview,
responsibilities and qualifications -- which robots.txt leaves open.
One request reads the whole board, and an ETag lets an unchanged list
cost nothing.

Unlike most custom careers sites, the descriptions are whole, so the gate
reads requirements here as it does on Greenhouse: years of experience,
sponsorship, citizenship.
"""

from __future__ import annotations

import re
from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters.html_text import (
    unescape_fully,
)
from backend.app.adapters.http_cache import (
    CacheValidators,
    validators_from_response,
)
from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import (
    CanonicalJob,
)


SOURCE = "atlassian"

COMPANY = "Atlassian"

LISTINGS = "https://www.atlassian.com/endpoint/careers/listings"

DETAILS = "https://www.atlassian.com/company/careers/details/{id}"

TIMEOUT_SECONDS = 60.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _text(
    value: object,
) -> str:
    if not value:
        return ""

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        unescape_fully(str(value)),
    )

    return re.sub(
        r"\s+",
        " ",
        without_tags,
    ).strip()


def _updated(
    listing: dict,
) -> datetime | None:
    post = listing.get("portalJobPost") or {}

    try:
        return datetime.strptime(
            str(post.get("updatedDate") or ""),
            "%Y-%m-%d %I:%M %p",
        ).replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def canonical_job(
    listing: dict,
) -> CanonicalJob | None:
    """One listing as a CanonicalJob, or None without an id or title."""

    job_id = str(listing.get("id") or "").strip()
    title = " ".join(str(listing.get("title") or "").split())

    if not job_id or not title:
        return None

    locations = [
        " ".join(str(place).split())
        for place in listing.get("locations") or []
        if str(place).strip()
    ]

    description = "\n\n".join(
        part
        for part in (
            _text(listing.get("overview")),
            _text(listing.get("responsibilities")),
            _text(listing.get("qualifications")),
        )
        if part
    )

    updated = _updated(
        listing
    )

    return CanonicalJob(
        source=SOURCE,
        company=COMPANY,
        external_id=job_id,
        requisition_id=job_id,
        title=title,
        location="; ".join(locations) or "Unknown",
        description=description,
        official_url=DETAILS.format(id=job_id),
        # Atlassian publishes only when a posting last changed. A
        # posting edited last week reads as a week old, never older
        # than it is.
        posted_at=updated,
        updated_at=updated,
        employment_type=(
            str(listing.get("type") or "").strip() or None
        ),
    )


def fetch_atlassian_jobs(
    *,
    client: httpx.Client | None = None,
    validators: CacheValidators | None = None,
) -> tuple[list[CanonicalJob], bool, CacheValidators]:
    """Read every Atlassian opening.

    Returns the jobs, whether the list was unchanged since the
    validators were taken, and the validators for the next poll.
    """

    owns_client = client is None

    http = client or httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        response = request_with_retry(
            lambda: http.get(
                LISTINGS,
                headers=(
                    validators.request_headers()
                    if validators
                    else {}
                ),
            )
        )

        if response.status_code == 304:
            return [], True, validators or CacheValidators()

        response.raise_for_status()

        listings = response.json()

    finally:
        if owns_client:
            http.close()

    jobs = [
        job
        for job in (
            canonical_job(listing)
            for listing in listings
            if isinstance(listing, dict)
        )
        if job is not None
    ]

    if not jobs:
        # An empty or unreadable list is never taken as every posting
        # closing at once.
        raise ValueError(
            "Atlassian's listings came back empty."
        )

    return jobs, False, validators_from_response(response)
