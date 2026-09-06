"""Tests for the ACE Workday CXS adapter."""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.workday import (
    DEFAULT_MAX_DETAIL_FETCHES,
    WORKDAY_PAGE_SIZE,
    WorkdaySourceError,
    fetch_workday_jobs,
    parse_posted_on,
    parse_source_account,
    parse_start_date,
)
from backend.app.runners.workday import (
    build_detail_predicate,
)


HOST = "acme.wd5.myworkdayjobs.com"

ACCOUNT = "acme/ExternalCareers"

REFERENCE = datetime(
    2026,
    9,
    6,
    12,
    0,
    tzinfo=timezone.utc,
)


def listing(
    *,
    title: str,
    path: str,
    posted: str = "Posted Today",
    req: str = "JR0001",
) -> dict:
    """Build one Workday list entry."""

    return {
        "title": title,
        "externalPath": path,
        "locationsText": "2 Locations",
        "postedOn": posted,
        "bulletFields": [
            "Spotlight Job",
            req,
        ],
    }


def build_transport(
    postings: list[dict],
    *,
    detail_calls: list[str] | None = None,
    description: str = (
        "<p>Build <b>software</b> in "
        "Python.</p>"
    ),
    start_date: str = "2026-09-04",
) -> httpx.MockTransport:
    """Serve a paginated Workday tenant from memory."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.method == "POST":
            import json as _json

            body = _json.loads(
                request.content
            )

            offset = body["offset"]

            page = postings[
                offset:offset
                + WORKDAY_PAGE_SIZE
            ]

            return httpx.Response(
                200,
                json={
                    "total": len(
                        postings
                    ),
                    "jobPostings": page,
                },
            )

        if detail_calls is not None:
            detail_calls.append(
                request.url.path
            )

        return httpx.Response(
            200,
            json={
                "jobPostingInfo": {
                    "jobDescription": (
                        description
                    ),
                    "location": (
                        "Seattle, WA"
                    ),
                    "additionalLocations": [
                        "Austin, TX",
                    ],
                    "startDate": (
                        start_date
                    ),
                    "jobReqId": "JR0042",
                    "externalUrl": (
                        f"https://{HOST}"
                        "/ExternalCareers"
                        "/job/real"
                    ),
                },
            },
        )

    return httpx.MockTransport(
        handler
    )


def fetch(
    postings: list[dict],
    **kwargs,
):
    """Run the adapter against an in-memory tenant."""

    detail_calls = kwargs.pop(
        "detail_calls",
        None,
    )

    transport = build_transport(
        postings,
        detail_calls=detail_calls,
    )

    with httpx.Client(
        transport=transport
    ) as client:
        return fetch_workday_jobs(
            source_account=ACCOUNT,
            company_name="Acme",
            source_host=HOST,
            client=client,
            now=REFERENCE,
            **kwargs,
        )


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------


def test_source_account_splits_tenant_and_site() -> None:
    assert parse_source_account(
        "nvidia/NVIDIAExternalCareerSite"
    ) == (
        "nvidia",
        "NVIDIAExternalCareerSite",
    )


@pytest.mark.parametrize(
    "value",
    [
        "nvidia",
        "",
        "a/b/c",
        "   ",
    ],
)
def test_malformed_source_account_is_rejected(
    value: str,
) -> None:
    with pytest.raises(
        WorkdaySourceError
    ):
        parse_source_account(
            value
        )


def test_missing_host_is_rejected() -> None:
    """The Workday data-centre number cannot be derived."""

    with pytest.raises(
        WorkdaySourceError
    ):
        fetch_workday_jobs(
            source_account=ACCOUNT,
            company_name="Acme",
            source_host=None,
        )


# ----------------------------------------------------------------------
# Date parsing
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_days",
    [
        ("Posted Today", 0),
        ("Posted Yesterday", 1),
        ("Posted 3 Days Ago", 3),
        ("Posted 30+ Days Ago", 30),
    ],
)
def test_relative_posted_labels_are_parsed(
    text: str,
    expected_days: int,
) -> None:
    parsed = parse_posted_on(
        text,
        reference=REFERENCE,
    )

    assert parsed is not None

    assert (
        REFERENCE - parsed
    ).days == expected_days


def test_unparseable_posted_label_is_none() -> None:
    """An unknown label is unknown, not a fabricated date."""

    assert (
        parse_posted_on(
            "Posted recently",
            reference=REFERENCE,
        )
        is None
    )


def test_start_date_is_preferred_over_relative() -> None:
    """The detail endpoint's real date wins over prose."""

    jobs = fetch(
        [
            listing(
                title=(
                    "Software Engineer, "
                    "New Grad"
                ),
                path="/job/a",
                posted="Posted Today",
            ),
        ]
    )

    assert jobs[0].posted_at == datetime(
        2026,
        9,
        4,
        tzinfo=timezone.utc,
    )


# ----------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------


def test_detail_fields_populate_the_job() -> None:
    jobs = fetch(
        [
            listing(
                title=(
                    "Software Engineer, "
                    "New Grad"
                ),
                path="/job/a",
            ),
        ]
    )

    job = jobs[0]

    assert job.source == "workday"

    assert job.company == "Acme"

    assert job.external_id == "/job/a"

    assert (
        job.description
        == "Build software in Python."
    )

    assert (
        job.location
        == "Seattle, WA; Austin, TX"
    )

    assert (
        job.requisition_id == "JR0042"
    )

    assert job.official_url.startswith(
        "https://"
    )


def test_pagination_collects_every_posting() -> None:
    postings = [
        listing(
            title=(
                "Software Engineer, "
                f"New Grad {index}"
            ),
            path=f"/job/{index}",
        )
        for index in range(
            45
        )
    ]

    jobs = fetch(
        postings
    )

    assert len(jobs) == 45

    assert len(
        {
            job.external_id
            for job in jobs
        }
    ) == 45


def test_duplicate_paths_are_collapsed() -> None:
    jobs = fetch(
        [
            listing(
                title="Software Engineer",
                path="/job/a",
            ),
            listing(
                title="Software Engineer",
                path="/job/a",
            ),
        ]
    )

    assert len(jobs) == 1


# ----------------------------------------------------------------------
# Detail-fetch economics
#
# Listing is cheap and detail is not, so the adapter must skip details
# for postings the gate already rejects on title alone.
# ----------------------------------------------------------------------


def test_predicate_skips_detail_for_rejected_titles() -> None:
    calls: list[str] = []

    jobs = fetch(
        [
            listing(
                title=(
                    "Software Engineer, "
                    "New Grad"
                ),
                path="/job/keep",
            ),
            listing(
                title=(
                    "Senior Staff Software "
                    "Engineer"
                ),
                path="/job/skip",
            ),
        ],
        detail_calls=calls,
        should_fetch_detail=(
            build_detail_predicate(
                company_name="Acme"
            )
        ),
    )

    # Both postings are still emitted: the snapshot is authoritative for
    # lifecycle, so omitting one would mark a live job closed.
    assert len(jobs) == 2

    assert len(calls) == 1

    kept = next(
        job
        for job in jobs
        if job.external_id == "/job/keep"
    )

    skipped = next(
        job
        for job in jobs
        if job.external_id == "/job/skip"
    )

    assert kept.description

    assert skipped.description == ""


def test_skipped_postings_are_still_rejected_downstream() -> None:
    """A shallow record must reach the same verdict as a full one."""

    from backend.app.intelligence.eligibility import (
        EligibilityStatus,
        evaluate_job,
    )

    jobs = fetch(
        [
            listing(
                title=(
                    "Senior Staff Software "
                    "Engineer"
                ),
                path="/job/skip",
            ),
        ],
        should_fetch_detail=(
            build_detail_predicate(
                company_name="Acme"
            )
        ),
    )

    assert (
        evaluate_job(
            jobs[0]
        ).status
        is EligibilityStatus.REJECT
    )


def test_detail_fetches_are_bounded() -> None:
    """One pathological tenant cannot hang a scheduler cycle."""

    calls: list[str] = []

    postings = [
        listing(
            title=(
                "Software Engineer, "
                f"New Grad {index}"
            ),
            path=f"/job/{index}",
        )
        for index in range(
            30
        )
    ]

    jobs = fetch(
        postings,
        detail_calls=calls,
        max_detail_fetches=5,
    )

    assert len(jobs) == 30

    assert len(calls) == 5


def test_page_limit_is_bounded() -> None:
    postings = [
        listing(
            title=f"Software Engineer {i}",
            path=f"/job/{i}",
        )
        for i in range(
            100
        )
    ]

    jobs = fetch(
        postings,
        max_pages=2,
    )

    assert len(jobs) == (
        2 * WORKDAY_PAGE_SIZE
    )


def test_no_predicate_fetches_every_detail() -> None:
    calls: list[str] = []

    fetch(
        [
            listing(
                title="Senior Engineer",
                path="/job/a",
            ),
        ],
        detail_calls=calls,
    )

    assert len(calls) == 1


def test_empty_tenant_returns_no_jobs() -> None:
    assert fetch(
        []
    ) == []
