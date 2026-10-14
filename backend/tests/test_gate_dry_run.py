"""The dry run reports what a profile would change and writes nothing."""

from datetime import (
    datetime,
    timezone,
)

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
from backend.scripts.gate_dry_run import dry_run


NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

BODY = (
    "We build distributed systems with Python and Go. You will design, "
    "build and operate services used by millions of customers, working "
    "closely with product and design. This is a full-time role based in "
    "Seattle, WA. Benefits include health insurance and a 401k. "
)


def add(session, external_id, title, requirement, status):
    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example Co",
        title=title,
        location="Seattle, WA",
        description=BODY + requirement,
        official_url=f"https://boards.example.com/{external_id}",
        content_hash=external_id,
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status=status,
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            rule_version="2026-10-09-v53",
            reason_codes=["EXPERIENCE_TOO_HIGH"] if status == "REJECT" else ["NO_HARD_BLOCKER"],
            reasons=[],
            content_hash=external_id,
            evaluated_at=NOW,
        )
    )


def test_sde2_lists_the_three_plus_role_and_writes_nothing() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    with factory.begin() as session:
        add(session, "1", "Software Engineer II", "3+ years of professional software development experience.", "REJECT")
        add(session, "2", "Software Engineer, New Grad", "", "PASS")
        add(session, "3", "Software Engineer", "5+ years of professional software development experience.", "REJECT")

    with factory() as session:
        flips, tally = dry_run(session, profile_key="sde2")

        stored = session.scalars(select(JobEvaluationRecord.eligibility_status).order_by(JobEvaluationRecord.job_id)).all()

    assert [(f.title, f.before, f.after) for f in flips] == [("Software Engineer II", "REJECT", "PASS")]
    assert tally[("PASS", "PASS")] == 1
    assert tally[("REJECT", "REJECT")] == 1
    assert stored == ["REJECT", "PASS", "REJECT"]
