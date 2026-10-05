"""A board that produces the roles the user wants is not polled daily.

An audit found 59 daily boards that had produced passing roles --
Amazon, Clera, Nuro, Neuralink, Twitch, Discord, Plaid among them. A
role opened at any of them could wait a day to be seen.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.coverage.cadence import (
    promote_productive_sources,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
)


MOMENT = datetime(
    2026,
    10,
    4,
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
    source_type: str,
    account: str,
    interval: int,
    *,
    enabled: bool = True,
) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=account,
            enabled=enabled,
            poll_interval_seconds=interval,
        )
    )

    session.flush()


def add_job(
    session: Session,
    source_type: str,
    account: str,
    status: str,
    external_id: str,
) -> None:
    job = JobRecord(
        source=source_type,
        source_account=account,
        external_id=external_id,
        company=account,
        title="Software Engineer, New Grad",
        location="New York, NY",
        description="",
        official_url=f"https://example.com/{external_id}",
        content_hash=f"hash-{external_id}",
        first_seen_at=MOMENT,
        last_seen_at=MOMENT,
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
            content_hash=f"hash-{external_id}",
            requirements_verified=True,
            is_early_career=True,
            is_new_grad=False,
            required_experience_years=None,
            evaluated_at=MOMENT,
        )
    )

    session.flush()


def interval(
    session: Session,
    source_type: str,
    account: str,
) -> int:
    return session.scalar(
        sa.select(
            JobSourceRecord.poll_interval_seconds,
        ).where(
            JobSourceRecord.source_type == source_type,
            JobSourceRecord.source_account == account,
        )
    )


def test_a_daily_board_that_produced_a_passing_role_is_sped_up(
    session: Session,
) -> None:
    add_source(session, "greenhouse", "nuro", 86400)
    add_job(session, "greenhouse", "nuro", "PASS", "1")

    [promotion] = promote_productive_sources(
        session
    )

    assert (
        promotion.old_interval,
        promotion.new_interval,
        promotion.passing_roles,
    ) == (86400, 900, 1)

    assert interval(session, "greenhouse", "nuro") == 900


def test_an_expensive_board_that_produced_nothing_wanted_stays_slow(
    session: Session,
) -> None:
    """A Workday tenant is a hundred requests a poll; it earns a faster
    cadence by producing something."""

    add_source(session, "workday", "tail/External", 86400)
    add_job(session, "workday", "tail/External", "REJECT", "1")

    assert promote_productive_sources(
        session
    ) == []

    assert interval(session, "workday", "tail/External") == 86400


def test_a_board_read_in_one_request_is_never_left_daily(
    session: Session,
) -> None:
    """Fifteen minutes costs four requests an hour there, and daily cost
    Duolingo's roles a day: the feed listed them first."""

    add_source(session, "greenhouse", "duolingo", 86400)
    add_job(session, "greenhouse", "duolingo", "REJECT", "1")

    # Never produced anything at all, not even a rejection.
    add_source(session, "ashby", "cloudflare", 86400)

    promoted = {
        promotion.source_account: promotion.passing_roles
        for promotion in promote_productive_sources(
            session
        )
    }

    assert promoted == {
        "duolingo": 0,
        "cloudflare": 0,
    }

    assert interval(session, "greenhouse", "duolingo") == 900

    assert interval(session, "ashby", "cloudflare") == 900


def test_a_faster_cadence_set_by_hand_is_never_slowed(
    session: Session,
) -> None:
    add_source(session, "greenhouse", "cursor", 300)
    add_job(session, "greenhouse", "cursor", "PASS", "1")

    assert promote_productive_sources(
        session
    ) == []

    assert interval(session, "greenhouse", "cursor") == 300


def test_eightfold_is_promoted_only_to_its_own_cadence(
    session: Session,
) -> None:
    """Ten postings a page, one shared edge: an hour, not fifteen
    minutes."""

    add_source(session, "eightfold_pcsx", "contoso.com", 21600)
    add_job(session, "eightfold_pcsx", "contoso.com", "PASS", "1")

    promote_productive_sources(
        session
    )

    assert interval(
        session,
        "eightfold_pcsx",
        "contoso.com",
    ) == 3600


def test_feeds_and_disabled_boards_are_left_alone(
    session: Session,
) -> None:
    add_source(session, "ripplematch", "public", 86400)
    add_job(session, "ripplematch", "public", "PASS", "1")

    add_source(session, "greenhouse", "retired", 86400, enabled=False)
    add_job(session, "greenhouse", "retired", "PASS", "2")

    assert promote_productive_sources(
        session
    ) == []
