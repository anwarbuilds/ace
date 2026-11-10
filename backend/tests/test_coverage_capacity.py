"""Can ace keep up? The capacity block's numbers (OPS-05). Fictional data."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.coverage import capacity as capacity_module
from backend.app.coverage.capacity import capacity_report
from backend.app.db.base import Base
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
    PollSessionRecord,
    SourceState,
)


NOW = datetime(
    2026,
    9,
    6,
    12,
    7,
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

    with Session(engine) as session:
        yield session


def board(
    session: Session,
    account: str,
    *,
    interval: int = 900,
    read_ago: timedelta | None = timedelta(minutes=5),
    source_type: str = "greenhouse",
    first_read_ago: timedelta = timedelta(days=30),
) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=f"Fictional {account}",
            enabled=True,
            poll_interval_seconds=interval,
            discovery_source="test",
            first_discovered_at=NOW - first_read_ago,
            created_at=NOW - first_read_ago,
            updated_at=NOW,
        )
    )

    if read_ago is not None:
        session.add(
            SourceState(
                source=source_type,
                source_account=account,
                initialized_at=NOW - first_read_ago,
                last_success_at=NOW - read_ago,
                last_job_count=3,
            )
        )


def window(
    session: Session,
    started_at: datetime,
    attempts: int,
) -> None:
    session.add(
        PollSessionRecord(
            started_at=started_at,
            last_activity_at=started_at + timedelta(minutes=14),
            jobs_discovered=0,
            qualifying_discovered=0,
            boards_checked=attempts,
            postings_checked=0,
            sources_attempted=attempts,
            poll_attempts=attempts,
            failed_checks=0,
        )
    )


counter = iter(
    range(1, 100_000)
)


def job(
    session: Session,
    *,
    account: str,
    posted_ago: timedelta | None,
    seen_ago: timedelta,
    source: str = "greenhouse",
    posted_at: datetime | None = None,
) -> None:
    number = next(counter)

    session.add(
        JobRecord(
            source=source,
            source_account=account,
            external_id=str(number),
            company="Fictional Labs",
            title="Software Engineer",
            location="Remote, US",
            description="Fictional",
            official_url=f"https://boards.example/{number}",
            posted_at=(
                posted_at
                if posted_at is not None
                else (
                    NOW - posted_ago
                    if posted_ago is not None
                    else None
                )
            ),
            content_hash="fictional",
            first_seen_at=NOW - seen_ago,
            last_seen_at=NOW - seen_ago,
            is_active=True,
        )
    )


def test_reads_count_the_last_four_complete_quarter_hours(session) -> None:
    board(session, "alpha", interval=900)
    board(session, "beta", interval=3600)

    # 12:07 now: the windows from 11:00 to 11:45 count; 12:00 is not complete.
    for minute, attempts in ((0, 10), (15, 11), (30, 12), (45, 13)):
        window(session, NOW.replace(hour=11, minute=minute), attempts)

    window(session, NOW.replace(hour=12, minute=0), 99)
    window(session, NOW.replace(hour=10, minute=45), 77)

    session.flush()

    report = capacity_report(session, now=NOW)

    assert report["reads_last_hour"] == 46

    # Four a quarter hour plus one an hour.
    assert report["reads_asked_per_hour"] == 5

    assert report["keeping_up"] is True


def test_a_board_read_late_or_never_is_not_on_time(session) -> None:
    board(session, "fresh", interval=900, read_ago=timedelta(minutes=20))
    board(session, "late", interval=900, read_ago=timedelta(minutes=23))
    board(session, "never", interval=900, read_ago=None)
    board(session, "feed", source_type="simplify", interval=1800)

    session.flush()

    report = capacity_report(session, now=NOW)

    # The feed is not a board ace reads for one employer.
    assert report["boards"] == 3

    assert report["boards_on_time"] == 1


def test_behind_when_reads_fall_short_of_what_the_boards_ask(session) -> None:
    for index in range(4):
        board(session, f"board{index}", interval=300)

    window(session, NOW.replace(hour=11, minute=30), 20)

    session.flush()

    report = capacity_report(session, now=NOW)

    assert report["reads_asked_per_hour"] == 48

    assert report["keeping_up"] is False

    assert report["status_label"] == (
        "ace is behind: some boards are read later than planned."
    )


def test_new_job_speed_uses_only_real_posting_times_on_boards_already_read(
    session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        capacity_module,
        "MIN_JOBS_FOR_SPEED",
        3,
    )

    board(session, "steady")
    board(session, "brand-new", first_read_ago=timedelta(hours=3))

    # Counted: 4, 10 and 30 minutes from posted to seen.
    for minutes in (4, 10, 30):
        job(
            session,
            account="steady",
            posted_ago=timedelta(hours=2, minutes=minutes),
            seen_ago=timedelta(hours=2),
        )

    # A date without a time of day says nothing about minutes.
    job(
        session,
        account="steady",
        posted_ago=None,
        posted_at=NOW.replace(hour=0, minute=0),
        seen_ago=timedelta(hours=1),
    )

    # Posted before ace's first read of its board: may have been there already.
    job(
        session,
        account="brand-new",
        posted_ago=timedelta(hours=3, minutes=30),
        seen_ago=timedelta(hours=2),
    )

    # A reposting keeps its first date.
    job(
        session,
        account="steady",
        posted_ago=timedelta(days=9),
        seen_ago=timedelta(hours=1),
    )

    # Seen more than a day ago.
    job(
        session,
        account="steady",
        posted_ago=timedelta(hours=30),
        seen_ago=timedelta(hours=26),
    )

    session.flush()

    speed = capacity_report(session, now=NOW)["new_jobs"]

    assert speed["jobs"] == 3

    assert speed["typical_minutes"] == 10.0

    assert speed["nine_in_ten_minutes"] == pytest.approx(26.0)


def test_too_few_new_jobs_give_no_speed(session) -> None:
    board(session, "steady")

    job(
        session,
        account="steady",
        posted_ago=timedelta(hours=2, minutes=5),
        seen_ago=timedelta(hours=2),
    )

    session.flush()

    speed = capacity_report(session, now=NOW)["new_jobs"]

    assert speed == {
        "jobs": 1,
        "typical_minutes": None,
        "nine_in_ten_minutes": None,
    }
