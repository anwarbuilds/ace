"""Tests for the Adzuna aggregator adapter.

Company exclusion lives one layer up, in the dispatcher, because it
needs a database read and every other adapter is a pure HTTP client
with none. What belongs here is the HTTP shape: paging, truncation,
deduplication across query terms, and refusing to fabricate a job from
a record missing what a real one cannot be missing.
"""

from datetime import (
    datetime,
    timezone,
)

import httpx
import pytest

from backend.app.adapters.adzuna import (
    _to_canonical,
    fetch_adzuna_jobs,
)


def posting(
    *,
    ident: str = "1",
    title: str = "Software Engineer - New Grad",
    company: str = "Example Corp",
    created: str = "2026-09-06T06:49:38Z",
) -> dict:
    """Build one Adzuna search result."""

    return {
        "id": ident,
        "title": title,
        "company": {
            "display_name": company,
        },
        "location": {
            "display_name": (
                "San Francisco, California"
            ),
        },
        "description": (
            "Build software that matters. "
            "0-2 years of experience."
        ),
        "redirect_url": (
            "https://www.adzuna.com"
            f"/details/{ident}"
        ),
        "created": created,
    }


def make_client(
    *,
    results_by_query: dict[str, list[dict]],
    seen: list[str] | None = None,
) -> httpx.Client:
    """Build a client serving a scripted Adzuna search."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if seen is not None:
            seen.append(
                str(
                    request.url
                )
            )

        query = request.url.params.get(
            "what",
            "",
        )

        page = int(
            request.url.path.rsplit(
                "/",
                1,
            )[-1]
        )

        all_results = (
            results_by_query.get(
                query,
                [],
            )
        )

        page_size = 50

        start = (
            page - 1
        ) * page_size

        page_results = all_results[
            start:start + page_size
        ]

        return httpx.Response(
            200,
            json={
                "count": len(
                    all_results
                ),
                "results": page_results,
            },
        )

    return httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        ),
    )


# --- normalization -------------------------------------------------


def test_contract_type_is_carried_as_employment_type() -> None:
    """A real Vestwell posting and a real T-Mobile posting both stated
    "contract" through this field, with nothing in the title or
    description saying so."""

    record = posting()

    record["contract_type"] = "contract"

    canonical = _to_canonical(
        record
    )

    assert (
        canonical.employment_type
        == "contract"
    )


def test_an_unstated_contract_type_is_none_not_full_time() -> None:
    """Most postings never carry this field at all. Treated as
    unknown, never as an assumption either way."""

    canonical = _to_canonical(
        posting()
    )

    assert (
        canonical.employment_type
        is None
    )


def test_a_complete_posting_normalizes() -> None:
    canonical = _to_canonical(
        posting()
    )

    assert canonical is not None

    assert canonical.source == "adzuna"

    assert (
        canonical.company
        == "Example Corp"
    )

    assert (
        canonical.title
        == "Software Engineer - New Grad"
    )

    assert (
        canonical.location
        == "San Francisco, California"
    )

    assert (
        canonical.official_url
        == "https://www.adzuna.com/details/1"
    )

    assert canonical.posted_at == (
        datetime(
            2026,
            9,
            6,
            6,
            49,
            38,
            tzinfo=timezone.utc,
        )
    )


def test_a_posting_with_no_company_is_dropped() -> None:
    """A fabricated company name is worse than a missing job."""

    record = posting()

    record["company"] = {}

    assert _to_canonical(
        record
    ) is None


def test_a_posting_with_no_url_is_dropped() -> None:
    record = posting()

    record["redirect_url"] = ""

    assert _to_canonical(
        record
    ) is None


def test_a_posting_with_no_created_date_still_normalizes() -> None:
    """The date is the least essential field here; a job without one
    is still a real job."""

    record = posting()

    del record[
        "created"
    ]

    canonical = _to_canonical(
        record
    )

    assert canonical is not None

    assert canonical.posted_at is None


def test_a_malformed_created_date_does_not_raise() -> None:
    record = posting()

    record["created"] = "not a date"

    canonical = _to_canonical(
        record
    )

    assert canonical is not None

    assert canonical.posted_at is None


# --- the full fetch --------------------------------------------------


def test_results_across_query_terms_are_deduplicated() -> None:
    """A posting matching two search terms is one posting, not two."""

    shared = posting(
        ident="1",
    )

    client = make_client(
        results_by_query={
            "new grad software engineer": [
                shared,
            ],
            "entry level software engineer": [
                shared,
            ],
        },
    )

    jobs = fetch_adzuna_jobs(
        app_id="id",
        app_key="key",
        query_terms=(
            "new grad software engineer",
            "entry level software engineer",
        ),
        client=client,
    )

    assert len(
        jobs
    ) == 1


def test_it_pages_a_query_with_more_than_one_page() -> None:
    many = [
        posting(
            ident=str(
                n
            ),
        )
        for n in range(120)
    ]

    client = make_client(
        results_by_query={
            "new grad software engineer": (
                many
            ),
        },
    )

    jobs = fetch_adzuna_jobs(
        app_id="id",
        app_key="key",
        query_terms=(
            "new grad software engineer",
        ),
        client=client,
    )

    assert len(
        jobs
    ) == 120


def test_a_400_on_a_page_past_the_end_is_treated_as_finished() -> (
    None
):
    """Adzuna 400s past its last real page rather than returning an
    empty list, which is otherwise indistinguishable from a real
    failure and would fail the whole poll."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        page = int(
            request.url.path.rsplit(
                "/",
                1,
            )[-1]
        )

        if page == 1:
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "results": [
                        posting(),
                    ],
                },
            )

        return httpx.Response(
            400,
            json={
                "exception": (
                    "InvalidPageException"
                ),
            },
        )

    client = httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        ),
    )

    jobs = fetch_adzuna_jobs(
        app_id="id",
        app_key="key",
        query_terms=(
            "new grad software engineer",
        ),
        client=client,
    )

    assert len(
        jobs
    ) == 1


def test_query_terms_are_sent_as_separate_requests() -> None:
    """Every term is a real request; nothing is silently skipped."""

    seen: list[str] = []

    client = make_client(
        results_by_query={
            "new grad software engineer": [
                posting(
                    ident="1",
                ),
            ],
            "entry level software engineer": [
                posting(
                    ident="2",
                ),
            ],
        },
        seen=seen,
    )

    fetch_adzuna_jobs(
        app_id="id",
        app_key="key",
        query_terms=(
            "new grad software engineer",
            "entry level software engineer",
        ),
        client=client,
    )

    assert any(
        "new+grad" in call
        or "new%20grad" in call
        for call in seen
    )

    assert any(
        "entry+level" in call
        or "entry%20level" in call
        for call in seen
    )


def test_an_empty_app_id_is_refused() -> None:
    with pytest.raises(
        ValueError,
    ):
        fetch_adzuna_jobs(
            app_id="  ",
            app_key="key",
        )


def test_an_empty_app_key_is_refused() -> None:
    with pytest.raises(
        ValueError,
    ):
        fetch_adzuna_jobs(
            app_id="id",
            app_key="  ",
        )
