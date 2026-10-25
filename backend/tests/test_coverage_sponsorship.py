"""Employers whose own readable postings refuse sponsorship."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.coverage.service import coverage, sponsorship_refusals
from backend.app.db.base import Base
from backend.app.db.models import JobEvaluationRecord
from backend.tests.test_web_api import add_job


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        counter = iter(range(1, 1000))

        def posting(company, *, refuses=False, readable=True):
            job = add_job(session, external_id=str(next(counter)), company=company, status="REJECT" if refuses else "PASS")
            session.query(JobEvaluationRecord).filter(JobEvaluationRecord.job_id == job.id).update(
                {
                    "reason_codes": ["SPONSORSHIP_BLOCKER"] if refuses else ["NO_HARD_BLOCKER"],
                    "requirements_verified": readable,
                }
            )

        # Six readable postings, three refusing, written two ways.
        for index in range(6):
            posting("Visa" if index % 2 else "visa", refuses=index < 3)
        # Refuses, but too few readable postings to judge.
        for index in range(3):
            posting("Tiny Co", refuses=True)
        # Unreadable postings never count.
        for index in range(6):
            posting("Quiet Co", refuses=True, readable=False)
        # Readable, never refusing.
        for index in range(6):
            posting("Open Co")
        session.commit()
        yield session


def test_lists_only_judgeable_refusers_grouped_case_insensitively(session) -> None:
    found = sponsorship_refusals(session)

    assert [(row["company"].lower(), row["readable"], row["refusing"]) for row in found] == [("visa", 6, 3)]
    assert found[0]["share"] == 0.5


def test_coverage_uses_a_snapshot_it_is_given(session) -> None:
    given = [{"company": "Snapshot Co", "readable": 9, "refusing": 9, "share": 1.0}]

    assert coverage(session, sponsorship=given)["sponsorship"] == given
    assert coverage(session)["sponsorship"] == sponsorship_refusals(session)
