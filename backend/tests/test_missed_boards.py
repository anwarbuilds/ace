"""The boards behind the daily score's missed roles (REC-02). Fictional companies and boards only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage import missed_boards as mb
from backend.app.coverage import recall
from backend.app.db.models import Base, EmployerLead, RecallRunRecord

NOW = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)
GREENHOUSE = "https://boards.greenhouse.io/zephyrlabs/jobs/4012345"
LEVER = "https://jobs.lever.co/quillworks/1b2c3d4e-0000-4000-8000-000000000001"


@dataclass(frozen=True)
class FakeOutcome:
    added: bool
    reason: str
    transient: bool = False


def miss(company, link, reason=recall.READABLE_NOT_ADDED, title="Software Engineer, New Grad"):
    return {"list": "speedyapply", "company": company, "title": title, "location": "Denver, CO",
            "listed_on": "2026-11-21", "link": link, "reason": reason}


def run(rows, *, known=(), allows=lambda *a: True, outcomes=None, limit=mb.BOARDS_PER_DAY, added_ok=True):
    tried = []

    def try_board(source_type, account, company, host):
        tried.append((source_type, account, company))
        value = (outcomes or {}).get(account, FakeOutcome(True, "hiring US engineers"))
        if isinstance(value, Exception):
            raise value
        return value

    fixed, counts = mb.fix_missed(rows, known=set(known), allows=allows, try_board=try_board,
                                  add_board=lambda outcome: added_ok, limit=limit)
    return fixed, counts, tried


def test_a_readable_board_ace_lacks_is_tried_and_added_once():
    rows = [miss("Zephyr Labs", GREENHOUSE), miss("Zephyr Labs", GREENHOUSE, title="Data Engineer I")]
    fixed, counts, tried = run(rows)
    assert tried == [("greenhouse", "zephyrlabs", "Zephyr Labs")]
    assert [row["fix"]["state"] for row in fixed] == [mb.ADDED, mb.ADDED]
    assert counts["boards_added"] == 1 and counts["boards_read"] == 1
    # The row keeps everything the score said about it.
    assert fixed[0]["reason"] == recall.READABLE_NOT_ADDED and fixed[0]["link"] == GREENHOUSE


def test_a_board_the_catalog_holds_is_never_read_again():
    fixed, _, tried = run([miss("Zephyr Labs", GREENHOUSE)], known={("greenhouse", "zephyrlabs")})
    assert tried == [] and fixed[0]["fix"]["state"] == mb.HELD


def test_reasons_that_need_no_read_are_said_plainly():
    rows = [
        miss("Quill Works", LEVER, reason=recall.BOARD_READ),
        miss("Quill Works", LEVER, reason=recall.NOT_READ_LATELY),
        miss("Quill Works", LEVER, reason=recall.OFF_AS_AGENCY),
        miss("Quill Works", LEVER, reason=recall.SWITCHED_OFF),
        miss("Orbit Pine", "https://orbitpine.icims.com/jobs/77/job", reason="Posted on iCIMS, which ace can't read yet"),
        miss("Nobody Known", None, reason=recall.NO_LEAD),
    ]
    fixed, _, tried = run(rows)
    assert tried == []
    assert [row["fix"]["state"] for row in fixed] == [mb.HELD, mb.HELD, mb.OFF, mb.OFF, mb.NO_BOARD, mb.NO_BOARD]
    assert fixed[4]["fix"]["note"] == "Posted on iCIMS, which ace can't read yet"
    assert fixed[5]["fix"]["note"] == recall.NO_LEAD


def test_a_test_list_link_is_never_followed():
    fixed, _, tried = run([miss("Zephyr Labs", "https://vansh.nyc/abc123")])
    assert tried == [] and fixed[0]["fix"]["state"] == mb.NO_BOARD


def test_robots_refusal_and_refusing_platforms_are_not_read():
    smart = "https://jobs.smartrecruiters.com/ZephyrLabs/744000012345678-software-engineer"
    fixed, _, tried = run([miss("Zephyr Labs", GREENHOUSE), miss("Zephyr Labs", smart)], allows=lambda *a: False)
    assert tried == []
    assert fixed[0]["fix"]["state"] == mb.NO_BOARD and "robots" in fixed[0]["fix"]["note"]
    assert fixed[1]["fix"]["state"] == mb.NO_BOARD and "SmartRecruiters" in fixed[1]["fix"]["note"]


def test_a_failed_or_slowed_read_tries_again_another_day():
    fixed, _, _ = run(
        [miss("Zephyr Labs", GREENHOUSE), miss("Quill Works", LEVER)],
        outcomes={"zephyrlabs": FakeOutcome(False, "http 429", transient=True), "quillworks": RuntimeError("boom")},
    )
    assert [row["fix"]["state"] for row in fixed] == [mb.TRYING, mb.TRYING]


def test_a_board_that_fails_the_checks_says_why_in_plain_words():
    fixed, counts, _ = run(
        [miss("Zephyr Labs", GREENHOUSE), miss("Quill Works", LEVER)],
        outcomes={"zephyrlabs": FakeOutcome(False, "staffing: our client"),
                  "quillworks": FakeOutcome(False, "no US software or ML roles today")},
    )
    assert [row["fix"]["state"] for row in fixed] == [mb.NOT_ADDED, mb.NOT_ADDED]
    assert fixed[0]["fix"]["note"] == "The board belongs to a staffing agency, not the employer"
    assert fixed[1]["fix"]["note"] == "The board has no US software or ML role today"
    assert counts["boards_added"] == 0


def test_only_so_many_boards_are_read_a_day():
    fixed, counts, tried = run([miss("Zephyr Labs", GREENHOUSE), miss("Quill Works", LEVER)], limit=1)
    assert len(tried) == 1 and counts["boards_read"] == 1
    assert [row["fix"]["state"] for row in fixed] == [mb.ADDED, mb.TRYING]


def test_a_board_added_meanwhile_is_not_added_twice():
    fixed, counts, _ = run([miss("Zephyr Labs", GREENHOUSE)], added_ok=False)
    assert fixed[0]["fix"]["state"] == mb.HELD and counts["boards_added"] == 0


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_the_latest_score_is_fixed_once_and_the_report_carries_it(factory):
    with factory.begin() as session:
        session.add(RecallRunRecord(day=date(2026, 11, 22), checked_at=NOW, summary={"total": {"listed": 1}},
                                    missed=[miss("Zephyr Labs", GREENHOUSE)]))
    registered = []

    def register(session, outcome):
        registered.append(outcome)
        return True

    args = dict(now=NOW, known=set, allows=lambda *a: True,
                try_board=lambda *a: FakeOutcome(True, "hiring US engineers"), register=register)
    counts = mb.fix_latest_run(factory, **args)
    assert counts["boards_added"] == 1 and len(registered) == 1
    assert mb.fix_latest_run(factory, **args) is None and len(registered) == 1
    with factory() as session:
        report = recall.recall_report(session)
    assert report["fixes"]["boards_added"] == 1
    assert report["missed"][0]["fix"] == {"state": mb.ADDED, "note": "ace added this company's board. New roles reach Pulls from it"}


def test_nothing_happens_before_the_first_score(factory):
    assert mb.fix_latest_run(factory, now=NOW, known=set, allows=lambda *a: True,
                             try_board=lambda *a: None, register=lambda s, o: True) is None


def test_a_company_ace_never_heard_of_goes_on_leads_by_itself(factory):
    from backend.app.coverage.leads import CHECKING, MISSED

    with factory.begin() as session:
        session.add(RecallRunRecord(day=date(2026, 11, 22), checked_at=NOW, summary={"total": {"listed": 3}}, missed=[
            miss("Kestrel Robotics", None, reason=recall.NO_LEAD),
            miss("Kestrel Robotics", None, reason=recall.NO_LEAD, title="Data Engineer I"),
            miss("3f2b1c4d-0000-4000-8000-000000000001", None, reason=recall.NO_LEAD),
        ]))
    args = dict(now=NOW, known=set, allows=lambda *a: True, register=lambda s, o: pytest.fail("nothing to register"),
                try_board=lambda *a: pytest.fail("no board to read"))
    counts = mb.fix_latest_run(factory, **args)
    assert counts["named"] == 1 and counts["roles"][mb.TRYING] == 2 and counts["roles"][mb.NO_BOARD] == 1
    with factory() as session:
        leads = session.scalars(sa.select(EmployerLead)).all()
        assert [(row.company_name, row.origin, row.state, row.boards) for row in leads] == [("Kestrel Robotics", MISSED, CHECKING, [])]
        run = session.scalars(sa.select(RecallRunRecord)).one()
        assert run.missed[0]["fix"] == {"state": mb.TRYING, "note": mb.NAMED_NOTE}
        assert run.missed[2]["fix"]["state"] == mb.NO_BOARD
    assert mb.fix_latest_run(factory, **args) is None


def test_a_score_fixed_before_naming_gets_only_the_naming_step(factory):
    fixed = [{**miss("Kestrel Robotics", None, reason=recall.NO_LEAD), "fix": {"state": mb.NO_BOARD, "note": recall.NO_LEAD}},
             {**miss("Zephyr Labs", GREENHOUSE), "fix": {"state": mb.ADDED, "note": "added"}}]
    with factory.begin() as session:
        session.add(RecallRunRecord(day=date(2026, 11, 22), checked_at=NOW, missed=fixed, summary={
            "fixes": {"boards_read": 1, "boards_added": 1, "checked_at": NOW.isoformat(), "roles": {}}}))
    counts = mb.fix_latest_run(factory, now=NOW, known=set, allows=lambda *a: True,
                               try_board=lambda *a: pytest.fail("no board read again"),
                               register=lambda s, o: pytest.fail("nothing registered again"))
    assert counts["boards_added"] == 1 and counts["named"] == 1
    assert counts["roles"][mb.ADDED] == 1 and counts["roles"][mb.TRYING] == 1


def test_a_company_already_on_leads_shows_what_the_lead_check_found():
    rows = [miss("Quill Works", None, reason=recall.LEAD_REASONS[state]) for state in ("checking", "dormant", "agency", "noreader")]
    fixed, _, tried = run(rows)
    assert tried == []
    assert [row["fix"]["state"] for row in fixed] == [mb.TRYING, mb.NOT_ADDED, mb.OFF, mb.NO_BOARD]
