"""FreeHire's boards become leads, once a week (DIS-02). Every company, board and posting here is fictional."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.leads import (
    AGENCY,
    CHECKING,
    DORMANT,
    FREEHIRE,
    POLLING,
    check_due_leads,
    leads_report,
    sync_leads,
)
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord
from backend.app.discovery import freehire as fh

NOW = datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)


def posting(platform, external_id, url, company):
    return {"source": platform, "external_id": external_id, "url": url + "?utm_source=freehire.me", "company": company,
            "title": "Software Engineer I"}


ZEPHYR = posting("greenhouse", "zephyrlabs:4012345", "https://careers.zephyrlabs.example/jobs/4012345", "Zephyr Labs")
QUILL = posting("lever", "quillworks:1b2c3d4e", "https://jobs.lever.co/quillworks/1b2c3d4e", "Quill Works")
ORBIT = posting("workday", "orbitpine.wd5.myworkdayjobs.com/careers:/job/x", "https://orbitpine.wd5.myworkdayjobs.com/Careers/job/Denver-CO/Software-Engineer_R1",
                "Orbit Pine")


def response(items, total, *, status=200, remaining="250", ignored=None, url=fh.API):
    meta = {"total": total, "limit": 100, "offset": 0}
    if ignored:
        meta["ignored_params"] = ignored
    return httpx.Response(status, json={"meta": meta, "data": items},
                          headers={"x-ratelimit-remaining": remaining, "x-ratelimit-reset": "42"},
                          request=httpx.Request("GET", url))


class FakeApi:
    """Answers per platform from a dict; records every query."""

    def __init__(self, pages: dict[str, list[list[dict]]], status: int = 200, **kwargs):
        self.pages, self.status, self.kwargs, self.asked = pages, status, kwargs, []

    def __call__(self, url):
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self.asked.append(query)
        pages = self.pages.get(query["source"], [[]])
        index = int(query["offset"]) // 100
        total = sum(len(p) for p in pages) if len(pages) == 1 else 100 * (len(pages) - 1) + len(pages[-1])
        return response(pages[index] if index < len(pages) else [], total, status=self.status, **self.kwargs)


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_each_posting_names_its_employers_board():
    assert fh.board_of(ZEPHYR) == ("greenhouse", "zephyrlabs", "boards.greenhouse.io")
    assert fh.board_of(QUILL)[:2] == ("lever", "quillworks")
    assert fh.board_of(ORBIT) == ("workday", "orbitpine/Careers", "orbitpine.wd5.myworkdayjobs.com")
    # A platform FreeHire reaches through a proxy or a disguise is never used, nor one ACE has no reader for.
    assert fh.board_of(posting("workable", "zephyr:1", "https://apply.workable.com/zephyr/j/1", "Zephyr Labs")) is None
    assert fh.board_of(posting("paycor", "orbit:9", "https://recruitingbypaycor.com/career/9", "Orbit Pine")) is None
    # iCIMS has a reader since 2026-11-28 (DIS-09): its site's host names the board.
    assert fh.board_of(posting("icims", "orbit:9", "https://careers-orbit.icims.com/jobs/9/job", "Orbit Pine")) == (
        "icims", "careers-orbit.icims.com", "careers-orbit.icims.com")
    # A link that names another platform than FreeHire says is not trusted.
    assert fh.board_of(posting("lever", "1", "https://jobs.ashbyhq.com/quill/1", "Quill Works")) is None


def test_no_bypassed_platform_is_ever_asked_for():
    assert not set(fh.PLATFORMS) & fh.BYPASSED
    api = FakeApi({})
    fh.harvest(api, pause=lambda s: None)
    assert {q["source"] for q in api.asked} == set(fh.PLATFORMS)
    for query in api.asked:
        assert query["countries"] == "US" and query["employment_type"] == "full_time"


def test_the_harvest_pages_through_and_keeps_one_entry_per_board():
    many = [dict(ZEPHYR, external_id=f"zephyrlabs:{n}") for n in range(100)]
    api = FakeApi({"greenhouse": [many, [ZEPHYR]], "lever": [[QUILL, QUILL]], "workday": [[ORBIT]]})
    found = fh.harvest(api, pause=lambda s: None)
    assert [q["offset"] for q in api.asked if q["source"] == "greenhouse"] == ["0", "100"]
    assert set(found.boards) == {("greenhouse", "zephyrlabs"), ("lever", "quillworks"), ("workday", "orbitpine/careers")}
    assert found.boards[("greenhouse", "zephyrlabs")].postings == 101
    assert found.postings == 104 and found.unmapped == 0


def test_it_paces_itself_and_waits_when_the_budget_runs_low():
    waits = []
    fh.harvest(FakeApi({}, remaining="5"), pause=waits.append, platforms=["greenhouse"])
    assert waits == [42.0]
    waits.clear()
    fh.harvest(FakeApi({}), pause=waits.append, platforms=["greenhouse"])
    assert waits == [fh.PAUSE_SECONDS]


def test_a_refusal_stops_the_harvest_and_an_ignored_filter_is_not_trusted():
    with pytest.raises(fh.Refused):
        fh.harvest(FakeApi({}, status=429), pause=lambda s: None)
    with pytest.raises(ValueError):
        fh.harvest(FakeApi({}, ignored=["category"]), pause=lambda s: None)


def harvest_of(*items):
    found = fh.Harvest()
    for item in items:
        source_type, account, host = fh.board_of(item)
        board = fh.Board(source_type, account, host, item["company"], item["source"], 1)
        found.boards[board.key] = board
    return found


def test_boards_ace_holds_or_already_knows_are_left_alone(sessions):
    with sessions.begin() as session:
        session.add(JobSourceRecord(source_type="lever", source_account="quillworks", company_name="Quill Works",
                                    enabled=False, poll_interval_seconds=900, discovery_source="board_probe"))
        session.add(EmployerLead(company_key="orbit pine", company_name="Orbit Pine", origin="network", origin_details=["network"],
                                 state=DORMANT, reason="Read before.", first_seen_at=NOW, next_check_at=NOW + timedelta(days=5),
                                 updated_at=NOW, boards=[{"source_type": "workday", "source_account": "orbitpine/Careers",
                                                          "source_host": "orbitpine.wd5.myworkdayjobs.com"}]))
    with sessions.begin() as session:
        counts = fh.remember(session, harvest_of(ZEPHYR, QUILL, ORBIT), now=NOW)
    assert counts["held_by_ace"] == 1 and counts["already_leads"] == 1 and counts["leads_new"] == 1
    with sessions() as session:
        row = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_name == "Zephyr Labs"))
        assert row.origin == FREEHIRE and row.state == CHECKING and row.next_check_at.replace(tzinfo=timezone.utc) == NOW
        assert row.boards == [{"source_type": "greenhouse", "source_account": "zephyrlabs", "source_host": "boards.greenhouse.io"}]
        assert "freehire:greenhouse" in row.origin_details
        # Registering is the lead check's job, after it reads the board itself.
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 1


def test_a_new_board_on_a_known_company_goes_first_and_a_staffing_lead_stays_out(sessions):
    with sessions.begin() as session:
        for name, state in (("Zephyr Labs", DORMANT), ("Quill Works", AGENCY)):
            session.add(EmployerLead(company_key=normalise_company(name), company_name=name, origin="search", origin_details=["search"],
                                     state=state, reason="Before.", first_seen_at=NOW, updated_at=NOW,
                                     next_check_at=NOW + timedelta(days=30),
                                     boards=[{"source_type": "ashby", "source_account": "old", "source_host": None}]))
    with sessions.begin() as session:
        fh.remember(session, harvest_of(ZEPHYR, QUILL), now=NOW)
    with sessions() as session:
        zephyr = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_name == "Zephyr Labs"))
        assert zephyr.boards[0]["source_account"] == "zephyrlabs" and zephyr.state == CHECKING
        quill = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_name == "Quill Works"))
        assert quill.state == AGENCY and quill.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=30)


def test_the_lead_check_reads_and_adds_a_freehire_board_and_the_ledger_keeps_its_origin(sessions, tmp_path):
    from backend.scripts.register_network_boards import Candidate, Outcome, register

    with sessions.begin() as session:
        fh.remember(session, harvest_of(ZEPHYR), now=NOW)
    read = []

    def assess(board, company):
        read.append((board["source_type"], board["source_account"], company))
        return Outcome(candidate=Candidate(source_type="greenhouse", source_account="zephyrlabs", company=company),
                       added=True, reason="hiring US engineers", jobs=4, us_engineering=2, passing=1)

    summary = check_due_leads(sessions, now=lambda: NOW, assess_board=assess, pause=lambda s: None,
                              diagnose_name=lambda company: pytest.fail("no name search"),
                              refusal=lambda session, target, now: None,
                              register_board=lambda session, outcome: register(session, outcome, now=NOW, origin="lead_ledger"))
    assert read == [("greenhouse", "zephyrlabs", "Zephyr Labs")] and summary.added == 1
    network = tmp_path / "network.json"
    network.write_text(json.dumps({"boards": []}))
    with sessions.begin() as session:
        sync_leads(session, now=NOW, network_file=network)
    with sessions() as session:
        row = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_name == "Zephyr Labs"))
        assert row.state == POLLING and row.origin == FREEHIRE
        report = leads_report(session)
        assert any(item["origin"] == FREEHIRE and item["label"] == "FreeHire" for item in report["origins"])


def scored(sessions, day=date(2026, 11, 22), summary=None):
    with sessions.begin() as session:
        session.add(RecallRunRecord(day=day, checked_at=NOW, summary=summary or {"total": {"listed": 1}}, missed=[]))


def test_it_runs_once_a_week_after_the_score_and_records_what_it_did(sessions):
    args = dict(allows=lambda url: True, pause=lambda s: None)
    assert fh.harvest_if_due(sessions, now=NOW, get=FakeApi({}), **args) is None  # no score yet
    scored(sessions)
    mark = fh.harvest_if_due(sessions, now=NOW, get=FakeApi({"greenhouse": [[ZEPHYR]]}), **args)
    assert mark["finished"] and mark["leads_new"] == 1 and mark["requests"] == len(fh.PLATFORMS)
    with sessions() as session:
        assert session.scalar(sa.select(RecallRunRecord.summary))["freehire"]["leads_new"] == 1
    assert fh.harvest_if_due(sessions, now=NOW + timedelta(days=3), get=FakeApi({}), **args) is None
    scored(sessions, day=date(2026, 11, 29))
    assert fh.harvest_if_due(sessions, now=NOW + timedelta(days=7, hours=1), get=FakeApi({}), **args)["finished"]


def test_a_refused_or_failed_harvest_is_tried_again_the_next_day_not_the_same_day(sessions):
    scored(sessions)
    args = dict(pause=lambda s: None, get=FakeApi({}, status=429))
    first = fh.harvest_if_due(sessions, now=NOW, allows=lambda url: True, **args)
    assert first["finished"] is False and "429" in first["stopped"]
    assert fh.harvest_if_due(sessions, now=NOW + timedelta(hours=2), allows=lambda url: True, **args) is None
    robots = fh.harvest_if_due(sessions, now=NOW + timedelta(days=1), allows=lambda url: False, get=FakeApi({}),
                               pause=lambda s: None)
    assert robots["stopped"] == "freehire's robots rules refuse ace"
