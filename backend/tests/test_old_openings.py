"""Openings a month old are noise: hidden from the queue and the pulls.

The first read of a board brings in everything already on it. ACE shows
when it first saw a posting, so on 2026-10-06 roles opened in June and
April sat in the latest pull looking brand new. When a posting opened is
judged by the best evidence: a posting ACE watched appear on a board it
was already reading opened then, whatever date its employer reports; for
a board's first read, and for the feeds, the employer's date is all
there is.
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

from backend.app.api.marks import (
    set_mark,
)
from backend.app.api.queries import (
    JobFilters,
    list_jobs,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    SourceState,
)
from backend.app.persistence.sessions import (
    record_discoveries,
)


NOW = datetime(
    2026,
    10,
    7,
    12,
    tzinfo=timezone.utc,
)

# ACE's first read of the example board.
FIRST_READ = NOW - timedelta(
    days=20,
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def add_board(
    session: Session,
    *,
    source: str = "greenhouse",
    first_read: datetime = FIRST_READ,
) -> None:
    session.add(
        SourceState(
            source=source,
            source_account="example",
            initialized_at=first_read,
            last_success_at=NOW,
            last_job_count=1,
        )
    )

    session.flush()


def add_job(
    session: Session,
    *,
    key: str,
    first_seen_at: datetime,
    posted_days_ago: int | None,
    source: str = "greenhouse",
) -> JobRecord:
    job = JobRecord(
        source=source,
        source_account="example",
        external_id=key,
        company="Example Co",
        requisition_id=None,
        title=f"Software Engineer {key}",
        location="Seattle, WA, US",
        description="Build software.",
        official_url=f"https://example.com/{key}",
        posted_at=(
            None
            if posted_days_ago is None
            else NOW
            - timedelta(
                days=posted_days_ago
            )
        ),
        content_hash=f"hash-{key}",
        first_seen_at=first_seen_at,
        last_seen_at=NOW,
        is_active=True,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{key}",
            requirements_verified=True,
            is_early_career=True,
            is_new_grad=False,
            required_experience_years=None,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def queue(
    session: Session,
    **filters,
) -> list[str]:
    page = list_jobs(
        session,
        filters=JobFilters(
            **filters
        ),
        now=NOW,
    )

    return sorted(
        item.external_id
        for item in page.items
    )


def test_a_first_read_opening_a_month_old_is_hidden(
    session_factory,
) -> None:
    """onsemi's board, read for the first time, brought in a June role."""

    with session_factory() as session:
        add_board(
            session
        )

        add_job(
            session,
            key="june",
            first_seen_at=FIRST_READ,
            posted_days_ago=118,
        )

        add_job(
            session,
            key="last-week",
            first_seen_at=FIRST_READ,
            posted_days_ago=25,
        )

        assert queue(
            session
        ) == ["last-week"]


def test_a_posting_seen_to_appear_counts_from_when_it_appeared(
    session_factory,
) -> None:
    """Greenhouse keeps a reopened role's first publication date:
    Anthropic's, back on its board on 2026-09-28, says June."""

    with session_factory() as session:
        add_board(
            session
        )

        add_job(
            session,
            key="reopened",
            first_seen_at=NOW
            - timedelta(
                days=2
            ),
            posted_days_ago=120,
        )

        assert queue(
            session
        ) == ["reopened"]


def test_a_posting_seen_to_appear_still_ages(
    session_factory,
) -> None:
    with session_factory() as session:
        add_board(
            session,
            first_read=NOW
            - timedelta(
                days=60
            ),
        )

        add_job(
            session,
            key="seen-long-ago",
            first_seen_at=NOW
            - timedelta(
                days=40
            ),
            posted_days_ago=None,
        )

        assert queue(
            session
        ) == []


def test_a_feed_posting_goes_by_the_employers_date(
    session_factory,
) -> None:
    """A feed listing an old role does not make it a new one."""

    with session_factory() as session:
        add_board(
            session,
            source="simplify",
        )

        add_job(
            session,
            key="feed-old",
            source="simplify",
            first_seen_at=NOW
            - timedelta(
                days=1
            ),
            posted_days_ago=40,
        )

        assert queue(
            session
        ) == []


def test_an_undated_posting_counts_from_when_it_was_seen(
    session_factory,
) -> None:
    """Never claimed to be old without evidence."""

    with session_factory() as session:
        add_board(
            session,
            source="lever",
        )

        add_job(
            session,
            key="undated",
            source="lever",
            first_seen_at=FIRST_READ,
            posted_days_ago=None,
        )

        assert queue(
            session
        ) == ["undated"]


def test_old_openings_are_hidden_not_deleted(
    session_factory,
) -> None:
    with session_factory() as session:
        add_board(
            session
        )

        add_job(
            session,
            key="june",
            first_seen_at=FIRST_READ,
            posted_days_ago=118,
        )

        assert queue(
            session,
            max_opening_age_days=None,
        ) == ["june"]


def test_an_application_to_an_old_opening_stays_on_applied(
    session_factory,
) -> None:
    """Marks are history; age never hides them."""

    with session_factory() as session:
        add_board(
            session
        )

        job = add_job(
            session,
            key="june",
            first_seen_at=FIRST_READ,
            posted_days_ago=118,
        )

        set_mark(
            session,
            job_id=job.id,
            applied=True,
            now=NOW,
        )

        assert queue(
            session,
            mark="applied",
            statuses=(),
        ) == ["june"]


def test_a_pull_does_not_count_old_openings_as_arrivals(
    session_factory,
) -> None:
    """Counted, they made the pull say "12 passed" and the desktop alert
    fire for roles opened in June."""

    with session_factory() as session:
        add_board(
            session
        )

        # A second board, read for the first time this cycle.
        session.add(
            SourceState(
                source="workday",
                source_account="example",
                initialized_at=NOW,
                last_success_at=NOW,
                last_job_count=2,
            )
        )

        add_job(
            session,
            key="backlog",
            source="workday",
            first_seen_at=NOW,
            posted_days_ago=49,
        )

        add_job(
            session,
            key="fresh",
            source="workday",
            first_seen_at=NOW,
            posted_days_ago=1,
        )

        run = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=15
            ),
            now=NOW,
        )

        assert run.jobs_discovered == 2

        assert run.qualifying_discovered == 1
