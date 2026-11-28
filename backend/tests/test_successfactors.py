"""SuccessFactors careers sites, read from their job feed (DIS-08). Every company, posting and host here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from backend.app.adapters import successfactors as sf
from backend.app.coverage.host_policy import read_targets
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.freehire import board_of
from backend.app.scheduling.dispatcher import SuccessFactorsSourceFetcher
from backend.app.scheduling.types import SourceDefinition, SourceType

NOW = datetime(2026, 11, 28, 2, 0, tzinfo=timezone.utc)

DESCRIPTION = ("&lt;p&gt;&lt;strong&gt;Requisition #:&lt;/strong&gt; 101&lt;br&gt;We build fictional software. "
               "A bachelor&amp;#39;s degree in computer science is required.&lt;/p&gt;")


def item(posting, title, place):
    return (f"<item><title>{title} ({place})</title><description><![CDATA[{DESCRIPTION}]]></description>"
            f"<link>https://jobs.zephyrlabs.example/job/Denver-Software-Engineer-CO-80202/{posting}/</link>"
            f"<guid>{posting}</guid><g:id>{posting}</g:id><g:employer>Zephyr Labs</g:employer>"
            f"<g:location>{place}</g:location></item>")


FEED = ('<?xml version="1.0" encoding="UTF-8" ?><rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>'
        + item("1453084400", "Software Engineer I", "Denver, CO, US, 80202")
        + item("1453084401", "Data Engineer", "Austin, TX, US")
        + item("1453084400", "Software Engineer I", "Denver, CO, US, 80202")
        + "</channel></rss>").encode()


def test_the_feed_is_the_whole_board_with_each_posting_whole():
    jobs = sf.parse_feed(FEED, company_name="Zephyr Labs")
    assert [job.external_id for job in jobs] == ["1453084400", "1453084401"]
    first = jobs[0]
    assert first.source == "successfactors" and first.company == "Zephyr Labs"
    assert first.title == "Software Engineer I" and first.location == "Denver, CO, US"
    assert first.official_url == "https://jobs.zephyrlabs.example/job/Denver-Software-Engineer-CO-80202/1453084400/"
    assert "bachelor's degree" in first.description and "<p>" not in first.description


@pytest.mark.parametrize("body", [
    b"<html><body>Careers</body></html>",
    b'<?xml version="1.0"?><urlset></urlset>',
    b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
    b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "y">]><rss><channel>&x;</channel></rss>',
])
def test_anything_but_a_job_feed_with_postings_raises_so_nothing_closes(body):
    with pytest.raises(sf.NotASuccessFactorsFeed):
        sf.parse_feed(body, company_name="Zephyr Labs")


def client(status=200, body=FEED, etag='"v1"'):
    seen = []

    def handler(request):
        seen.append(request)
        if request.headers.get("if-none-match") == etag:
            return httpx.Response(304, headers={"etag": etag})
        return httpx.Response(status, content=body, headers={"etag": etag})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_a_read_asks_once_honestly_and_an_unchanged_feed_costs_nothing():
    http, seen = client()
    jobs, unchanged, validators = sf.fetch_successfactors_jobs(source_account="jobs.zephyrlabs.example",
                                                               company_name="Zephyr Labs", client=http)
    assert len(jobs) == 2 and not unchanged and validators.etag == '"v1"'
    assert str(seen[0].url) == "https://jobs.zephyrlabs.example/sitemap.xml"
    assert seen[0].headers["user-agent"] == sf.USER_AGENT
    again, unchanged, _ = sf.fetch_successfactors_jobs(source_account="jobs.zephyrlabs.example",
                                                       company_name="Zephyr Labs", client=http, validators=validators)
    assert unchanged and again == []
    with pytest.raises(httpx.HTTPStatusError):
        sf.fetch_successfactors_jobs(source_account="jobs.zephyrlabs.example", company_name="Zephyr Labs",
                                     client=client(status=429)[0])
    with pytest.raises(ValueError):
        sf.board_host("not a host/../x")


def test_the_dispatcher_reads_one_board_by_its_host():
    source = SourceDefinition(source_type=SourceType.SUCCESSFACTORS, source_account="jobs.zephyrlabs.example",
                              company_name="Zephyr Labs", poll_interval_seconds=900)
    http, _seen = client()

    def fetcher(**kwargs):
        return sf.fetch_successfactors_jobs(client=http, **kwargs)

    snapshot = SuccessFactorsSourceFetcher(fetcher=fetcher, clock=lambda: NOW)(source)
    assert snapshot.complete and len(snapshot.jobs) == 2 and snapshot.etag == '"v1"'


def test_a_posting_link_names_the_board_and_freehire_entries_map_to_it():
    found = detect_source_from_url("https://jobs.zephyrlabs.example/job/Denver-Software-Engineer-CO-80202/1453084400/")
    assert found.source_type == SourceType.SUCCESSFACTORS and found.source_account == "jobs.zephyrlabs.example"
    assert detect_source_from_url("https://www.linkedin.com/job/denver-engineer/1453084400/") is None
    assert detect_source_from_url("https://careers.quill.example/job/denver/engineer/quill/1453084400") is None
    assert board_of({"source": "successfactors", "external_id": "jobs.zephyrlabs.example:1453084400", "url": ""}) == (
        "successfactors", "jobs.zephyrlabs.example", "jobs.zephyrlabs.example")
    (target,) = read_targets("successfactors", "jobs.zephyrlabs.example", None)
    assert target.host == "jobs.zephyrlabs.example" and "/sitemap.xml" in target.paths
