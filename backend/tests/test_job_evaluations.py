"""Tests for materialized job-evaluation persistence.

The read model must reflect exactly what ACE decided, and must be
detectably stale when either the job or the rules change.
"""

from datetime import (
    datetime,
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

from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
)
from backend.app.intelligence.eligibility import (
    ELIGIBILITY_RULE_VERSION,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.evaluations import (
    iter_stale_job_ids,
    record_job_evaluations,
)
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


NOW = datetime(
    2026,
    9,
    5,
    16,
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


def make_canonical(
    *,
    external_id: str = "1",
    title: str = "Software Engineer",
    description: str = (
        "Build reliable software systems "
        "in Python."
    ),
) -> CanonicalJob:
    """Create one normalized job."""

    return CanonicalJob(
        source="greenhouse",
        company="Example Co",
        external_id=external_id,
        title=title,
        location="Seattle, WA",
        description=description,
        official_url=(
            "https://example.com/jobs/"
            f"{external_id}"
        ),
    )


def make_candidate(
    job: CanonicalJob,
) -> EvaluatedJob:
    """Wrap a job with its real eligibility decision."""

    return EvaluatedJob(
        job=job,
        observation_status=(
            JobObservationStatus.NEW
        ),
        eligibility=evaluate_job(
            job
        ),
        alert_disposition=(
            AlertDisposition.ALERT
        ),
    )


def add_job_row(
    session: Session,
    job: CanonicalJob,
) -> JobRecord:
    """Persist the job record the evaluation attaches to."""

    record = JobRecord(
        source=job.source,
        source_account="example",
        external_id=job.external_id,
        company=job.company,
        requisition_id=None,
        title=job.title,
        location=job.location,
        description=job.description,
        official_url=job.official_url,
        posted_at=None,
        source_updated_at=None,
        content_hash=(
            compute_job_content_hash(
                job
            )
        ),
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )

    session.add(
        record
    )

    session.flush()

    return record


def test_evaluation_is_written_for_each_job(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        jobs = [
            make_canonical(
                external_id=str(
                    index
                )
            )
            for index in range(
                1,
                4,
            )
        ]

        for job in jobs:
            add_job_row(
                session,
                job,
            )

        written = record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    job
                )
                for job in jobs
            ],
            evaluated_at=NOW,
        )

    assert written == 3

    with session_factory() as session:
        rows = session.scalars(
            select(
                JobEvaluationRecord
            )
        ).all()

    assert len(rows) == 3

    assert all(
        row.eligibility_status == "PASS"
        for row in rows
    )

    assert all(
        row.rule_version
        == ELIGIBILITY_RULE_VERSION
        for row in rows
    )


def test_evaluation_matches_the_gate_decision(
    session_factory,
) -> None:
    """The read model never disagrees with the gate."""

    job = make_canonical(
        title="Senior Staff Engineer",
    )

    with session_factory.begin() as session:
        add_job_row(
            session,
            job,
        )

        record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    job
                ),
            ],
            evaluated_at=NOW,
        )

    with session_factory() as session:
        row = session.scalars(
            select(
                JobEvaluationRecord
            )
        ).one()

    assert (
        row.eligibility_status
        == "REJECT"
    )

    assert (
        "SENIOR_TITLE"
        in row.reason_codes
    )


def test_re_evaluation_updates_in_place(
    session_factory,
) -> None:
    """A job has exactly one current evaluation."""

    job = make_canonical()

    with session_factory.begin() as session:
        add_job_row(
            session,
            job,
        )

        record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    job
                ),
            ],
            evaluated_at=NOW,
        )

    changed = make_canonical(
        title="Senior Engineer",
    )

    with session_factory.begin() as session:
        record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    changed
                ),
            ],
            evaluated_at=NOW,
        )

    with session_factory() as session:
        rows = session.scalars(
            select(
                JobEvaluationRecord
            )
        ).all()

    assert len(rows) == 1

    assert (
        rows[0].eligibility_status
        == "REJECT"
    )


def test_unknown_jobs_are_skipped(
    session_factory,
) -> None:
    """Evaluations are never orphaned from their job."""

    with session_factory.begin() as session:
        written = record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    make_canonical()
                ),
            ],
            evaluated_at=NOW,
        )

    assert written == 0


def test_empty_input_is_a_no_op(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        assert (
            record_job_evaluations(
                session,
                source="greenhouse",
                source_account="example",
                evaluated_jobs=[],
                evaluated_at=NOW,
            )
            == 0
        )


def test_missing_evaluation_is_reported_stale(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job_row(
            session,
            make_canonical(),
        )

    with session_factory() as session:
        stale = list(
            iter_stale_job_ids(
                session,
                rule_version=(
                    ELIGIBILITY_RULE_VERSION
                ),
            )
        )

    assert len(stale) == 1


def test_rule_version_change_is_reported_stale(
    session_factory,
) -> None:
    """Changing the gate makes every stored decision rebuildable."""

    job = make_canonical()

    with session_factory.begin() as session:
        add_job_row(
            session,
            job,
        )

        record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    job
                ),
            ],
            evaluated_at=NOW,
        )

    with session_factory() as session:
        current = list(
            iter_stale_job_ids(
                session,
                rule_version=(
                    ELIGIBILITY_RULE_VERSION
                ),
            )
        )

        after_rules_change = list(
            iter_stale_job_ids(
                session,
                rule_version=(
                    "some-newer-version"
                ),
            )
        )

    assert current == []

    assert len(
        after_rules_change
    ) == 1


def test_content_change_is_reported_stale(
    session_factory,
) -> None:
    """An edited posting needs re-evaluation."""

    job = make_canonical()

    with session_factory.begin() as session:
        record = add_job_row(
            session,
            job,
        )

        record_job_evaluations(
            session,
            source="greenhouse",
            source_account="example",
            evaluated_jobs=[
                make_candidate(
                    job
                ),
            ],
            evaluated_at=NOW,
        )

        record.content_hash = (
            "a-different-hash"
        )

    with session_factory() as session:
        stale = list(
            iter_stale_job_ids(
                session,
                rule_version=(
                    ELIGIBILITY_RULE_VERSION
                ),
            )
        )

    assert len(stale) == 1
