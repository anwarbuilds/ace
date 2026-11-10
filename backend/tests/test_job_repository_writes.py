"""An unchanged posting is not rewritten on every read (OPS-05).

Measured on 2026-11-09: refreshing every posting's last-seen time on every
read was about 1.2 million row rewrites an hour. Fictional postings only.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    event,
)
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import JobRecord
from backend.app.models.job import CanonicalJob
from backend.app.persistence.repository import (
    LAST_SEEN_REFRESH,
    JobRepository,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


START = datetime(
    2026,
    9,
    6,
    12,
    0,
    tzinfo=timezone.utc,
)

SOURCE = "greenhouse"

ACCOUNT = "fictional-robotics"


def posting(
    *,
    external_id: str = "1001",
    title: str = "Software Engineer, New Grad",
    updated_at: datetime | None = None,
) -> CanonicalJob:
    return CanonicalJob(
        source=SOURCE,
        company="Fictional Robotics",
        external_id=external_id,
        title=title,
        location="Remote, US",
        description="Build fictional robots.",
        official_url=f"https://boards.example/fictional/{external_id}",
        posted_at=START - timedelta(days=1),
        updated_at=updated_at,
    )


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(
        engine
    )

    return engine


def observe(
    engine,
    jobs: list[CanonicalJob],
    at: datetime,
) -> tuple[dict, list[str]]:
    """One read: the statuses, and every UPDATE the database received."""

    updates: list[str] = []

    def capture(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if statement.lstrip().upper().startswith(
            "UPDATE"
        ):
            updates.append(
                statement
            )

    event.listen(
        engine,
        "before_cursor_execute",
        capture,
    )

    try:
        with Session(engine) as session:
            statuses = JobRepository(
                session
            ).observe_jobs(
                source=SOURCE,
                source_account=ACCOUNT,
                jobs=jobs,
                observed_at=at,
            )

            session.commit()

    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            capture,
        )

    return statuses, updates


def stored(
    engine,
) -> JobRecord:
    with Session(engine) as session:
        record = session.query(
            JobRecord
        ).one()

        session.expunge(
            record
        )

        return record


def as_utc(
    value: datetime,
) -> datetime:
    return (
        value
        if value.tzinfo
        else value.replace(
            tzinfo=timezone.utc
        )
    )


def test_an_unchanged_posting_read_again_soon_is_not_rewritten(
    engine,
) -> None:
    observe(engine, [posting()], START)

    statuses, updates = observe(
        engine,
        [posting()],
        START
        + timedelta(
            minutes=15
        ),
    )

    assert statuses == {
        "1001": JobObservationStatus.UNCHANGED,
    }

    assert updates == []

    assert as_utc(
        stored(engine).last_seen_at
    ) == START


def test_its_last_seen_time_is_refreshed_once_an_hour_old(
    engine,
) -> None:
    observe(engine, [posting()], START)

    later = START + LAST_SEEN_REFRESH

    statuses, updates = observe(
        engine,
        [posting()],
        later,
    )

    assert statuses == {
        "1001": JobObservationStatus.UNCHANGED,
    }

    assert len(updates) == 1

    assert as_utc(
        stored(engine).last_seen_at
    ) == later


def test_a_changed_posting_is_written_in_full_at_once(
    engine,
) -> None:
    observe(engine, [posting()], START)

    soon = START + timedelta(
        minutes=5
    )

    statuses, _updates = observe(
        engine,
        [
            posting(
                title="Software Engineer I, New Grad",
            )
        ],
        soon,
    )

    assert statuses == {
        "1001": JobObservationStatus.UPDATED,
    }

    record = stored(
        engine
    )

    assert record.title == "Software Engineer I, New Grad"

    assert as_utc(
        record.last_seen_at
    ) == soon


def test_a_reopened_posting_is_written_in_full_at_once(
    engine,
) -> None:
    observe(engine, [posting()], START)

    with Session(engine) as session:
        record = session.query(
            JobRecord
        ).one()

        record.is_active = False

        record.closed_at = START

        session.commit()

    soon = START + timedelta(
        minutes=5
    )

    statuses, _updates = observe(
        engine,
        [posting()],
        soon,
    )

    assert statuses == {
        "1001": JobObservationStatus.REOPENED,
    }

    record = stored(
        engine
    )

    assert record.is_active

    assert record.closed_at is None

    assert as_utc(
        record.last_seen_at
    ) == soon


def test_a_new_provider_update_time_is_kept_without_counting_as_an_edit(
    engine,
) -> None:
    observe(
        engine,
        [posting(updated_at=START)],
        START,
    )

    edited_at = START + timedelta(
        minutes=10
    )

    statuses, updates = observe(
        engine,
        [posting(updated_at=edited_at)],
        START
        + timedelta(
            minutes=15
        ),
    )

    assert statuses == {
        "1001": JobObservationStatus.UNCHANGED,
    }

    assert len(updates) == 1

    record = stored(
        engine
    )

    assert as_utc(
        record.source_updated_at
    ) == edited_at

    assert as_utc(
        record.last_seen_at
    ) == START


def test_an_unchanged_provider_update_time_writes_nothing(
    engine,
) -> None:
    observe(
        engine,
        [posting(updated_at=START)],
        START,
    )

    _statuses, updates = observe(
        engine,
        [posting(updated_at=START)],
        START
        + timedelta(
            minutes=15
        ),
    )

    assert updates == []
