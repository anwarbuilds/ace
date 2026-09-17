"""What "ACE can already reach this company" is allowed to mean.

The distinction this file pins cost real coverage. A job arriving
through a multi-employer feed proves the feed listed it; it says
nothing about whether ACE can read the employer's own board. Counting
it as reach made a company look covered, so it was dropped from the
probe list and its board was never looked for -- and being reached once
through a feed is precisely what stopped it ever being reached
properly.

Two Sigma is the case that exposed it. Five roles arrived through the
curated feed, so it never appeared in a single probe, while its own
board carried 55 -- including the campus software engineering posts the
user found by hand.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
)
from backend.scripts.probe_coverage import (
    reachable_keys,
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
    company: str,
    source: str,
) -> None:
    """Insert one live job from one source."""

    moment = datetime(
        2026,
        9,
        17,
        tzinfo=timezone.utc,
    )

    session.add(
        JobRecord(
            source=source,
            source_account="acct",
            external_id=f"{source}-{company}",
            company=company,
            title="Software Engineer",
            location="Houston, Texas",
            description="",
            official_url=(
                f"https://example.com/{company}"
            ),
            content_hash=f"hash-{source}-{company}",
            first_seen_at=moment,
            last_seen_at=moment,
            is_active=True,
        )
    )

    session.commit()


def test_a_feed_job_is_not_reach(
    session_factory,
) -> None:
    """The bug, stated directly.

    Two Sigma's roles came through the curated feed. That made it
    "reachable", which took it off the probe list, which is why its own
    board was never found.
    """

    with session_factory() as session:
        add_job(
            session,
            company="Two Sigma",
            source="simplify",
        )

        assert not (
            reachable_keys(
                session
            )
        ), (
            "a job from a multi-employer feed counted as reaching the "
            "employer, which is what stops the employer being probed"
        )


def test_every_feed_lane_counts_the_same_way(
    session_factory,
) -> None:
    """Whatever the feed is called. RippleMatch arrived later and
    would have reintroduced the same hole on its own."""

    for source in sorted(
        MULTI_EMPLOYER_SOURCES
    ):
        with session_factory() as session:
            add_job(
                session,
                company="Example Corp",
                source=source,
            )

            assert not (
                reachable_keys(
                    session
                )
            ), source


def test_a_job_from_the_company_s_own_board_is_reach(
    session_factory,
) -> None:
    """The other direction, or the fix is just "never reachable".

    A Greenhouse job means ACE polled that company's own board, which
    is exactly what being reachable means, and probing it again would
    be wasted effort.
    """

    with session_factory() as session:
        add_job(
            session,
            company="Two Sigma",
            source="greenhouse",
        )

        assert reachable_keys(
            session
        ), "a job from the company's own board is reach"


def test_a_registered_source_is_reach_with_no_jobs_yet(
    session_factory,
) -> None:
    """A board ACE polls counts before it has returned anything.

    A newly registered source that has not completed a poll is still
    reachable; re-probing it would find the board it already has.
    """

    with session_factory() as session:
        session.add(
            JobSourceRecord(
                source_type="greenhouse",
                source_account="twosigma",
                company_name="Two Sigma",
                enabled=True,
                poll_interval_seconds=900,
            )
        )

        session.commit()

        assert reachable_keys(
            session
        ), "a registered board is reach"
