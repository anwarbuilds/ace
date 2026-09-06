"""Tests for durable saved, reviewed and applied marks.

Marks are the one kind of job data ACE cannot recompute, so the
properties worth pinning are about not losing them: a mark must be
findable anywhere in the corpus, and setting one must never clear
another.
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

from backend.app.api.marks import (
    mark_counts,
    set_mark,
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
    6,
    12,
    0,
    tzinfo=timezone.utc,
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
    index: int,
) -> JobRecord:
    """Insert one qualifying job."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index
        ),
        company="Example Co",
        requisition_id=None,
        title=f"Software Engineer {index}",
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            "https://example.com/"
            f"{index}"
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
            requirements_verified=True,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def test_saved_job_is_found_anywhere_in_the_corpus(
    session_factory,
) -> None:
    """Saved must search every job, not one page of results.

    The browser-local version filtered whichever page happened to be
    loaded, so a job saved at position 120 of 150 simply vanished from
    Saved. This is the regression that motivated the table.
    """

    with session_factory() as session:
        jobs = [
            add_job(
                session,
                index=i,
            )
            for i in range(
                150
            )
        ]

        deep = jobs[120]

        set_mark(
            session,
            job_id=deep.id,
            saved=True,
            now=NOW,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                mark="saved",
                limit=60,
            ),
            now=NOW,
        )

        assert page.total == 1

        assert (
            page.items[0].id
            == deep.id
        )

        assert page.items[0].is_saved


def test_saving_does_not_clear_a_review_state(
    session_factory,
) -> None:
    """Marks are independent, and a partial update must stay partial."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            review_state="reviewed",
            now=NOW,
        )

        record = set_mark(
            session,
            job_id=job.id,
            saved=True,
            now=NOW,
        )

        assert record.is_saved

        assert (
            record.review_state
            == "reviewed"
        )


def test_review_states_are_mutually_exclusive(
    session_factory,
) -> None:
    """Reviewed and dismissed both mean handled; one column enforces it."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            review_state="reviewed",
            now=NOW,
        )

        record = set_mark(
            session,
            job_id=job.id,
            review_state="dismissed",
            now=NOW,
        )

        assert (
            record.review_state
            == "dismissed"
        )


def test_unknown_review_state_is_refused(
    session_factory,
) -> None:
    """A typo must fail loudly rather than store an unrenderable state."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        with pytest.raises(
            ValueError,
            match="unknown review state",
        ):
            set_mark(
                session,
                job_id=job.id,
                review_state="archived",
                now=NOW,
            )


def test_clearing_a_review_differs_from_leaving_it_alone(
    session_factory,
) -> None:
    """None means "unchanged", so clearing needs its own signal."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            review_state="dismissed",
            now=NOW,
        )

        untouched = set_mark(
            session,
            job_id=job.id,
            saved=True,
            now=NOW,
        )

        assert (
            untouched.review_state
            == "dismissed"
        )

        cleared = set_mark(
            session,
            job_id=job.id,
            clear_review=True,
            now=NOW,
        )

        assert (
            cleared.review_state
            is None
        )


def test_archive_covers_both_handled_states(
    session_factory,
) -> None:
    with session_factory() as session:
        reviewed = add_job(
            session,
            index=1,
        )

        dismissed = add_job(
            session,
            index=2,
        )

        add_job(
            session,
            index=3,
        )

        set_mark(
            session,
            job_id=reviewed.id,
            review_state="reviewed",
            now=NOW,
        )

        set_mark(
            session,
            job_id=dismissed.id,
            review_state="dismissed",
            now=NOW,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                mark="archived",
            ),
            now=NOW,
        )

        assert page.total == 2


def test_counts_describe_the_whole_corpus(
    session_factory,
) -> None:
    with session_factory() as session:
        jobs = [
            add_job(
                session,
                index=i,
            )
            for i in range(
                5
            )
        ]

        set_mark(
            session,
            job_id=jobs[0].id,
            saved=True,
            now=NOW,
        )

        set_mark(
            session,
            job_id=jobs[1].id,
            saved=True,
            review_state="reviewed",
            now=NOW,
        )

        set_mark(
            session,
            job_id=jobs[2].id,
            applied=True,
            now=NOW,
        )

        assert mark_counts(
            session
        ) == {
            "saved": 2,
            "archived": 1,
            "applied": 1,
        }


def test_marks_do_not_multiply_the_listing(
    session_factory,
) -> None:
    """The mark join must not duplicate rows or inflate the total."""

    with session_factory() as session:
        for i in range(
            4
        ):
            job = add_job(
                session,
                index=i,
            )

            set_mark(
                session,
                job_id=job.id,
                saved=True,
                now=NOW,
            )

        page = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        )

        assert page.total == 4

        assert len(
            page.items
        ) == 4
