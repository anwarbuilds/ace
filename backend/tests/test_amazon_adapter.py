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
    IncompleteAmazonRead,
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
    pages: list[list[dict]] | dict[str, list[list[dict]]],
    *,
    hits: int | None = None,
    requests: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    """Serve paginated Amazon search results, per category.

    A plain list is served for every category.
    """

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if requests is not None:
            requests.append(
                request
            )

        offset = int(
            request.url.params.get(
                "offset",
                0,
            )
        )

        category_pages = (
            pages.get(
                request.url.params.get(
                    "category[]"
                ),
                [],
            )
            if isinstance(
                pages,
                dict,
            )
            else pages
        )

        index = offset // AMAZON_PAGE_SIZE

        page = (
            category_pages[index]
            if index < len(category_pages)
            else []
        )

        body = {
            "jobs": page,
        }

        if hits is not None:
            body["hits"] = hits

        return httpx.Response(
            200,
            json=body,
        )

    return httpx.MockTransport(
        handler
    )


def fetch(
    pages,
    *,
    hits: int | None = None,
    requests: list[httpx.Request] | None = None,
    **kwargs,
):
    """Run the adapter against in-memory pages."""

    with httpx.Client(
        transport=transport(
            pages,
            hits=hits,
            requests=requests,
        )
    ) as client:
        return fetch_amazon_jobs(
            client=client,
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


def full_page(
    prefix: str,
    *,
    posted: str = "September 4, 2026",
) -> list[dict]:
    return [
        posting(
            job_id=f"{prefix}{index}",
            posted=posted,
        )
        for index in range(
            AMAZON_PAGE_SIZE
        )
    ]


def test_an_old_posting_that_is_still_open_is_read() -> None:
    """The bug. Amazon's new-grad postings stay open for months:
    "Software Development Engineer - 2026 (US)" was posted in February,
    and a 45-day horizon hid it."""

    jobs = fetch(
        {
            "software-development": [
                full_page(
                    "recent-"
                ),
                [
                    posting(
                        job_id="3177934",
                        title=(
                            "Software Development Engineer "
                            "- 2026 (US)"
                        ),
                        posted="February 10, 2026",
                    ),
                ],
            ],
        },
        categories=(
            "software-development",
        ),
    )

    assert "3177934" in {
        job.external_id
        for job in jobs
    }


def test_every_page_of_every_category_is_read() -> None:
    requests: list[httpx.Request] = []

    jobs = fetch(
        {
            "software-development": [
                full_page("sde-"),
                full_page("sde2-"),
                [posting(job_id="sde-last")],
            ],
            "machine-learning-science": [
                [posting(job_id="ml-1")],
            ],
        },
        requests=requests,
        categories=(
            "software-development",
            "machine-learning-science",
        ),
    )

    assert len(jobs) == 2 * AMAZON_PAGE_SIZE + 2

    assert {
        request.url.params.get(
            "category[]"
        )
        for request in requests
    } == {
        "software-development",
        "machine-learning-science",
    }


def test_a_posting_filed_under_two_categories_is_read_once() -> None:
    jobs = fetch(
        {
            "software-development": [
                [posting(job_id="1")],
            ],
            "machine-learning-science": [
                [posting(job_id="1")],
            ],
        },
        categories=(
            "software-development",
            "machine-learning-science",
        ),
    )

    assert len(jobs) == 1


def test_the_walk_stops_at_the_reported_total() -> None:
    """A full last page is not a reason to ask for one more."""

    requests: list[httpx.Request] = []

    fetch(
        {
            "software-development": [
                full_page("a-"),
                full_page("b-"),
            ],
        },
        hits=2 * AMAZON_PAGE_SIZE,
        requests=requests,
        categories=(
            "software-development",
        ),
    )

    assert len(requests) == 2


def test_a_category_too_large_to_finish_is_refused_not_cut() -> None:
    """A snapshot is authoritative: whatever it lacks is marked closed.
    The 25-page limit closed every open posting past the 2,500th."""

    with pytest.raises(
        IncompleteAmazonRead,
    ):
        fetch(
            {
                "software-development": [
                    full_page(f"p{index}-")
                    for index in range(5)
                ],
            },
            categories=(
                "software-development",
            ),
            max_pages_per_category=3,
        )


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
