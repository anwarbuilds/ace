"""Tests for ACE SmartRecruiters Posting API adapter."""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.smartrecruiters import (
    fetch_smartrecruiters_jobs,
)


def test_fetches_and_normalizes_smartrecruiters_posting() -> None:
    requests: list[
        httpx.Request
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(
            request
        )

        if request.url.path.endswith(
            "/postings"
        ):
            return httpx.Response(
                200,
                json={
                    "offset": 0,
                    "limit": 100,
                    "totalFound": 1,
                    "content": [
                        {
                            "id": "12345",
                            "uuid": (
                                "aaaaaaaa-bbbb-cccc-"
                                "dddd-eeeeeeeeeeee"
                            ),
                            "name": (
                                "Software Engineer"
                            ),
                            "refNumber": "REQ-123",
                            "releasedDate": (
                                "2026-09-03T"
                                "14:30:00.000Z"
                            ),
                        }
                    ],
                },
            )

        return httpx.Response(
            200,
            json={
                "id": "12345",
                "uuid": (
                    "aaaaaaaa-bbbb-cccc-"
                    "dddd-eeeeeeeeeeee"
                ),
                "name": (
                    "Software Engineer"
                ),
                "company": {
                    "identifier": (
                        "ExampleCompany"
                    ),
                    "name": (
                        "Example Company"
                    ),
                },
                "location": {
                    "city": (
                        "San Francisco"
                    ),
                    "region": "CA",
                    "country": "us",
                    "remote": True,
                },
                "releasedDate": (
                    "2026-09-03T"
                    "14:30:00.000Z"
                ),
                "postingUrl": (
                    "https://"
                    "jobs.smartrecruiters.com/"
                    "ExampleCompany/"
                    "12345-software-engineer"
                ),
                "jobAd": {
                    "sections": {
                        "companyDescription": {
                            "title": (
                                "Company Description"
                            ),
                            "text": (
                                "We have been operating "
                                "for 20 years."
                            ),
                        },
                        "jobDescription": {
                            "title": (
                                "Job Description"
                            ),
                            "text": (
                                "<p>Build APIs "
                                "and distributed "
                                "systems.</p>"
                            ),
                        },
                        "qualifications": {
                            "title": (
                                "Qualifications"
                            ),
                            "text": (
                                "<p>0-2 years "
                                "experience.</p>"
                            ),
                        },
                        "additionalInformation": {
                            "title": (
                                "Additional Information"
                            ),
                            "text": (
                                "Excellent benefits."
                            ),
                        },
                    },
                },
                "active": True,
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:
        jobs = (
            fetch_smartrecruiters_jobs(
                "ExampleCompany",
                "Example Company",
                client=client,
            )
        )

    assert len(
        jobs
    ) == 1

    job = jobs[
        0
    ]

    assert (
        job.source
        == "smartrecruiters"
    )

    assert (
        job.company
        == "Example Company"
    )

    assert (
        job.external_id
        == (
            "aaaaaaaa-bbbb-cccc-"
            "dddd-eeeeeeeeeeee"
        )
    )

    assert (
        job.requisition_id
        == "REQ-123"
    )

    assert (
        job.title
        == "Software Engineer"
    )

    assert (
        job.location
        == (
            "Remote | "
            "San Francisco, CA, US"
        )
    )

    assert (
        "Build APIs"
        in job.description
    )

    assert (
        "0-2 years experience"
        in job.description
    )

    assert (
        "Excellent benefits"
        in job.description
    )

    assert (
        "20 years"
        not in job.description
    )

    assert (
        job.official_url
        == (
            "https://"
            "jobs.smartrecruiters.com/"
            "ExampleCompany/"
            "12345-software-engineer"
        )
    )

    assert (
        job.posted_at
        == datetime(
            2026,
            9,
            3,
            14,
            30,
            tzinfo=timezone.utc,
        )
    )

    assert len(
        requests
    ) == 2


def test_paginates_all_postings() -> None:
    observed_offsets: list[
        int
    ] = []

    detail_ids: list[
        str
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path.endswith(
            "/postings"
        ):
            offset = int(
                request.url.params[
                    "offset"
                ]
            )

            observed_offsets.append(
                offset
            )

            posting_number = (
                offset + 1
            )

            return httpx.Response(
                200,
                json={
                    "offset": offset,
                    "limit": 1,
                    "totalFound": 2,
                    "content": [
                        {
                            "id": str(
                                posting_number
                            ),
                            "uuid": (
                                f"uuid-{posting_number}"
                            ),
                            "name": (
                                f"Job {posting_number}"
                            ),
                        }
                    ],
                },
            )

        posting_id = (
            request.url.path
            .rstrip("/")
            .split("/")[-1]
        )

        detail_ids.append(
            posting_id
        )

        return httpx.Response(
            200,
            json={
                "id": posting_id,
                "uuid": (
                    f"uuid-{posting_id}"
                ),
                "name": (
                    f"Job {posting_id}"
                ),
                "location": {
                    "city": "New York",
                    "region": "NY",
                    "country": "us",
                    "remote": False,
                },
                "postingUrl": (
                    "https://"
                    "jobs.smartrecruiters.com/"
                    "ExampleCompany/"
                    f"{posting_id}-job"
                ),
                "jobAd": {
                    "sections": {
                        "jobDescription": {
                            "text": (
                                "Build software."
                            ),
                        },
                    },
                },
                "active": True,
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:
        jobs = (
            fetch_smartrecruiters_jobs(
                "ExampleCompany",
                "Example Company",
                client=client,
            )
        )

    assert observed_offsets == [
        0,
        1,
    ]

    assert detail_ids == [
        "1",
        "2",
    ]

    assert [
        job.external_id
        for job in jobs
    ] == [
        "uuid-1",
        "uuid-2",
    ]


def test_detail_http_failure_is_not_silently_swallowed() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path.endswith(
            "/postings"
        ):
            return httpx.Response(
                200,
                json={
                    "offset": 0,
                    "limit": 100,
                    "totalFound": 1,
                    "content": [
                        {
                            "id": "123",
                            "name": (
                                "Software Engineer"
                            ),
                        }
                    ],
                },
            )

        return httpx.Response(
            500,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport
    ) as client:
        with pytest.raises(
            httpx.HTTPStatusError
        ):
            fetch_smartrecruiters_jobs(
                "ExampleCompany",
                "Example Company",
                client=client,
            )


def test_list_http_failure_is_not_silently_swallowed() -> None:
    transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(
                500
            )
        )
    )

    with httpx.Client(
        transport=transport
    ) as client:
        with pytest.raises(
            httpx.HTTPStatusError
        ):
            fetch_smartrecruiters_jobs(
                "ExampleCompany",
                "Example Company",
                client=client,
            )


def test_rejects_empty_company_identifier() -> None:
    with pytest.raises(
        ValueError,
        match="company_identifier",
    ):
        fetch_smartrecruiters_jobs(
            "   ",
            "Example Company",
        )
