"""Gem: job boards at jobs.gem.com, read from Gem's public job board API.

Groq was on ACE's list of top employers and its careers page now only
redirects home; its openings are on a Gem job board,
``jobs.gem.com/groq``. Gem publishes every board's postings at
``api.gem.com/job_board/v0/<board>/job_posts/`` -- shaped much like
Greenhouse's, with the whole description -- so one request reads a
board. The account is the board's name.

A posting open in several cities is one post per city, each with its own
link; they are kept apart, as the board shows them.
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
from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import (
    CanonicalJob,
)


SOURCE = "gem"

API = "https://api.gem.com/job_board/v0/{board}/job_posts/"

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


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


def _description(
    post: dict,
) -> str:
    plain = str(post.get("content_plain") or "")

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
                str(post.get("content") or "")
            ),
        ),
    ).strip()


def canonical_job(
    post: dict,
    *,
    company_name: str,
) -> CanonicalJob | None:
    """One post as a CanonicalJob, or None without an id, title or link."""

    post_id = str(post.get("id") or "").strip()
    title = " ".join(
        str(post.get("title") or "").split()
    )
    url = str(post.get("absolute_url") or "").strip()

    if not post_id or not title or not url:
        return None

    location = post.get("location") or {}

    place = (
        str(location.get("name") or "").strip()
        if isinstance(location, dict)
        else str(location).strip()
    )

    if post.get("location_type") == "remote":
        place = f"Remote - {place}" if place else "Remote"

    return CanonicalJob(
        source=SOURCE,
        company=company_name,
        external_id=post_id,
        requisition_id=(
            str(post.get("requisition_id") or "").strip() or None
        ),
        title=title,
        location=place or "Unknown",
        description=_description(
            post
        ),
        official_url=url,
        posted_at=_when(
            post.get("first_published_at")
        ),
        updated_at=_when(
            post.get("updated_at")
        ),
        employment_type=(
            str(post.get("employment_type") or "").strip().lower() or None
        ),
    )


def fetch_gem_jobs(
    *,
    source_account: str,
    company_name: str,
    client: httpx.Client | None = None,
) -> list[CanonicalJob]:
    """Read every post on one Gem job board."""

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
                API.format(
                    board=source_account
                )
            )
        )

        response.raise_for_status()

        posts = response.json()

    finally:
        if owns_client:
            http.close()

    if not isinstance(posts, list):
        raise ValueError(
            f"Gem board {source_account} did not answer with a list."
        )

    return [
        job
        for job in (
            canonical_job(
                post,
                company_name=company_name,
            )
            for post in posts
            if isinstance(post, dict)
        )
        if job is not None
    ]
