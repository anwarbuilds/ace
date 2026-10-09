"""iCIMS Jibe careers sites: AMD's and Susquehanna's job API.

Fixtures are trimmed to the fields the reader uses, with fictional
openings.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters import jibe
from backend.app.adapters.jibe import (
    canonical_job,
    fetch_jibe_jobs,
)
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)


NOW = datetime(
    2026,
    10,
    9,
    12,
    tzinfo=timezone.utc,
)


def opening(
    slug: str,
    *,
    title: str = "Software Development Engineer",
    day: str = "2026-10-08",
    country: str = "United States",
    employment: str | None = "FULL_TIME",
) -> dict:
    return {
        "data": {
            "slug": slug,
            "req_id": slug,
            "title": title,
            "city": "Austin",
            "state": "Texas",
            "country": country,
            "full_location": "Austin, Texas",
            "posted_date": f"{day}T18:51:00+0000",
            "update_date": f"{day}T18:52:00+0000",
            "employment_type": employment,
            "description": "<p>Build the drivers for our GPUs.</p>",
            "responsibilities": "<ul><li>Write C++ and Python.</li></ul>",
            "qualifications": "<p>BS in Computer Science. 1-3 years of experience.</p>",
        }
    }


def api(
    pages: dict[int, list[dict]],
    *,
    etag: str | None = None,
):
    asked: list[dict] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            {
                "page": int(request.url.params["page"]),
                "if_none_match": request.headers.get("if-none-match"),
            }
        )

        if etag and request.headers.get("if-none-match") == etag:
            return httpx.Response(304)

        page = int(
            request.url.params["page"]
        )

        return httpx.Response(
            200,
            json={"jobs": pages.get(page, [])},
            headers={"ETag": etag} if etag else {},
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
    ), asked


def test_an_opening_is_read_whole_and_placed() -> None:
    job = canonical_job(
        opening("93498")["data"],
        source_account="careers.example-chips.com/careers-home",
        company_name="Example Chips",
    )

    assert job.official_url == (
        "https://careers.example-chips.com/careers-home/jobs/93498?lang=en-us"
    )

    assert job.location == "Austin, Texas, United States"

    assert "Write C++ and Python." in job.description

    assert job.posted_at == datetime(
        2026,
        10,
        8,
        18,
        51,
        tzinfo=timezone.utc,
    )

    assert evaluate_job(
        job
    ).status == EligibilityStatus.PASS


def test_a_contract_to_hire_opening_is_a_contract() -> None:
    job = canonical_job(
        opening("1", employment="CONTRACT_TO_HIRE")["data"],
        source_account="careers.example.com",
        company_name="Example",
    )

    assert (
        EligibilityReasonCode.CONTRACT_ROLE
        in evaluate_job(job).reason_codes
    )


def test_a_poll_reads_only_the_recent_pages_and_closes_nothing() -> None:
    client, asked = api(
        {
            1: [opening(str(i), day="2026-10-08") for i in range(100)],
            2: [opening(str(100 + i), day="2026-10-02") for i in range(100)],
            3: [opening(str(200 + i), day="2026-09-01") for i in range(20)],
        }
    )

    jobs = fetch_jibe_jobs(
        source_account="test-recent",
        company_name="Example",
        client=client,
        now=NOW,
        full=False,
        crawl_delay_seconds=0,
    )

    assert [ask["page"] for ask in asked] == [1, 2]

    assert len(jobs) == 200

    assert jobs.complete is False


def test_a_full_read_reaches_the_end_and_is_complete() -> None:
    client, asked = api(
        {
            1: [opening(str(i), day="2026-10-08") for i in range(100)],
            2: [opening(str(100 + i), day="2026-09-01") for i in range(30)],
        }
    )

    jobs = fetch_jibe_jobs(
        source_account="test-full",
        company_name="Example",
        client=client,
        now=NOW,
        full=True,
        crawl_delay_seconds=0,
    )

    assert [ask["page"] for ask in asked] == [1, 2]

    assert len(jobs) == 130

    assert jobs.complete is True


def test_an_unchanged_first_page_reads_nothing_more() -> None:
    jibe._first_page_etag.pop(
        "test-etag",
        None,
    )

    client, asked = api(
        {
            1: [opening(str(i)) for i in range(100)],
        },
        etag='W/"abc"',
    )

    fetch_jibe_jobs(
        source_account="test-etag",
        company_name="Example",
        client=client,
        now=NOW,
        full=True,
        crawl_delay_seconds=0,
    )

    asked.clear()

    jobs = fetch_jibe_jobs(
        source_account="test-etag",
        company_name="Example",
        client=client,
        now=NOW,
        full=False,
        crawl_delay_seconds=0,
    )

    assert asked == [
        {"page": 1, "if_none_match": 'W/"abc"'},
    ]

    assert len(jobs) == 0

    assert jobs.complete is False


def test_an_empty_full_read_is_never_every_posting_closing() -> None:
    client, _asked = api(
        {}
    )

    with pytest.raises(ValueError):
        fetch_jibe_jobs(
            source_account="test-empty",
            company_name="Example",
            client=client,
            now=NOW,
            full=True,
            crawl_delay_seconds=0,
        )
