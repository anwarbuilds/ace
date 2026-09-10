"""Tests for the applied-date drift repair.

The asymmetry is the whole point. Missing a drifted row leaves one date
a day out, which the user can see and fix. Catching a row that is not
drifted rewrites a real application date to something that never
happened, and nothing downstream would ever question it.

So most of these pin the refusal to touch a row.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    JobMarkRecord,
    JobRecord,
)
from backend.scripts.repair_applied_date_drift import (
    _as_utc,
    find_drifted,
)


PACIFIC = ZoneInfo(
    "America/Los_Angeles"
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


def add_mark(
    session: Session,
    *,
    index: int,
    applied_at: datetime,
    status_changed_at: datetime | None,
) -> None:
    """Insert one job and the mark recorded against it."""

    moment = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index
        ),
        company=f"Company {index}",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            "https://example.com"
            f"/jobs/{index}"
        ),
        posted_at=moment,
        content_hash=f"hash-{index}",
        first_seen_at=moment,
        last_seen_at=moment,
        is_active=True,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobMarkRecord(
            job_id=job.id,
            applied_at=applied_at,
            status_changed_at=(
                status_changed_at
            ),
            updated_at=moment,
        )
    )

    session.flush()


def noon_utc(
    day: int,
) -> datetime:
    """The instant an imported sheet date is stored as."""

    return datetime(
        2026,
        9,
        day,
        12,
        0,
        tzinfo=timezone.utc,
    )


def pacific(
    day: int,
    hour: int,
) -> datetime:
    """A local wall-clock moment, as the stored UTC instant."""

    return datetime(
        2026,
        9,
        day,
        hour,
        0,
        tzinfo=PACIFIC,
    ).astimezone(
        timezone.utc
    )


def test_an_evening_mark_pushed_a_day_forward_is_found(
    session_factory,
) -> None:
    """The bug itself.

    Marked at 19:00 on the 9th in Seattle, which is already the 10th in
    UTC. The export wrote "10 September", re-importing read that back as
    a real date, and the click's own instant was lost.
    """

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                10
            ),
            status_changed_at=pacific(
                9,
                19,
            ),
        )

        drifted = find_drifted(
            session,
            zone=PACIFIC,
        )

        assert len(
            drifted
        ) == 1


def test_an_old_application_imported_later_is_left_alone(
    session_factory,
) -> None:
    """The case that must not be swept up with it.

    A job applied to in August and typed into the sheet, then imported
    in September, legitimately has an applied date well before the
    moment ACE recorded it. That gap is correct. Repairing it would
    overwrite a real date with the day the import happened to run.
    """

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                1
            ),
            status_changed_at=pacific(
                9,
                19,
            ),
        )

        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_a_daytime_mark_is_left_alone(
    session_factory,
) -> None:
    """Before the rollover hour the drift cannot have happened."""

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                10
            ),
            status_changed_at=pacific(
                9,
                10,
            ),
        )

        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_a_mark_still_holding_its_click_instant_is_left_alone(
    session_factory,
) -> None:
    """Only a date that went round the import loop can have drifted.

    A mark never exported and re-imported still carries the real time of
    the click, not noon, and its date was never rewritten.
    """

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=pacific(
                9,
                19,
            ),
            status_changed_at=pacific(
                9,
                19,
            ),
        )

        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_a_gap_of_more_than_one_day_is_left_alone(
    session_factory,
) -> None:
    """The rollover moves a date by exactly one day, never more."""

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                12
            ),
            status_changed_at=pacific(
                9,
                19,
            ),
        )

        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_a_mark_with_no_recorded_change_is_left_alone(
    session_factory,
) -> None:
    """Without the click's own instant there is no evidence to act on."""

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                10
            ),
            status_changed_at=None,
        )

        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_the_repair_restores_the_instant_of_the_click(
    session_factory,
) -> None:
    """The real answer, not a reconstruction of it.

    status_changed_at still holds the moment the mark was made, so the
    repair puts that back rather than inventing noon on the corrected
    day.
    """

    clicked = pacific(
        9,
        19,
    )

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                10
            ),
            status_changed_at=clicked,
        )

        mark, _job = find_drifted(
            session,
            zone=PACIFIC,
        )[0]

        mark.applied_at = (
            mark.status_changed_at
        )

        session.flush()

        # Normalised the way the script reads it. SQLite gives the
        # value back without its zone, and reading that as system-local
        # is the very mistake being tested for.
        assert (
            _as_utc(
                mark.applied_at
            )
            .astimezone(
                PACIFIC
            )
            .date()
            == clicked.astimezone(
                PACIFIC
            ).date()
        )

        # And it must not be found a second time.
        assert find_drifted(
            session,
            zone=PACIFIC,
        ) == []


def test_a_zone_that_never_rolled_over_finds_nothing(
    session_factory,
) -> None:
    """The rule is about the reader's zone, not a fixed offset.

    Run against UTC itself, an evening mark and its stored date fall on
    the same day, so there is nothing to repair.
    """

    with session_factory() as session:
        add_mark(
            session,
            index=1,
            applied_at=noon_utc(
                10
            ),
            status_changed_at=datetime(
                2026,
                9,
                10,
                2,
                43,
                tzinfo=timezone.utc,
            ),
        )

        assert find_drifted(
            session,
            zone=ZoneInfo(
                "UTC"
            ),
        ) == []
