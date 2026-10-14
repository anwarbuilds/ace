"""Tests for the demo database builder.

The repository is public, so the demo must hold nothing real: invented
employers, links on the reserved .example domain, and verdicts that come
from the real gate rather than being written in by hand.
"""

from urllib.parse import urlparse

from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import Session

from backend.app.answers.catalogue import QUESTIONS
from backend.app.db.models import (
    ApplicationAnswerRecord,
    JobEvaluationRecord,
    JobMarkRecord,
    JobRecord,
    JobResumeScoreRecord,
    PollSessionRecord,
)
from backend.app.demo.companies import DEMO_COMPANY_TIERS
from backend.scripts.seed_demo import seed


def test_demo_is_fictional_and_realistic(
    tmp_path,
) -> None:
    url = f"sqlite:///{tmp_path / 'demo.db'}"

    summary = seed(
        url,
        job_count=200,
    )

    engine = create_engine(
        url
    )

    with Session(engine) as session:
        companies = set(
            session.scalars(
                select(JobRecord.company).distinct()
            )
        )

        hosts = {
            urlparse(link).hostname
            for link in session.scalars(
                select(JobRecord.official_url)
            )
        }

        statuses = dict(
            session.execute(
                select(
                    JobEvaluationRecord.eligibility_status,
                    func.count(),
                ).group_by(
                    JobEvaluationRecord.eligibility_status
                )
            ).all()
        )

        unscored_passing = session.scalar(
            select(func.count())
            .select_from(JobRecord)
            .join(
                JobEvaluationRecord,
                JobEvaluationRecord.job_id == JobRecord.id,
            )
            .outerjoin(
                JobResumeScoreRecord,
                JobResumeScoreRecord.job_id == JobRecord.id,
            )
            .where(
                JobEvaluationRecord.eligibility_status == "PASS",
                JobResumeScoreRecord.job_id.is_(None),
            )
        )

        answers = session.scalar(
            select(func.count()).select_from(ApplicationAnswerRecord)
        )

        marks = session.scalar(
            select(func.count()).select_from(JobMarkRecord)
        )

        pulls = session.scalar(
            select(func.count()).select_from(PollSessionRecord)
        )

    assert companies <= set(DEMO_COMPANY_TIERS)

    assert len(companies) >= 25

    assert all(
        host and host.endswith(".example")
        for host in hosts
    )

    # The gate, not the seed, decided: both outcomes occur.
    assert statuses.get("PASS", 0) > 50
    assert statuses.get("REJECT", 0) > 10

    assert unscored_passing == 0

    assert answers == len(QUESTIONS) >= 66

    assert marks > 0

    # More than one page (30) of the activity log.
    assert pulls > 30

    assert summary["jobs"] >= 200


def test_seed_refuses_nothing_on_a_fresh_sqlite_file(
    tmp_path,
) -> None:
    """Re-running replaces the file rather than doubling the data."""

    url = f"sqlite:///{tmp_path / 'demo.db'}"

    seed(url, job_count=40)

    seed(url, job_count=40)

    with Session(create_engine(url)) as session:
        assert session.scalar(
            select(func.count()).select_from(JobRecord)
        ) == 44
