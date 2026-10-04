"""A feed's copy of a role ACE already reads from the employer.

Adding direct boards for companies a curated feed already listed --
Microsoft among them -- put the same role in the queue twice. The
feed's copy is the worse of the two: its description is a placeholder,
so the gate cannot read it, which is exactly how clearance roles were
getting through.

Only exact duplicates are hidden. Measured before applying, 14 feed
rows matched a direct posting on company and title, and 56 did not --
worded differently, or listed by the feed and not the board. Those 56
stay, because hiding them would hide roles the user may see nowhere
else.
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

from backend.app.api.queries import (
    JobFilters,
    list_jobs,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)


NOW = datetime(
    2026,
    10,
    4,
    12,
    tzinfo=timezone.utc,
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


def add_job(
    session: Session,
    *,
    key: str,
    source: str,
    title: str,
    company: str = "Microsoft",
    active: bool = True,
) -> JobRecord:
    job = JobRecord(
        source=source,
        source_account="acct",
        external_id=key,
        company=company,
        requisition_id=None,
        title=title,
        location="Redmond, WA, US",
        description="Build software.",
        official_url=f"https://example.com/{key}",
        posted_at=NOW,
        content_hash=f"hash-{key}",
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=active,
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
) -> list[tuple[str, str]]:
    page = list_jobs(
        session,
        filters=JobFilters(),
        now=NOW,
    )

    return sorted(
        (
            item.source,
            item.title,
        )
        for item in page.items
    )


def test_a_feed_copy_of_a_direct_role_is_hidden(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer - Intune",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer - Intune",
        )

        assert queue(
            session
        ) == [
            (
                "eightfold_pcsx",
                "Software Engineer - Intune",
            ),
        ], "the same role appeared twice"


def test_a_feed_role_the_board_lacks_is_kept(
    session_factory,
) -> None:
    """The reason this is exact-match only. A feed role with no twin on
    the direct board may be the only place the user sees it."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer II",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer - Forward Deployed",
        )

        assert len(
            queue(
                session
            )
        ) == 2


def test_a_closed_direct_posting_does_not_hide_the_feed_copy(
    session_factory,
) -> None:
    """If the employer's own copy has gone, the feed's is all that is
    left; hiding it would hide the role entirely."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer",
            active=False,
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer",
        )

        assert queue(
            session
        ) == [
            (
                "simplify",
                "Software Engineer",
            ),
        ]


def test_the_same_title_at_another_company_is_not_a_duplicate(
    session_factory,
) -> None:
    """"Software Engineer" is the most common title there is."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="greenhouse",
            title="Software Engineer",
            company="Algolia",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer",
            company="Microsoft",
        )

        assert len(
            queue(
                session
            )
        ) == 2
