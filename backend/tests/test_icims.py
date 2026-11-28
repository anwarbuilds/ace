"""iCIMS careers sites, read through their sitemap (DIS-09). Every company, posting and host here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.app.adapters.sitemap_jobs import fetch_sitemap_jobs, site_for
from backend.app.coverage.host_policy import read_targets
from backend.app.discovery.detector import detect_source_from_url
from backend.app.scheduling.dispatcher import SitemapSourceFetcher
from backend.app.scheduling.types import SourceDefinition, SourceType

NOW = datetime(2026, 11, 28, 6, 0, tzinfo=timezone.utc)
HOST = "careers-zephyr.icims.com"

SITEMAP = (f"<urlset><url><loc>https://{HOST}/jobs/search</loc></url>"
           f"<url><loc>https://{HOST}/jobs/2478/software-engineer-i/job</loc><lastmod>2026-11-27T12:00:00-05:00</lastmod></url>"
           f"<url><loc>https://{HOST}/jobs/2479/office-manager/job</loc></url></urlset>")

PAGE = ('<html><script type="application/ld+json">{"@context": "http://schema.org", "@type": "JobPosting", '
        '"title": "Software Engineer I", "description": "<p>We build fictional software. A bachelor degree in computer '
        'science is required.</p>", "datePosted": "2026-11-27T05:00:00.000Z", '
        '"hiringOrganization": {"@type": "Organization", "name": "Zephyr Labs"}, '
        '"jobLocation": [{"address": {"addressLocality": "Denver", "addressRegion": "CO", "addressCountry": "US"}}]}'
        '</script></html>')


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def load(self, urls):
        return {url: self.rows[url] for url in urls if url in self.rows}

    def save(self, readings, *, moment):
        self.rows.update({url: (reading, moment) for url, reading in readings.items()})


def test_an_icims_site_is_read_through_its_sitemap_under_its_own_name():
    asked = []

    def handler(request):
        asked.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=SITEMAP)
        if request.url.path == "/jobs/2478/software-engineer-i/job":
            return httpx.Response(200, text=PAGE)
        return httpx.Response(404, text="")

    jobs = fetch_sitemap_jobs(host=HOST, company_name="Zephyr Labs", client=httpx.Client(transport=httpx.MockTransport(handler)),
                              should_fetch_detail=lambda title: "Engineer" in title, store=MemoryStore(),
                              now=lambda: NOW, pause_seconds=0, source="icims")
    by_id = {job.external_id: job for job in jobs}
    assert set(by_id) == {"2478", "2479"} and all(job.source == "icims" for job in jobs)
    assert "bachelor degree" in by_id["2478"].description and "Denver" in by_id["2478"].location
    assert by_id["2479"].description == ""
    assert f"https://{HOST}/jobs/2479/office-manager/job" not in asked
    assert jobs.complete


def test_its_links_name_the_board_and_robots_paths_are_its_own():
    found = detect_source_from_url(f"https://{HOST}/jobs/2478/software-engineer-i/job")
    assert found.source_type == SourceType.ICIMS and found.source_account == HOST
    assert detect_source_from_url("https://www.icims.com/products/") is None
    assert site_for(HOST).sitemap == f"https://{HOST}/sitemap.xml"
    (target,) = read_targets("icims", HOST, None)
    assert target.host == HOST and "/sitemap.xml" in target.paths


def test_the_scheduler_reads_it_as_its_own_source_type():
    seen = {}

    def fetcher(**kwargs):
        seen.update(kwargs)
        from backend.app.adapters.sitemap_jobs import JobList
        return JobList([], complete=True)

    source = SourceDefinition(source_type=SourceType.ICIMS, source_account=HOST, company_name="Zephyr Labs",
                              poll_interval_seconds=900)
    snapshot = SitemapSourceFetcher(fetcher=fetcher, clock=lambda: NOW, source_type=SourceType.ICIMS)(source)
    assert snapshot.complete and seen["source"] == "icims" and seen["host"] == HOST
