"""Greenhouse ATS adapter for ACE.

This module retrieves public job postings from a Greenhouse job board
and converts Greenhouse-specific payloads into ACE's CanonicalJob model.
"""

import html
import re

import httpx

from backend.app.adapters.http_cache import (
    CacheValidators,
    conditional_headers,
    is_unchanged,
    unchanged_result,
    validators_from_response,
)
from backend.app.models.job import CanonicalJob


GREENHOUSE_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

REQUEST_TIMEOUT_SECONDS = 20.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project; "
    "https://github.com/anwarbuilds/ace)"
)


def _clean_html(raw_html: str | None) -> str:
    """Convert HTML job-description content into normalized plain text."""

    if not raw_html:
        return ""

    decoded_html = html.unescape(raw_html)

    text_without_tags = re.sub(
        r"<[^>]+>",
        " ",
        decoded_html,
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        text_without_tags,
    )

    return normalized_text.strip()


def fetch_greenhouse_jobs(
    board_token: str,
    company_name: str,
    *,
    validators: CacheValidators | None = None,
) -> tuple[
    list[CanonicalJob],
    bool,
    CacheValidators,
]:
    """Fetch and normalize published jobs from a Greenhouse board.

    Args:
        board_token:
            Greenhouse board identifier, such as ``databricks``.

        company_name:
            Human-readable employer name ACE should store.

        validators:
            HTTP validators from the previous poll. Greenhouse honours
            ETag, so an unchanged board answers 304 with no body and the
            entire download and diff are skipped.

    Returns:
        The jobs, whether the board was unchanged, and the validators to
        send on the next poll.

    Raises:
        httpx.HTTPStatusError:
            Greenhouse returned an unsuccessful HTTP status.

        httpx.RequestError:
            The request failed before a response was received.
    """

    url = f"{GREENHOUSE_BASE_URL}/{board_token}/jobs"

    params = {
        "content": "true",
    }

    headers = {
        "User-Agent": USER_AGENT,
    }

    response = httpx.get(
        url,
        params=params,
        headers=conditional_headers(
            headers,
            validators,
        ),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if is_unchanged(
        response
    ):
        return unchanged_result(
            validators
        )

    response.raise_for_status()

    next_validators = (
        validators_from_response(
            response
        )
    )

    payload = response.json()

    raw_jobs = payload.get("jobs", [])

    normalized_jobs: list[CanonicalJob] = []

    for raw_job in raw_jobs:
        location_data = raw_job.get("location") or {}

        normalized_job = CanonicalJob(
            source="greenhouse",
            company=company_name,
            external_id=str(raw_job["id"]),
            requisition_id=raw_job.get("requisition_id"),
            title=raw_job["title"],
            location=location_data.get("name", "Unknown"),
            description=_clean_html(raw_job.get("content")),
            official_url=raw_job["absolute_url"],
            posted_at=raw_job.get("first_published"),
            updated_at=raw_job.get("updated_at"),
        )

        normalized_jobs.append(normalized_job)

    return (
        normalized_jobs,
        False,
        next_validators,
    )