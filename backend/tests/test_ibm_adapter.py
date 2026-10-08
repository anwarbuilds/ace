"""IBM's careers search: what ACE reads in place of careers.ibm.com.

careers.ibm.com is behind a bot challenge ACE does not get round, and
no IBM role had ever been in ACE -- the user found IBM's "2027
Entry-Level -- Software Developer, AI & Marketing Platforms" by hand.
"""

from __future__ import annotations

import json
from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters import ibm
from backend.app.adapters.ibm import (
    COUNTRIES,
    _location,
    canonical_job,
    fetch_ibm_jobs,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    _is_us_location,
    evaluate_job,
)


NOW = datetime(
    2026,
    10,
    8,
    12,
    tzinfo=timezone.utc,
)


def result(
    job_id: int,
    *,
    title: str = "Software Developer",
    location: str = "New York, US",
    day: str = "2026-10-07",
    level: str = "Entry Level",
) -> dict:
    return {
        "_source": {
            "url": f"https://careers.ibm.com/careers/JobDetail?jobId={job_id}",
            "title": title,
            "description": "At IBM, work is more than a job...",
            "dcdate": day,
            "field_keyword_08": "Software Engineering",
            "field_keyword_17": "Hybrid",
            "field_keyword_18": level,
            "field_keyword_19": location,
        }
    }


def search(
    pages: list[list[dict]],
):
    asked: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        index = body["from"] // body["size"]
        asked.append(index)
        hits = pages[index] if index < len(pages) else []
        return httpx.Response(
            200,
            json={"hits": {"total": {"value": 0}, "hits": hits}},
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), asked


def test_the_reported_role_is_read_and_passes_the_gate() -> None:
    job = canonical_job(
        result(
            133448,
            title=(
                "2027 Entry-Level — Software Developer, "
                "AI & Marketing Platforms"
            ),
            day="2026-10-06",
        )["_source"]
    )

    assert job.external_id == "133448"

    assert job.location == "New York, United States"

    assert "Entry Level" in job.description

    assert job.posted_at == datetime(
        2026,
        10,
        6,
        tzinfo=timezone.utc,
    )

    assert evaluate_job(
        job
    ).status == EligibilityStatus.PASS


def test_a_country_code_that_is_also_a_state_is_written_out() -> None:
    """43 Canadian and 19 German openings would have read as Californian
    and Delawarean."""

    assert _location("Toronto, CA", "") == "Toronto, Canada"
    assert _location("Böblingen, DE", "") == "Böblingen, Germany"
    assert _location("Bangalore, IN", "") == "Bangalore, India"

    for written in (
        "Toronto, Canada",
        "Böblingen, Germany",
        "Bangalore, India",
    ):
        assert not _is_us_location(
            written
        ), written


def test_every_country_ibm_can_name_is_outside_the_us() -> None:
    for code, name in COUNTRIES.items():
        assert not _is_us_location(
            _location(f"Somewhere, {code}", "")
        ), (code, name)


def test_multiple_cities_takes_the_us_places_its_title_names() -> None:
    assert _location(
        "Multiple Cities",
        "Site Reliability Engineer ELH - OneIT - Durham, NC - 2027",
    ) == "Durham, NC"

    assert _location(
        "Multiple Cities",
        "Power Backend Developer Intern - Rochester, MN & Austin, TX - 2027",
    ) == "Rochester, MN; Austin, TX"

    assert _location(
        "Multiple Cities",
        "Entry Level Hardware Developer 2027 -New York",
    ) == "New York, NY"

    assert _is_us_location(
        "Durham, NC"
    )


def test_multiple_cities_with_no_us_place_stays_unplaced() -> None:
    location = _location(
        "Multiple Cities",
        "Data Engineer-Data Modeling",
    )

    assert location == "Multiple Cities"

    assert not _is_us_location(
        location
    )


def test_a_poll_reads_only_the_recent_pages_and_closes_nothing() -> None:
    pages = [
        [result(i, day="2026-10-07") for i in range(100)],
        [result(100 + i, day="2026-10-02") for i in range(100)],
        [result(200 + i, day="2026-09-20") for i in range(100)],
        [result(300 + i, day="2026-09-01") for i in range(10)],
    ]

    client, asked = search(pages)

    jobs = fetch_ibm_jobs(
        source_account="test-recent",
        client=client,
        now=NOW,
        full=False,
        pause_seconds=0,
    )

    assert asked == [0, 1]

    assert len(jobs) == 200

    assert jobs.complete is False


def test_a_full_read_reaches_the_end_and_is_complete() -> None:
    pages = [
        [result(i, day="2026-10-07") for i in range(100)],
        [result(100 + i, day="2026-09-01") for i in range(40)],
    ]

    client, asked = search(pages)

    jobs = fetch_ibm_jobs(
        source_account="test-full",
        client=client,
        now=NOW,
        full=True,
        pause_seconds=0,
    )

    assert asked == [0, 1]

    assert len(jobs) == 140

    assert jobs.complete is True


def test_the_first_poll_is_a_full_read() -> None:
    ibm._last_full_read.pop(
        "test-first",
        None,
    )

    pages = [
        [result(i, day="2026-09-01") for i in range(30)],
    ]

    client, _asked = search(pages)

    jobs = fetch_ibm_jobs(
        source_account="test-first",
        client=client,
        now=NOW,
        pause_seconds=0,
    )

    assert jobs.complete is True
