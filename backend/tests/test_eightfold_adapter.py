"""Tests for the Eightfold ATS adapter.

Eightfold splits a posting across two calls: a search that carries no
description, and a per-posting detail that does. Most of what matters
here is that split behaving safely, because the obvious optimisation
(only return postings worth reading) would silently close every job it
skipped.
"""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.eightfold import (
    _clean_html,
    _location_of,
    _updated_at,
    fetch_eightfold_jobs,
)


def position(
    *,
    ident: str = "1",
    name: str = "Software Engineer",
    location: str = (
        "Los Gatos,California,"
        "United States of America"
    ),
) -> dict:
    """Build one Eightfold search result."""

    return {
        "id": ident,
        "name": name,
        "location": location,
        "display_job_id": f"REQ{ident}",
        "canonicalPositionUrl": (
            "https://example.com/careers/"
            f"job/{ident}"
        ),
        "t_update": 1788393600,
        "job_description": "",
    }


def make_client(
    *,
    pages: list[list[dict]],
    details: dict[str, str],
    seen: list[str] | None = None,
) -> httpx.Client:
    """Build a client serving a scripted Eightfold tenant."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if seen is not None:
            seen.append(
                str(
                    request.url
                )
            )

        path = request.url.path

        if path.endswith(
            "/jobs"
        ):
            start = int(
                request.url.params.get(
                    "start",
                    0,
                )
            )

            index = start // 100

            page = (
                pages[index]
                if index < len(pages)
                else []
            )

            total = sum(
                len(p)
                for p in pages
            )

            return httpx.Response(
                200,
                json={
                    "positions": page,
                    "count": total,
                },
            )

        posting_id = path.rsplit(
            "/",
            1,
        )[-1]

        if posting_id not in details:
            return httpx.Response(
                404,
                json={},
            )

        return httpx.Response(
            200,
            json={
                "job_description": (
                    details[posting_id]
                ),
            },
        )

    return httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        ),
        base_url="https://example.com",
    )


def test_locations_are_made_readable() -> None:
    """Eightfold ships comma-joined locations with no spaces.

    Left alone the gate reads the whole run as one unknown token and
    cannot tell a US posting from a foreign one.
    """

    assert _location_of(
        {
            "location": (
                "Los Gatos,California,"
                "United States of America"
            ),
        }
    ) == (
        "Los Gatos, California, "
        "United States of America"
    )


def test_location_falls_back_to_the_list() -> None:
    assert _location_of(
        {
            "location": "",
            "locations": [
                "Remote,United States",
            ],
        }
    ) == "Remote, United States"


def test_html_is_reduced_to_prose() -> None:
    """The gate reads descriptions, so markup must not reach its rules."""

    text = _clean_html(
        "<p>Must be a U.S. citizen.</p>"
        "<ul><li>5+ years</li></ul>"
    )

    assert "<" not in text

    assert "U.S. citizen" in text

    assert "5+ years" in text


def test_update_stamp_is_read_as_utc() -> None:
    assert _updated_at(
        {
            "t_update": 1788393600,
        }
    ) == datetime.fromtimestamp(
        1788393600,
        tz=timezone.utc,
    )


def test_unreadable_stamp_is_dropped_not_guessed() -> None:
    assert _updated_at(
        {
            "t_update": "sometime",
        }
    ) is None


def test_every_posting_is_returned_even_when_detail_is_skipped() -> None:
    """The predicate saves requests; it must not shrink the snapshot.

    The snapshot is authoritative for lifecycle, so a posting missing
    from it reads as closed. Skipping its description must never remove
    it.
    """

    client = make_client(
        pages=[
            [
                position(
                    ident="1",
                    name="Software Engineer",
                ),
                position(
                    ident="2",
                    name="Senior Staff Engineer",
                ),
            ],
        ],
        details={
            "1": "<p>Build things.</p>",
            "2": "<p>Lead things.</p>",
        },
    )

    jobs = fetch_eightfold_jobs(
        "example.com",
        "Netflix",
        domain="netflix.com",
        client=client,
        should_fetch_detail=(
            lambda title: "Senior"
            not in title
        ),
    )

    assert len(
        jobs
    ) == 2

    by_id = {
        job.external_id: job
        for job in jobs
    }

    assert (
        by_id["1"].description
        == "Build things."
    )

    # Present, but unread, which the gate treats as unverified.
    assert (
        by_id["2"].description == ""
    )


def test_only_accepted_titles_cost_a_detail_request() -> None:
    """The saving is the whole point: 79 of 501 on the live tenant."""

    seen: list[str] = []

    client = make_client(
        pages=[
            [
                position(
                    ident=str(
                        index
                    ),
                    name=(
                        "Software Engineer"
                        if index < 2
                        else "Chef"
                    ),
                )
                for index in range(
                    5
                )
            ],
        ],
        details={
            str(
                index
            ): "<p>Text.</p>"
            for index in range(
                5
            )
        },
        seen=seen,
    )

    fetch_eightfold_jobs(
        "example.com",
        "Netflix",
        domain="netflix.com",
        client=client,
        should_fetch_detail=(
            lambda title: title
            == "Software Engineer"
        ),
    )

    detail_calls = [
        url
        for url in seen
        if "/jobs/" in url
    ]

    assert len(
        detail_calls
    ) == 2


def test_paging_collects_every_posting() -> None:
    client = make_client(
        pages=[
            [
                position(
                    ident=str(
                        index
                    )
                )
                for index in range(
                    100
                )
            ],
            [
                position(
                    ident=str(
                        100 + index
                    )
                )
                for index in range(
                    7
                )
            ],
        ],
        details={},
    )

    jobs = fetch_eightfold_jobs(
        "example.com",
        "Netflix",
        domain="netflix.com",
        client=client,
        should_fetch_detail=(
            lambda title: False
        ),
    )

    assert len(
        jobs
    ) == 107


def test_one_unreadable_detail_does_not_fail_the_poll() -> None:
    """A single bad posting must not close an entire employer."""

    client = make_client(
        pages=[
            [
                position(
                    ident="1"
                ),
                position(
                    ident="2"
                ),
            ],
        ],
        details={
            "1": "<p>Fine.</p>",
        },
    )

    jobs = fetch_eightfold_jobs(
        "example.com",
        "Netflix",
        domain="netflix.com",
        client=client,
    )

    assert len(
        jobs
    ) == 2

    assert (
        sorted(
            job.description
            for job in jobs
        )
        == [
            "",
            "Fine.",
        ]
    )


def test_postings_without_an_identity_are_dropped() -> None:
    """A posting with no id cannot be tracked across polls."""

    client = make_client(
        pages=[
            [
                position(
                    ident="1"
                ),
                {
                    "name": "Ghost",
                },
            ],
        ],
        details={
            "1": "<p>Fine.</p>",
        },
    )

    jobs = fetch_eightfold_jobs(
        "example.com",
        "Netflix",
        domain="netflix.com",
        client=client,
    )

    assert len(
        jobs
    ) == 1


@pytest.mark.parametrize(
    "host,company",
    [
        ("", "Netflix"),
        ("example.com", ""),
    ],
)
def test_empty_configuration_is_refused(
    host,
    company,
) -> None:
    with pytest.raises(
        ValueError
    ):
        fetch_eightfold_jobs(
            host,
            company,
        )
