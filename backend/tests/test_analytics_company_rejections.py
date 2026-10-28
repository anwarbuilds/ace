"""Company-only rejection evidence stays separate from application outcomes."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import analytics_read
from backend.app.db.base import Base
from backend.app.db.models import ApplicationEventRecord, GmailConnectionRecord, GmailMessageRecord, JobMarkRecord
from backend.app.inbox.company_outcomes import COMPANY_REASON, encode_reason
from backend.tests.test_analytics_read import app


NOW = datetime(2026, 10, 26, 6, tzinfo=timezone.utc)  # October 25 in Pacific time.


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def read(db, **kwargs):
    db.flush()
    return analytics_read(db, now=NOW, tz="America/Los_Angeles", **kwargs)


def mail(db, index, *, received=None):
    connection = db.scalar(select(GmailConnectionRecord).limit(1))
    if connection is None:
        connection = GmailConnectionRecord(owner_id=1, email="fixture@example.test", encrypted_refresh_token=b"",
                                           scope="gmail.readonly", state="disconnected")
        db.add(connection)
        db.flush()
    message = GmailMessageRecord(connection_id=connection.id, gmail_id=f"company-fixture-{index}",
                                 received_at=received or NOW - timedelta(days=2), sender="talent@fictional.example",
                                 subject="Fictional application decision", snippet="We will not move forward.",
                                 classification="rejection", decision="update", decision_reason=COMPANY_REASON,
                                 selected_application_key=None, candidate_keys=[], parser_version="fixture")
    db.add(message)
    db.flush()
    return message


def record(db, message, company="Silverpine Labs", **kwargs):
    row = ApplicationEventRecord(application_key=f"email:{message.id}", gmail_message_id=message.id,
                                 kind="company_rejection", actor="verified_automation",
                                 reason=encode_reason(company, "The employer communicated a rejection."),
                                 occurred_at=message.received_at,
                                 dedupe_key=f"company-fixture:{db.scalar(select(func.count()).select_from(ApplicationEventRecord))}")
    for key, value in kwargs.items():
        setattr(row, key, value)
    db.add(row)
    db.flush()
    return row


def test_company_evidence_counts_unique_emails_without_changing_any_application_metric(db):
    key = app(db, 1)
    app(db, 2)
    baseline = read(db, records=True)
    older = mail(db, 1, received=NOW - timedelta(days=10))
    latest = mail(db, 2)
    other = mail(db, 3, received=NOW - timedelta(days=3))
    record(db, older)
    record(db, latest)
    record(db, latest)  # A repeated ledger entry cannot become a second email.
    record(db, other, company="Northwind Robotics")
    result = read(db, records=True)
    assert result["company_rejections"] == [
        {"company": "Silverpine Labs", "messages": 2, "latest_at": latest.received_at.isoformat(),
         "message_ids": [latest.id, older.id]},
        {"company": "Northwind Robotics", "messages": 1, "latest_at": other.received_at.isoformat(),
         "message_ids": [other.id]},
    ]
    assert result["company_rejection_summary"] == {
        "companies": 2, "messages": 3, "latest_at": latest.received_at.isoformat(),
        "date_basis": "email_received", "start": None, "end": "2026-10-25", "family_excluded_messages": 0,
    }
    for field in ("total_submitted", "submitted", "statuses", "positive", "assessments", "interviews",
                  "has_outcome_evidence", "evidence", "cohort", "roles", "timing", "median_days", "timing_sample",
                  "rejected_companies", "rejection_summary", "records"):
        assert result[field] == baseline[field], field
    assert db.get(JobMarkRecord, int(key.split(":")[1])).application_status == "applied"


def test_company_evidence_undo_and_later_owner_filing_remove_only_active_evidence(db):
    undone = mail(db, 1)
    event_row = record(db, undone)
    record(db, undone, kind="undo", actor="owner", undo_of_id=event_row.id)
    filed = mail(db, 2)
    record(db, filed)
    filed.decision_reason = "You marked this as a status update"
    linked = mail(db, 3)
    record(db, linked)
    linked.selected_application_key = "job:1"
    active = mail(db, 4)
    record(db, active)
    result = read(db)
    assert result["company_rejection_summary"]["messages"] == 1
    assert result["company_rejections"][0]["message_ids"] == [active.id]
    # History remains append-only: the projection did not erase any event.
    assert db.scalar(select(func.count()).select_from(ApplicationEventRecord)) == 5


def test_company_evidence_uses_local_email_dates_instead_of_submission_or_recorded_dates(db):
    app(db, 1, age=120)
    inside = mail(db, 1, received=datetime(2026, 10, 25, 1, tzinfo=timezone.utc))  # October 24 Pacific.
    outside = mail(db, 2, received=datetime(2026, 10, 25, 8, tzinfo=timezone.utc))
    first = record(db, inside)
    first.recorded_at = NOW  # Historical cleanup date must not replace the email's date.
    record(db, outside)
    result = read(db, start=date(2026, 10, 24), end=date(2026, 10, 24))
    assert result["submitted"] == 0  # This application was submitted months earlier.
    assert result["company_rejections"][0]["message_ids"] == [inside.id]
    assert result["company_rejection_summary"]["start"] == result["company_rejection_summary"]["end"] == "2026-10-24"
    assert not read(db, start=date(2026, 10, 23), end=date(2026, 10, 23))["company_rejections"]


def test_all_time_includes_email_before_first_submission_and_company_filter_is_exact(db):
    app(db, 1, age=1)
    older = mail(db, 1, received=NOW - timedelta(days=300))
    record(db, older)
    record(db, mail(db, 2), company="Silverpine Labs Holdings")
    result = read(db, company="silverpine labs")
    assert result["company_rejections"][0]["message_ids"] == [older.id]
    assert result["company_rejection_summary"]["messages"] == 1
    assert result["company_rejection_summary"]["start"] is None
    assert not read(db, days="30", company="Silverpine Labs")["company_rejections"]
    assert not read(db, company="Silverpine")["company_rejections"]


def test_unknown_role_company_evidence_is_not_attributed_to_selected_role_family(db):
    app(db, 1, family="SOFTWARE_ENGINEERING")
    app(db, 2, family="ML_ENGINEERING")
    record(db, mail(db, 1))
    record(db, mail(db, 2), company="Northwind Robotics")
    result = read(db, family="SOFTWARE_ENGINEERING", company="Silverpine Labs")
    assert result["company_rejections"] == []
    assert result["company_rejection_summary"]["messages"] == result["company_rejection_summary"]["companies"] == 0
    assert result["company_rejection_summary"]["family_excluded_messages"] == 1
    assert result["roles"][0]["rejections"] == 0
    assert result["cohort"]["rejected"] == 0


@pytest.mark.parametrize("change", [
    {"actor": "classifier"}, {"application_key": "job:1"}, {"reason": "not JSON"}, {"reason": "[]"},
    {"reason": '{"scope":"application","version":1,"company":"Silverpine Labs"}'},
    {"reason": '{"scope":"company","version":2,"company":"Silverpine Labs"}'},
    {"reason": '{"scope":"company","version":1,"company":""}'},
    {"new_status": "rejected"}, {"occurred_at": NOW + timedelta(days=1)},
])
def test_invalid_company_ledger_claims_are_not_counted_as_company_or_application_outcomes(db, change):
    app(db, 1)
    record(db, mail(db, 1), **change)
    result = read(db)
    assert result["company_rejections"] == []
    assert result["company_rejection_summary"]["messages"] == 0
    assert result["evidence"]["rejected"] == 0


@pytest.mark.parametrize("change", [
    {"classification": "possible_rejection"}, {"decision": "receipt"},
    {"decision_reason": "Owner chose a different filing"},
    {"received_at": NOW + timedelta(minutes=1)},
])
def test_company_evidence_requires_the_current_exact_email_state(db, change):
    message = mail(db, 1)
    record(db, message)
    for key, value in change.items():
        setattr(message, key, value)
    assert read(db)["company_rejections"] == []


def test_conflicting_company_claims_for_one_email_are_excluded_instead_of_duplicated(db):
    message = mail(db, 1)
    record(db, message)
    record(db, message, company="Northwind Robotics")
    assert read(db)["company_rejections"] == []


def test_company_evidence_projection_remains_read_only(db):
    record(db, mail(db, 1))
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        result = read(db)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
    assert result["company_rejection_summary"]["messages"] == 1
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
