"""Each host ACE reads has a dated verdict, judged on the pages it reads.

Every host and company here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.host_policy import (
    ALLOWED,
    REFUSED,
    UNKNOWN,
    HostTarget,
    PoliteReader,
    check_due_hosts,
    check_host,
    hosts_report,
    judge,
    read_targets,
    refusal_for,
    refused_hosts,
    sync_hosts,
    without_refused_hosts,
)
from backend.app.coverage.host_terms import TERMS, PlatformTerms
from backend.app.db.base import Base
from backend.app.db.models import EmployerPageReading, HostPolicyRecord, JobSourceRecord
from backend.app.scheduling.types import SourceDefinition, SourceType


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

# One representative account for each source type, in the shape it is stored.
ACCOUNTS = {
    "avature": ("https://jobs.fictional.example/en_US/careers/SearchJobs", None),
    "bytedance": ("tiktok", None),
    "eightfold": ("fictional.example", "fictional.eightfold.example"),
    "eightfold_pcsx": ("fictional.example", "careers.fictional.example"),
    "jibe": ("careers.fictional.example/careers-home", None),
    "jobposting_sitemap": ("careers.fictional.example", None),
    "oracle_recruiting": ("fictional.fa.us2.oraclecloud.example/CX_1", None),
    "workday": ("fictional/External", "fictional.wd5.myworkdayjobs.example"),
}


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def source(session, source_type="workday", account="fictional/External", host="fictional.wd5.myworkdayjobs.example", enabled=True):
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            source_host=host,
            company_name="Fictional Works",
            enabled=enabled,
            poll_interval_seconds=900,
        )
    )
    session.flush()


def test_every_source_type_says_which_host_and_paths_it_reads() -> None:
    """A new reader with no entry here would have no verdict at all."""

    for source_type in SourceType:
        account, host = ACCOUNTS.get(source_type.value, ("fictional", None))
        targets = read_targets(source_type.value, account, host)
        assert targets, source_type.value
        for target in targets:
            assert target.host and "/" not in target.host
            assert target.paths and all(path.startswith("/") for path in target.paths)


def test_tenant_hosts_use_the_real_path_and_shared_hosts_a_stand_in() -> None:
    [workday] = read_targets("workday", "fictional/External", "Fictional.wd5.myworkdayjobs.example/")
    assert workday.host == "fictional.wd5.myworkdayjobs.example"
    assert workday.paths == ("/wday/cxs/fictional/External/jobs",)

    [greenhouse] = read_targets("greenhouse", "fictional", "job-boards.greenhouse.io")
    assert greenhouse.host == "boards-api.greenhouse.io"
    assert "fictional" not in greenhouse.paths[0]

    [eu] = read_targets("lever", "fictional", "jobs.eu.lever.co")
    assert eu.host == "api.eu.lever.co"


def test_the_verdict_comes_from_the_paths_ace_reads_and_longest_match_wins() -> None:
    text = "User-agent: *\nDisallow: /\nAllow: /api/\nDisallow: /api/private/\n"
    assert judge("h.example", ["/api/jobs"], 200, text).verdict == ALLOWED
    closed = judge("h.example", ["/api/jobs", "/api/private/x", "/search"], 200, text)
    assert closed.verdict == REFUSED
    assert "/api/private/x" in closed.detail and "/search" in closed.detail
    assert "/api/jobs" not in closed.detail


@pytest.mark.parametrize("status", [401, 403, 404, 405, 410])
def test_a_client_error_on_the_robots_file_sets_no_rules(status) -> None:
    """RFC 9309. An API-only host answering 401 here refuses nobody."""

    reading = judge("h.example", ["/jobs"], status, "")
    assert reading.verdict == ALLOWED
    assert str(status) in reading.detail


@pytest.mark.parametrize("status", [None, 429, 500, 503, 202])
def test_a_failed_read_decides_nothing(status) -> None:
    assert judge("h.example", ["/jobs"], status, "").verdict is None


def test_a_failed_recheck_keeps_the_verdict_and_says_so(sessions) -> None:
    with sessions.begin() as session:
        row = HostPolicyRecord(
            host="h.example",
            platform="workday",
            paths=["/jobs"],
            robots_verdict=ALLOWED,
            robots_detail="Robots file allows the pages ACE reads.",
            checked_at=NOW - timedelta(days=31),
            next_check_at=NOW,
            first_seen_at=NOW,
            updated_at=NOW,
        )
        session.add(row)
        session.flush()

        assert check_host(row, now=NOW, fetch_robots=lambda host: (503, "")) == ALLOWED
        assert row.robots_verdict == ALLOWED
        assert row.last_error
        assert row.next_check_at == NOW + timedelta(days=1)
        # The dated verdict still says when it was last actually read.
        assert row.checked_at == NOW - timedelta(days=31)


def test_every_enabled_source_and_employer_page_gets_a_host_row(sessions) -> None:
    with sessions.begin() as session:
        source(session)
        source(session, "greenhouse", "fictional", "job-boards.greenhouse.io")
        source(session, "lever", "offline", "jobs.lever.co", enabled=False)
        session.add(EmployerPageReading(url="https://careers.fictional.example/job/1#jobposting", status="read", description="", checked_at=NOW))
        session.flush()
        assert sync_hosts(session, now=NOW) == 3

    with sessions() as session:
        rows = {row.host: row for row in session.scalars(sa.select(HostPolicyRecord))}

    assert set(rows) == {
        "fictional.wd5.myworkdayjobs.example",
        "boards-api.greenhouse.io",
        "careers.fictional.example",
    }
    assert all(row.robots_verdict == UNKNOWN for row in rows.values())
    assert rows["careers.fictional.example"].platform == "employer_page"


def test_a_host_ace_stops_reading_keeps_its_dated_row(sessions) -> None:
    with sessions.begin() as session:
        source(session)
        sync_hosts(session, now=NOW)
        session.execute(sa.update(JobSourceRecord).values(enabled=False))
        assert sync_hosts(session, now=NOW) == 0

    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(HostPolicyRecord)) == 1


def test_a_run_is_bounded_and_oldest_first(sessions) -> None:
    with sessions.begin() as session:
        for number in range(5):
            session.add(
                HostPolicyRecord(
                    host=f"h{number}.example",
                    platform="workday",
                    paths=["/jobs"],
                    next_check_at=NOW - timedelta(days=number),
                    first_seen_at=NOW,
                    updated_at=NOW,
                )
            )

    read: list[str] = []

    def fetch(host):
        read.append(host)
        return 200, "User-agent: *\nDisallow:\n"

    assert check_due_hosts(sessions, now=lambda: NOW, fetch_robots=fetch, limit=2) == 2
    assert read == ["h4.example", "h3.example"]

    with sessions() as session:
        row = session.get(HostPolicyRecord, "h4.example")
        assert row.robots_verdict == ALLOWED
        assert row.next_check_at.replace(tzinfo=timezone.utc) == NOW + timedelta(days=30)


def test_a_host_not_due_is_not_asked_again(sessions) -> None:
    with sessions.begin() as session:
        session.add(
            HostPolicyRecord(
                host="fresh.example",
                platform="workday",
                paths=["/jobs"],
                robots_verdict=ALLOWED,
                next_check_at=NOW + timedelta(days=9),
                first_seen_at=NOW,
                updated_at=NOW,
            )
        )

    assert check_due_hosts(sessions, now=lambda: NOW, fetch_robots=pytest.fail) == 0


def test_a_new_read_asks_first_and_obeys(sessions) -> None:
    target = HostTarget("closed.example", "workday", ("/jobs",))

    with sessions.begin() as session:
        why = refusal_for(
            session,
            target,
            now=NOW,
            fetch_robots=lambda host: (200, "User-agent: *\nDisallow: /jobs\n"),
        )
        assert why and "/jobs" in why
        assert refused_hosts(session) == {"closed.example"}

        # Already known and not due: no second request, same answer.
        assert refusal_for(session, target, now=NOW + timedelta(days=1), fetch_robots=pytest.fail)


def test_rules_that_cannot_be_read_close_the_host_for_new_reads(sessions) -> None:
    """RFC 9309: unknown rules are read as disallow, for anything new."""

    with sessions.begin() as session:
        why = refusal_for(
            session,
            HostTarget("silent.example", "workday", ("/jobs",)),
            now=NOW,
            fetch_robots=lambda host: (None, ""),
        )
        assert why
        assert refused_hosts(session) == set()


def test_paths_a_verdict_never_judged_are_asked_about(sessions) -> None:
    with sessions.begin() as session:
        session.add(
            HostPolicyRecord(
                host="partly.example",
                platform="workday",
                paths=["/open"],
                robots_verdict=ALLOWED,
                next_check_at=NOW + timedelta(days=9),
                first_seen_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        why = refusal_for(
            session,
            HostTarget("partly.example", "workday", ("/open", "/closed")),
            now=NOW,
            fetch_robots=lambda host: (200, "User-agent: *\nDisallow: /closed\n"),
        )
        assert why and "/closed" in why


def definition(source_type: SourceType, account: str, host: str | None = None) -> SourceDefinition:
    return SourceDefinition(
        source_type=source_type,
        source_account=account,
        company_name="Fictional Works",
        enabled=True,
        poll_interval_seconds=900,
        source_host=host,
    )


def test_enforcing_takes_only_refused_hosts_out_of_polling() -> None:
    closed = definition(SourceType.WORKDAY, "closed/External", "closed.wd5.myworkdayjobs.example")
    open_ = definition(SourceType.WORKDAY, "open/External", "open.wd5.myworkdayjobs.example")
    assert without_refused_hosts([closed, open_], {"closed.wd5.myworkdayjobs.example"}) == [open_]


def test_the_polite_reader_never_reads_what_robots_or_a_verdict_closes() -> None:
    requests: list[str] = []

    def robots(host):
        return {"open.example": "User-agent: *\nDisallow: /private\n", "silent.example": None}.get(host, "")

    def record(url, *args, **kwargs):
        requests.append(url)
        return "read"

    reader = PoliteReader(
        {"refused.example"},
        fetch=record,
        fetch_text=record,
        post=record,
        robots=robots,
        refuses=lambda url: True,
    )

    assert reader.fetch_text("https://open.example/careers") == "read"
    assert reader.fetch_text("https://open.example/private/x") == ""
    assert reader.fetch("https://refused.example/x") is None
    assert reader.post("https://silent.example/x", {}) is None
    assert reader.refuses("https://refused.example") is False
    assert requests == ["https://open.example/careers"]


def test_the_report_groups_by_platform_and_names_each_refused_host(sessions) -> None:
    with sessions.begin() as session:
        source(session, "workday", "open/External", "open.wd5.myworkdayjobs.example")
        source(session, "workday", "closed/External", "closed.wd5.myworkdayjobs.example")
        sync_hosts(session, now=NOW)
        session.get(HostPolicyRecord, "open.wd5.myworkdayjobs.example").robots_verdict = ALLOWED
        closed = session.get(HostPolicyRecord, "closed.wd5.myworkdayjobs.example")
        closed.robots_verdict = REFUSED
        closed.robots_detail = "Robots file disallows /wday/."
        closed.checked_at = NOW

    terms = {
        "workday": PlatformTerms(
            verdict="restricted",
            note="A fictional note.",
            url="https://terms.example",
            reviewed_on=NOW.date(),
            recheck_on=NOW.date(),
        )
    }

    with sessions() as session:
        report = hosts_report(session, enforcing=False, terms=terms)

    assert report["enforcing"] is False
    assert (report["total"], report["allowed"], report["refused"], report["unknown"]) == (2, 1, 1, 0)
    [group] = report["groups"]
    assert group["label"] == "Workday"
    assert (group["hosts"], group["allowed"], group["refused"], group["sources"]) == (2, 1, 1, 2)
    assert group["terms"]["verdict"] == "restricted"
    [refused] = report["refused_hosts"]
    assert refused["host"] == "closed.wd5.myworkdayjobs.example"
    assert refused["sources"] == 1


def test_a_platform_nobody_has_read_says_so(sessions) -> None:
    """Silence is never reported as allowed."""

    with sessions.begin() as session:
        source(session)
        sync_hosts(session, now=NOW)

    with sessions() as session:
        [group] = hosts_report(session, enforcing=False, terms={})["groups"]

    assert group["terms"]["verdict"] == "not_read"


def test_each_terms_reading_is_dated_and_uses_a_known_verdict() -> None:
    for reading in TERMS.values():
        assert reading.verdict in {"allowed", "restricted", "unclear"}
        assert reading.note and reading.url.startswith("https://")
        assert reading.reviewed_on < reading.recheck_on


def test_a_board_added_by_hand_on_a_refused_host_is_not_registered(sessions) -> None:
    """Pasting a link is no way around a refusal."""

    from backend.app.coverage.service import add_source

    def fetch(url, **kwargs):
        return {"jobs": [{"id": "1", "title": "Software Engineer", "location": "Ashfield, WA"}]}

    with sessions.begin() as session:
        session.add(
            HostPolicyRecord(
                host="api.ashbyhq.com",
                platform="ashby",
                paths=["/posting-api/job-board/example"],
                robots_verdict=REFUSED,
                next_check_at=NOW,
                first_seen_at=NOW,
                updated_at=NOW,
            )
        )

    with sessions() as session:
        result = add_source(
            session,
            text="https://jobs.ashbyhq.com/fictional",
            fetch=fetch,
            fetch_text=lambda url, **kwargs: "",
        )
        assert result.status == "refused"
        assert "will not try another route" in result.detail
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0

    with sessions.begin() as session:
        session.get(HostPolicyRecord, "api.ashbyhq.com").robots_verdict = ALLOWED

    with sessions() as session:
        result = add_source(
            session,
            text="https://jobs.ashbyhq.com/fictional",
            fetch=fetch,
            fetch_text=lambda url, **kwargs: "",
        )
        assert result.status == "added"
