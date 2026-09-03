"""Ashby ATS adapter for ACE.

Fetches publicly listed job postings from an Ashby-hosted job board and
normalizes them into ACE CanonicalJob objects.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from backend.app.models.job import CanonicalJob


ASHBY_POSTING_API_BASE_URL = (
    "https://api.ashbyhq.com/posting-api/job-board"
)

REQUEST_TIMEOUT_SECONDS = 20.0


def fetch_ashby_jobs(
    board_name: str,
    company_name: str,
    *,
    client: httpx.Client | None = None,
) -> list[CanonicalJob]:
    """Fetch one public Ashby board."""

    normalized_board_name = board_name.strip()

    if not normalized_board_name:
        raise ValueError(
            "board_name must not be empty."
        )

    normalized_company_name = company_name.strip()

    if not normalized_company_name:
        raise ValueError(
            "company_name must not be empty."
        )

    url = (
        f"{ASHBY_POSTING_API_BASE_URL}/"
        f"{normalized_board_name}"
    )

    owns_client = client is None

    http_client = (
        client
        if client is not None
        else httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    )

    try:
        response = http_client.get(url)
        response.raise_for_status()

        payload = response.json()
    finally:
        if owns_client:
            http_client.close()

    raw_jobs = payload.get(
        "jobs",
        [],
    )

    jobs: list[CanonicalJob] = []

    for raw_job in raw_jobs:
        if not raw_job.get(
            "isListed",
            True,
        ):
            continue

        job_url = (
            raw_job.get("jobUrl")
            or raw_job.get("applyUrl")
        )

        if not job_url:
            continue

        external_id = _external_id_from_job_url(
            job_url
        )

        jobs.append(
            CanonicalJob(
                source="ashby",
                company=normalized_company_name,
                external_id=external_id,
                requisition_id=None,
                title=(
                    raw_job.get("title")
                    or "Untitled role"
                ),
                location=(
                    raw_job.get("location")
                    or "Unknown"
                ),
                description=(
                    raw_job.get("descriptionPlain")
                    or raw_job.get("description")
                    or ""
                ),
                official_url=job_url,
                posted_at=_parse_datetime(
                    raw_job.get(
                        "publishedAt"
                    )
                ),
                updated_at=_parse_datetime(
                    raw_job.get(
                        "updatedAt"
                    )
                ),
            )
        )

    return jobs


def _external_id_from_job_url(
    job_url: str,
) -> str:
    """Return a durable identifier from an Ashby posting URL."""

    path = (
        httpx.URL(job_url)
        .path
        .rstrip("/")
    )

    external_id = path.split("/")[-1]

    if not external_id:
        raise ValueError(
            "Ashby job URL does not contain an identifier."
        )

    return external_id


def _parse_datetime(
    value: object,
) -> datetime | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = (
        value.strip()
        .replace(
            "Z",
            "+00:00",
        )
    )

    if not normalized:
        return None

    try:
        return datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None
