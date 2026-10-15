"""Pulls: fifteen minute windows that say what was checked, honestly.

Sources checked, attempts and failures are different numbers; a window
written before attempts were recorded says so instead of guessing; a
quiet window still appears; and the scheduler is "live" only when a
board answered recently, not because the website did.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.api.routers.pulls import build_pulls, day_bounds, pull_state
from backend.app.auth.guard import require_auth
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import JobSourceRecord, PollSessionRecord, SourceState
from backend.app.persistence.sessions import record_attempts
from backend.app.scheduling import SchedulerRuntime, SourceDefinition, SourceRegistry
from backend.tests.test_scheduler_runtime import FakeClock, make_source


PT = ZoneInfo("America/Los_Angeles")

# 12:07 PM Pacific on a fictional day.
NOW = datetime(2026, 10, 15, 19, 7, tzinfo=timezone.utc)


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _window(start: datetime, **counts) -> PollSessionRecord:
    defaults = dict(
        jobs_discovered=0,
        qualifying_discovered=0,
        boards_checked=0,
        postings_checked=0,
    )
    defaults.update(counts)
    return PollSessionRecord(started_at=start, last_activity_at=start + timedelta(minutes=14), **defaults)


def _source(account: str, last_success: datetime) -> list:
    return [
        JobSourceRecord(source_type="greenhouse", source_account=account, company_name=f"Example {account}", enabled=True),
        SourceState(
            source="greenhouse",
            source_account=account,
            initialized_at=last_success - timedelta(days=3),
            last_success_at=last_success,
            last_job_count=10,
        ),
    ]


# --- live, delayed, stalled ---------------------------------------------


def test_live_only_while_boards_answer_recently() -> None:
    assert pull_state(NOW - timedelta(minutes=3), NOW) == "live"
    assert pull_state(NOW - timedelta(minutes=15), NOW) == "live"
    assert pull_state(NOW - timedelta(minutes=16), NOW) == "delayed"
    assert pull_state(NOW - timedelta(minutes=45), NOW) == "delayed"
    # A stopped scheduler, even though this request was answered.
    assert pull_state(NOW - timedelta(minutes=46), NOW) == "stalled"
    assert pull_state(None, NOW) == "unknown"


def test_stale_scheduler_reads_stalled_in_the_response(factory) -> None:
    with factory.begin() as session:
        session.add_all(_source("north", NOW - timedelta(hours=2)))

    with factory() as session:
        out = build_pulls(session, zone=PT, now=NOW)

    assert out.status.state == "stalled"
    assert out.status.age_seconds == 7200
    assert out.status.sources_enabled == 1
    # Two hours ago is still inside the last 24 hours.
    assert out.summary.sources_succeeded == 1


# --- windows ------------------------------------------------------------


def test_quiet_windows_stay_visible_and_filters_split_them(factory) -> None:
    with factory.begin() as session:
        session.add_all(_source("north", NOW - timedelta(minutes=2)))
        session.add_all(
            [
                # 11:45 AM PT: two qualifying arrivals.
                _window(
                    datetime(2026, 10, 15, 18, 45, tzinfo=timezone.utc),
                    jobs_discovered=5,
                    qualifying_discovered=2,
                    boards_checked=40,
                    postings_checked=900,
                    sources_attempted=42,
                    poll_attempts=55,
                    failed_checks=2,
                ),
                # 11:30 AM PT: checked, nothing new at all.
                _window(
                    datetime(2026, 10, 15, 18, 30, tzinfo=timezone.utc),
                    boards_checked=38,
                    postings_checked=870,
                    sources_attempted=38,
                    poll_attempts=50,
                    failed_checks=0,
                ),
                # 11:15 AM PT: new postings, none of them for the owner.
                _window(
                    datetime(2026, 10, 15, 18, 15, tzinfo=timezone.utc),
                    jobs_discovered=3,
                    boards_checked=37,
                    postings_checked=850,
                ),
            ]
        )

    with factory() as session:
        everything = build_pulls(session, zone=PT, now=NOW)
        quiet = build_pulls(session, zone=PT, now=NOW, filter="quiet")
        found = build_pulls(session, zone=PT, now=NOW, filter="opportunities")

    assert everything.status.state == "live"
    assert [b.outcome for b in everything.buckets] == ["opportunities", "quiet", "new_postings"]
    assert everything.day.counts == {"all": 3, "opportunities": 1, "quiet": 2}
    assert everything.day.new_postings == 8
    assert everything.day.new_qualifying == 2

    top = everything.buckets[0]
    # Attempted, answered and failed are three numbers, not one.
    assert (top.sources_attempted, top.sources_succeeded, top.failed_checks, top.poll_attempts) == (42, 40, 2, 55)
    assert top.end == datetime(2026, 10, 15, 19, 0, tzinfo=timezone.utc).isoformat()
    assert top.telemetry == "full"

    # Written before attempts were recorded: reported, not invented.
    old = everything.buckets[2]
    assert old.telemetry == "partial"
    assert old.sources_attempted is None and old.failed_checks is None and old.poll_attempts is None

    assert [b.outcome for b in quiet.buckets] == ["quiet", "new_postings"]
    assert [b.outcome for b in found.buckets] == ["opportunities"]
    # Counts describe the day, whatever the filter shows.
    assert quiet.day.counts == everything.day.counts

    assert everything.summary.new_postings == 8
    assert everything.summary.new_qualifying == 2
    assert everything.summary.windows == 3
    assert everything.summary.windows_with_failures == 1


def test_midnight_splits_days_in_the_display_zone(factory) -> None:
    with factory.begin() as session:
        session.add_all(
            [
                # 11:45 PM PT on the 14th, which is 06:45 UTC on the 15th.
                _window(datetime(2026, 10, 15, 6, 45, tzinfo=timezone.utc), jobs_discovered=1),
                # 12:00 AM PT on the 15th.
                _window(datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc), jobs_discovered=2),
            ]
        )

    with factory() as session:
        today = build_pulls(session, zone=PT, now=NOW)
        yesterday = build_pulls(session, zone=PT, now=NOW, day=date(2026, 10, 14))
        future = build_pulls(session, zone=PT, now=NOW, day=date(2026, 10, 20))

    assert [b.new_postings for b in today.buckets] == [2]
    assert today.prev_date == "2026-10-14"
    assert today.next_date is None

    assert [b.new_postings for b in yesterday.buckets] == [1]
    assert yesterday.prev_date is None
    assert yesterday.next_date == "2026-10-15"

    # A day that has not happened yet is today.
    assert future.date == "2026-10-15"


def test_a_day_is_23_hours_when_the_clocks_go_forward() -> None:
    start, end = day_bounds(date(2026, 3, 8), PT)
    assert end - start == timedelta(hours=23)


# --- what the scheduler attempted ----------------------------------------


def test_attempts_failures_and_repeat_reads_are_counted_apart() -> None:
    """One board read twice, one board failing, one failing then
    answering. Three boards attempted, five attempts, two answered,
    two failed: the failure and the later success both count."""

    moments = [datetime(2026, 10, 15, 18, 46, tzinfo=timezone.utc)]
    clock = FakeClock()
    flaky_calls = {"n": 0}

    def poller(source: SourceDefinition):
        if source.source_account == "down":
            raise RuntimeError("board unavailable")
        if source.source_account == "flaky":
            flaky_calls["n"] += 1
            if flaky_calls["n"] == 1:
                raise RuntimeError("timed out")
        return SimpleNamespace(
            fetched_count=10,
            checked_count=10,
            evaluated_count=0,
            alert_candidate_count=0,
            stale_suppressed_count=0,
            queued_notification_count=0,
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                make_source(source_account="steady", poll_interval_seconds=300),
                make_source(source_account="down", poll_interval_seconds=600),
                make_source(source_account="flaky", poll_interval_seconds=300),
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
        wall_clock=lambda: moments[0],
    )

    window = datetime(2026, 10, 15, 18, 45, tzinfo=timezone.utc)

    runtime.run_due_sources()
    moments[0] = datetime(2026, 10, 15, 18, 51, tzinfo=timezone.utc)
    clock.advance(300)
    runtime.run_due_sources()

    activity = runtime.activity_since(window)

    assert activity.sources_attempted == 3
    assert activity.poll_attempts == 5
    assert activity.succeeded == 2
    assert activity.failed == 2
    assert activity.postings == 20

    # Nothing attempted after the window closed counts in the next one.
    assert runtime.activity_since(datetime(2026, 10, 15, 19, 0, tzinfo=timezone.utc)).poll_attempts == 0


def test_recorded_attempts_are_never_lowered() -> None:
    """After a restart the scheduler remembers nothing from before it;
    the window keeps what it already counted."""

    run = PollSessionRecord(sources_attempted=None, poll_attempts=None, failed_checks=None)

    record_attempts(run, SimpleNamespace(sources_attempted=30, poll_attempts=41, failed=3))
    record_attempts(run, SimpleNamespace(sources_attempted=4, poll_attempts=4, failed=0))

    assert (run.sources_attempted, run.poll_attempts, run.failed_checks) == (30, 41, 3)


# --- the route --------------------------------------------------------------


@pytest.fixture(name="app_factory")
def fixture_app(factory):
    get_settings.cache_clear()

    def build(signed_in: bool):
        def override():
            with factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_session] = override
        if signed_in:
            app.dependency_overrides[require_auth] = lambda: None
        return TestClient(app)

    yield build
    get_settings.cache_clear()


def test_route_answers_with_the_contract_and_rejects_a_bad_zone(app_factory) -> None:
    client = app_factory(True)

    body = client.get("/api/pulls", params={"tz": "America/Los_Angeles", "filter": "quiet"}).json()
    assert body["timezone"] == "America/Los_Angeles"
    assert body["filter"] == "quiet"
    assert body["status"]["state"] == "unknown"
    assert body["buckets"] == []

    bad = client.get("/api/pulls", params={"tz": "Mars/Olympus"})
    assert bad.status_code == 422


def test_route_is_private(app_factory, monkeypatch) -> None:
    monkeypatch.setenv("ACE_AUTH", "required")
    get_settings.cache_clear()
    client = app_factory(False)

    assert client.get("/api/pulls").status_code == 401
