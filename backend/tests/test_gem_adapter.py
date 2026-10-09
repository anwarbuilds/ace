"""Gem job boards, read from Gem's public job board API.

Fixtures are trimmed to the fields the reader uses, with fictional
posts.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.gem import (
    canonical_job,
    fetch_gem_jobs,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)


POST = {
    "id": "am9icG9zdDpleGFtcGxl",
    "title": "Cloud Platform Software Engineer",
    "absolute_url": "https://jobs.gem.com/example/am9icG9zdDpleGFtcGxl",
    "content": "<p>Build our inference cloud.</p>",
    "content_plain": "Build our inference cloud. 2+ years of experience with Kubernetes.",
    "location": {"name": "San Francisco, United States"},
    "location_type": "in_office",
    "employment_type": "full_time",
    "first_published_at": "2026-10-07T22:50:01.732Z",
    "updated_at": "2026-10-08T21:27:27.196Z",
    "requisition_id": "R801",
}


def test_a_post_becomes_a_job_with_its_description() -> None:
    job = canonical_job(
        POST,
        company_name="Example",
    )

    assert job.external_id == "am9icG9zdDpleGFtcGxl"

    assert job.official_url == POST["absolute_url"]

    assert "Kubernetes" in job.description

    assert job.posted_at == datetime(
        2026,
        10,
        7,
        22,
        50,
        1,
        732000,
        tzinfo=timezone.utc,
    )

    assert evaluate_job(
        job
    ).status == EligibilityStatus.PASS


def test_a_remote_post_says_so() -> None:
    job = canonical_job(
        {
            **POST,
            "location": {"name": "United States"},
            "location_type": "remote",
        },
        company_name="Example",
    )

    assert job.location == "Remote - United States"


def test_a_board_is_one_request() -> None:
    asked: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            str(request.url)
        )

        return httpx.Response(
            200,
            json=[POST, {"id": "", "title": "No id"}],
        )

    jobs = fetch_gem_jobs(
        source_account="example",
        company_name="Example",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
        ),
    )

    assert asked == [
        "https://api.gem.com/job_board/v0/example/job_posts/",
    ]

    assert [job.title for job in jobs] == [
        "Cloud Platform Software Engineer",
    ]


def test_an_answer_that_is_not_a_list_is_an_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": "not found"},
        )

    with pytest.raises(ValueError):
        fetch_gem_jobs(
            source_account="example",
            company_name="Example",
            client=httpx.Client(
                transport=httpx.MockTransport(handler),
            ),
        )
