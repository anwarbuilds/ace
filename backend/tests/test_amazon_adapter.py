"""Tests for the ACE Amazon Jobs adapter."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.amazon import (
    AMAZON_PAGE_SIZE,
    build_description,
    build_location,
    fetch_amazon_jobs,
    parse_posted_date,
)


NOW = datetime(
    2026,
    9,
    6,
    12,
    0,
    tzinfo=timezone.utc,
)


def posting(
    *,
    job_id: str,
    title: str = "Software Development Engineer",
    posted: str = "September 4, 2026",
) -> dict:
    """Build one Amazon search result."""

    return {
        "id_icims": job_id,
        "title": title,
        "job_path": f"/en/jobs/{job_id}/x",
        "location": "US, WA, Seattle",
        "city": "Seattle",
        "state": "WA",
        "posted_date": posted,
        "description": (
            "<p>Build distributed "
            "systems.</p>"
        ),
        "basic_qualifications": (
            "<li>Experience with "
            "Python</li>"
        ),
        "preferred_qualifications": (
            "MS degree"
        ),
    }


def transport(
    pages: list[list[dict]],
) -> httpx.MockTransport:
    """Serve paginated Amazon search results."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        offset = int(
            request.url.params.get(
                "offset",
                0,
            )
        )

        index = offset // AMAZON_PAGE_SIZE

        page = (
            pages[index]
            if index < len(pages)
            else []
        )

        return httpx.Response(
            200,
            json={
                "hits": 10000,
                "jobs": page,
            },
        )

    return httpx.MockTransport(
        handler
    )


def fetch(
    pages: list[list[dict]],
    **kwargs,
):
    """Run the adapter against in-memory pages."""

    with httpx.Client(
        transport=transport(
            pages
        )
    ) as client:
        return fetch_amazon_jobs(
            client=client,
            now=NOW,
            **kwargs,
        )


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "September 4, 2026",
        "September  4, 2026",
        "Sep 4, 2026",
    ],
)
def test_posted_dates_are_parsed(
    value: str,
) -> None:
    """Amazon renders dates with inconsistent spacing."""

    assert parse_posted_date(
        value
    ) == datetime(
        2026,
        9,
        4,
        tzinfo=timezone.utc,
    )


def test_unparseable_date_is_none() -> None:
    assert (
        parse_posted_date(
            "sometime"
        )
        is None
    )


def test_description_joins_all_requirement_sections() -> None:
    """The gate reads requirements that live outside the description."""

    text = build_description(
        {
            "description": "<p>Build.</p>",
            "basic_qualifications": (
                "3+ years of experience"
            ),
            "preferred_qualifications": (
                "MS degree"
            ),
        }
    )

    assert "Build." in text

    assert (
        "3+ years of experience" in text
    )

    assert "MS degree" in text


def test_location_falls_back_to_city_state() -> None:
    assert build_location(
        {
            "city": "Seattle",
            "state": "WA",
        }
    ) == "Seattle, WA"


# ----------------------------------------------------------------------
# Recency paging
# ----------------------------------------------------------------------


def test_paging_stops_once_results_predate_the_horizon() -> None:
    """Results are newest first, so an old page ends the walk."""

    recent = [
        posting(
            job_id=str(
                index
            ),
            posted="September 4, 2026",
        )
        for index in range(
            AMAZON_PAGE_SIZE
        )
    ]

    old = [
        posting(
            job_id=f"old-{index}",
            posted="January 1, 2020",
        )
        for index in range(
            AMAZON_PAGE_SIZE
        )
    ]

    jobs = fetch(
        [
            recent,
            old,
            recent,
        ],
        horizon_days=45,
    )

    # The third page is never reached.
    assert len(jobs) == AMAZON_PAGE_SIZE


def test_unknown_dates_do_not_end_the_walk() -> None:
    """An unparseable date is unknown, not old."""

    jobs = fetch(
        [
            [
                posting(
                    job_id="1",
                    posted="whenever",
                ),
            ],
        ]
    )

    assert len(jobs) == 1

    assert jobs[0].posted_at is None


def test_official_url_points_at_amazon_jobs() -> None:
    jobs = fetch(
        [
            [
                posting(
                    job_id="123"
                ),
            ],
        ]
    )

    assert jobs[0].official_url == (
        "https://www.amazon.jobs"
        "/en/jobs/123/x"
    )


def test_duplicate_ids_are_collapsed() -> None:
    jobs = fetch(
        [
            [
                posting(
                    job_id="1"
                ),
                posting(
                    job_id="1"
                ),
            ],
        ]
    )

    assert len(jobs) == 1


def test_empty_result_returns_no_jobs() -> None:
    assert fetch(
        [
            [],
        ]
    ) == []
