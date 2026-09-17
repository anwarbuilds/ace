"""Tests for the RippleMatch adapter.

The fixtures here are trimmed copies of the real pages, including the
Plaid posting that prompted the source existing: a "Software
Engineering, New Grad" role that was reachable on RippleMatch and
absent from Plaid's own Ashby board, which carried 110 live postings at
the time and not one mentioning new grad, graduate, university or
campus.
"""

from __future__ import annotations

import httpx
import pytest

from backend.app.adapters.ripplematch import (
    fetch_ripplematch_jobs,
    parse_job_page,
    parse_sitemap,
)


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://app.ripplematch.com/dmca</loc>
       <changefreq>monthly</changefreq></url>
  <url><loc>https://app.ripplematch.com/company/plaid</loc>
       <changefreq>daily</changefreq></url>
  <url><loc>https://app.ripplematch.com/v2/public/job/726e99d1</loc>
       <changefreq>daily</changefreq><lastmod>2026-09-16</lastmod></url>
  <url><loc>https://app.ripplematch.com/v2/public/job/9c7c5a7f</loc>
       <changefreq>daily</changefreq><lastmod>2026-07-22</lastmod></url>
</urlset>"""


def page(
    *,
    title: str = "Software Engineering, New Grad",
    company: str = "Plaid",
    date_posted: str = "2026-09-16",
    description: str = (
        "<p>Build payments infrastructure.</p>"
        "<p>0-2 years of experience.</p>"
    ),
    employment_type: str = "FULL_TIME",
    locality: str = "Seattle",
    region: str = "WA",
) -> str:
    """One public job page, shaped like the real thing."""

    return f"""<!doctype html><html><head>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "{title}",
  "datePosted": "{date_posted}",
  "employmentType": "{employment_type}",
  "hiringOrganization": {{
    "@type": "Organization",
    "name": "{company}",
    "sameAs": "https://plaid.com/"
  }},
  "jobLocation": {{
    "@type": "Place",
    "address": {{
      "@type": "PostalAddress",
      "addressLocality": "{locality}",
      "addressRegion": "{region}",
      "addressCountry": "US"
    }}
  }},
  "description": "{description}"
}}
</script>
</head><body><div id="app"></div></body></html>"""


# --- the sitemap is the snapshot ------------------------------------


def test_only_job_pages_are_taken_from_the_sitemap() -> None:
    """It also lists company and marketing pages."""

    entries = parse_sitemap(
        SITEMAP,
    )

    assert entries == [
        (
            "726e99d1",
            "https://app.ripplematch.com/v2/public/job/726e99d1",
        ),
        (
            "9c7c5a7f",
            "https://app.ripplematch.com/v2/public/job/9c7c5a7f",
        ),
    ]


def test_a_repeated_id_is_listed_once() -> None:
    """Emitting one posting twice would make the lifecycle diff read a
    job it already holds as a second, unrelated arrival."""

    doubled = SITEMAP.replace(
        "</urlset>",
        "<url><loc>https://app.ripplematch.com/v2/public/job/726e99d1"
        "</loc></url></urlset>",
    )

    ids = [
        job_id
        for job_id, _ in parse_sitemap(
            doubled,
        )
    ]

    assert ids.count(
        "726e99d1",
    ) == 1


# --- one page becomes one job ---------------------------------------


def test_the_plaid_posting_parses() -> None:
    """The role this source exists for."""

    job = parse_job_page(
        page(),
        job_id="726e99d1",
        url="https://app.ripplematch.com/v2/public/job/726e99d1",
    )

    assert job is not None
    assert job.source == "ripplematch"
    assert job.company == "Plaid"
    assert job.title == "Software Engineering, New Grad"
    assert job.location == "Seattle, WA, US"
    assert job.external_id == "726e99d1"
    assert job.employment_type == "FULL_TIME"
    assert job.posted_at is not None
    assert job.posted_at.year == 2026


def test_the_description_survives_as_readable_text() -> None:
    """The gate reads requirement text, so paragraphs must not run
    together into one line and entities must not survive as markup."""

    job = parse_job_page(
        page(
            description=(
                "<p>Own the platform.</p>"
                "<p>Requires 0&ndash;2 years "
                "experience.</p>"
            ),
        ),
        job_id="x",
        url="https://app.ripplematch.com/v2/public/job/x",
    )

    assert job is not None
    assert "Own the platform." in job.description
    assert "years" in job.description
    assert "<p>" not in job.description
    assert "&ndash;" not in job.description

    # The two paragraphs are separated rather than concatenated.
    assert "platform.Requires" not in job.description


def test_the_apply_link_is_the_page_it_came_from() -> None:
    """This source is the deliberate exception to "the apply link is
    the employer's own posting": for these roles there is no employer
    posting to link to, and RippleMatch is where the application is
    actually received."""

    url = "https://app.ripplematch.com/v2/public/job/726e99d1"

    job = parse_job_page(
        page(),
        job_id="726e99d1",
        url=url,
    )

    assert job is not None
    assert job.official_url == url


def test_a_page_with_no_posting_is_skipped_not_raised() -> None:
    """One malformed page out of hundreds must not fail the poll.

    A failed poll returns no snapshot, and persistence would be asked
    to read a missing snapshot as every job closing at once.
    """

    for html in (
        "<html><body>nothing here</body></html>",
        '<script type="application/ld+json">{ not json </script>',
        '<script type="application/ld+json">'
        '{"@type":"Organization","name":"Plaid"}</script>',
    ):
        assert parse_job_page(
            html,
            job_id="x",
            url="https://app.ripplematch.com/v2/public/job/x",
        ) is None


def test_a_posting_missing_its_employer_is_skipped() -> None:
    """It would otherwise appear in the queue as a role at nobody."""

    assert parse_job_page(
        page(
            company="",
        ),
        job_id="x",
        url="https://app.ripplematch.com/v2/public/job/x",
    ) is None


def test_an_unparseable_date_is_left_unset() -> None:
    """Freshness treats a missing date as unknown, which is honest.

    Substituting today would make every posting look permanently new.
    """

    job = parse_job_page(
        page(
            date_posted="not-a-date",
        ),
        job_id="x",
        url="https://app.ripplematch.com/v2/public/job/x",
    )

    assert job is not None
    assert job.posted_at is None


# --- the whole fetch ------------------------------------------------


def _transport(
    pages: dict[str, str],
    *,
    sitemap: str = SITEMAP,
) -> httpx.MockTransport:
    def handle(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path.endswith(
            "sitemap.xml",
        ):
            return httpx.Response(
                200,
                text=sitemap,
            )

        job_id = request.url.path.rsplit(
            "/",
            1,
        )[-1]

        if job_id not in pages:
            return httpx.Response(
                404,
                text="gone",
            )

        return httpx.Response(
            200,
            text=pages[job_id],
        )

    return httpx.MockTransport(
        handle,
    )


def test_every_listed_posting_is_fetched() -> None:
    client = httpx.Client(
        transport=_transport(
            {
                "726e99d1": page(),
                "9c7c5a7f": page(
                    title="2027 Spring Co-Op",
                    company="Sanofi",
                ),
            }
        ),
    )

    jobs = fetch_ripplematch_jobs(
        client=client,
        concurrency=2,
    )

    assert {
        job.company
        for job in jobs
    } == {
        "Plaid",
        "Sanofi",
    }


def test_one_dead_page_does_not_empty_the_snapshot() -> None:
    """The failure that matters most.

    An empty snapshot is refused by persistence rather than read as
    every job closing, but a snapshot missing most of its postings
    would not be refused -- it would close them. So a page that 404s is
    dropped and the rest still arrive.
    """

    client = httpx.Client(
        transport=_transport(
            {
                "726e99d1": page(),
            }
        ),
    )

    jobs = fetch_ripplematch_jobs(
        client=client,
        concurrency=2,
    )

    assert [
        job.company
        for job in jobs
    ] == [
        "Plaid",
    ]


def test_the_company_name_on_the_source_is_ignored() -> None:
    """This feed spans employers; each posting carries its own."""

    client = httpx.Client(
        transport=_transport(
            {
                "726e99d1": page(),
                "9c7c5a7f": page(
                    company="Sanofi",
                ),
            }
        ),
    )

    jobs = fetch_ripplematch_jobs(
        client=client,
        company_name="Not This Company",
        concurrency=2,
    )

    assert "Not This Company" not in {
        job.company
        for job in jobs
    }
