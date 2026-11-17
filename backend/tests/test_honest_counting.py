"""Honest counting: every board and company in exactly one group (REC-05).

Every company and board here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.accounting import (
    OFF,
    REFUSED_BOARD,
    STALE,
    UNREAD,
    WORKING,
    board_group,
    counting_report,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    EmployerLead,
    HostPolicyRecord,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    SourceState,
)


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


def board(account, *, source_type="greenhouse", enabled=True, read=None, host=None):
    rows = [
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            source_host=host,
            company_name=account.title(),
            enabled=enabled,
            poll_interval_seconds=900,
        )
    ]
    if read is not None:
        rows.append(
            SourceState(
                source=source_type,
                source_account=account,
                initialized_at=read,
                last_success_at=read,
                last_job_count=4,
            )
        )
    return rows


def lead(key, state):
    return EmployerLead(
        company_key=key,
        company_name=key.title(),
        origin="network",
        origin_details=[],
        state=state,
        reason="",
        boards=[],
        first_seen_at=NOW,
        next_check_at=NOW,
    )


def test_each_board_lands_in_one_group_in_order() -> None:
    fresh = NOW - timedelta(hours=3)
    old = NOW - timedelta(days=3)
    assert board_group(enabled=False, refused=True, last_success_at=fresh, has_state=True, now=NOW) == OFF
    assert board_group(enabled=True, refused=True, last_success_at=fresh, has_state=True, now=NOW) == REFUSED_BOARD
    assert board_group(enabled=True, refused=False, last_success_at=None, has_state=False, now=NOW) == UNREAD
    assert board_group(enabled=True, refused=False, last_success_at=old, has_state=True, now=NOW) == STALE
    assert board_group(enabled=True, refused=False, last_success_at=fresh, has_state=True, now=NOW) == WORKING


def test_groups_add_up_and_feeds_companies_and_jobs_stay_apart(session) -> None:
    rows = []
    rows += board("northwind", read=NOW - timedelta(hours=1))
    rows += board("lumora", read=NOW - timedelta(hours=5))
    rows += board("kestrel", read=NOW - timedelta(days=4))
    rows += board("driftmark")
    rows += board("halcyon", enabled=False, read=NOW)
    rows += board("closedco/External", source_type="workday", host="closedco.wd5.myworkdayjobs.example", read=NOW)
    rows += board("new-grad", source_type="simplify", read=NOW)
    rows.append(
        HostPolicyRecord(
            host="closedco.wd5.myworkdayjobs.example",
            platform="workday",
            paths=["/wday/cxs/closedco/External/jobs"],
            robots_verdict="refused",
            next_check_at=NOW,
        )
    )
    rows += [lead("northwind", "polling"), lead("lumora", "polling"), lead("palm ridge", "noreader"), lead("staffco", "agency")]
    rows += [
        JobRecord(
            id=1, source="greenhouse", source_account="northwind", external_id="1", company="Northwind",
            title="Software Engineer", location="Denver, CO", description="", official_url="",
            content_hash="a", first_seen_at=NOW, last_seen_at=NOW, is_active=True,
        ),
        JobRecord(
            id=2, source="greenhouse", source_account="lumora", external_id="2", company="Lumora",
            title="Account Manager", location="Austin, TX", description="", official_url="",
            content_hash="b", first_seen_at=NOW, last_seen_at=NOW, is_active=True,
        ),
        JobEvaluationRecord(
            job_id=1, eligibility_status="PASS", role_family="SOFTWARE_ENGINEERING", role_priority="HIGH",
            rule_version="test", reason_codes=[], reasons=[], content_hash="a", is_early_career=True,
            is_new_grad=True, requirements_verified=True, evaluated_at=NOW,
        ),
    ]
    session.add_all(rows)
    session.commit()

    report = counting_report(session, now=NOW)

    groups = {item["key"]: item["count"] for item in report["boards"]["groups"]}
    assert groups == {WORKING: 2, STALE: 1, UNREAD: 1, REFUSED_BOARD: 1, OFF: 1}
    assert report["boards"]["total"] == sum(groups.values()) == 6
    assert report["feeds"] == 1

    companies = {item["key"]: item["count"] for item in report["companies"]["groups"]}
    assert report["companies"]["total"] == sum(companies.values()) == 4
    assert companies["polling"] == 2 and companies["noreader"] == 1 and companies["agency"] == 1

    assert report["jobs"] == {"open": 2, "passing": 1}
