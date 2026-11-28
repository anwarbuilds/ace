"""Paylocity boards (DIS-09). Every company, posting and board here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import httpx
import pytest

from backend.app.adapters import paylocity
from backend.app.coverage.host_policy import read_targets
from backend.app.discovery.detector import detect_source_from_url
from backend.app.scheduling.types import SourceType

NOW = datetime(2026, 11, 28, 7, 0, tzinfo=timezone.utc)
BOARD = "0b1c2d3e-4f50-4a61-8b72-93a4b5c6d7e8"

ROWS = [
    {"JobId": "4001", "JobTitle": "Software Engineer I", "PublishedDate": "2026-11-25T13:22:40-06:00", "IsInternal": False,
     "Description": "Company Description: a short teaser", "JobLocation": {"City": "Durham", "State": "NC", "Country": "USA"},
     "IsRemote": False},
    {"JobId": "4002", "JobTitle": "Office Coordinator", "IsInternal": False, "JobLocation": {"City": "Durham", "State": "NC"},
     "IsRemote": True},
    {"JobId": "4003", "JobTitle": "Internal Transfer", "IsInternal": True},
]

PAGE = "<html><script>window.pageData = " + json.dumps({"Jobs": ROWS}) + ";\n</script></html>"
DETAIL = ('<script type="application/ld+json">{"@type": "JobPosting", "title": "Software Engineer I", '
          '"description": "<p>We build fictional software. A bachelor degree in computer science is required.</p>", '
          '"hiringOrganization": {"@type": "Organization", "name": "Zephyr Labs"}}</script>')


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def load(self, urls):
        return {url: self.rows[url] for url in urls if url in self.rows}

    def save(self, readings, *, moment):
        self.rows.update({url: (reading, moment) for url, reading in readings.items()})


def test_a_board_page_lists_the_board_and_promising_postings_are_read_whole():
    asked = []

    def handler(request):
        asked.append(str(request.url))
        if request.url.path == f"/Recruiting/Jobs/All/{BOARD}":
            return httpx.Response(200, text=PAGE)
        if request.url.path == "/Recruiting/Jobs/Details/4001":
            return httpx.Response(200, text=DETAIL)
        return httpx.Response(404, text="")

    jobs = paylocity.fetch_paylocity_jobs(source_account=BOARD, company_name="Zephyr Labs",
                                          client=httpx.Client(transport=httpx.MockTransport(handler)),
                                          should_fetch_detail=lambda title: "Engineer" in title, store=MemoryStore(),
                                          now=lambda: NOW)
    assert [job.external_id for job in jobs] == ["4001", "4002"]
    first, second = jobs
    assert first.official_url == "https://recruiting.paylocity.com/Recruiting/Jobs/Details/4001"
    assert "bachelor degree" in first.description and first.location == "Durham, NC, United States"
    assert first.posted_at is not None and second.location == "Durham, NC (Remote)" and second.description == ""
    assert not any(url.endswith("/4002") for url in asked)
    assert paylocity.employer_of(DETAIL) == "Zephyr Labs"


def test_a_page_without_its_list_raises_so_nothing_closes():
    with pytest.raises(ValueError):
        paylocity.listed("<html>Maintenance</html>")
    with pytest.raises(ValueError):
        paylocity.board_id("not-a-board")


def test_its_board_address_is_detected_and_robots_paths_are_its_own():
    found = detect_source_from_url(f"https://recruiting.paylocity.com/Recruiting/Jobs/All/{BOARD}")
    assert found.source_type == SourceType.PAYLOCITY and found.source_account == BOARD
    assert detect_source_from_url("https://recruiting.paylocity.com/Recruiting/Jobs/Details/4001") is None
    (target,) = read_targets("paylocity", BOARD, None)
    assert target.host == "recruiting.paylocity.com" and f"/Recruiting/Jobs/All/{BOARD}" in target.paths
