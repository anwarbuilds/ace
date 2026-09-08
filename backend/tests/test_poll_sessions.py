"""Tests for grouping discoveries into readable runs.

The grouping decision matters more than the plumbing. A scheduler cycle
is the wrong unit: measured live, 38 of roughly 65 cycles polled a
single source, so cycle-level runs would hold one job each and tell the
user nothing.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    PollSessionRecord,
)
from backend.app.persistence.sessions import (
    SESSION_MERGE_WINDOW,
    record_check,
    record_discoveries,
)


NOW = datetime(
    2026,
    9,
    6,
    9,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    """Provide an isolated in-memory database."""

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


def add_job(
    session: Session,
    *,
    external_id: str,
    first_seen_at: datetime,
    status: str = "PASS",
) -> JobRecord:
    """Insert one discovered job with its evaluation."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example Co",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            "https://example.com/"
            f"{external_id}"
        ),
        posted_at=first_seen_at,
        source_updated_at=None,
        content_hash=(
            f"hash-{external_id}"
        ),
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
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
            role_family=(
                "SOFTWARE_ENGINEERING"
            ),
            role_priority="PRIMARY",
            rule_version="test",
            reason_codes=[],
            reasons=[],
            required_experience_years=None,
            content_hash=(
                f"hash-{external_id}"
            ),
            evaluated_at=first_seen_at,
        )
    )

    session.flush()

    return job


def test_a_cycle_finding_nothing_creates_no_run(
    session_factory,
) -> None:
    """An empty run would be noise, not information."""

    with session_factory.begin() as session:
        run = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

        assert run is None

    with session_factory() as session:
        assert (
            session.scalars(
                select(
                    PollSessionRecord
                )
            ).all()
            == []
        )


def test_discovered_jobs_are_attached_to_a_run(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        for index in range(3):
            add_job(
                session,
                external_id=str(
                    index
                ),
                first_seen_at=NOW,
            )

        run = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

        assert run is not None

        assert run.jobs_discovered == 3

        assert (
            run.qualifying_discovered
            == 3
        )

    with session_factory() as session:
        jobs = session.scalars(
            select(
                JobRecord
            )
        ).all()

        assert all(
            job.first_seen_session_id
            is not None
            for job in jobs
        )


def test_nearby_discoveries_join_the_same_run(
    session_factory,
) -> None:
    """A staggered sweep is one pull, not five."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            first_seen_at=NOW,
        )

        record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

    later = NOW + timedelta(
        minutes=5
    )

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="2",
            first_seen_at=later,
        )

        record_discoveries(
            session,
            since=later
            - timedelta(
                minutes=1
            ),
            now=later,
        )

    with session_factory() as session:
        runs = session.scalars(
            select(
                PollSessionRecord
            )
        ).all()

    assert len(runs) == 1

    assert runs[0].jobs_discovered == 2


def test_distant_discoveries_start_a_new_run(
    session_factory,
) -> None:
    """A morning pull and an afternoon one stay separate."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            first_seen_at=NOW,
        )

        record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

    much_later = (
        NOW
        + SESSION_MERGE_WINDOW
        + timedelta(
            minutes=1
        )
    )

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="2",
            first_seen_at=much_later,
        )

        record_discoveries(
            session,
            since=much_later
            - timedelta(
                minutes=1
            ),
            now=much_later,
        )

    with session_factory() as session:
        runs = session.scalars(
            select(
                PollSessionRecord
            )
        ).all()

    assert len(runs) == 2

    assert all(
        run.jobs_discovered == 1
        for run in runs
    )


def test_a_job_is_claimed_by_exactly_one_run(
    session_factory,
) -> None:
    """Re-running must not double-count an already-claimed job."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            first_seen_at=NOW,
        )

        record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

    with session_factory.begin() as session:
        second = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

        assert second is None

    with session_factory() as session:
        run = session.scalars(
            select(
                PollSessionRecord
            )
        ).one()

    assert run.jobs_discovered == 1


def test_jobs_from_before_the_window_are_not_claimed(
    session_factory,
) -> None:
    """A run owns what it found, not the whole backlog."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="old",
            first_seen_at=NOW
            - timedelta(
                hours=3
            ),
        )

        run = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

        assert run is None


def test_rejected_jobs_count_as_discovered_but_not_qualifying(
    session_factory,
) -> None:
    """The two counts answer different questions."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            first_seen_at=NOW,
            status="PASS",
        )

        add_job(
            session,
            external_id="2",
            first_seen_at=NOW,
            status="REJECT",
        )

        run = record_discoveries(
            session,
            since=NOW
            - timedelta(
                minutes=5
            ),
            now=NOW,
        )

    assert run.jobs_discovered == 2

    assert run.qualifying_discovered == 1


def test_a_check_that_finds_nothing_is_still_recorded(
    session_factory,
) -> None:
    """record_discoveries never creates an empty run, which is right
    for a run, and left the activity log unable to answer the question
    it is read for. A check at 1:43pm that found nothing appeared
    nowhere, so the log's newest entry read an hour old while the
    header said the last check was a minute ago."""

    with session_factory() as session:
        assert record_discoveries(
            session,
            since=NOW,
            now=NOW,
        ) is None

        run = record_check(
            session,
            now=NOW,
        )

        session.commit()

        assert run is not None

        assert run.jobs_discovered == 0


def test_a_quiet_stretch_extends_one_entry(
    session_factory,
) -> None:
    """The scheduler completes a cycle every few seconds, so a row per
    cycle would be thousands a day. Inside the merge window the same
    entry is extended instead."""

    with session_factory() as session:
        first = record_check(
            session,
            now=NOW,
        )

        session.flush()

        first_id = first.id

        later = record_check(
            session,
            now=NOW
            + timedelta(
                minutes=5
            ),
        )

        session.commit()

        assert later.id == first_id

        stamp = later.last_activity_at

        if stamp.tzinfo is None:
            stamp = stamp.replace(
                tzinfo=timezone.utc
            )

        assert stamp == NOW + timedelta(
            minutes=5
        )


def test_a_gap_past_the_window_starts_a_new_entry(
    session_factory,
) -> None:
    """Otherwise one row would swallow a whole day and the log could
    not show when ACE stopped."""

    with session_factory() as session:
        first = record_check(
            session,
            now=NOW,
        )

        session.flush()

        first_id = first.id

        later = record_check(
            session,
            now=NOW
            + timedelta(
                minutes=45
            ),
        )

        session.commit()

        assert later.id != first_id
