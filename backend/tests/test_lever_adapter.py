"""Tests for ACE Lever Postings API adapter."""

import httpx
import pytest

from backend.app.adapters.lever import (
    fetch_lever_jobs,
)


def response_for(
    url: str,
    payload,
    *,
    status_code: int = 200,
) -> httpx.Response:
    request = httpx.Request(
        "GET",
        url,
    )

    return httpx.Response(
        status_code,
        request=request,
        json=payload,
    )


def test_global_lever_board_is_normalized(
    monkeypatch,
) -> None:
    calls = []

    payload = [
        {
            "id": "posting-1",
            "text": "Software Engineer I",
            "categories": {
                "location": "New York, NY",
                "team": "Engineering",
            },
            "descriptionPlain": (
                "Build production software."
            ),
            "lists": [
                {
                    "text": "Requirements",
                    "content": (
                        "<li>0-2 years of "
                        "experience</li>"
                    ),
                },
            ],
            "additionalPlain": (
                "Candidates requiring "
                "sponsorship may apply."
            ),
            "hostedUrl": (
                "https://jobs.lever.co/"
                "examplecompany/posting-1"
            ),
            "workplaceType": "hybrid",
        },
    ]

    def fake_get(
        url,
        **kwargs,
    ):
        calls.append(
            (
                url,
                kwargs,
            )
        )

        return response_for(
            url,
            payload,
        )

    monkeypatch.setattr(
        httpx,
        "get",
        fake_get,
    )

    jobs = fetch_lever_jobs(
        source_account=(
            "examplecompany"
        ),
        company_name=(
            "Example Company"
        ),
        source_host=(
            "jobs.lever.co"
        ),
    )

    assert len(
        jobs
    ) == 1

    job = jobs[0]

    assert job.source == "lever"

    assert (
        job.company
        == "Example Company"
    )

    assert (
        job.external_id
        == "posting-1"
    )

    assert (
        job.title
        == "Software Engineer I"
    )

    assert (
        job.location
        == "New York, NY"
    )

    assert (
        "Build production software."
        in job.description
    )

    assert (
        "0-2 years of experience"
        in job.description
    )

    assert (
        "sponsorship may apply"
        in job.description
    )

    assert (
        job.official_url
        == (
            "https://jobs.lever.co/"
            "examplecompany/posting-1"
        )
    )

    assert job.posted_at is None
    assert job.updated_at is None

    assert len(
        calls
    ) == 1

    url, kwargs = calls[0]

    assert (
        url
        == (
            "https://api.lever.co/"
            "v0/postings/"
            "examplecompany"
        )
    )

    assert (
        kwargs["params"]["mode"]
        == "json"
    )

    assert (
        kwargs["params"]["skip"]
        == 0
    )


def test_eu_lever_board_uses_eu_api(
    monkeypatch,
) -> None:
    observed_urls = []

    def fake_get(
        url,
        **kwargs,
    ):
        del kwargs

        observed_urls.append(
            url
        )

        return response_for(
            url,
            [],
        )

    monkeypatch.setattr(
        httpx,
        "get",
        fake_get,
    )

    jobs = fetch_lever_jobs(
        source_account="example-eu",
        company_name="Example EU",
        source_host=(
            "jobs.eu.lever.co"
        ),
    )

    assert jobs == []

    assert observed_urls == [
        (
            "https://api.eu.lever.co/"
            "v0/postings/example-eu"
        )
    ]


def test_lever_pagination_fetches_all_pages(
    monkeypatch,
) -> None:
    skips = []

    def posting(
        number: int,
    ) -> dict:
        return {
            "id": f"id-{number}",
            "text": (
                f"Engineer {number}"
            ),
            "categories": {
                "location": "Remote",
            },
            "descriptionPlain": (
                "Build software."
            ),
            "hostedUrl": (
                "https://jobs.lever.co/"
                "example/"
                f"id-{number}"
            ),
        }

    def fake_get(
        url,
        **kwargs,
    ):
        skip = (
            kwargs[
                "params"
            ][
                "skip"
            ]
        )

        skips.append(
            skip
        )

        if skip == 0:
            payload = [
                posting(1),
                posting(2),
            ]

        elif skip == 2:
            payload = [
                posting(3),
            ]

        else:
            payload = []

        return response_for(
            url,
            payload,
        )

    monkeypatch.setattr(
        httpx,
        "get",
        fake_get,
    )

    jobs = fetch_lever_jobs(
        source_account="example",
        company_name="Example",
        source_host="jobs.lever.co",
        page_size=2,
    )

    assert [
        job.external_id
        for job in jobs
    ] == [
        "id-1",
        "id-2",
        "id-3",
    ]

    assert skips == [
        0,
        2,
    ]


def test_remote_workplace_is_location_fallback(
    monkeypatch,
) -> None:
    payload = [
        {
            "id": "remote-1",
            "text": "Backend Engineer",
            "categories": {},
            "descriptionPlain": (
                "Build APIs."
            ),
            "hostedUrl": (
                "https://jobs.lever.co/"
                "example/remote-1"
            ),
            "workplaceType": "remote",
        },
    ]

    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: (
            response_for(
                url,
                payload,
            )
        ),
    )

    jobs = fetch_lever_jobs(
        source_account="example",
        company_name="Example",
        source_host="jobs.lever.co",
    )

    assert (
        jobs[0].location
        == "Remote"
    )


def test_unknown_lever_host_is_rejected(
    monkeypatch,
) -> None:
    def should_not_call(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "HTTP must not be called."
        )

    monkeypatch.setattr(
        httpx,
        "get",
        should_not_call,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported Lever "
            "source_host"
        ),
    ):
        fetch_lever_jobs(
            source_account="example",
            company_name="Example",
            source_host=(
                "jobs.example.com"
            ),
        )


def test_missing_lever_host_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "source_host is required"
        ),
    ):
        fetch_lever_jobs(
            source_account="example",
            company_name="Example",
            source_host=None,
        )


def test_http_failure_is_not_hidden(
    monkeypatch,
) -> None:
    def fake_get(
        url,
        **kwargs,
    ):
        del kwargs

        return response_for(
            url,
            {
                "error": "not found",
            },
            status_code=404,
        )

    monkeypatch.setattr(
        httpx,
        "get",
        fake_get,
    )

    with pytest.raises(
        httpx.HTTPStatusError
    ):
        fetch_lever_jobs(
            source_account="missing",
            company_name="Missing",
            source_host="jobs.lever.co",
        )
