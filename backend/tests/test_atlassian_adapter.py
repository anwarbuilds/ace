"""Atlassian: the job list its own careers site loads, read whole."""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.atlassian import (
    canonical_job,
    fetch_atlassian_jobs,
)
from backend.app.adapters.http_cache import (
    CacheValidators,
)
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)


LISTING = {
    "id": "12345",
    "title": "Software Engineer, Early Career",
    "type": "Full-Time",
    "locations": [
        "San Francisco - United States - San Francisco, CA 94104 United States",
        "Remote - United States - Remote",
    ],
    "category": "Engineering",
    "overview": "<p>Working at Atlassian</p>",
    "responsibilities": "<ul><li><p>Build features in Java and React</p></li></ul>",
    "qualifications": "<ul><li><p>New graduates welcome. 0-2 years of experience.</p></li></ul>",
    "portalJobPost": {"updatedDate": "2026-10-07 03:33 PM"},
}


def test_a_listing_becomes_a_job_with_its_whole_description() -> None:
    job = canonical_job(
        LISTING
    )

    assert job.external_id == "12345"

    assert job.official_url == (
        "https://www.atlassian.com/company/careers/details/12345"
    )

    assert "United States" in job.location

    assert "Build features in Java and React" in job.description

    assert "0-2 years of experience" in job.description

    assert job.posted_at == datetime(
        2026,
        10,
        7,
        15,
        33,
        tzinfo=timezone.utc,
    )

    assert evaluate_job(
        job
    ).status == EligibilityStatus.PASS


def test_a_listing_outside_the_us_is_outside_the_us() -> None:
    job = canonical_job(
        {
            **LISTING,
            "locations": ["Bengaluru - India - Bengaluru, 560071 India"],
        }
    )

    assert (
        EligibilityReasonCode.OUTSIDE_US
        in evaluate_job(job).reason_codes
    )


def _client(
    status: int,
    body=None,
    headers=None,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json=body,
            headers=headers or {},
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
    )


def test_an_unchanged_list_downloads_nothing() -> None:
    jobs, unchanged, _validators = fetch_atlassian_jobs(
        client=_client(304),
        validators=CacheValidators(etag='W/"abc"'),
    )

    assert unchanged is True

    assert jobs == []


def test_a_read_list_carries_its_validator_for_next_time() -> None:
    jobs, unchanged, validators = fetch_atlassian_jobs(
        client=_client(200, [LISTING], {"ETag": 'W/"def"'}),
    )

    assert unchanged is False

    assert [job.external_id for job in jobs] == ["12345"]

    assert validators.etag == 'W/"def"'


def test_an_empty_list_is_never_every_posting_closing() -> None:
    with pytest.raises(ValueError):
        fetch_atlassian_jobs(
            client=_client(200, []),
        )
