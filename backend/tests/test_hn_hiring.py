"""Hacker News "Who is hiring?" companies become leads (DIS-11). Every company, comment and link here is fictional."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.leads import CHECKING, HN, NOREADER, ORIGIN_LABELS
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord
from backend.app.discovery import hn_hiring as hn
from backend.app.discovery.yc_names import site_hints

NOW = datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc)

ZEPHYR = ('Zephyr Labs (YC S21) | Backend Engineer, New Grad | New York, NY | Full-time | '
          '<a href="https:&#x2F;&#x2F;jobs.ashbyhq.com&#x2F;zephyr" rel="nofollow">https:&#x2F;&#x2F;jobs.ashbyhq.com&#x2F;zephyr</a>'
          '<p>We build fictional things. Email jobs@zephyrlabs.example')
QUILL = 'Quill Works | Software Engineer | Remote (US) | https:&#x2F;&#x2F;quillworks.example&#x2F;careers<p>Small team.'
CHATTY = 'We are hiring lots of engineers this month, come talk to us<p>No pipes here.'
ORBIT = ('Orbit Pine | Data Engineer | Denver | '
         '<a href="https:&#x2F;&#x2F;boards.greenhouse.io&#x2F;orbitpine&#x2F;jobs&#x2F;4001">apply</a>')


def test_a_comment_gives_its_company_and_board_and_nothing_else():
    post = hn.post_of(ZEPHYR)
    assert post.company == "Zephyr Labs" and post.boards == [("ashby", "zephyr", "jobs.ashbyhq.com")]
    assert post.host is None
    quill = hn.post_of(QUILL)
    assert quill.company == "Quill Works" and quill.boards == [] and quill.host == "quillworks.example"
    assert hn.post_of(CHATTY) is None


class FakeHN:
    def __init__(self, items, *, status=200):
        self.items, self.status, self.asked = items, status, []

    def __call__(self, url):
        self.asked.append(url)
        if self.status != 200:
            return httpx.Response(self.status, request=httpx.Request("GET", url))
        key = url.rsplit("/", 1)[1].removesuffix(".json")
        body = self.items["user"] if url.endswith(f"/user/{hn.ACCOUNT}.json") else self.items.get(int(key))
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))


def items(kids=(101, 102, 103)):
    return {
        "user": {"id": hn.ACCOUNT, "submitted": [902, 901, 900]},
        902: {"id": 902, "title": "Ask HN: Who wants to be hired? (December 2026)", "kids": [999]},
        901: {"id": 901, "title": "Ask HN: Who is hiring? (December 2026)", "kids": list(kids)},
        101: {"id": 101, "text": ZEPHYR},
        102: {"id": 102, "text": QUILL},
        103: {"id": 103, "text": CHATTY},
        104: {"id": 104, "text": ORBIT},
        105: {"id": 105, "deleted": True},
    }


def test_only_the_hiring_thread_is_read_and_only_comments_newer_than_the_last_read():
    api = FakeHN(items())
    first = hn.read(api, pause=lambda s: None)
    assert first.thread == 901 and first.new_comments == 3 and first.last_id == 103
    assert [post.company for post in first.posts] == ["Zephyr Labs", "Quill Works"]
    assert not any(url.endswith("/999.json") for url in api.asked)
    api = FakeHN(items(kids=(101, 102, 103, 104, 105)))
    later = hn.read(api, after=103, thread=901, pause=lambda s: None)
    assert later.new_comments == 2 and [post.company for post in later.posts] == ["Orbit Pine"]
    assert not any(url.endswith(("/101.json", "/102.json", "/103.json")) for url in api.asked)
    # A new month starts from its first comment.
    fresh = hn.read(FakeHN(items()), after=500, thread=800, pause=lambda s: None)
    assert fresh.new_comments == 3


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_companies_ace_does_not_read_become_leads_with_their_board_or_website(sessions):
    with sessions.begin() as session:
        session.add(JobSourceRecord(source_type="greenhouse", source_account="orbitpine", company_name="Orbit Pine",
                                    enabled=True, poll_interval_seconds=900, discovery_source="curated_list"))
        session.add(EmployerLead(company_key="quill works", company_name="Quill Works", origin="network",
                                 origin_details=["network"], state=NOREADER, reason="Nothing found.", boards=[],
                                 first_seen_at=NOW, next_check_at=NOW + timedelta(days=30), updated_at=NOW))
    posts = [hn.post_of(text) for text in (ZEPHYR, QUILL, ORBIT)]
    with sessions.begin() as session:
        counts = hn.remember(session, posts, now=NOW)
    assert counts == {"posts": 3, "read_by_ace": 1, "leads_new": 1, "leads_updated": 1, "skipped": 0}
    with sessions() as session:
        rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    zephyr = rows["zephyr"]
    assert zephyr.origin == HN and zephyr.state == CHECKING
    assert zephyr.boards == [{"source_type": "ashby", "source_account": "zephyr", "source_host": "jobs.ashbyhq.com"}]
    quill = rows["quill works"]
    assert quill.origin == "network" and quill.state == CHECKING and site_hints(quill.origin_details) == ("quillworks.example",)
    assert ORIGIN_LABELS[HN] == "Hacker News"


def scored(sessions, day=date(2026, 12, 1)):
    with sessions.begin() as session:
        session.add(RecallRunRecord(day=day, checked_at=NOW, summary={"total": {"listed": 1}}, missed=[]))


def test_it_reads_every_six_hours_and_remembers_where_it_stopped(sessions):
    scored(sessions)
    args = dict(allows=lambda url: True, pause=lambda s: None)
    first = hn.read_if_due(sessions, now=NOW, get=FakeHN(items()), **args)
    assert first["finished"] and first["thread"] == 901 and first["last_id"] == 103 and first["leads_new"] == 2
    assert hn.read_if_due(sessions, now=NOW + timedelta(hours=5), get=FakeHN(items()), **args) is None
    later_api = FakeHN(items(kids=(101, 102, 103, 104)))
    later = hn.read_if_due(sessions, now=NOW + timedelta(hours=6, minutes=1), get=later_api, **args)
    assert later["new_comments"] == 1 and later["last_id"] == 104
    refused = hn.read_if_due(sessions, now=NOW + timedelta(hours=13), get=FakeHN(items(), status=429), **args)
    assert refused["finished"] is False and "429" in refused["stopped"] and refused["last_id"] == 104
    robots = hn.read_if_due(sessions, now=NOW + timedelta(hours=20), allows=lambda url: False, get=FakeHN(items()),
                            pause=lambda s: None)
    assert robots["stopped"] == "hacker news's robots rules refuse ace"
