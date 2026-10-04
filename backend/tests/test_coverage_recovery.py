"""A board that stops answering is noticed, and a company that moved is
followed to its new one.

Postman's Greenhouse board had been gone seventeen days, and Amplitude,
Wayve and Iterable had moved to Ashby, before anyone noticed: the
scheduler logged each failure and carried on, and the old postings
stayed active, so Coverage still counted all four as reached.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.coverage.diagnosis import (
    NO_BOARD_FOUND,
    REACHED,
    Diagnosis,
)
from backend.app.coverage.probing import (
    BoardCandidate,
)
from backend.app.coverage.recovery import (
    dark_sources,
    recover_dark_sources,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
    SourceState,
)


NOW = datetime(
    2026,
    10,
    4,
    18,
    0,
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


def add_source(
    session: Session,
    *,
    source_type: str = "greenhouse",
    account: str = "amplitude",
    company: str = "Amplitude",
    last_success: timedelta | None = timedelta(days=6),
    created: timedelta = timedelta(days=20),
    interval: int = 900,
    enabled: bool = True,
) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=company,
            enabled=enabled,
            poll_interval_seconds=interval,
            created_at=NOW - created,
            first_discovered_at=NOW - created,
        )
    )

    if last_success is not None:
        session.add(
            SourceState(
                source=source_type,
                source_account=account,
                initialized_at=NOW - created,
                last_success_at=NOW - last_success,
                last_job_count=3,
            )
        )

    session.flush()


def add_job(
    session: Session,
    *,
    source: str = "greenhouse",
    account: str = "amplitude",
    external_id: str = "1",
) -> None:
    session.add(
        JobRecord(
            source=source,
            source_account=account,
            external_id=external_id,
            company="Amplitude",
            title="Software Engineer",
            location="San Francisco, CA",
            description="",
            official_url=f"https://example.com/{external_id}",
            content_hash=f"hash-{source}-{external_id}",
            first_seen_at=NOW - timedelta(days=10),
            last_seen_at=NOW - timedelta(days=6),
            is_active=True,
        )
    )

    session.flush()


def moved_to(
    source_type: str,
    account: str,
):
    def diagnose(company: str) -> Diagnosis:
        return Diagnosis(
            company=company,
            outcome=REACHED,
            detail=f"board page titled {company!r}",
            candidate=BoardCandidate(
                company=company,
                source_type=source_type,
                source_account=account,
                job_count=12,
                evidence=f"board page titled {company!r}",
            ),
        )

    return diagnose


def nothing_found(company: str) -> Diagnosis:
    return Diagnosis(
        company=company,
        outcome=NO_BOARD_FOUND,
        detail="Their site points at no job board ACE recognises.",
    )


def source(
    session: Session,
    source_type: str,
    account: str,
) -> JobSourceRecord | None:
    return session.scalar(
        sa.select(
            JobSourceRecord,
        ).where(
            JobSourceRecord.source_type == source_type,
            JobSourceRecord.source_account == account,
        )
    )


def test_a_company_that_moved_is_followed_to_its_new_board(
    session: Session,
) -> None:
    add_source(session)

    add_job(session, external_id="1")
    add_job(session, external_id="2")

    # Another company's posting, which must not be touched.
    add_job(
        session,
        source="ashby",
        account="wayve",
        external_id="w1",
    )

    [recovery] = recover_dark_sources(
        session,
        now=NOW,
        diagnose=moved_to("ashby", "amplitude"),
    )

    assert recovery.replaced_by == ("ashby", "amplitude")

    assert recovery.closed_jobs == 2

    new = source(session, "ashby", "amplitude")

    assert new is not None
    assert new.enabled
    # The name the user knows, the old cadence, and a host to poll.
    assert new.company_name == "Amplitude"
    assert new.poll_interval_seconds == 900
    assert new.source_host == "jobs.ashbyhq.com"
    assert new.discovery_source == "dark_source_recovery"

    assert not source(session, "greenhouse", "amplitude").enabled

    open_jobs = session.scalars(
        sa.select(
            JobRecord.external_id,
        ).where(
            JobRecord.is_active.is_(True),
        )
    ).all()

    assert open_jobs == ["w1"]


def test_a_source_that_answered_recently_is_not_dark(
    session: Session,
) -> None:
    add_source(
        session,
        last_success=timedelta(hours=2),
    )

    def diagnose(_company: str) -> Diagnosis:
        raise AssertionError(
            "a healthy source must not be diagnosed"
        )

    assert recover_dark_sources(
        session,
        now=NOW,
        diagnose=diagnose,
    ) == []


def test_a_slow_source_is_given_three_of_its_intervals(
    session: Session,
) -> None:
    """A daily board a few hours late is not dark."""

    add_source(
        session,
        account="daily-late",
        interval=86400,
        last_success=timedelta(hours=30),
    )

    add_source(
        session,
        account="daily-gone",
        interval=86400,
        last_success=timedelta(days=4),
    )

    assert [
        dark.source_account
        for dark in dark_sources(
            session,
            now=NOW,
        )
    ] == ["daily-gone"]


def test_a_source_that_never_answered_counts_from_when_it_was_added(
    session: Session,
) -> None:
    add_source(
        session,
        account="added-an-hour-ago",
        last_success=None,
        created=timedelta(hours=1),
    )

    add_source(
        session,
        account="added-two-days-ago",
        last_success=None,
        created=timedelta(days=2),
    )

    [dark] = dark_sources(
        session,
        now=NOW,
    )

    assert dark.source_account == "added-two-days-ago"

    assert dark.last_success_at is None


def test_nothing_better_found_leaves_the_source_alone(
    session: Session,
) -> None:
    """A board answering nothing may be a company with no openings.
    It stays polled, and stays listed as dark."""

    add_source(
        session,
        account="postman",
        company="Postman",
        last_success=timedelta(days=17),
    )

    add_job(session, account="postman")

    [recovery] = recover_dark_sources(
        session,
        now=NOW,
        diagnose=nothing_found,
    )

    assert recovery.replaced_by is None

    assert recovery.closed_jobs == 0

    assert source(session, "greenhouse", "postman").enabled

    assert session.scalar(
        sa.select(
            sa.func.count(),
        ).where(
            JobRecord.is_active.is_(True),
        )
    ) == 1


def test_the_same_board_spelled_differently_is_not_a_move(
    session: Session,
) -> None:
    add_source(
        session,
        source_type="ashby",
        account="Lightfield",
        company="Lightfield",
    )

    add_job(
        session,
        source="ashby",
        account="Lightfield",
    )

    [recovery] = recover_dark_sources(
        session,
        now=NOW,
        diagnose=moved_to("ashby", "lightfield"),
    )

    assert recovery.replaced_by is None

    assert source(session, "ashby", "Lightfield").enabled

    assert source(session, "ashby", "lightfield") is None

    assert session.scalar(
        sa.select(
            sa.func.count(),
        ).where(
            JobRecord.is_active.is_(True),
        )
    ) == 1


def test_a_replacement_already_known_is_switched_on_not_duplicated(
    session: Session,
) -> None:
    add_source(session)

    add_source(
        session,
        source_type="ashby",
        account="amplitude",
        last_success=None,
        enabled=False,
    )

    recover_dark_sources(
        session,
        now=NOW,
        diagnose=moved_to("ashby", "amplitude"),
    )

    rows = session.scalars(
        sa.select(
            JobSourceRecord,
        ).where(
            JobSourceRecord.source_type == "ashby",
        )
    ).all()

    assert len(rows) == 1

    assert rows[0].enabled


def test_a_disabled_source_is_not_checked(
    session: Session,
) -> None:
    add_source(
        session,
        enabled=False,
    )

    assert dark_sources(
        session,
        now=NOW,
    ) == []


def test_coverage_lists_what_stopped_answering(
    session: Session,
) -> None:
    """The part that was missing: the Coverage page says so."""

    from backend.app.coverage.service import (
        coverage,
    )

    add_source(
        session,
        account="postman",
        company="Postman",
        last_success=timedelta(days=17),
    )

    add_source(
        session,
        source_type="ashby",
        account="starbucks-never",
        company="Starbucks",
        last_success=None,
        created=timedelta(days=3),
    )

    dark = {
        row["company"]: row
        for row in coverage(
            session
        )["dark"]
    }

    assert set(dark) == {"Postman", "Starbucks"}

    assert dark["Postman"]["last_success_at"].startswith(
        "2026-09-17"
    )

    assert dark["Starbucks"]["last_success_at"] is None


def test_a_company_that_moved_to_eightfold_is_polled_as_eightfold_is(
    session: Session,
) -> None:
    add_source(session)

    recover_dark_sources(
        session,
        now=NOW,
        diagnose=moved_to("eightfold_pcsx", "amplitude.com"),
    )

    assert source(
        session,
        "eightfold_pcsx",
        "amplitude.com",
    ).poll_interval_seconds == 3600
