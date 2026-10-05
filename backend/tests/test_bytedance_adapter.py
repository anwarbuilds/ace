"""ByteDance and TikTok, read from their own careers API.

139 passing roles -- 106 TikTok, 33 ByteDance, nearly all new-graduate
engineering -- reached ACE only through the Simplify feed, because
neither company's real board was read.
"""

from __future__ import annotations

import json

import httpx
import pytest

from backend.app.adapters.bytedance import (
    PAGE_SIZE,
    IncompleteByteDanceRead,
    build_location,
    fetch_bytedance_jobs,
)
from backend.app.intelligence.eligibility import (
    _is_us_location,
)


SAN_JOSE = {
    "code": "CT_1",
    "en_name": "San Jose",
    "parent": {
        "code": "ST_1",
        "en_name": "California",
        "parent": {
            "code": "CN_6",
            "en_name": "United States of America",
            "parent": None,
        },
    },
}

SINGAPORE = {
    "code": "CT_2",
    "en_name": "Singapore",
    "parent": {
        "code": "CN_25",
        "en_name": "Singapore",
        "parent": None,
    },
}


def posting(
    job_id: str,
    *,
    title: str = "Software Engineer Graduate (Backend) - 2027 Start",
    city: dict = SAN_JOSE,
    recruit_type: str = "Graduate",
) -> dict:
    return {
        "id": job_id,
        "code": f"A{job_id}",
        "title": title,
        "description": "Build the systems behind the feed.",
        "requirement": (
            "Minimum Qualifications\n"
            "- Final year or recent graduate in Computer Science."
        ),
        "recruit_type": {
            "en_name": recruit_type,
        },
        "city_info": city,
    }


def serve(
    pages: list[list[dict]],
    *,
    count: int | None = None,
    requests: list[httpx.Request] | None = None,
    code: int = 0,
) -> httpx.Client:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if requests is not None:
            requests.append(
                request
            )

        body = json.loads(
            request.content
        )

        index = body["offset"] // PAGE_SIZE

        page = (
            pages[index]
            if index < len(pages)
            else []
        )

        return httpx.Response(
            200,
            json={
                "code": code,
                "message": "ok",
                "data": {
                    "job_post_list": page,
                    "count": (
                        count
                        if count is not None
                        else sum(
                            map(
                                len,
                                pages,
                            )
                        )
                    ),
                },
            },
        )

    return httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )


def full_page(
    prefix: str,
) -> list[dict]:
    return [
        posting(
            f"{prefix}{index}"
        )
        for index in range(
            PAGE_SIZE
        )
    ]


def test_a_tiktok_posting_links_to_tiktoks_own_page() -> None:
    requests: list[httpx.Request] = []

    [job] = fetch_bytedance_jobs(
        source_account="tiktok",
        company_name="TikTok",
        client=serve(
            [[posting("7669773447288031493")]],
            requests=requests,
        ),
    )

    assert job.official_url == (
        "https://lifeattiktok.com/search/7669773447288031493"
    )

    assert job.company == "TikTok"

    assert requests[0].url.host == "api.lifeattiktok.com"

    assert requests[0].headers["website-path"] == "tiktok"


def test_a_bytedance_posting_links_to_bytedances_own_page() -> None:
    requests: list[httpx.Request] = []

    [job] = fetch_bytedance_jobs(
        source_account="bytedance",
        company_name="ByteDance",
        client=serve(
            [[posting("7670355647603984693")]],
            requests=requests,
        ),
    )

    assert job.official_url == (
        "https://jobs.bytedance.com/en/position/"
        "7670355647603984693/detail"
    )

    assert requests[0].url.host == "jobs.bytedance.com"

    assert requests[0].headers["website-path"] == "en"


def test_the_requirements_are_read_with_the_description() -> None:
    """Years of experience and work authorisation are stated in the
    requirements, which the gate's phrase rules must see."""

    [job] = fetch_bytedance_jobs(
        source_account="tiktok",
        company_name="TikTok",
        client=serve(
            [[posting("1")]],
        ),
    )

    assert "Build the systems" in job.description

    assert "recent graduate in Computer Science" in job.description


def test_the_location_is_one_the_gate_reads_correctly() -> None:
    assert build_location(
        SAN_JOSE
    ) == "San Jose, California, United States of America"

    assert _is_us_location(
        build_location(
            SAN_JOSE
        )
    )

    assert not _is_us_location(
        build_location(
            SINGAPORE
        )
    )


def test_every_page_is_read_until_the_reported_total() -> None:
    requests: list[httpx.Request] = []

    jobs = fetch_bytedance_jobs(
        source_account="tiktok",
        company_name="TikTok",
        client=serve(
            [
                full_page("a"),
                full_page("b"),
            ],
            requests=requests,
        ),
    )

    assert len(jobs) == 2 * PAGE_SIZE

    # The total was reached on a full page: no third request.
    assert len(requests) == 2


def test_a_portal_too_large_to_finish_is_refused_not_cut() -> None:
    with pytest.raises(
        IncompleteByteDanceRead,
    ):
        fetch_bytedance_jobs(
            source_account="tiktok",
            company_name="TikTok",
            client=serve(
                [
                    full_page(f"p{index}-")
                    for index in range(5)
                ],
            ),
            max_pages=3,
        )


def test_an_api_error_is_an_error_not_an_empty_board() -> None:
    """An empty snapshot would be refused anyway; an error code with
    an empty list must not be mistaken for a quiet day."""

    with pytest.raises(
        RuntimeError,
        match="code",
    ):
        fetch_bytedance_jobs(
            source_account="bytedance",
            company_name="ByteDance",
            client=serve(
                [[]],
                code=1001,
            ),
        )


def test_an_unknown_portal_is_refused() -> None:
    with pytest.raises(
        ValueError,
    ):
        fetch_bytedance_jobs(
            source_account="douyin",
            company_name="Douyin",
            client=serve(
                [[]],
            ),
        )


def test_the_recruit_type_is_carried_as_employment_type() -> None:
    [job] = fetch_bytedance_jobs(
        source_account="tiktok",
        company_name="TikTok",
        client=serve(
            [[posting("1", recruit_type="Regular")]],
        ),
    )

    assert job.employment_type == "regular"


def test_a_third_party_associate_is_a_contract_role() -> None:
    """Employed by a staffing vendor, placed at TikTok: not a hire the
    company can sponsor."""

    from backend.app.intelligence.eligibility import (
        EligibilityStatus,
        evaluate_job,
    )

    [job] = fetch_bytedance_jobs(
        source_account="tiktok",
        company_name="TikTok",
        client=serve(
            [[posting("1", recruit_type="Third-party Associate")]],
        ),
    )

    assert "contract" in job.employment_type

    assert evaluate_job(
        job
    ).status == EligibilityStatus.REJECT
