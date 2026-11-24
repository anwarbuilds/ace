"""Workable's public job file, read as pointers (DIS-05). Every company, posting and link here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from xml.etree import ElementTree

from backend.app.adapters import workable_feed as wf
from backend.app.coverage.host_policy import read_targets
from backend.app.coverage.leads import WORKABLE_FILE, gather_evidence
from backend.app.db.base import Base
from backend.app.db.models import JobRecord
from backend.app.persistence.repository import JobRepository
from backend.app.scheduling.dispatcher import (
    WorkableFeedSourceFetcher,
    _held_workable_postings,
)
from backend.app.scheduling.types import SourceDefinition, SourceType
from backend.app.workflows.source_snapshot import run_source_snapshot_workflow

NOW = datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc)

PAD = (
    "We build reliable software for fictional customers. You will write and review code, design services and help "
    "operate what you ship. A bachelor's degree in computer science or a related field is required, with zero to "
    "two years of experience. Python, SQL and a willingness to learn matter more than any one framework. "
) * 2


def job_xml(code, title, *, company="Zephyr Labs", country="US", jobtype="Full-time", city="Denver", state="CO",
            remote="false", url=None, description=PAD):
    url = url or f"https://apply.workable.com/j/{code}"
    return (
        "<job>"
        f"<title><![CDATA[{title}]]></title>"
        "<date><![CDATA[Mon, 23 Nov 2026 15:30:00 UTC]]></date>"
        f"<referencenumber><![CDATA[{code}]]></referencenumber>"
        f"<url><![CDATA[{url}]]></url>"
        f"<company><![CDATA[{company}]]></company>"
        f"<city><![CDATA[{city}]]></city><state><![CDATA[{state}]]></state>"
        f"<country><![CDATA[{country}]]></country><remote><![CDATA[{remote}]]></remote>"
        "<postalcode><![CDATA[]]></postalcode>"
        f"<description><![CDATA[<p>{description}</p><ul><li>Python</li></ul>]]></description>"
        "<education><![CDATA[Bachelor's Degree]]></education>"
        f"<jobtype><![CDATA[{jobtype}]]></jobtype>"
        "<category><![CDATA[Engineering]]></category><experience><![CDATA[Entry level]]></experience>"
        "<website><![CDATA[https://zephyrlabs.example]]></website>"
        "</job>"
    )


def feed(*jobs: str, close: bool = True) -> bytes:
    body = '<?xml version="1.0" encoding="utf-8"?><source><publisher>Workable</publisher>' + "".join(jobs)
    return (body + ("</source>" if close else "")).encode()


MIXED = (
    job_xml("AB12CD34EF", "Software Engineer, New Grad"),
    job_xml("BC23DE45FA", "Software Engineer", company="Quill Works", remote="true", city="", state="TX"),
    job_xml("CD34EF56AB", "Software Engineer", country="CA", city="Toronto", state="ON"),
    job_xml("DE45FA67BC", "Software Engineer", jobtype="Contract"),
    job_xml("EF56AB78CD", "Carwash Detailer"),
    job_xml("FA67BC89DE", "Data Engineer", jobtype=""),
    job_xml("0A1B2C3D4E", "Software Engineer", url="https://apply.workable.com/j/FFFFFFFFFF"),
)


def every_title(title: str, company: str) -> bool:
    return "Carwash" not in title


def chunks(data: bytes, size: int = 97):
    for start in range(0, len(data), size):
        yield data[start:start + size]


def test_the_file_is_read_entry_by_entry_and_must_arrive_whole():
    entries = list(wf.entries(chunks(feed(*MIXED))))
    assert [entry["referencenumber"] for entry in entries][:2] == ["AB12CD34EF", "BC23DE45FA"]
    assert len(entries) == len(MIXED)
    assert entries[0]["country"] == "US" and "<p>" in entries[0]["description"]

    with pytest.raises((wf.IncompleteWorkableFeed, ElementTree.ParseError)):
        list(wf.entries(chunks(feed(*MIXED, close=False))))

    truncated = feed(*MIXED)[:-200]
    with pytest.raises((wf.IncompleteWorkableFeed, ElementTree.ParseError)):
        list(wf.entries(chunks(truncated)))


def test_a_file_declaring_entities_is_refused():
    unsafe = b'<?xml version="1.0"?><!DOCTYPE source [<!ENTITY x "y">]><source>&x;</source>'
    with pytest.raises(wf.UnsafeWorkableFeed):
        list(wf.entries([unsafe]))


def test_only_us_full_time_or_unstated_postings_the_gate_could_pass_are_kept():
    stats = wf.FeedStats()
    kept = [job for entry in wf.entries([feed(*MIXED)])
            if (job := wf.posting(entry, could_pass=every_title, stats=stats)) is not None]
    assert [job.external_id for job in kept] == ["AB12CD34EF", "BC23DE45FA", "FA67BC89DE"]
    first, remote, unstated = kept
    assert first.source == "workable_feed" and first.company == "Zephyr Labs"
    assert first.location == "Denver, CO, United States"
    assert remote.location == "TX, United States (Remote)"
    assert first.official_url == "https://apply.workable.com/j/AB12CD34EF"
    assert first.posted_at == datetime(2026, 11, 23, 15, 30, tzinfo=timezone.utc)
    assert first.employment_type == "full-time" and unstated.employment_type is None
    assert "<p>" not in first.description and "Python" in first.description
    # The link and the code must name the same posting.
    assert stats.us_kept_type == 4 and stats.could_pass == 3


def test_a_posting_code_is_read_from_any_workable_link():
    assert wf.posting_code("https://apply.workable.com/j/ab12cd34ef") == "AB12CD34EF"
    assert wf.posting_code("https://apply.workable.com/zephyr-labs/j/AB12CD34EF/") == "AB12CD34EF"
    assert wf.posting_code("https://boards.greenhouse.example/zephyr/jobs/1") is None


class FileServer:
    """Answers the file request; records the headers ACE sent."""

    def __init__(self, body: bytes, *, status: int = 200, last_modified: str = "Tue, 24 Nov 2026 00:15:15 GMT"):
        self.body, self.status, self.last_modified, self.seen = body, status, last_modified, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.headers.get("if-modified-since") == self.last_modified:
            return httpx.Response(304, headers={"last-modified": self.last_modified})
        if self.status != 200:
            return httpx.Response(self.status, text="Too many requests")
        return httpx.Response(200, content=gzip.compress(self.body),
                              headers={"content-encoding": "gzip", "content-type": "application/xml",
                                       "last-modified": self.last_modified})


def client_for(server: FileServer) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(server))


def test_a_read_sends_an_honest_compressed_request_and_drops_what_ace_holds():
    server = FileServer(feed(*MIXED))
    jobs, unchanged, validators, stats = wf.fetch_workable_feed_jobs(
        could_pass=every_title, held=lambda codes: {"BC23DE45FA"} & codes,
        client=client_for(server), min_postings=1)
    assert not unchanged and [job.external_id for job in jobs] == ["AB12CD34EF", "FA67BC89DE"]
    assert stats.postings == len(MIXED) and stats.held == 1 and stats.copies == 2
    assert validators.last_modified == "Tue, 24 Nov 2026 00:15:15 GMT"
    sent = server.seen[0].headers
    assert sent["user-agent"] == wf.USER_AGENT and sent["accept-encoding"] == "gzip"
    assert str(server.seen[0].url) == wf.FEED_URL

    # Unchanged since the last read: nothing downloaded, nothing changes.
    again, unchanged, _validators, _stats = wf.fetch_workable_feed_jobs(
        could_pass=every_title, client=client_for(server), validators=validators, min_postings=1)
    assert unchanged and again == []


def test_a_refusal_or_a_short_file_raises_so_nothing_closes():
    with pytest.raises(httpx.HTTPStatusError):
        wf.fetch_workable_feed_jobs(could_pass=every_title, client=client_for(FileServer(b"", status=429)))
    with pytest.raises(wf.IncompleteWorkableFeed):
        wf.fetch_workable_feed_jobs(could_pass=every_title, client=client_for(FileServer(feed(*MIXED))),
                                    min_postings=len(MIXED) + 1)


@pytest.fixture(name="sessions")
def fixture_sessions(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    monkeypatch.setattr("backend.app.db.session.SessionLocal", factory)
    return factory


def stored(session, source, account, code, *, url, active=True, company="Zephyr Labs"):
    session.add(JobRecord(source=source, source_account=account, company=company, external_id=code,
                          title="Software Engineer", location="Denver, CO, United States", description="",
                          official_url=url, content_hash="x", is_active=active))


def test_ace_holds_a_posting_read_from_the_board_or_copied_by_another_list(sessions):
    with sessions.begin() as session:
        stored(session, "workable", "zephyr-labs", "AB12CD34EF", url="https://apply.workable.com/zephyr-labs/j/AB12CD34EF/")
        stored(session, "workable", "zephyr-labs", "CD34EF56AB", url="https://apply.workable.com/zephyr-labs/j/CD34EF56AB/",
               active=False)
        stored(session, "simplify", "new-grad", "s-1", url="https://apply.workable.com/quill-works/j/BC23DE45FA")
    held = _held_workable_postings({"AB12CD34EF", "BC23DE45FA", "CD34EF56AB", "FA67BC89DE"})
    assert held == {"AB12CD34EF", "BC23DE45FA"}


def test_the_dispatcher_reads_the_file_as_one_source():
    server = FileServer(feed(*MIXED))
    source = SourceDefinition(source_type=SourceType.WORKABLE_FEED, source_account=wf.ACCOUNT,
                              company_name="Workable job file", poll_interval_seconds=3600)

    def fetcher(**kwargs):
        return wf.fetch_workable_feed_jobs(client=client_for(server), min_postings=1, **kwargs)

    snapshot = WorkableFeedSourceFetcher(fetcher=fetcher, could_pass=every_title, held=lambda codes: set(),
                                         clock=lambda: NOW)(source)
    assert snapshot.complete and not snapshot.unchanged
    assert {job.external_id for job in snapshot.jobs} == {"AB12CD34EF", "BC23DE45FA", "FA67BC89DE"}
    assert snapshot.last_modified == "Tue, 24 Nov 2026 00:15:15 GMT"
    with pytest.raises(ValueError):
        WorkableFeedSourceFetcher(fetcher=fetcher)(SourceDefinition(
            source_type=SourceType.SIMPLIFY, source_account="new-grad", company_name="x", poll_interval_seconds=900))


def test_a_whole_file_closes_only_its_own_copies_never_a_board_posting(sessions):
    copies = [wf.posting(entry, could_pass=every_title) for entry in wf.entries([feed(*MIXED)])]
    copies = [job for job in copies if job is not None]
    with sessions.begin() as session:
        stored(session, "workable", "zephyr-labs", "AB12CD34EF", url="https://apply.workable.com/zephyr-labs/j/AB12CD34EF/")
    with sessions.begin() as session:
        run_source_snapshot_workflow(JobRepository(session), source="workable_feed", source_account=wf.ACCOUNT,
                                     jobs=copies, observed_at=NOW)
    with sessions.begin() as session:
        # The next file no longer lists two of them.
        run_source_snapshot_workflow(JobRepository(session), source="workable_feed", source_account=wf.ACCOUNT,
                                     jobs=copies[:1], observed_at=NOW.replace(hour=3))
    with sessions() as session:
        rows = {(row.source, row.external_id): row.is_active for row in session.scalars(select(JobRecord))}
    assert rows[("workable", "AB12CD34EF")] is True
    assert rows[("workable_feed", "AB12CD34EF")] is True
    assert rows[("workable_feed", "BC23DE45FA")] is False and rows[("workable_feed", "FA67BC89DE")] is False


def test_its_companies_are_leads_from_the_workable_file_and_it_is_read_where_robots_allows(sessions):
    with sessions.begin() as session:
        stored(session, "workable_feed", wf.ACCOUNT, "AB12CD34EF", url="https://apply.workable.com/j/AB12CD34EF",
               company="Orbit Pine")
    with sessions() as session:
        evidence = gather_evidence(session)
    assert WORKABLE_FILE in evidence["orbit pine"].details
    assert evidence["orbit pine"].origin() == WORKABLE_FILE
    (target,) = read_targets("workable_feed", wf.ACCOUNT, None)
    assert target.host == "www.workable.com" and target.paths == ("/boards/workable.xml",)
