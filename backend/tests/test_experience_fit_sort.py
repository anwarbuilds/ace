"""Tests for the experience-fit ordering.

The user applies to anything asking three years or less. Two different
postings qualify: one labelled early career, and one stating a ceiling
the gate already admitted. Before this sort existed, only the first
floated up, so 52 postings stating one to three years, including every
single three-year role, sat mixed into a queue of 986 with no way to
bring them forward.

The property this file exists to defend is that the ordering **orders**
and never excludes. Hiding the postings that state no requirement at
all would be the easy way to make the queue look focused, and it would
quietly undo the gate's own decision to keep them: a terse posting with
no experience bar is frequently open to a new grad.
"""

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
    9,
    11,
    12,
    0,
    tzinfo=timezone.utc,
)

SORT = "experience_fit_first"


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
    index: int,
    title: str,
    early_career: bool = False,
    years: int | None = None,
    verified: bool = True,
) -> JobRecord:
    """Insert one qualifying job with a given experience profile."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index
        ),
        company="Example Co",
        requisition_id=None,
        title=title,
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            f"https://example.com/{index}"
        ),
        posted_at=NOW,
        content_hash=f"hash-{index}",
        first_seen_at=NOW
        - timedelta(
            minutes=index
        ),
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
            role_family=(
                "SOFTWARE_ENGINEERING"
            ),
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{index}",
            requirements_verified=verified,
            is_early_career=early_career,
            required_experience_years=years,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def titles(
    session: Session,
    sort: str = SORT,
) -> list[str]:
    """Return the job titles in the order the sort produces."""

    page = list_jobs(
        session,
        filters=JobFilters(
            sort=sort,
        ),
        now=NOW,
    )

    return [
        item.title
        for item in page.items
    ]


def test_a_stated_ceiling_leads_a_posting_stating_nothing(
    session_factory,
) -> None:
    """The case that prompted this: 33 three-year roles were invisible.

    They are not labelled early career, so every ordering ACE had put
    them level with postings that say nothing about experience at all.
    A stated three-year ceiling is direct evidence the user qualifies.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Silent",
        )

        add_job(
            session,
            index=2,
            title="Three years",
            years=3,
        )

        assert titles(
            session
        ) == [
            "Three years",
            "Silent",
        ]


def test_read_evidence_leads_a_title_alone(
    session_factory,
) -> None:
    """128 in-band postings carry no description.

    Lane B has no text to read, so the only evidence is a title saying
    "New Grad". That is real, and beats silence, but it is weaker than
    a description ACE actually checked, so it sits between the two.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Silent",
        )

        add_job(
            session,
            index=2,
            title="Unverified new grad",
            early_career=True,
            verified=False,
        )

        add_job(
            session,
            index=3,
            title="Verified new grad",
            early_career=True,
            verified=True,
        )

        assert titles(
            session
        ) == [
            "Verified new grad",
            "Unverified new grad",
            "Silent",
        ]


def test_the_sort_never_removes_a_posting(
    session_factory,
) -> None:
    """The whole point of choosing a sort over a filter.

    A posting stating no requirement is frequently open to a new grad,
    which is why the gate keeps it. Ordering it below the user's band
    is help; dropping it is the gate being overruled by a control that
    only claims to sort.
    """

    with session_factory() as session:
        for index in range(
            1,
            6
        ):
            add_job(
                session,
                index=index,
                title=f"Silent {index}",
            )

        add_job(
            session,
            index=6,
            title="Two years",
            years=2,
        )

        ordered = titles(
            session
        )

        assert ordered[0] == "Two years"

        assert len(ordered) == 6


def test_four_years_is_the_gate_s_job_not_this_sort_s(
    session_factory,
) -> None:
    """A four-year role never reaches the queue to be sorted.

    Pinned so the ceiling here stays tied to the gate's constant
    rather than drifting into a second, quieter definition of what the
    user can apply to.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Four years",
            years=4,
        )

        add_job(
            session,
            index=2,
            title="Three years",
            years=3,
        )

        # Both are stored as PASS here, because this test is about the
        # ordering alone. The four-year posting sorts with the ones
        # stating nothing, which is the honest place for a figure this
        # sort does not consider in band.
        assert titles(
            session
        ) == [
            "Three years",
            "Four years",
        ]
