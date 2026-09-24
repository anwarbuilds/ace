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
from backend.app.coverage.service import (
    coverage,
)
from backend.scripts.probe_coverage import (
    corpus_companies,
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


def test_the_coverage_page_makes_the_same_distinction(
    session_factory,
) -> None:
    """reachable_keys() decides what gets probed; coverage() renders
    the page a person reads. They drifted, and only one of them was
    fixed.

    Qualcomm stayed "reached" on the Coverage page after the probing
    fix already shipped, because eight of its postings arrive through
    the curated feed and this function had never stopped counting that
    as reach -- so its own blocked board never showed up as a gap on
    the one page that exists to show a gap like that.
    """

    with session_factory() as session:
        add_job(
            session,
            company="Two Sigma",
            source="simplify",
        )

        report = coverage(
            session
        )

        names = {
            row["company"]
            for row in report["unreached"]
        }

        assert "Two Sigma" in names, (
            "a feed job counted as reaching the company on the "
            "Coverage page, the same bug reachable_keys() was fixed "
            "for"
        )


def test_the_coverage_page_still_recognises_a_real_board(
    session_factory,
) -> None:
    """The other direction, on the same function this time."""

    with session_factory() as session:
        add_job(
            session,
            company="Two Sigma",
            source="greenhouse",
        )

        report = coverage(
            session
        )

        names = {
            row["company"]
            for row in report["unreached"]
        }

        assert "Two Sigma" not in names


def test_the_corpus_offers_more_names_than_the_curated_list(
    session_factory,
) -> None:
    """Where the next 500 companies come from.

    The curated list is the user's own 412 picks. The corpus is every
    employer any feed has ever listed a job for -- names ACE learned
    for free and then mostly never looked at again. 574 of them had no
    board being polled and 563 had never been probed once, and two
    that were finally checked turned out to be plain Greenhouse boards
    with 33 and 93 postings on them.
    """

    with session_factory() as session:
        add_job(
            session,
            company="Algolia",
            source="simplify",
        )

        add_job(
            session,
            company="Upstart",
            source="greenhouse",
        )

        names = corpus_companies(
            session
        )

        assert "Algolia" in names, (
            "a company known only through a feed was not offered as "
            "somewhere to look for a real board"
        )

        assert "Upstart" in names


def test_the_corpus_ignores_closed_postings(
    session_factory,
) -> None:
    """A company whose last posting closed is not currently hiring,
    and probing it on that basis would be work done for nothing."""

    moment = datetime(
        2026,
        9,
        23,
        tzinfo=timezone.utc,
    )

    with session_factory() as session:
        session.add(
            JobRecord(
                source="simplify",
                source_account="acct",
                external_id="gone-1",
                company="Departed Corp",
                title="Software Engineer",
                location="Remote",
                description="",
                official_url="https://example.com/gone",
                content_hash="hash-gone",
                first_seen_at=moment,
                last_seen_at=moment,
                is_active=False,
            )
        )

        session.commit()

        assert "Departed Corp" not in corpus_companies(
            session
        )


def test_the_same_company_is_offered_once(
    session_factory,
) -> None:
    """Boards write an employer both ways -- "Esri" and "esri" both
    appear -- and probing each spelling separately is the same work
    twice for the same answer."""

    with session_factory() as session:
        add_job(
            session,
            company="Algolia",
            source="simplify",
        )

        add_job(
            session,
            company="algolia",
            source="ripplematch",
        )

        names = [
            name
            for name in corpus_companies(
                session
            )
            if name.casefold() == "algolia"
        ]

        assert len(
            names
        ) == 1, names
