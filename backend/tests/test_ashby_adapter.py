"""Tests for the ACE Ashby ATS adapter."""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.ashby import (
    fetch_ashby_jobs,
)


def make_client(
    payload: dict[str, object],
    *,
    status_code: int = 200,
) -> httpx.Client:
    """Build a deterministic HTTP client for adapter tests."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code,
            json=payload,
            request=request,
        )

    return httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )


def test_fetch_ashby_jobs_normalizes_public_posting() -> None:
    client = make_client(
        {
            "apiVersion": "1",
            "jobs": [
                {
                    "title": "Software Engineer I",
                    "location": "New York, NY",
                    "isListed": True,
                    "descriptionPlain": (
                        "Build reliable software."
                    ),
                    "publishedAt": (
                        "2026-09-03T12:30:00+00:00"
                    ),
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "12345678-abcd"
                    ),
                    "applyUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "12345678-abcd/application"
                    ),
                },
            ],
        }
    )

    jobs = fetch_ashby_jobs(
        "ExampleAI",
        "Example AI",
        client=client,
    )

    assert len(jobs) == 1

    job = jobs[0]

    assert job.source == "ashby"
    assert job.company == "Example AI"

    assert (
        job.external_id
        == "12345678-abcd"
    )

    assert (
        job.title
        == "Software Engineer I"
    )

    assert (
        job.location
        == "New York, NY"
    )

    assert (
        job.description
        == "Build reliable software."
    )

    assert (
        job.official_url
        == (
            "https://jobs.ashbyhq.com/"
            "ExampleAI/"
            "12345678-abcd"
        )
    )

    assert (
        job.posted_at
        == datetime(
            2026,
            9,
            3,
            12,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_unlisted_ashby_posting_is_ignored() -> None:
    client = make_client(
        {
            "jobs": [
                {
                    "title": "Hidden Role",
                    "location": "Remote",
                    "isListed": False,
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "hidden-role"
                    ),
                },
            ],
        }
    )

    jobs = fetch_ashby_jobs(
        "ExampleAI",
        "Example AI",
        client=client,
    )

    assert jobs == []


def test_missing_description_is_allowed() -> None:
    client = make_client(
        {
            "jobs": [
                {
                    "title": "Software Engineer",
                    "location": "Remote",
                    "isListed": True,
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "engineer-123"
                    ),
                },
            ],
        }
    )

    jobs = fetch_ashby_jobs(
        "ExampleAI",
        "Example AI",
        client=client,
    )

    assert len(jobs) == 1

    assert jobs[0].description == ""


def test_missing_location_uses_unknown() -> None:
    client = make_client(
        {
            "jobs": [
                {
                    "title": "Software Engineer",
                    "isListed": True,
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "engineer-123"
                    ),
                },
            ],
        }
    )

    jobs = fetch_ashby_jobs(
        "ExampleAI",
        "Example AI",
        client=client,
    )

    assert jobs[0].location == "Unknown"


def test_invalid_datetime_is_treated_as_missing() -> None:
    client = make_client(
        {
            "jobs": [
                {
                    "title": "Software Engineer",
                    "location": "Remote",
                    "isListed": True,
                    "publishedAt": "not-a-date",
                    "updatedAt": "also-not-a-date",
                    "jobUrl": (
                        "https://jobs.ashbyhq.com/"
                        "ExampleAI/"
                        "engineer-123"
                    ),
                },
            ],
        }
    )

    jobs = fetch_ashby_jobs(
        "ExampleAI",
        "Example AI",
        client=client,
    )

    assert jobs[0].posted_at is None
    assert jobs[0].updated_at is None


def test_blank_board_name_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="board_name",
    ):
        fetch_ashby_jobs(
            "   ",
            "Example AI",
        )


def test_blank_company_name_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="company_name",
    ):
        fetch_ashby_jobs(
            "ExampleAI",
            "   ",
        )


def test_http_failure_is_not_silently_swallowed() -> None:
    client = make_client(
        {
            "error": "synthetic",
        },
        status_code=500,
    )

    with pytest.raises(
        httpx.HTTPStatusError,
    ):
        fetch_ashby_jobs(
            "ExampleAI",
            "Example AI",
            client=client,
        )
