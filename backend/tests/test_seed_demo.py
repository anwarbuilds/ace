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
                JobRecord.is_active.is_(True),
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


def test_the_activity_feed_is_a_few_queries_and_unchanged(tmp_path):
    """The feed once ran a full job listing per run (about 140 queries for
    30 runs). It must stay a constant handful, and list the same jobs the
    per-run listing would."""

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session

    from backend.app.api import main
    from backend.app.api.queries import JobFilters, list_discovery_runs, list_jobs
    from backend.app.matching.service import get_active_resume
    from backend.scripts.seed_demo import seed

    url = f"sqlite:///{tmp_path / 'feed.db'}"
    seed(url, job_count=200)
    engine = create_engine(url)
    count = [0]
    event.listen(engine, "before_cursor_execute", lambda *a: count.__setitem__(0, count[0] + 1))

    with Session(engine) as session:
        runs = list_discovery_runs(session, limit=30)
        count[0] = 0
        feed = main._with_session_jobs(session, runs=runs, per_session=6)
        assert count[0] <= 10

        resume = get_active_resume(session)
        for run in feed:
            expected = (
                [j.id for j in list_jobs(session, filters=JobFilters(
                    session_id=run["id"], resume_id=resume.id, sort="best_match", limit=6)).items]
                if run.get("qualifying_discovered") else []
            )
            assert [j["id"] for j in run["jobs"]] == expected
