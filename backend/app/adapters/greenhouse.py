"""Greenhouse ATS adapter for ACE.

This module retrieves public job postings from a Greenhouse job board
and converts Greenhouse-specific payloads into ACE's CanonicalJob model.
"""

import html
import re

import httpx

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
) -> list[CanonicalJob]:
    """Fetch and normalize published jobs from a Greenhouse board.

    Args:
        board_token:
            Greenhouse board identifier, such as ``databricks``.

        company_name:
            Human-readable employer name ACE should store.

    Returns:
        A list of normalized CanonicalJob objects.

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
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

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

    return normalized_jobs