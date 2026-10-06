"""One batch must not fail on two names that share a key."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import SourceProbeRecord
from backend.app.coverage.diagnosis import Diagnosis, SITE_UNREACHABLE
import backend.scripts.probe_coverage as pc


@pytest.fixture(name="patched_session")
def fixture_patched_session(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    # autoflush=False is what production uses, and is the whole reason
    # the batch failed: a row added a moment ago is invisible to the
    # next query, so both names created one.
    factory = sessionmaker(
        bind=engine, class_=Session, autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr(pc, "SessionLocal", factory)
    return factory


def test_two_names_sharing_a_key_write_one_row(patched_session):
    """The bug that rolled back a 699-company run.

    Every probe completed and the single write at the end threw all of
    them away, because "Medpace" and "Medpace, Inc." normalise to one
    key and each created a row.
    """

    pc.record(
        [
            Diagnosis(
                company="Medpace",
                outcome=SITE_UNREACHABLE,
                detail="first",
            ),
            Diagnosis(
                company="Medpace, Inc.",
                outcome=SITE_UNREACHABLE,
                detail="second",
            ),
        ]
    )

    with patched_session() as session:
        rows = session.query(SourceProbeRecord).all()

    assert len(rows) == 1, [r.company_key for r in rows]


def test_an_eightfold_board_is_registered_hourly(patched_session):
    """Eightfold pages ten postings at a time, so a large board is two
    or three hundred requests a poll, all to one shared edge. Registered
    at the usual fifteen minutes, its boards together drew a refusal on
    every tenant."""

    from backend.app.coverage.diagnosis import REACHED
    from backend.app.coverage.probing import BoardCandidate
    from backend.app.db.models import JobSourceRecord

    def reached(company, source_type, account):
        return Diagnosis(
            company=company,
            outcome=REACHED,
            detail="board found",
            candidate=BoardCandidate(
                company=company,
                source_type=source_type,
                source_account=account,
                job_count=2000,
                evidence="board found",
                source_host=f"careers.{account}",
            ),
        )

    pc.record(
        [
            reached("Qualcomm", "eightfold_pcsx", "qualcomm.com"),
            reached("Cursor", "ashby", "cursor"),
        ]
    )

    with patched_session() as session:
        intervals = {
            row.source_account: row.poll_interval_seconds
            for row in session.query(JobSourceRecord).all()
        }

    assert intervals == {
        "qualcomm.com": 3600,
        "cursor": 900,
    }


def test_a_staffing_agency_the_probe_reaches_is_recorded_switched_off(
    patched_session,
):
    """The corpus holds every company a feed ever named, agencies too."""

    from backend.app.coverage.diagnosis import REACHED
    from backend.app.coverage.probing import BoardCandidate
    from backend.app.db.models import JobSourceRecord

    pc.record(
        [
            Diagnosis(
                company="Testing Xperts",
                outcome=REACHED,
                detail="board found",
                candidate=BoardCandidate(
                    company="Testing Xperts",
                    source_type="smartrecruiters",
                    source_account="TestingXperts",
                    job_count=179,
                    evidence="board found",
                ),
            ),
        ]
    )

    with patched_session() as session:
        [row] = session.query(JobSourceRecord).all()

    assert not row.enabled

    assert row.discovery_source.startswith("probe rejected: staffing")


def test_a_second_site_of_a_known_oracle_tenant_is_not_registered(
    patched_session,
):
    from backend.app.coverage.diagnosis import REACHED
    from backend.app.coverage.probing import BoardCandidate
    from backend.app.db.models import JobSourceRecord

    with patched_session() as session:
        session.add(
            JobSourceRecord(
                source_type="oracle_recruiting",
                source_account="eofe.fa.us2.oraclecloud.com/CX_1001",
                company_name="BNY",
                enabled=True,
                poll_interval_seconds=900,
            )
        )
        session.commit()

    pc.record(
        [
            Diagnosis(
                company="BNY",
                outcome=REACHED,
                detail="board found",
                candidate=BoardCandidate(
                    company="BNY",
                    source_type="oracle_recruiting",
                    source_account="eofe.fa.us2.oraclecloud.com/BNY-Careers",
                    job_count=1367,
                    evidence="linked from the company's own careers page",
                    source_host="eofe.fa.us2.oraclecloud.com",
                ),
            ),
        ]
    )

    with patched_session() as session:
        rows = session.query(JobSourceRecord).all()

    assert [row.source_account for row in rows] == [
        "eofe.fa.us2.oraclecloud.com/CX_1001",
    ]
