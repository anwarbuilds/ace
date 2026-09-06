"""Tests for the curated new-grad feed adapter."""

import httpx
import pytest

from backend.app.adapters.simplify import (
    build_description,
    fetch_simplify_jobs,
    is_included,
    is_reachable_by_adapter,
    parse_feed_name,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)


def entry(
    **overrides,
) -> dict:
    """Build one feed entry."""

    base = {
        "id": "abc",
        "title": "Software Engineer, New Grad",
        "company_name": "Acme",
        "url": (
            "https://careers.acme.example"
            "/jobs/1"
        ),
        "active": True,
        "is_visible": True,
        "category": "Software",
        "date_posted": 1788000000,
        "date_updated": 1788000000,
        "locations": [
            "Seattle, WA",
        ],
        "sponsorship": "Other",
        "degrees": [
            "Bachelor's",
        ],
    }

    base.update(
        overrides
    )

    return base


def fetch(
    entries: list[dict],
):
    """Run the adapter against an in-memory feed."""

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=entries,
        )
    )

    with httpx.Client(
        transport=transport
    ) as client:
        jobs, _unchanged, _validators = (
            fetch_simplify_jobs(
                source_account="new-grad",
                client=client,
            )
        )

        return jobs


def test_unknown_feed_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        parse_feed_name(
            "not-a-feed"
        )


# ----------------------------------------------------------------------
# Scope: this lane covers only what direct polling cannot reach
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://job-boards.greenhouse.io/x/jobs/1",
        "https://jobs.ashbyhq.com/x/1",
        "https://jobs.lever.co/x/1",
        "https://acme.wd5.myworkdayjobs.com/Careers/job/1",
    ],
)
def test_ats_reachable_postings_are_excluded(
    url: str,
) -> None:
    """An employer on a supported ATS belongs in the source catalog.

    Ingesting it here too would duplicate the posting and vet it less
    thoroughly, since this feed carries no description.
    """

    assert is_reachable_by_adapter(
        url
    )

    assert not is_included(
        entry(
            url=url
        )
    )


def test_unreachable_postings_are_included() -> None:
    for url in (
        "https://lifeattiktok.com/search/1",
        "https://jobs.apple.com/role/1",
        "https://www.tesla.com/careers/job/1",
    ):
        assert not is_reachable_by_adapter(
            url
        )

        assert is_included(
            entry(
                url=url
            )
        )


@pytest.mark.parametrize(
    "category,included",
    [
        ("Software", True),
        ("AI/ML/Data", True),
        ("Hardware", False),
        ("Quant", False),
        ("Product", False),
    ],
)
def test_only_target_categories_are_included(
    category: str,
    included: bool,
) -> None:
    """Hardware is excluded to match ACE's own hardware rule."""

    assert is_included(
        entry(
            url=(
                "https://lifeattiktok.com/1"
            ),
            category=category,
        )
    ) is included


def test_inactive_entries_are_excluded() -> None:
    assert not is_included(
        entry(
            url="https://lifeattiktok.com/1",
            active=False,
        )
    )


# ----------------------------------------------------------------------
# Structured metadata is rendered as text the existing gate understands
# ----------------------------------------------------------------------


def test_sponsorship_blocker_becomes_gate_readable_text() -> None:
    """No parallel rule path: the gate evaluates it as prose."""

    job = fetch(
        [
            entry(
                url=(
                    "https://lifeattiktok.com/1"
                ),
                sponsorship=(
                    "Does Not Offer Sponsorship"
                ),
            ),
        ]
    )[0]

    decision = evaluate_job(
        job
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "SPONSORSHIP_BLOCKER"
        in {
            code.value
            for code
            in decision.reason_codes
        }
    )


def test_citizenship_requirement_becomes_gate_readable_text() -> None:
    job = fetch(
        [
            entry(
                url=(
                    "https://lifeattiktok.com/1"
                ),
                sponsorship=(
                    "U.S. Citizenship is Required"
                ),
            ),
        ]
    )[0]

    assert (
        evaluate_job(
            job
        ).status
        is EligibilityStatus.REJECT
    )


def test_ordinary_entry_survives_the_gate() -> None:
    job = fetch(
        [
            entry(
                url=(
                    "https://lifeattiktok.com/1"
                ),
            ),
        ]
    )[0]

    assert (
        evaluate_job(
            job
        ).status
        is EligibilityStatus.PASS
    )


def test_description_records_its_own_limits() -> None:
    """The card should say the requirements were not read."""

    text = build_description(
        entry()
    )

    assert "curated" in text.lower()

    assert (
        "employer" in text.lower()
    )


# ----------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------


def test_entry_maps_to_canonical_job() -> None:
    job = fetch(
        [
            entry(
                url=(
                    "https://lifeattiktok.com/1"
                ),
                company_name="TikTok",
            ),
        ]
    )[0]

    assert job.source == "simplify"

    assert job.company == "TikTok"

    assert job.external_id == "abc"

    assert (
        job.official_url
        == "https://lifeattiktok.com/1"
    )

    assert (
        job.location == "Seattle, WA"
    )

    assert job.posted_at is not None


def test_entries_without_a_url_are_skipped() -> None:
    assert fetch(
        [
            entry(
                url="",
            ),
        ]
    ) == []


# ----------------------------------------------------------------------
# Conditional fetching
#
# These feeds are the catalog's largest download and are usually
# unchanged between polls, so an unchanged feed must cost one 304 with
# no body rather than several megabytes of JSON.
# ----------------------------------------------------------------------


def test_unchanged_feed_returns_no_jobs_and_says_so() -> None:
    """A 304 means nothing was added, edited or closed."""

    from backend.app.adapters.http_cache import (
        CacheValidators,
    )

    calls: list[dict] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        calls.append(
            dict(
                request.headers
            )
        )

        return httpx.Response(
            304
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        jobs, unchanged, validators = (
            fetch_simplify_jobs(
                source_account="new-grad",
                client=client,
                validators=CacheValidators(
                    etag='W/"abc"',
                ),
            )
        )

    assert unchanged is True

    assert jobs == []

    # The validator was actually sent.
    assert (
        calls[0]["if-none-match"]
        == 'W/"abc"'
    )

    # And is preserved for the next poll.
    assert validators.etag == 'W/"abc"'


def test_changed_feed_returns_new_validators() -> None:
    """A 200 supplies the validator to send next time."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                entry(
                    url=(
                        "https://lifeattiktok.com/1"
                    ),
                ),
            ],
            headers={
                "ETag": 'W/"fresh"',
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        jobs, unchanged, validators = (
            fetch_simplify_jobs(
                source_account="new-grad",
                client=client,
            )
        )

    assert unchanged is False

    assert len(jobs) == 1

    assert validators.etag == 'W/"fresh"'


def test_first_poll_sends_no_validators() -> None:
    """With nothing remembered, the request is unconditional."""

    calls: list[dict] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        calls.append(
            dict(
                request.headers
            )
        )

        return httpx.Response(
            200,
            json=[],
        )

    with httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    ) as client:
        fetch_simplify_jobs(
            source_account="new-grad",
            client=client,
        )

    assert (
        "if-none-match"
        not in calls[0]
    )
