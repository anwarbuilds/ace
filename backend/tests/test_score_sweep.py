"""Tests for scoring jobs found after the resume was uploaded.

Scores used to be written only by ``rescore_corpus``, which runs when a
resume is uploaded. Every job found afterwards had no score row at all,
so on 2026-10-10 1,238 of the 1,249 jobs in the queue showed "n/a" and
the job page told the user ACE "could not read this posting", which was
false: ACE had simply never scored it.

``score_unscored_jobs`` is the sweep the scheduler runs after each
cycle. These tests pin what it must and must not touch.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.api.queries import (
    JobFilters,
    get_job,
    list_jobs,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
)
from backend.app.matching.scoring import (
    MATCHING_ALGORITHM_VERSION,
)
from backend.app.matching.service import (
    rescore_corpus,
    score_unscored_jobs,
    store_resume,
)


NOW = datetime.now(
    timezone.utc
).replace(
    microsecond=0,
) - timedelta(
    hours=1,
)

RICH = (
    "Python, Kafka, PostgreSQL and Kubernetes required, "
    "building distributed systems on AWS."
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
    external_id: str,
    description: str = RICH,
    status: str = "PASS",
    is_active: bool = True,
    evaluated_at: datetime = NOW,
) -> JobRecord:
    """Store one evaluated job."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example Co",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description=description,
        official_url=(
            "https://boards.example.com/"
            f"{external_id}"
        ),
        posted_at=NOW,
        content_hash=external_id * 8,
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=is_active,
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
            reason_codes=["NO_HARD_BLOCKER"],
            reasons=["No hard eligibility blocker detected."],
            content_hash=job.content_hash,
            requirements_verified=True,
            evaluated_at=evaluated_at,
        )
    )

    session.flush()

    return job


def add_resume(
    session: Session,
):
    return store_resume(
        session,
        label="CV",
        filename="cv.pdf",
        raw_text="Python, Kafka, PostgreSQL and AWS.",
        now=NOW - timedelta(days=30),
    )


def score_row(
    session: Session,
    job_id: int,
) -> JobResumeScoreRecord | None:
    return session.scalars(
        select(
            JobResumeScoreRecord
        ).where(
            JobResumeScoreRecord.job_id == job_id
        )
    ).first()


def test_job_found_after_upload_is_scored(
    session_factory,
) -> None:
    """The bug: a job stored after the upload never got a score."""

    with session_factory() as session:
        resume = add_resume(
            session
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        later = add_job(
            session,
            external_id="1",
        )

        assert score_row(session, later.id) is None

        swept = score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=5),
        )

        row = score_row(
            session,
            later.id,
        )

    assert swept == 1

    assert row is not None

    assert row.resume_id == resume.id

    assert row.score is not None and row.score > 0

    assert "python" in row.matched_skills

    assert row.algorithm_version == MATCHING_ALGORITHM_VERSION

    # Never scored before is not the same as unchanged.
    assert row.previous_score is None


def test_scored_jobs_are_left_alone(
    session_factory,
) -> None:
    """Each cycle must not re-score the whole queue."""

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
        )

        add_resume(
            session
        )

        assert score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=5),
        ) == 1

        assert score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=10),
        ) == 0


def test_changed_posting_is_rescored_and_remembers_its_old_score(
    session_factory,
) -> None:
    """A retitled or rewritten posting is re-evaluated; its score must
    follow, or the number describes text that no longer exists."""

    with session_factory() as session:
        job = add_job(
            session,
            external_id="1",
        )

        add_resume(
            session
        )

        score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=5),
        )

        before = score_row(
            session,
            job.id,
        ).score

        job.description = (
            "Rust, Terraform, GraphQL, React and Spark required."
        )

        evaluation = session.get(
            JobEvaluationRecord,
            job.id,
        )

        evaluation.evaluated_at = NOW + timedelta(minutes=20)

        session.flush()

        swept = score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=25),
        )

        row = score_row(
            session,
            job.id,
        )

    assert swept == 1

    assert row.previous_score == before

    assert row.score < before

    assert "rust" in row.missing_skills


def test_only_active_qualifying_jobs_are_swept(
    session_factory,
) -> None:
    """The sweep keeps the queue scored; it is not a corpus rescore."""

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            status="REJECT",
        )

        add_job(
            session,
            external_id="2",
            is_active=False,
        )

        kept = add_job(
            session,
            external_id="3",
        )

        add_resume(
            session
        )

        assert score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=5),
        ) == 1

        assert [
            row.job_id
            for row in session.scalars(
                select(JobResumeScoreRecord)
            )
        ] == [kept.id]


def test_no_resume_means_nothing_to_score(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            external_id="1",
        )

        assert score_unscored_jobs(
            session,
            now=NOW,
        ) == 0


def test_listing_tells_unscored_from_unreadable(
    session_factory,
) -> None:
    """"Not scored yet" and "could not read" are different facts.

    The job page said the second when the first was true. A posting
    with no score row has not been scored; one with a row and a null
    score was read and carried too little to rank.
    """

    with session_factory() as session:
        resume = add_resume(
            session
        )

        rescore_corpus(
            session,
            resume=resume,
        )

        thin = add_job(
            session,
            external_id="1",
            description="Join us.",
        )

        pending = add_job(
            session,
            external_id="2",
        )

        score_unscored_jobs(
            session,
            now=NOW + timedelta(minutes=5),
        )

        session.delete(
            score_row(
                session,
                pending.id,
            )
        )

        session.flush()

        unreadable = get_job(
            session,
            job_id=thin.id,
            resume_id=resume.id,
        )

        unscored = get_job(
            session,
            job_id=pending.id,
            resume_id=resume.id,
        )

        listed = {
            item.id: item
            for item in list_jobs(
                session,
                filters=JobFilters(
                    resume_id=resume.id,
                ),
                now=NOW + timedelta(minutes=5),
            ).items
        }

    assert unreadable.match_score is None
    assert unreadable.is_scored is True

    assert unscored.match_score is None
    assert unscored.is_scored is False

    assert listed[thin.id].is_scored is True
    assert listed[pending.id].is_scored is False
