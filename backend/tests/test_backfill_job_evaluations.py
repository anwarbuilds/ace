"""The backfill can re-evaluate only the jobs still on the list.

After a rule change that only rejects more -- site reliability and
mobile roles leaving the list on 2026-10-29 -- the decisions that can
change are the passing ones. Re-evaluating those first takes minutes
where the whole corpus takes hours.
"""

from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    update,
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
    evaluate_job,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.evaluations import (
    record_job_evaluations,
)
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)
from backend.scripts.backfill_job_evaluations import (
    count_pending,
    load_batch,
)


NOW = datetime(
    2026,
    10,
    29,
    tzinfo=timezone.utc,
)

DESCRIPTION = (
    "New grad role. Build reliable software systems in Python. "
    "You will write and review code and help operate what you ship. "
    "We value clear writing and steady engineering judgement. "
) * 4


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def _store(
    session: Session,
    external_id: str,
    title: str,
) -> None:
    job = CanonicalJob(
        source="greenhouse",
        company="Example Co",
        external_id=external_id,
        title=title,
        location="Seattle, WA",
        description=DESCRIPTION,
        official_url=f"https://example.com/jobs/{external_id}",
    )

    session.add(
        JobRecord(
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
            content_hash=compute_job_content_hash(
                job
            ),
            first_seen_at=NOW,
            last_seen_at=NOW,
            is_active=True,
        )
    )

    session.flush()

    record_job_evaluations(
        session,
        source="greenhouse",
        source_account="example",
        evaluated_jobs=[
            EvaluatedJob(
                job=job,
                observation_status=JobObservationStatus.NEW,
                eligibility=evaluate_job(
                    job
                ),
                alert_disposition=AlertDisposition.ALERT,
            )
        ],
        evaluated_at=NOW,
    )


def test_status_narrows_the_backfill_to_stored_passing_decisions(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        _store(
            session,
            "1",
            "Software Engineer",
        )

        _store(
            session,
            "2",
            "Account Executive",
        )

        # Both decided under rules that no longer exist.
        session.execute(
            update(
                JobEvaluationRecord
            ).values(
                rule_version="2026-10-14-v54",
            )
        )

    with session_factory() as session:
        assert count_pending(
            session,
            rebuild_all=False,
        ) == 2

        assert count_pending(
            session,
            rebuild_all=False,
            status="PASS",
        ) == 1

        assert count_pending(
            session,
            rebuild_all=True,
            status="REJECT",
        ) == 1

        assert [
            record.title
            for record in load_batch(
                session,
                rebuild_all=False,
                after_id=0,
                batch_size=10,
                status="PASS",
            )
        ] == [
            "Software Engineer",
        ]


def test_a_current_decision_is_not_pending_under_any_status(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        _store(
            session,
            "1",
            "Software Engineer",
        )

    with session_factory() as session:
        assert count_pending(
            session,
            rebuild_all=False,
            status="PASS",
        ) == 0


def test_required_years_narrows_to_the_decisions_a_profile_switch_moves(
    session_factory,
) -> None:
    """The sde2 profile admits open-ended "3+" postings, stored with three
    required years: those rejected decisions are the only ones it moves."""

    with session_factory.begin() as session:
        _store(
            session,
            "1",
            "Software Engineer",
        )

        _store(
            session,
            "2",
            "Software Engineer II",
        )

        session.execute(
            update(
                JobEvaluationRecord
            ).values(
                # Decided under the other profile's rules.
                rule_version="2026-10-29-v55",
            )
        )

        session.execute(
            update(
                JobEvaluationRecord
            )
            .where(
                JobEvaluationRecord.job_id == 2
            )
            .values(
                eligibility_status="REJECT",
                required_experience_years=3,
            )
        )

    with session_factory() as session:
        assert count_pending(
            session,
            rebuild_all=False,
            status="REJECT",
            required_years=3,
        ) == 1

        assert [
            record.title
            for record in load_batch(
                session,
                rebuild_all=False,
                after_id=0,
                batch_size=10,
                status="REJECT",
                required_years=3,
            )
        ] == [
            "Software Engineer II",
        ]
