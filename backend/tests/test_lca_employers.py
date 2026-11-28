"""Visa filings become name leads (DIS-10). Every employer, person and filing here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from openpyxl import Workbook
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage.leads import ORIGIN_LABELS, VISA_FILINGS
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord
from backend.scripts import import_lca_employers as lca

HEADER = ["CASE_NUMBER", "CASE_STATUS", "DECISION_DATE", "VISA_CLASS", "JOB_TITLE", "SOC_CODE", "FULL_TIME_POSITION",
          "EMPLOYER_NAME", "TRADE_NAME_DBA", "EMPLOYER_POC_EMAIL", "EMPLOYER_PHONE", "WORKSITE_STATE", "H_1B_DEPENDENT"]


def filing(status="Certified", visa="H-1B", soc="15-1252.00", full="Y", employer="Zephyr Labs, Inc.", trade="",
           state="CO", dependent="No", day=datetime(2026, 9, 1)):
    return ["I-200-0000", status, day, visa, "Software Engineer", soc, full, employer, trade,
            "someone@zephyrlabs.example", "+10000000000", state, dependent]


def workbook(tmp_path, rows, name="LCA_Disclosure_Data_FY2026_Q4.xlsx"):
    book = Workbook()
    sheet = book.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    book.save(path)
    return path


def test_only_certified_full_time_us_h1b_software_filings_count_and_no_contact_is_kept(tmp_path):
    path = workbook(tmp_path, [
        filing(),
        filing(status="Certified - Withdrawn", day=datetime(2026, 9, 20)),
        filing(soc="15-2051.00", employer="Zephyr Labs Inc", trade="Zephyr"),
        filing(status="Denied"),
        filing(full="N"),
        filing(visa="E-3 Australian"),
        filing(soc="13-2011.00"),
        filing(state=""),
        filing(employer="Quill Works LLC", dependent="Yes"),
    ])
    data = lca.aggregate([path])
    assert data["rows_read"] == 9 and data["filings_kept"] == 4
    by_key = {row["key"]: row for row in data["employers"]}
    zephyr = by_key["zephyr"]
    assert zephyr["filings"] == 3 and zephyr["last_decision"] == "2026-09-20" and zephyr["h1b_dependent_share"] == 0
    assert by_key["quill works"]["h1b_dependent_share"] == 1
    text = json.dumps(data)
    assert "someone@" not in text and "+1000" not in text


def test_a_file_without_the_expected_columns_is_refused(tmp_path):
    book = Workbook()
    book.active.append(["CASE_NUMBER", "EMPLOYER_NAME"])
    path = tmp_path / "other.xlsx"
    book.save(path)
    with pytest.raises(SystemExit):
        lca.aggregate([path])


@pytest.fixture(name="sessions")
def fixture_sessions(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr("backend.app.db.session.SessionLocal", factory)
    return factory


DATA = {"employers": [
    {"key": "zephyr", "name": "Zephyr Labs, Inc.", "filings": 40, "h1b_dependent_share": 0, "last_decision": "2026-09-01"},
    {"key": "quill works", "name": "Quill Works LLC", "filings": 12, "h1b_dependent_share": 0, "last_decision": "2026-08-01"},
    {"key": "orbit pine", "name": "Orbit Pine", "filings": 5, "h1b_dependent_share": 0, "last_decision": "2026-07-01"},
    {"key": "cobalt ferry", "name": "Cobalt Ferry", "filings": 1, "h1b_dependent_share": 0, "last_decision": "2026-06-01"},
    {"key": "zephyr labs usa", "name": "Zephyr Labs", "filings": 3, "h1b_dependent_share": 0, "last_decision": "2026-05-01"},
]}


def test_employers_ace_does_not_read_become_leads_and_a_dry_run_writes_nothing(sessions):
    now = datetime(2026, 11, 28, tzinfo=timezone.utc)
    with sessions.begin() as session:
        session.add(JobSourceRecord(source_type="greenhouse", source_account="quillworks", company_name="Quill Works",
                                    enabled=True, poll_interval_seconds=900, discovery_source="curated_list"))
        session.add(EmployerLead(company_key="orbit pine", company_name="Orbit Pine", origin="network",
                                 origin_details=["network"], state="dormant", reason="Read before.", boards=[],
                                 first_seen_at=now, next_check_at=now, updated_at=now))
    dry = lca.import_leads(DATA, apply=False, min_filings=2)
    assert dry == {"mode": "dry-run", "min_filings": 2, "read_by_ace": 1, "already_leads": 1, "leads_new": 1, "below_min": 1,
                   "same_company_again": 1}
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(EmployerLead)) == 1
    applied = lca.import_leads(DATA, apply=True, min_filings=2)
    assert applied["leads_new"] == 1
    with sessions() as session:
        rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    assert rows["zephyr"].origin == VISA_FILINGS and rows["zephyr"].state == "checking"
    assert rows["zephyr"].boards == [] and rows["zephyr"].company_name == "Zephyr Labs, Inc."
    assert rows["orbit pine"].origin == "network" and VISA_FILINGS in rows["orbit pine"].origin_details
    assert "cobalt ferry" not in rows
    assert ORIGIN_LABELS[VISA_FILINGS] == "Visa filings"
