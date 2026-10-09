"""Careers sites read through their sitemap and their postings' JSON-LD.

Meta's job sitemap and the Radancy sitemaps of Intuit, Arm and Synopsys.
Fixtures are fictional postings in the sites' shapes.
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

from backend.app.adapters.sitemap_jobs import (
    REREAD_AFTER,
    fetch_sitemap_jobs,
    parse_posting_page,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)
from backend.app.verification.employer_page import (
    READ,
    Reading,
)


NOW = datetime(
    2026,
    10,
    9,
    tzinfo=timezone.utc,
)


class MemoryStore:
    def __init__(
        self,
    ) -> None:
        self.rows: dict[str, tuple[Reading, datetime]] = {}

    def load(
        self,
        urls,
    ):
        return {
            url: self.rows[url]
            for url in urls
            if url in self.rows
        }

    def save(
        self,
        readings,
        *,
        moment,
    ) -> None:
        for url, reading in readings.items():
            if reading.status != READ and url in self.rows:
                continue

            self.rows[url] = (reading, moment)


def sitemap(
    *urls: str,
) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><urlset>'
        + "".join(
            f"<url><loc>{url}</loc><lastmod>2026-10-09T00:42:16Z</lastmod></url>"
            for url in urls
        )
        + "</urlset>"
    )


def posting_page(
    title: str = "Software Engineer 2",
    *,
    years: str = "2+ years of experience in software development.",
    remote: bool = False,
) -> str:
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": title,
        "datePosted": "2026-10-06",
        "employmentType": "Full-Time",
        "description": f"<p>Build tax software.</p><ul><li>{years}</li></ul>",
        "jobLocation": [
            {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Mountain View",
                    "addressRegion": "California",
                    "addressCountry": "United States",
                },
            }
        ],
    }

    if remote:
        posting["jobLocationType"] = "TELECOMMUTE"
        posting["applicantLocationRequirements"] = [
            {"@type": "Country", "name": "United States of America"}
        ]

    return (
        "<html><head><script type=\"application/ld+json\">"
        + json.dumps(posting)
        + "</script></head><body></body></html>"
    )


RADANCY = "jobs.example-tax.com"

SWE = f"https://{RADANCY}/job/mountain-view/software-engineer-2/27595/101"

STAFF = f"https://{RADANCY}/job/mountain-view/staff-software-engineer/27595/102"


def site(
    pages: dict[str, str],
):
    asked: list[str] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        url = str(request.url)
        asked.append(url)

        if url in pages:
            return httpx.Response(200, text=pages[url])

        return httpx.Response(404, text="gone")

    return httpx.Client(
        transport=httpx.MockTransport(handler),
    ), asked


def test_a_radancy_posting_is_read_once_and_a_senior_one_never() -> None:
    client, asked = site(
        {
            f"https://{RADANCY}/sitemap.xml": sitemap(SWE, STAFF),
            SWE: posting_page(),
        }
    )

    store = MemoryStore()

    jobs = fetch_sitemap_jobs(
        host=RADANCY,
        company_name="Example Tax",
        client=client,
        should_fetch_detail=lambda title: "Staff" not in title,
        store=store,
        now=lambda: NOW,
        pause_seconds=0,
    )

    assert STAFF not in asked

    by_id = {
        job.external_id: job
        for job in jobs
    }

    assert by_id["101"].location == "Mountain View, California, United States"

    assert evaluate_job(
        by_id["101"]
    ).status == EligibilityStatus.PASS

    # Kept, so the board is whole, without its page being read.
    assert by_id["102"].title == "Staff Software Engineer"

    assert jobs.complete is True

    asked.clear()

    fetch_sitemap_jobs(
        host=RADANCY,
        company_name="Example Tax",
        client=client,
        should_fetch_detail=lambda title: "Staff" not in title,
        store=store,
        now=lambda: NOW + timedelta(hours=1),
        pause_seconds=0,
    )

    assert asked == [
        f"https://{RADANCY}/sitemap.xml",
    ]


def test_a_reading_is_taken_again_after_a_month() -> None:
    client, asked = site(
        {
            f"https://{RADANCY}/sitemap.xml": sitemap(SWE),
            SWE: posting_page(),
        }
    )

    store = MemoryStore()

    for moment in (NOW, NOW + REREAD_AFTER):
        fetch_sitemap_jobs(
            host=RADANCY,
            company_name="Example Tax",
            client=client,
            store=store,
            now=lambda moment=moment: moment,
            pause_seconds=0,
        )

    assert asked.count(SWE) == 2


def test_meta_postings_are_read_a_few_at_a_time() -> None:
    """Meta's sitemap carries no titles, so each posting's page is read;
    one not yet read is left out, never guessed at."""

    host = "www.metacareers.com"
    urls = [
        f"https://{host}/profile/job_details/{number}/"
        for number in (11, 12, 13)
    ]

    client, asked = site(
        {
            f"https://{host}/jobsearch/sitemap.xml": sitemap(*urls),
            **{
                url: posting_page("Software Engineer, Product", remote=True)
                for url in urls
            },
        }
    )

    jobs = fetch_sitemap_jobs(
        host=host,
        company_name="Meta",
        client=client,
        store=MemoryStore(),
        now=lambda: NOW,
        max_reads=2,
        pause_seconds=0,
    )

    assert [job.external_id for job in jobs] == ["11", "12"]

    assert jobs[0].location == (
        "Mountain View, California, United States; "
        "Remote - United States of America"
    )


def test_a_failed_read_keeps_the_good_one_before_it() -> None:
    pages = {
        f"https://{RADANCY}/sitemap.xml": sitemap(SWE),
        SWE: posting_page(),
    }

    client, _asked = site(
        pages
    )

    store = MemoryStore()

    fetch_sitemap_jobs(
        host=RADANCY,
        company_name="Example Tax",
        client=client,
        store=store,
        now=lambda: NOW,
        pause_seconds=0,
    )

    del pages[SWE]

    jobs = fetch_sitemap_jobs(
        host=RADANCY,
        company_name="Example Tax",
        client=client,
        store=store,
        now=lambda: NOW + REREAD_AFTER,
        pause_seconds=0,
    )

    assert [job.title for job in jobs] == ["Software Engineer 2"]


def test_an_empty_sitemap_is_never_every_posting_closing() -> None:
    client, _asked = site(
        {f"https://{RADANCY}/sitemap.xml": sitemap()}
    )

    with pytest.raises(ValueError):
        fetch_sitemap_jobs(
            host=RADANCY,
            company_name="Example Tax",
            client=client,
            store=MemoryStore(),
            now=lambda: NOW,
            pause_seconds=0,
        )


def test_a_page_without_a_jobposting_has_none() -> None:
    assert parse_posting_page(
        "<html><script type='application/ld+json'>"
        '{"@type": "Organization"}</script></html>'
    ) is None
