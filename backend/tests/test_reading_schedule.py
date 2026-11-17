"""Is reading on schedule? (FRS-02) Every board here is fictional."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.schedule import plan_label, schedule_report
from backend.app.db.base import Base
from backend.app.db.models import JobSourceRecord, SourceState


NOW = datetime(2026, 11, 16, 16, 0, tzinfo=timezone.utc)


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


def board(session, source_type, account, *, interval, ago=None, unchanged_ago=None, enabled=True):
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=account,
            enabled=enabled,
            poll_interval_seconds=interval,
        )
    )
    if ago is not None:
        session.add(
            SourceState(
                source=source_type,
                source_account=account,
                initialized_at=NOW - timedelta(days=9),
                last_success_at=NOW - ago,
                last_unchanged_at=NOW - unchanged_ago if unchanged_ago else None,
                last_job_count=3,
            )
        )


def test_each_site_against_its_plan(session) -> None:
    board(session, "greenhouse", "a", interval=900, ago=timedelta(minutes=4))
    board(session, "greenhouse", "b", interval=900, ago=timedelta(minutes=50), unchanged_ago=timedelta(minutes=6))
    board(session, "greenhouse", "c", interval=900, ago=timedelta(minutes=30))  # late: past 22.5 min
    board(session, "workday", "d/Ext", interval=3600, ago=timedelta(minutes=70))  # due, not late
    board(session, "workday", "e/Ext", interval=3600, ago=timedelta(days=3))  # not read lately: left out
    board(session, "workday", "f/Ext", interval=3600)  # not read yet: left out
    board(session, "lever", "g", interval=900, ago=timedelta(minutes=1), enabled=False)
    board(session, "simplify", "new-grad", interval=900, ago=timedelta(minutes=1))
    session.commit()

    report = schedule_report(session, now=NOW)

    assert report["working_boards"] == 4
    sites = {row["site"]: row for row in report["sites"]}
    assert set(sites) == {"Greenhouse", "Workday"}
    assert sites["Greenhouse"]["boards"] == 3
    assert sites["Greenhouse"]["typical_minutes"] == 6.0
    assert sites["Greenhouse"]["late"] == 1
    assert sites["Greenhouse"]["plan"] == "Every 15 min"
    assert sites["Workday"]["late"] == 0
    assert report["late"] == 1
    # Due now: Greenhouse c (30 min against 15) and Workday d (70 against 60).
    assert report["due_now"] == 2
    assert report["longest_wait_minutes"] == 15.0


def test_plan_words() -> None:
    assert plan_label(900) == "Every 15 min"
    assert plan_label(3600) == "Hourly"
    assert plan_label(21600) == "Every 6 h"
    assert plan_label(86400) == "Daily"
