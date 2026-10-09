"""Google's careers search: the first page of each search, newest first.

Google's robots.txt disallows paging the results and allows the first
page. The fixtures are trimmed copies of a results row, with fictional
postings.
"""

from __future__ import annotations

import json
from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.google import (
    canonical_job,
    fetch_google_jobs,
    parse_results,
)
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)


def row(
    job_id: str,
    *,
    title: str = "Software Engineer III, Example Infrastructure",
    years: str = "2 years of experience with software development.",
) -> list:
    fields: list = [None] * 21
    fields[0] = job_id
    fields[1] = title
    fields[3] = [None, "<ul><li>Write and review code.</li></ul>"]
    fields[4] = [
        None,
        "<h3>Minimum qualifications:</h3><ul><li>Bachelor's degree or "
        f"equivalent practical experience.</li><li>{years}</li></ul>",
    ]
    fields[7] = "Google"
    fields[9] = [
        ["Mountain View, CA, USA", ["1 Example Way"], "Mountain View", "94043", "CA", "US"],
        ["Kirkland, WA, USA", ["2 Example Way"], "Kirkland", "98033", "WA", "US"],
    ]
    fields[10] = [None, "<p>Google's software engineers build things.</p>"]
    fields[12] = [1791468934, 513000000]
    fields[14] = [1791468934, 829000000]
    return fields


def page(
    rows: list[list],
) -> str:
    data = json.dumps([rows, None, len(rows), 20])

    return (
        "<html><body>"
        "<script>AF_initDataCallback({key: 'ds:0', hash: '1', "
        "data:[[]], sideChannel: {}});</script>"
        "<script>AF_initDataCallback({key: 'ds:1', hash: '2', "
        f"data:{data}, sideChannel: {{}}}});</script>"
        "</body></html>"
    )


def test_a_result_becomes_a_job_with_its_whole_posting() -> None:
    job = canonical_job(
        row("87326868012704454")
    )

    assert job.official_url == (
        "https://www.google.com/about/careers/applications/jobs/results/"
        "87326868012704454-software-engineer-iii-example-infrastructure"
    )

    assert job.location == "Mountain View, CA, USA; Kirkland, WA, USA"

    assert "2 years of experience" in job.description

    assert job.posted_at == datetime.fromtimestamp(
        1791468934,
        tz=timezone.utc,
    )


def test_software_engineer_iii_asking_two_years_passes() -> None:
    """Google's second rung: 19 of its first 20 mid-level software
    postings were rejected as senior for the numeral."""

    assert evaluate_job(
        canonical_job(
            row("1")
        )
    ).status == EligibilityStatus.PASS


def test_level_iii_with_no_stated_years_stays_senior() -> None:
    assert (
        EligibilityReasonCode.SENIOR_TITLE
        in evaluate_job(
            canonical_job(
                row(
                    "1",
                    title="Software Engineer III",
                    years="Experience with distributed systems.",
                )
            )
        ).reason_codes
    )


def test_level_iii_asking_five_years_is_rejected() -> None:
    assert evaluate_job(
        canonical_job(
            row(
                "1",
                years="5 years of experience with software development.",
            )
        )
    ).status == EligibilityStatus.REJECT


def test_only_first_pages_are_read_and_nothing_is_closed() -> None:
    asked: list[httpx.URL] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            request.url
        )

        return httpx.Response(
            200,
            text=page([row("1"), row("2", title="Data Center Technician")]),
        )

    jobs = fetch_google_jobs(
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
        ),
        pause_seconds=0,
    )

    assert len(asked) == 3

    assert all(
        "page" not in url.params
        for url in asked
    )

    # The same posting from two searches is one job.
    assert sorted(job.external_id for job in jobs) == ["1", "2"]

    assert jobs.complete is False


def test_a_search_that_pages_is_refused() -> None:
    with pytest.raises(ValueError):
        fetch_google_jobs(
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, text=page([]))
                ),
            ),
            searches=({"q": "software", "page": "2"},),
            pause_seconds=0,
        )


def test_a_page_without_results_data_is_an_error() -> None:
    with pytest.raises(ValueError):
        parse_results(
            "<html></html>"
        )
