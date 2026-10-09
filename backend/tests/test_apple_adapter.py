"""Apple's careers search, read from the pages jobs.apple.com serves.

Apple was on ACE's list of top employers and no Apple role had ever been
read from Apple. The fixtures are trimmed to the fields the reader uses.
"""

from __future__ import annotations

import json
from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters import apple
from backend.app.adapters.apple import (
    TEAMS,
    fetch_apple_jobs,
    parse_job_page,
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


def page(
    loader_data: dict,
) -> str:
    """A server-rendered page, its data embedded as the site embeds it."""

    return (
        "<html><body><script>"
        "window.__staticRouterHydrationData = JSON.parse("
        + json.dumps(json.dumps({"loaderData": loader_data}))
        + ");</script></body></html>"
    )


def row(
    position: str,
    *,
    title: str = "Software Engineer, Siri",
    place: str = "Cupertino",
    day: str = "2026-10-08",
) -> dict:
    return {
        "id": f"{position}-0836",
        "positionId": position,
        "postingTitle": title,
        "transformedPostingTitle": title.lower().replace(" ", "-"),
        "postDateInGMT": f"{day}T23:39:49.358065956Z",
        "locations": [
            {"name": place, "countryName": "United States of America"}
        ],
        "homeOffice": False,
    }


def search_page(
    rows: list[dict],
    total: int,
) -> str:
    return page(
        {
            "search": {
                "searchResults": rows,
                "totalRecords": total,
                "filters": {"teams": [{"code": team} for team in TEAMS]},
            }
        }
    )


def job_page(
    *,
    years: str = "3+ years of industry experience.",
) -> str:
    return page(
        {
            "jobDetails": {
                "jobsData": {
                    "jobSummary": "Build the services behind Siri.",
                    "description": "You will design and ship features.",
                    "minimumQualifications": "BS in Computer Science.",
                    "preferredQualifications": years,
                    "lowJobTitle": "Software Engineering Applications ICT3",
                    "highJobTitle": "Software Engineering Applications ICT4",
                    "locations": [
                        {
                            "name": "Cupertino",
                            "city": "Cupertino",
                            "stateProvince": "California",
                            "countryName": "United States",
                        }
                    ],
                    "homeOffice": False,
                }
            }
        }
    )


def site(
    pages: dict[int, str],
    *,
    detail: str | None = None,
):
    asked: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            str(request.url)
        )

        if "/details/" in request.url.path:
            return httpx.Response(
                200,
                text=detail or job_page(),
            )

        number = int(
            request.url.params.get(
                "page",
                1,
            )
        )

        return httpx.Response(
            200,
            text=pages.get(
                number,
                search_page([], 0),
            ),
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
    ), asked


def test_a_posting_in_three_cities_is_one_job() -> None:
    client, _asked = site(
        {
            1: search_page(
                [
                    row("200686913", place="Cupertino"),
                    row("200686913", place="Seattle"),
                    row("200686913", place="Austin"),
                ],
                3,
            )
        }
    )

    jobs = fetch_apple_jobs(
        source_account="test-merge",
        client=client,
        now=NOW,
        full=True,
        should_fetch_detail=lambda title: False,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert len(jobs) == 1

    assert jobs[0].location == (
        "Cupertino, United States; "
        "Seattle, United States; "
        "Austin, United States"
    )

    assert jobs[0].official_url == (
        "https://jobs.apple.com/en-us/details/200686913-0836/"
        "software-engineer,-siri"
    )


def test_the_team_list_keeps_its_plus_signs() -> None:
    """An encoded "+" reads as one unknown team, and the search falls
    back to all 4,440 US openings."""

    client, asked = site(
        {
            1: search_page(
                [row("1")],
                1,
            )
        }
    )

    fetch_apple_jobs(
        source_account="test-plus",
        client=client,
        now=NOW,
        full=True,
        should_fetch_detail=lambda title: False,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert "+".join(TEAMS) in asked[0]

    assert "%2B" not in asked[0]


def test_a_poll_reads_only_the_recent_pages_and_closes_nothing() -> None:
    client, asked = site(
        {
            1: search_page(
                [row(str(i), day="2026-10-08") for i in range(20)],
                80,
            ),
            2: search_page(
                [row(str(20 + i), day="2026-10-06") for i in range(20)],
                80,
            ),
            3: search_page(
                [row(str(40 + i), day="2026-10-01") for i in range(20)],
                80,
            ),
        }
    )

    jobs = fetch_apple_jobs(
        source_account="test-recent",
        client=client,
        now=NOW,
        full=False,
        should_fetch_detail=lambda title: False,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert [
        url
        for url in asked
        if "/search" in url
    ] == [
        apple._page_url(1),
        apple._page_url(2),
    ]

    assert len(jobs) == 40

    assert jobs.complete is False


def test_a_full_read_reaches_the_end_and_is_complete() -> None:
    client, _asked = site(
        {
            1: search_page(
                [row(str(i), day="2026-10-08") for i in range(20)],
                25,
            ),
            2: search_page(
                [row(str(20 + i), day="2026-09-01") for i in range(5)],
                25,
            ),
        }
    )

    jobs = fetch_apple_jobs(
        source_account="test-full",
        client=client,
        now=NOW,
        full=True,
        should_fetch_detail=lambda title: False,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert len(jobs) == 25

    assert jobs.complete is True


def test_a_posting_s_own_page_gives_the_gate_its_requirements() -> None:
    location, description = parse_job_page(
        job_page()
    )

    assert location == "Cupertino, California, United States"

    assert "Preferred Qualifications\n3+ years" in description

    assert "ICT3 to Software Engineering Applications ICT4" in description


def test_a_role_asking_five_years_is_rejected_on_its_own_page() -> None:
    client, _asked = site(
        {
            1: search_page(
                [row("200683887")],
                1,
            )
        },
        detail=job_page(
            years="5+ years of experience building backend services.",
        ),
    )

    jobs = fetch_apple_jobs(
        source_account="test-years",
        client=client,
        now=NOW,
        full=True,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert (
        EligibilityReasonCode.EXPERIENCE_TOO_HIGH
        in evaluate_job(jobs[0]).reason_codes
    )


def test_an_in_cap_role_passes() -> None:
    client, _asked = site(
        {
            1: search_page(
                [row("200683887", title="Backend Software Engineer - Apple TV")],
                1,
            )
        },
    )

    jobs = fetch_apple_jobs(
        source_account="test-pass",
        client=client,
        now=NOW,
        full=True,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert evaluate_job(
        jobs[0]
    ).status == EligibilityStatus.PASS


def test_a_posting_already_held_is_not_read_again() -> None:
    client, asked = site(
        {
            1: search_page(
                [row("1"), row("2")],
                2,
            )
        },
    )

    jobs = fetch_apple_jobs(
        source_account="test-known",
        client=client,
        now=NOW,
        full=True,
        known={
            "1": (
                "Cupertino, California, United States",
                "What ACE read before.",
            )
        },
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    read = [
        url
        for url in asked
        if "/details/" in url
    ]

    assert len(read) == 1 and "/details/2-0836/" in read[0]

    by_id = {
        job.external_id: job
        for job in jobs
    }

    assert by_id["1"].description == "What ACE read before."


def test_a_title_the_gate_rejects_is_never_read_in_full() -> None:
    client, asked = site(
        {
            1: search_page(
                [row("1", title="Engineering Manager, Siri")],
                1,
            )
        },
    )

    jobs = fetch_apple_jobs(
        source_account="test-skip",
        client=client,
        now=NOW,
        full=True,
        should_fetch_detail=lambda title: "Manager" not in title,
        page_pause_seconds=0,
        detail_pause_seconds=0,
    )

    assert not [
        url
        for url in asked
        if "/details/" in url
    ]

    assert jobs[0].description == ""
