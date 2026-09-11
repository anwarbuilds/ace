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
    new_grad: bool = False,
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
            is_new_grad=new_grad,
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


def test_the_early_career_chip_keeps_a_three_year_role(
    session_factory,
) -> None:
    """The chip is what the user reaches for most, and it lied.

    It filtered on the early-career label alone, so of 986 qualifying
    postings it showed 385 and hid 52 stating one to three years,
    including every one of the 33 three-year roles. The band the user
    was using the chip to find was the band it removed.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Labelled",
            early_career=True,
        )

        add_job(
            session,
            index=2,
            title="Three years",
            years=3,
        )

        add_job(
            session,
            index=3,
            title="Silent",
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                experience_fit_only=True,
            ),
            now=NOW,
        )

        assert sorted(
            item.title
            for item in page.items
        ) == [
            "Labelled",
            "Three years",
        ]


def test_the_chip_and_the_sort_agree(
    session_factory,
) -> None:
    """Both ask the same question, so both read one definition.

    A chip filtering to a different set than the sort orders by would
    be worse than having neither: the rows that led the list would
    vanish when the user narrowed to them.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Three years",
            years=3,
        )

        add_job(
            session,
            index=2,
            title="Silent",
        )

        kept = {
            item.title
            for item in list_jobs(
                session,
                filters=JobFilters(
                    experience_fit_only=True,
                ),
                now=NOW,
            ).items
        }

        leading = titles(
            session
        )[0]

        assert leading in kept


def test_new_grad_is_narrower_than_early_career(
    session_factory,
) -> None:
    """The user asks the two separately, so ACE stores them separately.

    is_early_career is deliberately wide: junior, associate, entry
    level, rotational and "Engineer I" all set it and none of them
    says new grad. Before this flag existed the narrower question
    could not be asked at all.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Software Engineer, New Grad 2026",
            early_career=True,
            new_grad=True,
        )

        add_job(
            session,
            index=2,
            title="Junior Software Engineer",
            early_career=True,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                new_grad_only=True,
            ),
            now=NOW,
        )

        assert [
            item.title
            for item in page.items
        ] == [
            "Software Engineer, New Grad 2026",
        ]


def test_the_new_grad_sort_leads_with_the_flag(
    session_factory,
) -> None:
    """A chip and a sort both named "New grad" must mean one thing.

    The sort ranked on is_early_career, so with the chip beside it the
    two would have selected and ordered different sets. The company
    tier work already had to fix that class of disagreement once.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            title="Junior Engineer",
            early_career=True,
        )

        add_job(
            session,
            index=2,
            title="New Grad Engineer",
            early_career=True,
            new_grad=True,
        )

        assert titles(
            session,
            sort="new_grad_first",
        )[0] == "New Grad Engineer"


def test_the_gate_sets_the_flag_from_the_title() -> None:
    """One definition of new grad, in Python, beside the other rules.

    The alternative was a second copy of the patterns as a Postgres
    regex. The company tier work records why that is a trap, and the
    SQLite test database cannot run one at all.
    """

    from backend.app.intelligence.eligibility import (
        is_new_grad_title,
    )

    for title in (
        "Software Engineer, New Grad 2026",
        "New Graduate Software Engineer",
        "University Graduate, Backend",
        "Campus Hire, Software",
        "2026 Graduate Software Engineer",
        "Recent Graduate Engineer",
    ):
        assert is_new_grad_title(
            title
        ), title

    # Early career, every one of them, and not one says new grad.
    for title in (
        "Junior Software Engineer",
        "Associate Software Engineer",
        "Software Engineer I",
        "Entry-Level Developer",
        "Rotational Engineer",
        "Senior Software Engineer",
    ):
        assert not is_new_grad_title(
            title
        ), title
