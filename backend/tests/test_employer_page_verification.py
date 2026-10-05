"""A feed posting is judged on the employer's own page.

The feed carries no description, so clearance, citizenship and
experience rules never ran on it. Read at the employer, 50 of 85 feed
postings that had passed should have been rejected -- 43 of them for a
security clearance. That was the noise the user kept reporting.
"""

from __future__ import annotations

import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import EmployerPageReading
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import (
    DISALLOWED,
    NO_DESCRIPTION,
    READ,
    UNREACHABLE,
    EmployerPageVerifier,
    RobotsCache,
    extract_job_description,
    read_employer_page,
)


NOW = datetime(
    2026,
    10,
    5,
    12,
    tzinfo=timezone.utc,
)

CLEARED_ROLE = (
    "<p>Join our mission team building software for national "
    "defense programs.</p><ul><li>Bachelor's degree in Computer "
    "Science</li><li>Active TS/SCI security clearance with "
    "polygraph is required.</li><li>US citizenship is required."
    "</li></ul><p>We design, build and test mission software in "
    "Python and C++ alongside systems engineers.</p>"
)

OPEN_ROLE = (
    "<p>Build the platform behind our product as a new graduate "
    "software engineer.</p><ul><li>Bachelor's degree in Computer "
    "Science or a related field</li><li>Experience with Python, "
    "Go or Java from coursework or internships</li></ul><p>You "
    "will ship features with mentorship from senior engineers.</p>"
)


def page(
    description: str | None,
    *,
    wrap: str = "plain",
) -> str:
    if description is None:
        return "<html><body><h1>Careers</h1></body></html>"

    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Software Engineer",
        "description": description,
    }

    if wrap == "graph":
        data = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "Northwind"},
                posting,
            ],
        }
    elif wrap == "list":
        data = [
            {"@type": "BreadcrumbList"},
            posting,
        ]
    else:
        data = posting

    return (
        "<html><head><script type=\"application/ld+json\">"
        + json.dumps(data)
        + "</script></head><body></body></html>"
    )


def feed_job(
    url: str,
    *,
    title: str = "Software Engineer - Entry Level",
) -> CanonicalJob:
    return CanonicalJob(
        source="simplify",
        company="Northwind Defense",
        external_id=url,
        title=title,
        location="Columbia, MD",
        description=(
            "Sourced from a curated new-graduate listing. Full "
            "requirements are on the employer's posting."
        ),
        official_url=url,
    )


class Site:
    """Employer sites served from memory, counting what is fetched."""

    def __init__(
        self,
        pages: dict[str, tuple[int, str]],
        *,
        robots: dict[str, tuple[int, str]] | None = None,
    ) -> None:
        self.pages = pages

        self.robots = robots or {}

        self.fetched: list[str] = []

    def client(
        self,
    ) -> httpx.Client:
        def handler(
            request: httpx.Request,
        ) -> httpx.Response:
            url = str(
                request.url
            )

            if request.url.path == "/robots.txt":
                status, text = self.robots.get(
                    request.url.host,
                    (404, ""),
                )

                return httpx.Response(
                    status,
                    text=text,
                )

            self.fetched.append(
                url
            )

            status, text = self.pages.get(
                url,
                (404, ""),
            )

            return httpx.Response(
                status,
                text=text,
            )

        return httpx.Client(
            transport=httpx.MockTransport(
                handler
            )
        )


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def verifier(
    sessions,
    site: Site,
    *,
    now: datetime = NOW,
    **kwargs,
) -> EmployerPageVerifier:
    return EmployerPageVerifier(
        session_factory=sessions,
        client_factory=site.client,
        now=lambda: now,
        **kwargs,
    )


# --- reading a page ---------------------------------------------------


@pytest.mark.parametrize(
    "wrap",
    ["plain", "graph", "list"],
)
def test_the_description_is_read_from_the_job_posting(
    wrap: str,
) -> None:
    text = extract_job_description(
        page(
            CLEARED_ROLE,
            wrap=wrap,
        )
    )

    assert "TS/SCI security clearance" in text

    # Tags are gone and list items do not fuse into one word.
    assert "<li>" not in text

    assert "Computer Science\n" in text


def test_a_page_without_a_job_posting_has_no_description() -> None:
    assert extract_job_description(
        page(None)
    ) is None


def test_a_page_its_site_disallows_is_not_fetched() -> None:
    url = "https://careers.northwind.example/job/1"

    site = Site(
        {url: (200, page(CLEARED_ROLE))},
        robots={
            "careers.northwind.example": (
                200,
                "User-agent: *\nDisallow: /job/\n",
            ),
        },
    )

    with site.client() as client:
        reading = read_employer_page(
            url,
            client=client,
            robots=RobotsCache(client),
        )

    assert reading.status == DISALLOWED

    assert site.fetched == []


def test_unreadable_robots_rules_mean_disallow() -> None:
    """RFC 9309: rules that could not be read must be taken as a
    refusal, not as permission."""

    url = "https://careers.northwind.example/job/1"

    site = Site(
        {url: (200, page(CLEARED_ROLE))},
        robots={
            "careers.northwind.example": (503, ""),
        },
    )

    with site.client() as client:
        reading = read_employer_page(
            url,
            client=client,
            robots=RobotsCache(client),
        )

    assert reading.status == DISALLOWED


@pytest.mark.parametrize(
    "response, expected",
    [
        ((404, ""), UNREACHABLE),
        ((200, page(None)), NO_DESCRIPTION),
        ((200, page("Apply now.")), NO_DESCRIPTION),
        ((200, page(OPEN_ROLE)), READ),
    ],
)
def test_what_a_page_can_say(
    response,
    expected,
) -> None:
    url = "https://careers.northwind.example/job/1"

    site = Site(
        {url: response},
    )

    with site.client() as client:
        assert read_employer_page(
            url,
            client=client,
            robots=RobotsCache(client),
        ).status == expected


# --- judging feed postings on it ---------------------------------------


def test_a_feed_posting_that_needs_a_clearance_is_rejected(
    sessions,
) -> None:
    """The user's complaint, end to end."""

    url = "https://careers.northwind.example/job/1"

    job = feed_job(url)

    # As the feed has it, the posting passes: nothing to read.
    assert evaluate_job(job).status == EligibilityStatus.PASS

    [checked] = verifier(
        sessions,
        Site({url: (200, page(CLEARED_ROLE))}),
    )([job])

    decision = evaluate_job(
        checked
    )

    assert decision.status == EligibilityStatus.REJECT

    assert (
        EligibilityReasonCode.CLEARANCE_BLOCKER
        in decision.reason_codes
    )

    # The feed's own sentences are kept after the employer's text.
    assert "curated new-graduate listing" in checked.description


def test_a_feed_posting_the_employer_page_supports_still_passes(
    sessions,
) -> None:
    url = "https://careers.northwind.example/job/2"

    [checked] = verifier(
        sessions,
        Site({url: (200, page(OPEN_ROLE))}),
    )([feed_job(url)])

    assert evaluate_job(
        checked
    ).status == EligibilityStatus.PASS


def test_an_unreadable_page_leaves_the_posting_as_it_was(
    sessions,
) -> None:
    """Silence is not rejection."""

    url = "https://careers.northwind.example/job/3"

    job = feed_job(url)

    [checked] = verifier(
        sessions,
        Site({}),
    )([job])

    assert checked == job


def test_a_page_is_read_once_a_week_not_every_poll(
    sessions,
) -> None:
    url = "https://careers.northwind.example/job/1"

    site = Site({url: (200, page(CLEARED_ROLE))})

    verifier(sessions, site)([feed_job(url)])

    # The next poll, an hour later: from memory, not from their server.
    [checked] = verifier(
        sessions,
        site,
        now=NOW + timedelta(hours=1),
    )([feed_job(url)])

    assert site.fetched == [url]

    assert "TS/SCI" in checked.description

    # A week on, it is read again.
    verifier(
        sessions,
        site,
        now=NOW + timedelta(days=8),
    )([feed_job(url)])

    assert site.fetched == [url, url]


def test_a_page_that_stops_answering_keeps_what_it_said(
    sessions,
) -> None:
    """A posting that has gone is closed by the feed, not by this; until
    then it is still the posting the page described."""

    url = "https://careers.northwind.example/job/1"

    verifier(
        sessions,
        Site({url: (200, page(CLEARED_ROLE))}),
    )([feed_job(url)])

    [checked] = verifier(
        sessions,
        Site({url: (503, "")}),
        now=NOW + timedelta(days=8),
    )([feed_job(url)])

    assert "TS/SCI" in checked.description

    with sessions() as session:
        row = session.scalar(
            sa.select(EmployerPageReading)
        )

    assert row.status == READ


def test_only_postings_whose_title_could_pass_are_read(
    sessions,
) -> None:
    wanted = "https://careers.northwind.example/job/1"

    skipped = "https://careers.northwind.example/job/2"

    site = Site(
        {
            wanted: (200, page(OPEN_ROLE)),
            skipped: (200, page(OPEN_ROLE)),
        }
    )

    verifier(
        sessions,
        site,
        worth_reading=lambda job: job.official_url == wanted,
    )([feed_job(wanted), feed_job(skipped)])

    assert site.fetched == [wanted]


def test_fresh_reads_per_poll_are_bounded(
    sessions,
) -> None:
    urls = [
        f"https://careers.northwind.example/job/{index}"
        for index in range(5)
    ]

    site = Site(
        {url: (200, page(OPEN_ROLE)) for url in urls}
    )

    verifier(
        sessions,
        site,
        fresh_reads=2,
    )([feed_job(url) for url in urls])

    assert len(site.fetched) == 2

    # The rest are read on later polls.
    verifier(
        sessions,
        site,
        fresh_reads=2,
    )([feed_job(url) for url in urls])

    assert len(set(site.fetched)) == 4


# --- where it runs -----------------------------------------------------


def _simplify_source():
    from backend.app.scheduling.types import (
        SourceDefinition,
        SourceType,
    )

    return SourceDefinition(
        source_type=SourceType.SIMPLIFY,
        source_account="new-grad",
        company_name="Simplify",
        enabled=True,
        poll_interval_seconds=300,
    )


def _fetcher(
    jobs,
    *,
    unchanged: bool,
    seen: list,
):
    from backend.app.adapters.http_cache import (
        CacheValidators,
    )
    from backend.app.scheduling.dispatcher import (
        SimplifySourceFetcher,
    )

    def verify(batch):
        seen.append(
            list(batch)
        )

        return [
            job.model_copy(
                update={
                    "description": "checked",
                },
            )
            for job in batch
        ]

    return SimplifySourceFetcher(
        fetcher=lambda **_kwargs: (
            jobs,
            unchanged,
            CacheValidators(
                etag=None,
                last_modified=None,
            ),
        ),
        verifier=verify,
    )


def test_the_feed_fetcher_judges_postings_on_their_pages() -> None:
    seen: list = []

    job = feed_job(
        "https://careers.northwind.example/job/1"
    )

    snapshot = _fetcher(
        [job],
        unchanged=False,
        seen=seen,
    )(
        _simplify_source()
    )

    assert seen == [[job]]

    assert snapshot.jobs[0].description == "checked"


def test_an_unchanged_feed_reads_no_pages() -> None:
    """A 304 has no postings to check, and nothing changed."""

    seen: list = []

    _fetcher(
        [],
        unchanged=True,
        seen=seen,
    )(
        _simplify_source()
    )

    assert seen == []
