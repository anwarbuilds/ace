"""BambooHR and Rippling boards (DIS-09). Every company, posting and board here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from backend.app.adapters import bamboohr, rippling
from backend.app.coverage.host_policy import read_targets
from backend.app.scheduling.dispatcher import ListedBoardSourceFetcher
from backend.app.scheduling.types import SourceDefinition, SourceType
from backend.app.verification.employer_page import READ, Reading

NOW = datetime(2026, 11, 28, 5, 0, tzinfo=timezone.utc)

DESCRIPTION = "<p>We build fictional software. A bachelor's degree in computer science is required.</p>"


class MemoryStore:
    """The shared reading store, in memory."""

    def __init__(self):
        self.rows = {}

    def load(self, urls):
        return {url: self.rows[url] for url in urls if url in self.rows}

    def save(self, readings, *, moment):
        self.rows.update({url: (reading, moment) for url, reading in readings.items()})


def transport(routes, asked):
    def handler(request):
        asked.append(str(request.url))
        body = routes.get(str(request.url))
        if body is None:
            return httpx.Response(404, json={})
        return httpx.Response(200, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler))


BAMBOO_LIST = {"meta": {"totalCount": 2}, "result": [
    {"id": "11", "jobOpeningName": "Software Engineer I", "employmentStatusLabel": "Full-Time",
     "location": {"city": "Golden", "state": "Colorado"}, "atsLocation": {"country": "United States"}},
    {"id": "12", "jobOpeningName": "Office Manager", "employmentStatusLabel": "Part-Time",
     "location": {"city": "Golden", "state": "Colorado"}, "atsLocation": {}},
]}


def test_bamboohr_lists_the_board_and_reads_only_promising_descriptions_once():
    base = "https://zephyr.bamboohr.com/careers"
    routes = {f"{base}/list": BAMBOO_LIST,
              f"{base}/11/detail": {"result": {"jobOpening": {"description": DESCRIPTION}}}}
    asked, store = [], MemoryStore()
    http = transport(routes, asked)
    jobs = bamboohr.fetch_bamboohr_jobs(source_account="zephyr", company_name="Zephyr Labs", client=http,
                                        should_fetch_detail=lambda title: "Engineer" in title, store=store, now=lambda: NOW)
    assert [job.external_id for job in jobs] == ["11", "12"]
    first, second = jobs
    assert first.official_url == f"{base}/11" and "bachelor's degree" in first.description
    assert first.location == "Golden, Colorado, United States" and first.employment_type == "full-time"
    assert second.description == "" and second.employment_type == "part-time"
    assert f"{base}/12/detail" not in asked
    asked.clear()
    bamboohr.fetch_bamboohr_jobs(source_account="zephyr", company_name="Zephyr Labs", client=http,
                                 should_fetch_detail=lambda title: "Engineer" in title, store=store, now=lambda: NOW)
    assert asked == [f"{base}/list"]
    assert bamboohr.company_name_of(lambda url: {"result": {"name": "Zephyr Labs"}}, "zephyr") == "Zephyr Labs"
    with pytest.raises(ValueError):
        bamboohr.board_account("www")


RIPPLING_LIST = [
    {"uuid": "a1", "name": "Machine Learning Engineer", "workLocation": {"label": "Chicago, IL"},
     "url": "https://ats.rippling.com/zephyr/jobs/a1"},
    {"uuid": "b2", "name": "Account Executive", "workLocation": {"label": "Remote (US)"}},
]


def test_rippling_lists_the_board_and_reads_the_role_before_the_company_text():
    api = "https://api.rippling.com/platform/api/ats/v1/board/zephyr/jobs"
    routes = {api: RIPPLING_LIST,
              f"{api}/a1": {"companyName": "Zephyr Labs", "description": {"company": "<p>About Zephyr.</p>",
                                                                          "role": DESCRIPTION}}}
    asked = []
    jobs = rippling.fetch_rippling_jobs(source_account="zephyr", company_name="Zephyr Labs",
                                        client=transport(routes, asked), should_fetch_detail=lambda t: "Engineer" in t,
                                        store=MemoryStore(), now=lambda: NOW)
    assert [job.external_id for job in jobs] == ["a1", "b2"]
    assert jobs[0].official_url == "https://ats.rippling.com/zephyr/jobs/a1" and jobs[0].location == "Chicago, IL"
    assert jobs[0].description.index("bachelor") < jobs[0].description.index("About Zephyr")
    assert jobs[1].description == "" and f"{api}/b2" not in asked
    assert rippling.company_name_of(lambda url: RIPPLING_LIST if url == api else routes[f"{api}/a1"], "zephyr") == "Zephyr Labs"


def test_both_are_read_by_the_scheduler_where_robots_allow():
    source = SourceDefinition(source_type=SourceType.BAMBOOHR, source_account="zephyr", company_name="Zephyr Labs",
                              poll_interval_seconds=900)
    seen = {}

    def fetcher(**kwargs):
        seen.update(kwargs)
        return []

    snapshot = ListedBoardSourceFetcher(SourceType.BAMBOOHR, fetcher=fetcher, clock=lambda: NOW)(source)
    assert snapshot.complete and seen["source_account"] == "zephyr" and callable(seen["should_fetch_detail"])
    with pytest.raises(ValueError):
        ListedBoardSourceFetcher(SourceType.RIPPLING, fetcher=fetcher)(source)
    (bamboo,) = read_targets("bamboohr", "zephyr", None)
    assert bamboo.host == "zephyr.bamboohr.com" and "/careers/list" in bamboo.paths
    (ripple,) = read_targets("rippling", "zephyr", None)
    assert ripple.host == "api.rippling.com" and ripple.paths == ("/platform/api/ats/v1/board/zephyr/jobs",)
