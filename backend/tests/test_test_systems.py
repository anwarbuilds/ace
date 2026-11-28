"""A provider's test system is never an employer's careers site.

On 2026-11-24 a lead added two Oracle hosts that were test copies of a live
board. Every company, host and posting here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.identity import staging_host_reason
from backend.app.coverage.leads import CHECKING, finding_from
from backend.app.coverage.probing import BoardRef
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord
from backend.app.discovery import freehire as fh
from backend.scripts.register_network_boards import Candidate, assess

NOW = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("source_type", "account", "host"),
    [
        ("oracle_recruiting", "zephyr-dev6.fa.oraclecloud.example/CX", None),
        ("oracle_recruiting", "fa-quil-dev3-saasfaprod1.fa.ocs.oraclecloud.example/CX_1", None),
        ("oracle_recruiting", "orbit-test.fa.us2.oraclecloud.example/CX_1", None),
        ("oracle_recruiting", "pine-uat.fa.oraclecloud.example/CX", None),
        ("workday", "zephyr/Careers", "zephyr.wd5-impl.myworkdayjobs.example"),
    ],
)
def test_a_test_system_host_is_named(source_type, account, host):
    assert staging_host_reason(source_type, account, host)


@pytest.mark.parametrize(
    ("source_type", "account", "host"),
    [
        ("oracle_recruiting", "zephyr.fa.oraclecloud.example/CX_1001", None),
        ("oracle_recruiting", "fa-quil-saasfaprod1.fa.ocs.oraclecloud.example/CX_1", None),
        ("workday", "testamerica/Careers", "testamerica.wd1.myworkdayjobs.example"),
        ("workday", "devryuniversity/External", "devryuniversity.wd5.myworkdayjobs.example"),
        ("workday", "zephyr/QA_Careers", "zephyr.wd5.myworkdayjobs.example"),
        # Only provider-hosted tenants: a Greenhouse token is a company's own word.
        ("greenhouse", "convex-dev", "job-boards.greenhouse.example"),
        ("ashby", "sandboxlabs", "jobs.ashbyhq.example"),
    ],
)
def test_a_live_host_or_a_company_name_is_not(source_type, account, host):
    assert staging_host_reason(source_type, account, host) is None


def test_assess_refuses_a_test_system_without_reading_it():
    reads = []
    candidate = Candidate("oracle_recruiting", "zephyr-dev7.fa.oraclecloud.example/CX", "Zephyr Labs",
                          "zephyr-dev7.fa.oraclecloud.example")
    outcome = assess(candidate, lambda definition: reads.append(definition) or [])
    assert not outcome.added and outcome.reason.startswith("test system:")
    assert reads == []
    finding = finding_from(outcome, {"source_type": "oracle_recruiting", "source_account": candidate.source_account})
    # The lead keeps looking, by name, for the live site.
    assert finding.state == CHECKING and finding.gone and "test system" in finding.reason


def test_freehire_never_makes_a_lead_of_a_test_system():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    found = fh.Harvest()
    for account in ("zephyr-dev6.fa.oraclecloud.example/CX", "zephyr.fa.oraclecloud.example/CX_1001"):
        board = fh.Board("oracle_recruiting", account, account.split("/")[0], "Zephyr Labs", "oracle", 1)
        found.boards[board.key] = board
    with sessions.begin() as session:
        fh.remember(session, found, now=NOW)
    with sessions() as session:
        boards = session.scalar(sa.select(EmployerLead.boards))
        assert [b["source_account"] for b in boards] == ["zephyr.fa.oraclecloud.example/CX_1001"]
        assert session.scalar(sa.select(sa.func.count()).select_from(JobSourceRecord)) == 0


def test_a_page_pointing_at_a_test_system_is_not_a_board():
    from backend.app.coverage.probing import ref_belongs_to

    ref = BoardRef(source_type="oracle_recruiting", token="zephyr-sit.fa.oraclecloud.example/CX",
                   source_host="zephyr-sit.fa.oraclecloud.example")
    assert ref_belongs_to(company="Zephyr Labs", ref=ref, jobs=[{"title": "Software Engineer"}],
                          fetch=lambda url: None, fetch_text=lambda url: "") is None
