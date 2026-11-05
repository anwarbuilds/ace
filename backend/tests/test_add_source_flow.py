"""Paste a job link or a name, and ACE always says what happened.

Every company and board here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.leads import NOREADER, POLLING, REFUSED, added_report, sync_leads
from backend.app.coverage.service import add_source, undo_added
from backend.app.coverage.sources_view import coverage_summary, sources_report
from backend.app.db.base import Base
from backend.app.db.models import (
    EmployerLead,
    HostPolicyRecord,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    SourceState,
)


NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

JOB_LINK = "https://jobs.ashbyhq.com/lumora-pay/0a1b2c3d"


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, class_=Session, expire_on_commit=False)() as session:
        yield session


def board_fetch(url, **kwargs):
    return {"jobs": [{"id": "0a1b2c3d", "title": "Associate Software Engineer", "location": "Denver, CO"}]}


def add(session, text, *, fetch=board_fetch, fetch_text=None, robots=None, fetch_robots=None, refuses=None):
    return add_source(
        session,
        text=text,
        fetch=fetch,
        fetch_text=fetch_text or (lambda url, **kwargs: ""),
        post=lambda url, payload, **kwargs: None,
        robots=robots or (lambda host: ""),
        refuses=refuses or (lambda url: False),
        fetch_robots=fetch_robots or (lambda host: (404, "")),
        now=NOW,
    )


def test_a_readable_job_link_starts_polling_and_says_so(session) -> None:
    result = add(session, JOB_LINK)

    assert result.status == "added"
    assert result.source_account == "lumora-pay"
    assert result.job_count == 1
    assert result.linked is True
    assert result.first_read_seconds

    board = session.scalar(sa.select(JobSourceRecord))
    assert board.enabled and board.discovery_source == "added_by_hand"

    lead = session.scalar(sa.select(EmployerLead))
    assert lead.state == POLLING
    assert lead.owner_added_at is not None
    assert lead.origin == "owner"


def test_what_you_added_shows_at_once_and_in_sources(session) -> None:
    add(session, JOB_LINK)

    [row] = added_report(session)
    assert row["state"] == POLLING
    assert row["state_label"] == "ace reads it"

    report = sources_report(session, now=NOW, show="mine")
    assert report["counts"]["mine"] == 1
    [board] = report["rows"]
    assert board["added_by_you"] is True
    assert board["status"] == "first_read"
    assert board["status_label"] == "First read soon"


def test_the_list_fills_in_once_the_board_has_been_read(session) -> None:
    add(session, JOB_LINK)
    session.add(SourceState(source="ashby", source_account="lumora-pay", initialized_at=NOW, last_success_at=NOW, last_job_count=14))
    job = JobRecord(
        source="ashby",
        source_account="lumora-pay",
        company="Lumora Pay",
        external_id="1",
        title="Associate Software Engineer",
        location="Denver, CO",
        description="",
        official_url=JOB_LINK,
        content_hash="x",
        is_active=True,
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            content_hash="x",
            rule_version="test",
            reason_codes=[],
            reasons=[],
            evaluated_at=NOW,
        )
    )
    session.commit()

    [row] = added_report(session)
    assert row["jobs"] == 14
    assert row["passing"] == 1
    assert row["last_read_at"]

    [board] = sources_report(session, now=NOW, show="mine")["rows"]
    assert board["status"] == "working"
    assert board["jobs"] == 14


def test_a_board_already_read_says_so_and_finds_your_job(session) -> None:
    session.add(JobSourceRecord(source_type="ashby", source_account="lumora-pay", company_name="Lumora Pay", enabled=True, poll_interval_seconds=900))
    session.add(SourceState(source="ashby", source_account="lumora-pay", initialized_at=NOW, last_success_at=NOW - timedelta(minutes=9)))
    job = JobRecord(
        source="ashby",
        source_account="lumora-pay",
        company="Lumora Pay",
        external_id="1",
        title="Associate Software Engineer",
        location="Denver, CO",
        description="",
        official_url=JOB_LINK + "/",
        content_hash="x",
        is_active=True,
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            content_hash="x",
            rule_version="test",
            reason_codes=[],
            reasons=[],
            evaluated_at=NOW,
        )
    )
    session.commit()

    result = add(session, JOB_LINK + "/application")

    assert result.status == "already_known"
    assert result.last_read_at
    # The apply page sits under the posting's own address.
    assert result.job["title"] == "Associate Software Engineer"
    assert result.job["passes"] is True

    # A posting ace has not stored yet is said plainly, with no guess.
    assert add(session, "https://jobs.ashbyhq.com/lumora-pay/ffffffff").job is None

    assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 1


def test_a_board_switched_off_as_an_agency_is_not_turned_back_on(session) -> None:
    session.add(
        JobSourceRecord(
            source_type="ashby",
            source_account="lumora-pay",
            company_name="Lumora Pay",
            enabled=False,
            poll_interval_seconds=900,
            discovery_source="feed_link rejected: staffing: agency name: 'Lumora Pay'",
        )
    )
    session.commit()

    result = add(session, JOB_LINK)

    assert result.status == "known_off"
    assert "staffing" in result.detail
    assert session.scalar(sa.select(JobSourceRecord)).enabled is False


def test_a_site_ace_has_no_reader_for_is_kept_with_the_reason(session) -> None:
    result = add(session, "https://quillfeather.teamtailor.com/jobs/4821", fetch=lambda url, **k: None)

    assert result.status == "saved_no_reader"
    assert "Teamtailor" in result.detail
    assert result.next_check_at

    lead = session.scalar(sa.select(EmployerLead))
    assert lead.state == NOREADER
    assert lead.owner_added_at is not None
    assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0


def test_a_page_whose_robots_say_no_is_never_read(session) -> None:
    read: list[str] = []

    def fetch_text(url, **kwargs):
        read.append(url)
        return ""

    result = add(
        session,
        "https://careers.oakhollow.example/jobs/1",
        fetch=lambda url, **k: None,
        fetch_text=fetch_text,
        robots=lambda host: "User-agent: *\nDisallow: /jobs\n",
    )

    assert result.status == "saved_refused"
    assert "stay off" in result.detail
    assert read == []
    assert session.scalar(sa.select(EmployerLead)).state == REFUSED


def test_a_good_board_on_a_refused_host_is_kept_but_not_read(session) -> None:
    """Pasting a link is no way around a refusal."""

    session.add(
        HostPolicyRecord(
            host="api.ashbyhq.com",
            platform="ashby",
            paths=["/posting-api/job-board/example"],
            robots_verdict="refused",
            next_check_at=NOW + timedelta(days=9),
            first_seen_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()

    # The refused host also blocks the read that would have found the board.
    result = add(session, JOB_LINK)

    assert result.status != "added"
    assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0
    assert session.scalar(sa.select(EmployerLead)) is not None


def test_robots_asked_for_the_first_time_can_still_say_no(session) -> None:
    result = add(session, JOB_LINK, fetch_robots=lambda host: (200, "User-agent: *\nDisallow: /\n"))

    assert result.status == "saved_refused"
    assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0
    # The board is remembered, so ace looks again when the site changes its mind.
    assert session.scalar(sa.select(EmployerLead)).boards[0]["source_account"] == "lumora-pay"


def test_a_name_with_nothing_found_is_saved_and_nothing_is_guessed(session) -> None:
    result = add(session, "Fernhollow", fetch=lambda url, **k: None)

    assert result.status == "saved_looking"
    assert result.company == "Fernhollow"
    assert result.next_check_at
    assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0
    assert session.scalar(sa.select(EmployerLead)).owner_added_at is not None


def test_undo_takes_a_board_back_and_it_is_never_proposed_again(session, tmp_path) -> None:
    network = tmp_path / "n.json"
    network.write_text('{"boards": []}')
    add(session, JOB_LINK)
    session.add(
        JobRecord(
            source="ashby",
            source_account="lumora-pay",
            company="Lumora Pay",
            external_id="1",
            title="Associate Software Engineer",
            location="Denver, CO",
            description="",
            official_url=JOB_LINK,
            content_hash="x",
            is_active=True,
        )
    )
    session.commit()

    assert undo_added(session, source_type="ashby", source_account="lumora-pay", now=NOW) is True

    board = session.scalar(sa.select(JobSourceRecord))
    assert board.enabled is False
    assert session.scalar(sa.select(JobRecord)).is_active is False
    assert added_report(session) == []
    assert session.scalar(sa.select(EmployerLead)) is None

    # Nothing brings it back: not the next sync, not a second undo.
    sync_leads(session, now=NOW, network_file=network)
    session.commit()
    assert session.scalar(sa.select(EmployerLead).where(EmployerLead.company_key == "lumora pay")) is None
    assert undo_added(session, source_type="ashby", source_account="lumora-pay", now=NOW) is False

    # Pasting it again says why it stays off.
    assert add(session, JOB_LINK).status == "known_off"


def test_only_a_board_you_added_can_be_undone(session) -> None:
    session.add(JobSourceRecord(source_type="ashby", source_account="other", company_name="Other", enabled=True, poll_interval_seconds=900, discovery_source="curated_list"))
    session.commit()
    assert undo_added(session, source_type="ashby", source_account="other", now=NOW) is False
    assert session.scalar(sa.select(JobSourceRecord)).enabled is True


def test_a_board_someone_added_earlier_counts_as_added_after_a_sync(session, tmp_path) -> None:
    network = tmp_path / "n.json"
    network.write_text('{"boards": []}')
    session.add(JobSourceRecord(source_type="ashby", source_account="earlier", company_name="Earlier Works", enabled=True, poll_interval_seconds=900, discovery_source="added_by_hand", first_discovered_at=NOW - timedelta(days=9)))
    session.commit()
    sync_leads(session, now=NOW, network_file=network)
    session.commit()
    [row] = added_report(session)
    assert row["company"] == "Earlier Works"


def test_sources_filters_counts_and_order(session) -> None:
    session.add(JobSourceRecord(source_type="greenhouse", source_account="working", company_name="Working Works", enabled=True, poll_interval_seconds=900, first_discovered_at=NOW - timedelta(days=30), created_at=NOW - timedelta(days=30)))
    session.add(SourceState(source="greenhouse", source_account="working", initialized_at=NOW, last_success_at=NOW - timedelta(minutes=6), last_job_count=22))
    session.add(JobSourceRecord(source_type="greenhouse", source_account="silent", company_name="Silent Works", enabled=True, poll_interval_seconds=900, first_discovered_at=NOW - timedelta(days=30), created_at=NOW - timedelta(days=30)))
    session.add(SourceState(source="greenhouse", source_account="silent", initialized_at=NOW, last_success_at=NOW - timedelta(days=4)))
    session.add(JobSourceRecord(source_type="workday", source_account="closed/External", source_host="closed.wd5.myworkdayjobs.example", company_name="Closed Works", enabled=True, poll_interval_seconds=900, first_discovered_at=NOW - timedelta(days=30), created_at=NOW - timedelta(days=30)))
    session.add(SourceState(source="workday", source_account="closed/External", initialized_at=NOW, last_success_at=NOW))
    session.add(HostPolicyRecord(host="closed.wd5.myworkdayjobs.example", platform="workday", paths=["/"], robots_verdict="refused", next_check_at=NOW, first_seen_at=NOW, updated_at=NOW))
    session.add(JobSourceRecord(source_type="simplify", source_account="new-grad", company_name="A Feed", enabled=True, poll_interval_seconds=900))
    session.add(JobSourceRecord(source_type="greenhouse", source_account="off", company_name="Off Works", enabled=False, poll_interval_seconds=900))
    session.commit()

    report = sources_report(session, now=NOW)

    assert report["counts"] == {"total": 3, "working": 1, "first_read": 0, "dark": 1, "says_no": 1, "mine": 0}
    assert [row["company"] for row in report["rows"]] == ["Silent Works", "Closed Works", "Working Works"]
    assert [row["company"] for row in sources_report(session, now=NOW, show="dark")["rows"]] == ["Silent Works"]
    assert [row["company"] for row in sources_report(session, now=NOW, show="says_no")["rows"]] == ["Closed Works"]
    assert [row["company"] for row in sources_report(session, now=NOW, query="work")["rows"]][:1] == ["Silent Works"]
    assert sources_report(session, now=NOW, limit=1, offset=1)["rows"][0]["company"] == "Closed Works"
    assert report["dark"][0]["company"] == "Silent Works"
    assert coverage_summary(session)["sources"] == 3
