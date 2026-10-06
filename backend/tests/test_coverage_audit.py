"""ACE's own daily account of what it caught late, and what it cannot see.

The user kept finding misses one report at a time -- Microsoft, Two
Sigma, Chewy -- and asked for them to be found and corrected every day.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.coverage.audit import (
    BOARD_ADDED_LATER,
    REPUBLISHED,
    SEEN_LATE,
    caught_late,
    feed_only,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
)


NOW = datetime(
    2026,
    10,
    6,
    18,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(
        engine
    )

    with sessionmaker(
        bind=engine,
        class_=Session,
    )() as session:
        yield session


_ids = iter(range(1, 10_000))


def add_job(
    session: Session,
    *,
    source: str,
    company: str,
    title: str,
    url: str,
    seen: datetime,
    status: str = "PASS",
    account: str = "acct",
    posted: datetime | None = None,
) -> None:
    key = next(_ids)

    job = JobRecord(
        source=source,
        source_account=account,
        external_id=str(key),
        company=company,
        title=title,
        location="Bellevue, WA",
        description="",
        official_url=url,
        posted_at=posted,
        content_hash=f"hash-{key}",
        first_seen_at=seen,
        last_seen_at=seen,
        is_active=True,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status=status,
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{key}",
            requirements_verified=True,
            is_early_career=True,
            is_new_grad=False,
            required_experience_years=None,
            evaluated_at=seen,
        )
    )

    session.flush()


def add_board(
    session: Session,
    *,
    company: str,
    account: str,
    added: datetime,
    source_type: str = "workday",
) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=company,
            enabled=True,
            poll_interval_seconds=900,
            created_at=added,
            first_discovered_at=added,
        )
    )

    session.flush()


CHEWY_LINK = (
    "https://wd5.myworkdaysite.com/recruiting/chewy/External/job/"
    "Bellevue-WA/Software-Engineer-I_R30985-1"
)


def test_a_role_the_feed_listed_first_is_reported_with_its_cause(
    session: Session,
) -> None:
    # Chewy's board was only added after the feed listed the role.
    add_board(
        session,
        company="Chewy",
        account="chewy/External",
        added=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        source="simplify",
        company="Chewy",
        title="Software Engineer 1",
        url=CHEWY_LINK,
        seen=NOW - timedelta(hours=6),
    )

    add_job(
        session,
        source="workday",
        account="chewy/External",
        company="Chewy",
        title="Software Engineer I",
        url=CHEWY_LINK,
        seen=NOW - timedelta(minutes=50),
    )

    # Duolingo's was already read, daily: the role was seen late.
    add_board(
        session,
        company="Duolingo",
        account="duolingo",
        added=NOW - timedelta(days=10),
        source_type="greenhouse",
    )

    add_job(
        session,
        source="simplify",
        company="Duolingo",
        title="Software Engineer, New Grad",
        url="https://boards.greenhouse.io/duolingo/jobs/1",
        seen=NOW - timedelta(hours=30),
    )

    add_job(
        session,
        source="greenhouse",
        account="duolingo",
        company="Duolingo",
        title="Software Engineer, New Grad",
        url="https://boards.greenhouse.io/duolingo/jobs/1",
        seen=NOW - timedelta(hours=6),
    )

    report = caught_late(
        session,
        now=NOW,
    )

    causes = {
        row["company"]: (row["cause"], row["lag_hours"])
        for row in report["rows"]
    }

    assert causes == {
        "Chewy": (BOARD_ADDED_LATER, 5.2),
        "Duolingo": (SEEN_LATE, 24.0),
    }

    assert (report["board_added_later"], report["seen_late"]) == (1, 1)


def test_a_role_seen_first_or_in_the_same_quarter_hour_is_not_a_miss(
    session: Session,
) -> None:
    add_job(
        session,
        source="simplify",
        company="TikTok",
        title="Backend Software Engineer Graduate",
        url="https://lifeattiktok.com/search/1",
        seen=NOW - timedelta(minutes=20),
    )

    add_job(
        session,
        source="bytedance",
        company="TikTok",
        title="Backend Software Engineer Graduate (Feed Safety)",
        url="https://lifeattiktok.com/search/1",
        seen=NOW - timedelta(minutes=10),
    )

    add_job(
        session,
        source="simplify",
        company="TikTok",
        title="Frontend Engineer Graduate",
        url="https://lifeattiktok.com/search/2",
        seen=NOW - timedelta(hours=1),
    )

    add_job(
        session,
        source="bytedance",
        company="TikTok",
        title="Frontend Engineer Graduate",
        url="https://lifeattiktok.com/search/2",
        seen=NOW - timedelta(hours=5),
    )

    assert caught_late(
        session,
        now=NOW,
    )["count"] == 0


def test_feed_only_names_where_direct_coverage_is_missing(
    session: Session,
) -> None:
    # Two passing roles from a company ACE reads no board for.
    for index in range(2):
        add_job(
            session,
            source="simplify",
            company="Garmin",
            title=f"Software Engineer {index}",
            url=f"https://careers.garmin.com/jobs/{index}",
            seen=NOW,
        )

    # A feed role ACE also holds directly is the queue's hidden
    # duplicate, not a gap.
    add_job(
        session,
        source="simplify",
        company="Chewy",
        title="Software Engineer 1",
        url=CHEWY_LINK,
        seen=NOW,
    )

    add_job(
        session,
        source="workday",
        company="Chewy",
        title="Software Engineer I",
        url=CHEWY_LINK,
        seen=NOW,
    )

    # A board ACE reads, missing a role the feed has: the reader's miss.
    add_board(
        session,
        company="Pinterest",
        account="pinterest",
        added=NOW - timedelta(days=30),
        source_type="greenhouse",
    )

    add_job(
        session,
        source="simplify",
        company="Pinterest",
        title="University Grad Software Engineer",
        url="https://www.pinterestcareers.com/jobs/?gh_jid=7838591",
        seen=NOW,
    )

    assert feed_only(
        session
    ) == [
        {"company": "Garmin", "passing": 2, "board_read": False},
        {"company": "Pinterest", "passing": 1, "board_read": True},
    ]



def test_a_role_republished_after_the_feed_listed_it_is_not_a_miss(
    session: Session,
) -> None:
    """Stripe's role: listed by the feed on the 18th, published on its
    board on the 2nd at 18:52, read by ACE at 18:55."""

    add_board(
        session,
        company="Stripe",
        account="stripe",
        added=NOW - timedelta(days=30),
        source_type="greenhouse",
    )

    link = "https://stripe.com/jobs/search?gh_jid=8249901"

    add_job(
        session,
        source="simplify",
        company="Stripe",
        title="Software Engineer",
        url=link,
        seen=NOW - timedelta(days=14),
    )

    add_job(
        session,
        source="greenhouse",
        account="stripe",
        company="Stripe",
        title="Software Engineer",
        url=link,
        seen=NOW - timedelta(hours=2),
        posted=NOW - timedelta(hours=2, minutes=3),
    )

    report = caught_late(
        session,
        now=NOW,
    )

    assert [row["cause"] for row in report["rows"]] == [REPUBLISHED]

    assert (report["seen_late"], report["republished"]) == (0, 1)
