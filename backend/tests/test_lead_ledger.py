"""Every employer ACE hears of keeps a state and a next check.

Every company and board here is fictional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.companies import TARGET_COMPANIES
from backend.app.coverage.leads import (
    AGENCY,
    CHECKING,
    CURATED,
    DORMANT,
    FEED,
    NETWORK,
    NOREADER,
    POLLING,
    REFUSED,
    STATES,
    WAITING,
    check_due_leads,
    finding_from,
    gather_evidence,
    leads_report,
    sync_leads,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    EmployerLead,
    JobRecord,
    JobSourceRecord,
    SourceProbeRecord,
    SourceState,
)


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@pytest.fixture(name="network")
def fixture_network(tmp_path):
    path = tmp_path / "network.json"
    path.write_text(
        json.dumps(
            {
                "boards": [
                    {
                        "source_type": "ashby",
                        "source_account": "quiet-fictional",
                        "company": "Quiet Fictional",
                        "networks": ["fictional network"],
                    },
                    {
                        "source_type": "greenhouse",
                        "source_account": "renamed-board",
                        "company": "Old Fictional Name",
                        "networks": ["fictional network"],
                    },
                ]
            }
        )
    )
    return path


def add_source(session, company, source_type="greenhouse", account=None, *, enabled=True, discovery="board_probe", host=None):
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account or company.lower().replace(" ", ""),
            source_host=host,
            company_name=company,
            enabled=enabled,
            poll_interval_seconds=900,
            discovery_source=discovery,
        )
    )
    session.flush()


def lead(session, company) -> EmployerLead:
    return session.scalar(sa.select(EmployerLead).where(EmployerLead.company_name == company))


def run_sync(sessions, network, now=NOW):
    with sessions.begin() as session:
        return sync_leads(session, now=now, network_file=network)


def test_an_enabled_board_is_polling_whichever_way_it_arrived(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Works", discovery="feed_link")
        session.add(
            SourceState(
                source="greenhouse",
                source_account="fictionalworks",
                initialized_at=NOW,
                last_success_at=NOW - timedelta(minutes=9),
            )
        )

    run_sync(sessions, network)

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == POLLING
        assert row.origin == FEED
        assert "Greenhouse" in row.reason
        assert row.last_checked_at.replace(tzinfo=timezone.utc) == NOW - timedelta(minutes=9)


def test_a_multi_employer_feed_is_not_an_employer(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Feed", source_type="simplify", account="new-grad")

    run_sync(sessions, network)

    with sessions() as session:
        assert lead(session, "Fictional Feed") is None


def test_a_board_left_out_for_having_no_role_is_no_longer_forgotten(sessions, network) -> None:
    """The point of the ledger: this board was dropped, and nothing came back."""

    run_sync(sessions, network)

    with sessions() as session:
        row = lead(session, "Quiet Fictional")
        assert row.state == CHECKING
        assert row.origin == NETWORK
        assert row.last_checked_at is None
        assert row.next_check_at.replace(tzinfo=timezone.utc) == NOW
        assert row.boards[0]["source_account"] == "quiet-fictional"


def test_a_board_registered_under_another_name_counts_as_polling(sessions, network) -> None:
    """Networks list an old name; a board registers under its own."""

    with sessions.begin() as session:
        add_source(session, "New Fictional Name", account="renamed-board", discovery="talent_network")

    run_sync(sessions, network)

    with sessions() as session:
        assert lead(session, "Old Fictional Name").state == POLLING


def test_probe_results_seed_their_state_and_a_date_in_the_past_is_due(sessions, network) -> None:
    checked = NOW - timedelta(days=30)

    with sessions.begin() as session:
        for key, outcome in (
            ("another ats", "other_ats"),
            ("no board", "no_board_found"),
            ("site gone", "site_unreachable"),
            ("wrong board", "refused"),
            ("blocked firm", "blocked"),
            ("empty board", "no_postings"),
        ):
            session.add(
                SourceProbeRecord(
                    company_key=key,
                    company_name=key.title(),
                    outcome=outcome,
                    detail=f"Detail for {key} -- with dashes",
                    checked_at=checked,
                )
            )

    run_sync(sessions, network)

    with sessions() as session:
        assert lead(session, "Another Ats").state == NOREADER
        assert lead(session, "No Board").state == NOREADER
        assert lead(session, "Site Gone").state == NOREADER
        assert lead(session, "Wrong Board").state == NOREADER
        assert lead(session, "Blocked Firm").state == REFUSED
        empty = lead(session, "Empty Board")
        assert empty.state == DORMANT
        assert empty.last_checked_at.replace(tzinfo=timezone.utc) == checked
        assert empty.next_check_at.replace(tzinfo=timezone.utc) == checked + timedelta(days=7)
        assert "--" not in empty.reason


def test_a_rejected_agency_stays_left_out_with_its_reason(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(
            session,
            "Fictional Staffing",
            enabled=False,
            discovery="feed_link rejected: staffing: contract templates in 3 of 5 described postings",
        )

    run_sync(sessions, network)

    with sessions() as session:
        row = lead(session, "Fictional Staffing")
        assert row.state == AGENCY
        assert "contract templates" in row.reason
        assert row.boards == []


def test_a_retired_duplicate_row_is_not_a_board_to_read(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Copy", enabled=False, discovery="duplicate of fictional/original")

    run_sync(sessions, network)

    with sessions() as session:
        assert lead(session, "Fictional Copy") is None


def test_a_feed_name_with_no_board_becomes_a_lead(sessions, network) -> None:
    with sessions.begin() as session:
        session.add(
            JobRecord(
                source="simplify",
                source_account="new-grad",
                company="Fictional Feedco",
                external_id="1",
                title="Software Engineer",
                location="Ashfield, WA",
                description="",
                official_url="https://careers.fictional.example/1",
                content_hash="x",
                is_active=True,
            )
        )

    run_sync(sessions, network)

    with sessions() as session:
        row = lead(session, "Fictional Feedco")
        assert row.origin == FEED
        assert row.state == CHECKING


def test_every_name_on_the_owners_list_is_a_lead(sessions, network) -> None:
    run_sync(sessions, network)

    with sessions() as session:
        origins = dict(session.execute(sa.select(EmployerLead.company_name, EmployerLead.origin)).all())

    assert all(origins.get(name) == CURATED for name in TARGET_COMPANIES)


def test_every_lead_always_has_a_state_a_reason_and_a_next_check(sessions, network) -> None:
    """Target T11: 100% of leads have a state and a next check date."""

    with sessions.begin() as session:
        add_source(session, "Fictional Works")
        add_source(session, "Fictional Staffing", enabled=False, discovery="manual rejected: staffing agency (feed only)")
        session.add(SourceProbeRecord(company_key="unknown outcome", company_name="Unknown Outcome", outcome="reached", detail="", checked_at=NOW))

    run_sync(sessions, network)

    with sessions() as session:
        rows = list(session.scalars(sa.select(EmployerLead)))
        evidence = gather_evidence(session, network_file=network)

    assert {row.company_key for row in rows} >= set(evidence)
    for row in rows:
        assert row.state in STATES
        assert row.next_check_at is not None
        assert row.reason.strip(), row.company_name


def test_a_second_sync_changes_nothing_and_writes_nothing_new(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Works")

    first = run_sync(sessions, network)
    second = run_sync(sessions, network, now=NOW + timedelta(minutes=30))

    assert first.created > 0
    assert second.created == 0
    assert second.changed == 0


def test_a_lead_whose_evidence_goes_away_keeps_its_row(sessions, network, tmp_path) -> None:
    run_sync(sessions, network)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"boards": []}))
    run_sync(sessions, empty, now=NOW + timedelta(days=1))

    with sessions() as session:
        assert lead(session, "Quiet Fictional") is not None


def test_a_board_switched_off_moves_the_lead_out_of_polling(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Works")

    run_sync(sessions, network)

    with sessions.begin() as session:
        session.execute(sa.update(JobSourceRecord).values(enabled=False))

    run_sync(sessions, network, now=NOW + timedelta(hours=1))

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == CHECKING
        assert row.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(hours=1)


@dataclass
class Outcome:
    added: bool = False
    reason: str = ""
    jobs: int = 0
    us_engineering: int = 0
    passing: int = 0
    transient: bool = False


BOARD = {"source_type": "ashby", "source_account": "fictional", "source_host": None}


@pytest.mark.parametrize(
    ("outcome", "state", "fragment"),
    [
        (Outcome(added=True, us_engineering=4, passing=1), WAITING, "4 US software roles"),
        (Outcome(reason="no US software or ML roles today"), DORMANT, "no US software role"),
        (Outcome(reason="empty: the board read, but holds nothing"), DORMANT, "holds nothing"),
        (Outcome(reason="staffing: agency name: 'Fictional'"), AGENCY, "Staffing firm"),
        (Outcome(reason="shared: a firm's portfolio board, 'Fictional VC'"), AGENCY, "shared portfolio"),
    ],
)
def test_what_a_read_found_becomes_a_state(outcome, state, fragment) -> None:
    finding = finding_from(outcome, BOARD)
    assert finding.state == state
    assert fragment in finding.reason


def test_a_busy_provider_says_nothing_about_the_employer() -> None:
    finding = finding_from(Outcome(reason="unreadable: HTTPStatusError: 429", transient=True), BOARD)
    assert finding.transient and not finding.gone


def test_a_board_that_is_gone_says_so() -> None:
    finding = finding_from(Outcome(reason="unreadable: HTTPStatusError: 404"), BOARD)
    assert finding.gone and not finding.transient


def check(sessions, *, assess=None, diagnose=None, refusal=None, **kwargs):
    return check_due_leads(
        sessions,
        now=lambda: NOW,
        assess_board=assess or (lambda board, company: pytest.fail("no board should be read")),
        diagnose_name=diagnose or (lambda company: pytest.fail("no name should be searched")),
        refusal=refusal or (lambda session, target, now: None),
        pause=lambda seconds: None,
        **kwargs,
    )


def seed(sessions, company, *, boards=(), state=CHECKING, next_check=NOW, reason="Not read yet."):
    with sessions.begin() as session:
        session.add(
            EmployerLead(
                company_key=company.lower(),
                company_name=company,
                origin=NETWORK,
                origin_details=[NETWORK],
                state=state,
                reason=reason,
                boards=list(boards),
                first_seen_at=NOW,
                next_check_at=next_check,
                updated_at=NOW,
            )
        )


def test_without_an_adder_a_hiring_board_waits_and_is_never_registered(sessions) -> None:
    """Callers that pass no ``register_board`` only record (the scheduler
    passes one since 2026-11-12)."""

    seed(sessions, "Fictional Works", boards=[BOARD])

    summary = check(sessions, assess=lambda board, company: Outcome(added=True, us_engineering=2, passing=1))

    assert summary.boards == 1

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == WAITING
        assert row.last_checked_at is not None
        assert row.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=7)
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0


def test_a_refused_host_is_never_read(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])

    summary = check(sessions, refusal=lambda session, target, now: "Robots file disallows /jobs.")

    assert summary.refused == 1

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == REFUSED
        assert "disallows" in row.reason
        assert row.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=30)


def test_a_lead_not_due_is_left_alone(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD], next_check=NOW + timedelta(days=1))
    assert check(sessions).boards == 0


def test_a_polling_lead_costs_no_request(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD], state=POLLING)
    assert check(sessions).boards == 0


def test_a_run_is_bounded_and_what_it_does_not_reach_stays_due(sessions) -> None:
    for number in range(3):
        seed(sessions, f"Fictional {number}", boards=[{**BOARD, "source_account": f"f{number}"}], next_check=NOW - timedelta(days=number))

    read: list[str] = []

    def assess(board, company):
        read.append(company)
        return Outcome(reason="no US software or ML roles today")

    assert check(sessions, assess=assess, boards_per_run=2).boards == 2
    # Oldest first.
    assert read == ["Fictional 2", "Fictional 1"]

    with sessions() as session:
        assert lead(session, "Fictional 0").state == CHECKING
        assert lead(session, "Fictional 0").next_check_at.replace(tzinfo=timezone.utc) == NOW


def test_paged_platforms_have_their_own_small_budget(sessions) -> None:
    for number in range(3):
        seed(
            sessions,
            f"Paged {number}",
            boards=[{"source_type": "workday", "source_account": f"p{number}/Site", "source_host": f"p{number}.wd5.myworkdayjobs.example"}],
        )

    read: list[str] = []

    def assess(board, company):
        read.append(company)
        return Outcome(reason="no US software or ML roles today")

    assert check(sessions, assess=assess, paged_per_run=1).boards == 1
    assert len(read) == 1


def test_a_provider_that_says_not_now_is_left_alone_for_the_run(sessions) -> None:
    seed(sessions, "First", boards=[BOARD], next_check=NOW - timedelta(days=1))
    seed(sessions, "Second", boards=[{**BOARD, "source_account": "second"}])

    read: list[str] = []

    def assess(board, company):
        read.append(company)
        return Outcome(reason="unreadable: HTTPStatusError: 429", transient=True)

    summary = check(sessions, assess=assess)

    assert read == ["First"]
    assert summary.deferred == 1

    with sessions() as session:
        first = lead(session, "First")
        assert first.state == CHECKING
        assert first.check_failures == 1
        assert first.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=1)
        # It never asked, so it stays due.
        assert lead(session, "Second").next_check_at.replace(tzinfo=timezone.utc) == NOW


def test_a_failed_read_does_not_overwrite_what_was_known(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD], state=DORMANT, reason="Ashby board read, no US software role today.")

    check(sessions, assess=lambda board, company: Outcome(reason="unreadable: 503", transient=True))

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == DORMANT
        assert row.reason.startswith("Ashby board read")
        assert row.last_checked_at is None


def test_repeated_failures_wait_longer(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])
    with sessions.begin() as session:
        lead(session, "Fictional Works").check_failures = 3

    check(sessions, assess=lambda board, company: Outcome(reason="unreadable: 503", transient=True))

    with sessions() as session:
        assert lead(session, "Fictional Works").next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=8)


def test_an_exception_while_reading_cannot_stop_the_run(sessions) -> None:
    seed(sessions, "First", boards=[BOARD], next_check=NOW - timedelta(days=1))
    seed(sessions, "Second", boards=[{"source_type": "lever", "source_account": "second", "source_host": None}])

    def assess(board, company):
        if company == "First":
            raise RuntimeError("fictional failure")
        return Outcome(added=True, us_engineering=1, passing=1)

    check(sessions, assess=assess)

    with sessions() as session:
        assert lead(session, "First").state == CHECKING
        assert lead(session, "Second").state == WAITING


def test_a_gone_board_sends_the_lead_to_a_name_search_next(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])

    check(sessions, assess=lambda board, company: Outcome(reason="unreadable: 404"))

    @dataclass
    class Diagnosis:
        outcome: str = "no_board_found"
        detail: str = "No board ACE recognises."
        candidate: object = None

    with sessions.begin() as session:
        row = lead(session, "Fictional Works")
        assert row.state == CHECKING
        assert row.boards[0]["gone"] is True
        row.next_check_at = NOW

    summary = check(sessions, diagnose=lambda company: Diagnosis())

    assert summary.names == 1

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == NOREADER
        # The Coverage page reads the same answer.
        probe = session.scalar(sa.select(SourceProbeRecord).where(SourceProbeRecord.company_key == "fictional works"))
        assert probe.outcome == "no_board_found"


def test_a_name_search_that_finds_a_board_reads_it_next_and_registers_nothing(sessions) -> None:
    @dataclass
    class Candidate:
        source_type: str = "lever"
        source_account: str = "fictional-found"
        source_host: str | None = None

    @dataclass
    class Diagnosis:
        outcome: str = "reached"
        detail: str = "board declares itself Fictional Works"
        candidate: object = None

    seed(sessions, "Fictional Works")

    check(sessions, diagnose=lambda company: Diagnosis(candidate=Candidate()))

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == CHECKING
        assert row.boards[0]["source_account"] == "fictional-found"
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0


def test_name_searches_have_their_own_small_budget(sessions) -> None:
    for number in range(3):
        seed(sessions, f"Name {number}")

    @dataclass
    class Diagnosis:
        outcome: str = "no_board_found"
        detail: str = "Nothing."
        candidate: object = None

    assert check(sessions, diagnose=lambda company: Diagnosis(), names_per_run=1).names == 1


def test_a_long_line_of_old_name_searches_does_not_starve_boards(sessions) -> None:
    """Found on the real shape: 689 old names sat ahead of 900 unread boards."""

    for number in range(500):
        seed(sessions, f"Old Name {number}", state=NOREADER, next_check=NOW - timedelta(days=30))

    seed(sessions, "Unread Board", boards=[BOARD])

    @dataclass
    class Diagnosis:
        outcome: str = "no_board_found"
        detail: str = "Nothing."
        candidate: object = None

    read: list[str] = []

    def assess(board, company):
        read.append(company)
        return Outcome(reason="no US software or ML roles today")

    summary = check(sessions, assess=assess, diagnose=lambda company: Diagnosis(), names_per_run=2)

    assert read == ["Unread Board"]
    assert summary.names == 2


def test_the_report_counts_every_state_and_filters(sessions) -> None:
    seed(sessions, "Waiting Works", boards=[BOARD], state=WAITING, reason="Waiting for your approval.")
    seed(sessions, "Quiet Works", state=DORMANT, reason="No US software role today.")

    with sessions() as session:
        report = leads_report(session)
        waiting = leads_report(session, state=WAITING)
        searched = leads_report(session, query="quiet")
        escaped = leads_report(session, query="100%")

    assert report["total"] == 2
    assert {item["state"]: item["leads"] for item in report["states"]}[WAITING] == 1
    # The owner's next action comes first.
    assert report["rows"][0]["company"] == "Waiting Works"
    assert report["rows"][0]["state_label"] == "Good board, left out"
    assert report["rows"][0]["next_check_at"]
    assert [row["company"] for row in waiting["rows"]] == ["Waiting Works"]
    assert [row["company"] for row in searched["rows"]] == ["Quiet Works"]
    assert escaped["rows"] == []


def test_a_polling_row_reports_its_real_last_read_and_cadence(sessions, network) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Works")
        session.add(
            SourceState(
                source="greenhouse",
                source_account="fictionalworks",
                initialized_at=NOW,
                last_success_at=NOW - timedelta(hours=2),
            )
        )

    run_sync(sessions, network)

    with sessions.begin() as session:
        session.execute(
            sa.update(SourceState).values(last_success_at=NOW - timedelta(minutes=3))
        )

    with sessions() as session:
        [row] = leads_report(session, state=POLLING)["rows"]

    assert row["poll_interval_seconds"] == 900
    assert row["last_checked_at"].startswith((NOW - timedelta(minutes=3)).isoformat()[:16])


def test_a_board_on_twice_with_different_capitals_counts_as_polling(sessions, network) -> None:
    """A switched-off copy under other capitals must not hide the enabled one
    (seen on 2026-11-12: three boards ACE reads were left waiting)."""

    with sessions.begin() as session:
        add_source(session, "Fictional Works", "workday", "fictional/Careers", enabled=False, discovery="duplicate of fictional/careers")
        add_source(session, "Fictional Works", "workday", "fictional/careers")
        session.add(
            EmployerLead(
                company_key="fictional works",
                company_name="Fictional Works",
                origin=NETWORK,
                origin_details=[NETWORK],
                state=WAITING,
                reason="old",
                boards=[{"source_type": "workday", "source_account": "fictional/careers", "source_host": None}],
                first_seen_at=NOW,
                next_check_at=NOW + timedelta(days=3),
                updated_at=NOW,
            )
        )

    run_sync(sessions, network)

    with sessions() as session:
        assert lead(session, "Fictional Works").state == POLLING


def _real_outcome(company="Fictional Works", account="fictional", passing=1):
    from backend.scripts.register_network_boards import Candidate, Outcome as Real

    return Real(
        candidate=Candidate(source_type="ashby", source_account=account, company=company),
        added=True,
        reason="hiring US engineers",
        jobs=5,
        us_engineering=3,
        passing=passing,
    )


def _adder():
    from backend.scripts.register_network_boards import register

    return lambda session, outcome: register(session, outcome, now=NOW, origin="lead_ledger")


def test_a_qualifying_board_is_added_and_the_lead_polls(sessions) -> None:
    """Owner request, 2026-11-12: a good board is added, not left waiting."""

    seed(sessions, "Fictional Works", boards=[BOARD])

    summary = check(sessions, assess=lambda board, company: _real_outcome(), register_board=_adder())

    assert summary.added == 1

    with sessions() as session:
        row = lead(session, "Fictional Works")
        assert row.state == POLLING
        assert row.reason.startswith("Added on November 5")
        source = session.scalar(sa.select(JobSourceRecord))
        assert (source.source_type, source.source_account, source.enabled) == ("ashby", "fictional", True)
        assert source.discovery_source == "lead_ledger"
        assert source.poll_interval_seconds == 900


def test_a_board_with_no_passing_role_yet_is_added_hourly(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])

    check(sessions, assess=lambda board, company: _real_outcome(passing=0), register_board=_adder())

    with sessions() as session:
        assert session.scalar(sa.select(JobSourceRecord)).poll_interval_seconds == 3600


def test_a_board_switched_off_earlier_stays_off(sessions) -> None:
    with sessions.begin() as session:
        add_source(session, "Fictional Works", "ashby", "Fictional", enabled=False)
    seed(sessions, "Fictional Works", boards=[BOARD])

    summary = check(sessions, assess=lambda board, company: _real_outcome(), register_board=_adder())

    assert summary.added == 0

    with sessions() as session:
        assert lead(session, "Fictional Works").state == WAITING
        rows = session.scalars(sa.select(JobSourceRecord)).all()
        assert [(row.source_account, row.enabled) for row in rows] == [("Fictional", False)]


def test_a_board_named_only_by_an_internal_id_is_not_added(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])

    check(
        sessions,
        assess=lambda board, company: _real_outcome(company="0b5d2c4e-1a2b-4c3d-8e9f-001122334455"),
        register_board=_adder(),
    )

    with sessions() as session:
        assert lead(session, "Fictional Works").state == WAITING
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0


def test_a_failed_add_leaves_the_lead_waiting_and_the_run_going(sessions) -> None:
    seed(sessions, "Fictional Works", boards=[BOARD])
    seed(sessions, "Other Fictional", boards=[{**BOARD, "source_account": "other"}])

    def broken(session, outcome):
        raise RuntimeError("fictional failure")

    summary = check(sessions, assess=lambda board, company: _real_outcome(company=company, account=board["source_account"]), register_board=broken)

    assert summary.boards == 2
    assert summary.added == 0

    with sessions() as session:
        assert lead(session, "Fictional Works").state == WAITING
        assert lead(session, "Other Fictional").state == WAITING
