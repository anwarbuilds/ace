"""Tests for the Eightfold PCSX adapter.

PCSX is the newer Eightfold product line Amdocs runs. It was found by
watching what a real browser sent to jobs.amdocs.com, because the
classic /api/apply/v2/jobs route answers with a 403 body reading
{"message": "Not authorized for PCSX"} -- the error the route's own
name comes from.
"""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.eightfold_pcsx import (
    _location_of,
    _posted_at,
    _to_canonical,
    _unwrap,
    fetch_eightfold_pcsx_jobs,
)


def wrapped(
    data: dict,
) -> dict:
    """Wrap a payload the way every PCSX response does."""

    return {
        "status": 200,
        "error": {
            "message": "",
            "body": "",
        },
        "data": data,
        "metadata": None,
    }


def position(
    *,
    ident: str = "1",
    name: str = "Software Engineer - Graduate",
    location: str = "USA-TX, Plano",
) -> dict:
    """Build one PCSX search result."""

    return {
        "id": ident,
        "name": name,
        "location": location,
        "displayJobId": 213264,
        "postedTs": 1788542653,
    }


def detail(
    *,
    description: str = "<p>Build software.</p>",
    standardized: list[str] | None = (
        None
    ),
    public_url: str = (
        "https://example.com/careers/"
        "job/1"
    ),
) -> dict:
    """Build one PCSX position_details response."""

    return {
        "jobDescription": description,
        "standardizedLocations": (
            standardized
            if standardized is not None
            else [
                "Plano, TX, US",
            ]
        ),
        "publicUrl": public_url,
        "displayJobId": 213264,
        "postedTs": 1788542653,
    }


def make_client(
    *,
    positions: list[dict],
    details: dict[str, dict],
    seen: list[str] | None = None,
) -> httpx.Client:
    """Build a client serving a scripted PCSX tenant.

    ``positions`` is the whole flat listing. The mock slices it by
    ``start``, matching the real loop's own bookkeeping, which advances
    ``start`` by however many items the previous response actually
    held rather than by a fixed page size.
    """

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
            "/search"
        ):
            start = int(
                request.url.params.get(
                    "start",
                    0,
                )
            )

            num = int(
                request.url.params.get(
                    "num",
                    50,
                )
            )

            page = positions[
                start:start + num
            ]

            return httpx.Response(
                200,
                json=wrapped(
                    {
                        "positions": page,
                        "count": len(
                            positions
                        ),
                    }
                ),
            )

        posting_id = request.url.params.get(
            "position_id"
        )

        if posting_id not in details:
            return httpx.Response(
                404,
                json={},
            )

        return httpx.Response(
            200,
            json=wrapped(
                details[posting_id]
            ),
        )

    return httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        ),
        base_url="https://example.com",
    )


# --- response envelope --------------------------------------------------


def test_unwrap_returns_the_data_object() -> None:
    assert _unwrap(
        wrapped(
            {
                "positions": [],
            }
        )
    ) == {
        "positions": [],
    }


def test_unwrap_survives_a_malformed_response() -> None:
    """One tenant answering strangely must not take the whole poll
    down."""

    assert _unwrap(
        {
            "status": 500,
        }
    ) == {}

    assert _unwrap(
        [
            1,
            2,
        ]
    ) == {}

    assert _unwrap(
        None
    ) == {}


# --- location -------------------------------------------------------


def test_standardized_location_is_preferred() -> None:
    """Cleaner than the search response's raw internal string."""

    assert _location_of(
        {
            "location": (
                "USA-TX, Plano, 2900 "
                "W Plano Pkwy (CU)"
            ),
        },
        {
            "standardizedLocations": [
                "Plano, TX, US",
            ],
        },
    ) == "Plano, TX, US"


def test_falls_back_to_the_raw_location_with_no_detail() -> None:
    """A posting whose detail was skipped by the predicate still needs
    a location the gate can read."""

    assert _location_of(
        {
            "location": "USA-TX, Plano",
        },
        {},
    ) == "USA-TX, Plano"


# --- posted date ------------------------------------------------------


def test_posted_ts_is_read_as_utc() -> None:
    assert _posted_at(
        {
            "postedTs": 1788542653,
        }
    ) == datetime.fromtimestamp(
        1788542653,
        tz=timezone.utc,
    )


def test_an_epoch_stamp_is_not_trusted() -> None:
    """0 means "no timestamp", not 1970."""

    assert _posted_at(
        {
            "postedTs": 0,
        }
    ) is None


def test_a_missing_stamp_is_none() -> None:
    assert _posted_at(
        {}
    ) is None


# --- normalization ------------------------------------------------------


def test_a_posting_with_detail_carries_its_description_and_url() -> (
    None
):
    canonical = _to_canonical(
        position(),
        detail=detail(),
        company="Amdocs",
        host="jobs.amdocs.com",
    )

    assert canonical.source == "eightfold_pcsx"

    assert (
        canonical.title
        == "Software Engineer - Graduate"
    )

    assert (
        canonical.location
        == "Plano, TX, US"
    )

    assert "Build software." in (
        canonical.description
    )

    assert (
        canonical.official_url
        == "https://example.com/careers/job/1"
    )

    assert canonical.requisition_id == "213264"


def test_a_posting_with_no_detail_still_carries_a_location() -> None:
    """A posting the predicate skipped is not dropped: the gate marks
    it unverified, but the snapshot still says it exists."""

    canonical = _to_canonical(
        position(),
        detail=None,
        company="Amdocs",
        host="jobs.amdocs.com",
    )

    assert canonical.title == (
        "Software Engineer - Graduate"
    )

    assert canonical.location == (
        "USA-TX, Plano"
    )

    assert canonical.description == ""


# --- the full fetch -----------------------------------------------------


def test_fetch_pages_through_search_results() -> None:
    positions = [
        position(
            ident="1",
        ),
        position(
            ident="2",
            name=(
                "Software Engineer"
            ),
        ),
    ]

    client = make_client(
        positions=positions,
        details={
            "1": detail(),
            "2": detail(),
        },
    )

    jobs = fetch_eightfold_pcsx_jobs(
        "example.com",
        "Amdocs",
        domain="amdocs.com",
        client=client,
    )

    assert {
        job.external_id
        for job in jobs
    } == {
        "1",
        "2",
    }


def test_detail_is_only_fetched_for_accepted_titles() -> None:
    """Fetching every posting's detail would be hundreds of requests
    against someone else's server to learn nothing the title did not
    already settle."""

    positions = [
        position(
            ident="1",
            name="Senior Software Engineer",
        ),
        position(
            ident="2",
            name="Software Engineer - Graduate",
        ),
    ]

    calls: list[str] = []

    client = make_client(
        positions=positions,
        details={
            "1": detail(),
            "2": detail(),
        },
        seen=calls,
    )

    jobs = fetch_eightfold_pcsx_jobs(
        "example.com",
        "Amdocs",
        domain="amdocs.com",
        client=client,
        should_fetch_detail=(
            lambda title: "senior"
            not in title.lower()
        ),
    )

    detail_calls = [
        call
        for call in calls
        if "position_details" in call
    ]

    assert len(
        detail_calls
    ) == 1

    assert "position_id=2" in (
        detail_calls[0]
    )

    by_id = {
        job.external_id: job
        for job in jobs
    }

    assert by_id["1"].description == ""

    assert "Build software." in (
        by_id["2"].description
    )


def test_a_broken_detail_call_does_not_fail_the_whole_poll() -> None:
    positions = [
        position(
            ident="1",
        ),
    ]

    client = make_client(
        positions=positions,
        details={},
    )

    jobs = fetch_eightfold_pcsx_jobs(
        "example.com",
        "Amdocs",
        domain="amdocs.com",
        client=client,
    )

    assert len(
        jobs
    ) == 1

    assert jobs[0].description == ""


def test_an_empty_host_is_refused() -> None:
    with pytest.raises(
        ValueError,
    ):
        fetch_eightfold_pcsx_jobs(
            "  ",
            "Amdocs",
        )


def test_an_empty_company_is_refused() -> None:
    with pytest.raises(
        ValueError,
    ):
        fetch_eightfold_pcsx_jobs(
            "example.com",
            "  ",
        )
