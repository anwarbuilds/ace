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

        counts = mark_counts(
            session
        )

        assert counts["saved"] == 2

        assert counts["archived"] == 1

        assert counts["applied"] == 1

        # Applying is itself a status, so the count carries through.
        assert (
            counts["by_status"]
            == {
                "applied": 1,
            }
        )

        # Nothing has closed yet, so the application is still open.
        assert (
            counts["open_applications"]
            == 1
        )


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


def test_applying_records_a_status_not_just_a_date(
    session_factory,
) -> None:
    """A job marked applied with no state at all reads as unknown."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        record = set_mark(
            session,
            job_id=job.id,
            applied=True,
            now=NOW,
        )

        assert (
            record.application_status
            == "applied"
        )


def test_a_rejection_does_not_overwrite_the_applied_date(
    session_factory,
) -> None:
    """applied_at is when it was sent; status is where it stands.

    Collapsing the two would lose the date the moment an outcome
    arrived, which is exactly when the history becomes interesting.
    """

    from datetime import timedelta

    applied_on = NOW - timedelta(
        days=20
    )

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            applied=True,
            applied_at=applied_on,
            now=applied_on,
        )

        record = set_mark(
            session,
            job_id=job.id,
            application_status="rejected",
            now=NOW,
        )

        # SQLite drops tzinfo on round-trip where PostgreSQL keeps it,
        # so compare the instant rather than the object.
        assert (
            record.applied_at
            .replace(tzinfo=None)
            == applied_on.replace(
                tzinfo=None
            )
        )

        assert (
            record.application_status
            == "rejected"
        )

        # The move is timestamped separately from the application.
        assert (
            record.status_changed_at
            .replace(tzinfo=None)
            != record.applied_at
            .replace(tzinfo=None)
        )


def test_a_status_implies_an_application_was_sent(
    session_factory,
) -> None:
    """"Rejected" on a job ACE thinks was never applied to is nonsense."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        record = set_mark(
            session,
            job_id=job.id,
            application_status="rejected",
            now=NOW,
        )

        assert record.applied_at is not None


def test_unapplying_clears_the_status_too(
    session_factory,
) -> None:
    """An application that never happened has no outcome."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            application_status="rejected",
            now=NOW,
        )

        record = set_mark(
            session,
            job_id=job.id,
            applied=False,
            now=NOW,
        )

        assert record.applied_at is None

        assert (
            record.application_status
            is None
        )


def test_unknown_application_status_is_refused(
    session_factory,
) -> None:
    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        with pytest.raises(
            ValueError,
            match="unknown application status",
        ):
            set_mark(
                session,
                job_id=job.id,
                application_status="maybe",
                now=NOW,
            )


def test_closed_applications_are_not_counted_as_open(
    session_factory,
) -> None:
    """A rejection is finished business and should stop asking for time."""

    with session_factory() as session:
        live = add_job(
            session,
            index=1,
        )

        dead = add_job(
            session,
            index=2,
        )

        set_mark(
            session,
            job_id=live.id,
            application_status=(
                "interviewing"
            ),
            now=NOW,
        )

        set_mark(
            session,
            job_id=dead.id,
            application_status="rejected",
            now=NOW,
        )

        counts = mark_counts(
            session
        )

        assert counts["applied"] == 2

        assert (
            counts["open_applications"]
            == 1
        )


def test_marked_pages_ignore_the_eligibility_gate(
    session_factory,
) -> None:
    """History is not a recommendation and must not be filtered as one.

    A job applied to, then later judged senior or out of family by a
    rule change, still happened. Filtering marked pages through the
    gate hid 20 of 27 real applications from the Applied page.
    """

    with session_factory() as session:
        kept = add_job(
            session,
            index=1,
        )

        rejected = add_job(
            session,
            index=2,
        )

        session.get(
            JobEvaluationRecord,
            rejected.id,
        ).eligibility_status = "REJECT"

        session.flush()

        for job in (
            kept,
            rejected,
        ):
            set_mark(
                session,
                job_id=job.id,
                applied=True,
                now=NOW,
            )

        page = list_jobs(
            session,
            filters=JobFilters(
                mark="applied",
            ),
            now=NOW,
        )

        assert page.total == 2


def test_marked_pages_still_show_closed_postings(
    session_factory,
) -> None:
    """A posting closing does not unmake the application."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        job.is_active = False

        session.flush()

        set_mark(
            session,
            job_id=job.id,
            applied=True,
            now=NOW,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                mark="applied",
            ),
            now=NOW,
        )

        assert page.total == 1


def test_the_queue_still_respects_the_gate(
    session_factory,
) -> None:
    """The exemption is for marked pages only, not everywhere."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
        )

        rejected = add_job(
            session,
            index=2,
        )

        session.get(
            JobEvaluationRecord,
            rejected.id,
        ).eligibility_status = "REJECT"

        session.flush()

        page = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        )

        assert page.total == 1
