"""Shopify's careers page, and the React Router data it is rendered from.

Shopify's postings live in an Ashby board ACE cannot name; its careers
page carries every listed posting. The fixtures are encoded the way the
page encodes them, trimmed to the fields the reader uses.
"""

from __future__ import annotations

import json

import httpx
import pytest

from backend.app.adapters.shopify import (
    fetch_shopify_jobs,
    parse_careers_page,
    parse_posting_page,
)
from backend.app.adapters.turbo_stream import (
    loader_data,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)


def turbo_page(
    data: dict,
) -> str:
    """A page whose loader data is written as turbo-stream writes it:
    every value once, everything else by its index."""

    values: list = []

    def encode(
        value: object,
    ) -> int:
        if value is None:
            return -5

        index = len(values)
        values.append(None)

        if isinstance(value, dict):
            encoded = {}

            for key, item in value.items():
                key_index = len(values)
                values.append(key)
                encoded[f"_{key_index}"] = encode(item)

            values[index] = encoded
        elif isinstance(value, list):
            values[index] = [encode(item) for item in value]
        else:
            values[index] = value

        return index

    encode(
        {"loaderData": data}
    )

    return (
        "<html><body><script>"
        "window.__reactRouterContext.streamController.enqueue("
        + json.dumps(json.dumps(values) + "\n")
        + ");</script></body></html>"
    )


AMERICAS = {
    "id": "loc-americas",
    "name": "Americas",
    "externalName": None,
    "isRemote": True,
    "address": {"postalAddress": {"addressCountry": "Americas"}},
}

TORONTO = {
    "id": "loc-toronto",
    "name": "Toronto",
    "externalName": None,
    "isRemote": False,
    "address": {
        "postalAddress": {
            "addressLocality": "Toronto",
            "addressRegion": "Ontario",
            "addressCountry": "Canada",
        }
    },
}


def posting(
    posting_id: str,
    title: str,
    *,
    primary: str = "loc-americas",
    employment: str = "FullTime",
) -> dict:
    return {
        "jobPosting": {
            "id": posting_id,
            "title": title,
            "isListed": True,
            "locationName": "Americas",
            "locationIds": {
                "primaryLocationId": primary,
                "secondaryLocationIds": [],
            },
            "employmentType": employment,
            "publishedDate": "2026-09-22",
            "updatedAt": "2026-09-23T10:00:00.000Z",
        }
    }


def careers_page(
    *postings: dict,
) -> str:
    return turbo_page(
        {
            "root": {},
            "($locale)/careers": {
                "atsLocations": [AMERICAS, TORONTO],
                "jobPostingsWithJobs": list(postings),
            },
        }
    )


def posting_page(
    description: str = (
        "Build the mobile apps merchants run their stores on. "
        "2+ years of experience with React Native."
    ),
) -> str:
    return turbo_page(
        {
            "($locale)/careers/$posting": {
                "jobPosting": {"descriptionPlain": description},
            }
        }
    )


def site(
    listing: str,
    *,
    detail: str | None = None,
):
    asked: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            request.url.path
        )

        if request.url.path == "/careers":
            return httpx.Response(
                200,
                text=listing,
            )

        return httpx.Response(
            200,
            text=detail or posting_page(),
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler),
    ), asked


def test_the_stream_decodes_to_the_page_s_data() -> None:
    assert loader_data(
        turbo_page(
            {"route": {"names": ["a", "b"], "missing": None}}
        )
    ) == {
        "route": {"names": ["a", "b"], "missing": None},
    }


def test_a_page_without_the_stream_is_an_error_not_an_empty_board() -> None:
    with pytest.raises(ValueError):
        loader_data(
            "<html></html>"
        )


def test_every_listed_posting_is_read_with_its_places() -> None:
    postings = parse_careers_page(
        careers_page(
            posting("p-1", "Software Engineers, Mobile"),
            posting("p-2", "Director, Partnerships", primary="loc-toronto"),
        )
    )

    assert [
        (item["id"], item["location"])
        for item in postings
    ] == [
        ("p-1", "Remote - Americas"),
        ("p-2", "Toronto, Ontario, Canada"),
    ]


def test_a_remote_americas_engineer_passes_the_gate() -> None:
    client, _asked = site(
        careers_page(
            posting("p-1", "Software Engineers, Mobile"),
        )
    )

    jobs = fetch_shopify_jobs(
        client=client,
        detail_pause_seconds=0,
    )

    assert jobs[0].official_url == (
        "https://www.shopify.com/careers/software-engineers-mobile_p-1"
    )

    assert "React Native" in jobs[0].description

    assert evaluate_job(
        jobs[0]
    ).status == EligibilityStatus.PASS


def test_a_contract_posting_is_a_contract() -> None:
    client, _asked = site(
        careers_page(
            posting("p-1", "Software Engineer", employment="Contract"),
        )
    )

    jobs = fetch_shopify_jobs(
        client=client,
        detail_pause_seconds=0,
    )

    assert evaluate_job(
        jobs[0]
    ).status == EligibilityStatus.REJECT


def test_a_posting_already_held_and_a_rejected_title_are_not_read() -> None:
    client, asked = site(
        careers_page(
            posting("p-1", "Software Engineers"),
            posting("p-2", "Director, Partnerships"),
            posting("p-3", "Software Engineers, Frontend"),
        )
    )

    jobs = fetch_shopify_jobs(
        client=client,
        should_fetch_detail=lambda title: "Director" not in title,
        known={"p-1": ("Remote - Americas", "What ACE read before.")},
        detail_pause_seconds=0,
    )

    assert asked == [
        "/careers",
        "/careers/software-engineers-frontend_p-3",
    ]

    assert jobs[0].description == "What ACE read before."


def test_an_empty_careers_page_is_never_every_posting_closing() -> None:
    client, _asked = site(
        careers_page()
    )

    with pytest.raises(ValueError):
        fetch_shopify_jobs(
            client=client,
            detail_pause_seconds=0,
        )


def test_the_posting_page_s_description_is_read() -> None:
    assert parse_posting_page(
        posting_page("Ruby on Rails at scale.")
    ) == "Ruby on Rails at scale."
