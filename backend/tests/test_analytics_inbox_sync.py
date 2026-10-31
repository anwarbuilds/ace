"""Fictional end-to-end evidence propagation through existing Inbox writes."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.routers import inbox
from backend.app.api.routers.analytics import EMAIL_KINDS, analytics_read, analytics_session
from backend.app.config import get_settings
from backend.app.db.models import ApplicationEventRecord as Event, GmailConnectionRecord, GmailMessageRecord as Mail, JobMarkRecord, JobRecord
from backend.app.inbox.company_outcomes import KIND as COMPANY_REJECTION
from backend.app.inbox.filed_evidence import ACTION_PREFIX, UNVERIFIED_NOTE
from backend.tests.test_analytics_read import NOW, app, db
from backend.tests.test_inbox_persistence import message, owner_request, verified_scope


@pytest.fixture()
def pipeline(db, monkeypatch):
    monkeypatch.setenv("GMAIL_AUTO_OUTCOMES_ALLOWED", "true")
    monkeypatch.setenv("GMAIL_AUTO_REJECTIONS", "true")
    get_settings.cache_clear()
    key = app(db, 1, age=80)
    db.get(JobRecord, int(key.split(":")[1])).requisition_id = "SE-101"
    conn = GmailConnectionRecord(owner_id=1, email="fixture@example.test", encrypted_refresh_token=b"fictional",
                                 scope="gmail.readonly", state="ready", auto_outcomes_enabled=True)
    db.add(conn)
    db.commit()
    yield db, conn, key
    get_settings.cache_clear()


def read(db, **kwargs):
    """The next independent request sees committed data, with no import step."""
    with Session(db.get_bind()) as reader:
        return analytics_read(reader, now=NOW, tz="America/Los_Angeles", emails=True, records=True, **kwargs)


def ingest(pipeline, name, body, *, received=None, preview=False, unknown_employer=False, authenticated=True, subject=None):
    db, conn, _ = pipeline
    data = message(name, body, received_at=received or NOW-timedelta(days=2))
    for header in data["payload"]["headers"]:
        if header["name"] == "Subject" and subject:
            header["value"] = subject
        if header["name"] == "From" and unknown_employer:
            header["value"] = "hiring@fictional-unrecorded.example"
        if header["name"] == "Authentication-Results":
            domain = "fictional-unrecorded.example" if unknown_employer else "careers.silverpine.example"
            header["value"] = f"mx.google.com; dmarc={'pass' if authenticated else 'fail'} header.from={domain}"
    result = inbox._ingest(db, conn, data, inbox._identities(db), preview=preview)
    db.commit()
    return result, db.scalar(select(Mail).where(Mail.gmail_id == name)), data


def test_acknowledgement_commit_updates_correspondence_without_manufacturing_a_reply(pipeline):
    db, _, _ = pipeline
    before = read(db)
    result, mail, _ = ingest(pipeline, "receipt", "Req ID: SE-101. Thank you for applying. We have received your application.")
    assert result == "receipt"
    after = read(db, email_kind="application_confirmation")
    assert after["classified_email_evidence"]["categories"]["application_confirmation"] == 1
    assert after["email_total"] == 1 and after["email_records"][0]["id"] == mail.id
    for key in ("positive", "assessments", "interviews", "cohort", "statuses"):
        assert after[key] == before[key]
    assert after["evidence"]["rejected"] == 0


def test_receipt_selected_key_without_verified_event_never_establishes_filtered_identity(pipeline):
    db, _, key = pipeline
    result, mail, _ = ingest(pipeline, "unverified-receipt", "Req ID: SE-101. Thank you for applying. We have received your application.",
                             authenticated=False)
    assert result == "receipt" and mail.selected_application_key == key
    report = read(db, email_kind="application_confirmation")
    assert report["email_total"] == 1
    assert report["email_records"][0]["application_key"] is None
    assert report["email_records"][0]["company"] is None
    assert report["classified_email_evidence"]["linked_messages"] == 0
    assert report["classified_email_evidence"]["unlinked_messages"] == 1
    assert read(db, family="SOFTWARE_ENGINEERING")["email_total"] == 0
    assert read(db, company="Silverpine Labs")["email_total"] == 0


@pytest.mark.parametrize("kind,body,status", [
    ("online_assessment", "Please complete your online assessment.", "screening"),
    ("interview", "Please book your technical interview.", "interviewing"),
    ("offer", "We are pleased to offer you the Software Engineer position.", "offer"),
    ("recruiter_reply", "We would like to speak with you about your application.", "screening"),
    ("rejection", "Your application was rejected.", "rejected"),
])
@pytest.mark.parametrize("verified", [False, True])
def test_new_recognition_and_verified_stage_use_distinct_counts(pipeline, kind, body, status, verified):
    db, _, key = pipeline
    result, mail, data = ingest(pipeline, kind, ("Req ID: SE-101. " if verified else "") + body,
                                unknown_employer=not verified)
    assert result == ("automatic" if verified else "classified_rejection" if kind == "rejection" else "classified_action")
    after = read(db, email_kind=kind)
    assert after["classified_email_evidence"]["categories"][kind] == after["email_total"] == 1
    assert after["classified_email_evidence"]["linked_messages"] == int(verified)
    assert after["classified_email_evidence"]["unlinked_messages"] == int(not verified)
    assert db.get(JobMarkRecord, int(key.split(":")[1])).application_status == (status if verified else "applied")
    assert after["positive"] == int(verified and kind != "rejection")
    assert after["evidence"]["rejected"] == int(verified and kind == "rejection")
    assert after["assessments"] == int(verified and kind == "online_assessment")
    assert after["interviews"] == int(verified and kind == "interview")
    event_count = db.scalar(select(func.count()).select_from(Event))
    assert inbox._ingest(db, pipeline[1], data, inbox._identities(db), preview=False) == "duplicate"
    db.commit()
    assert read(db, email_kind=kind)["email_total"] == 1
    assert db.scalar(select(func.count()).select_from(Event)) == event_count


def test_ambiguous_company_rejection_does_not_change_any_application(pipeline):
    db, _, _ = pipeline
    app(db, 2, age=80)
    db.commit()
    result, mail, _ = ingest(pipeline, "company", "Your application was rejected.")
    assert result == COMPANY_REJECTION
    after = read(db, email_kind="rejection", email_scope="company")
    assert after["email_total"] == after["company_rejection_summary"]["messages"] == 1
    assert after["email_records"][0]["id"] == mail.id
    assert after["classified_email_evidence"]["company_messages"] == 1
    assert after["evidence"]["rejected"] == 0 and after["statuses"] == {"applied": 2}
    event = db.scalar(select(Event).where(Event.kind == COMPANY_REJECTION))
    inbox.undo(event.id, owner_request(), db)
    assert read(db)["email_total"] == read(db)["company_rejection_summary"]["messages"] == 0
    assert db.scalar(select(func.count()).select_from(Event)) == 3


def test_conversational_invitation_receipt_history_survives_later_rejection_without_inventing_a_stage(pipeline):
    db, _, key = pipeline
    receipt = datetime(2026, 9, 15, 19, tzinfo=timezone.utc)
    body = ("Our hiring team is interested in your background. We would love the opportunity to meet you and learn about your background.\n\n"
            "The interview will cover your recent projects and the engineering position.\n\n"
            "If you are interested, please select a convenient time below.")
    result, invite, _ = ingest(pipeline, "conversational", body, received=receipt, unknown_employer=True,
                               subject="Interview with Fictional Robotics")
    assert result == "classified_action" and invite.classification == "interview"
    ingest(pipeline, "final-rejection", "Req ID: SE-101. Your application was rejected.")
    all_time = read(db, email_kind="interview")
    assert all_time["email_records"][0]["id"] == invite.id
    assert all_time["interviews"] == 0 and all_time["evidence"]["rejected"] == 1
    assert db.get(JobMarkRecord, int(key.split(":")[1])).application_status == "rejected"
    for days in ("14", "30", "90", "all"):
        report = read(db, days=days, email_kind="interview")
        assert report["email_total"] == int(days in {"90", "all"})
    assert read(db, start=date(2026, 9, 15), end=date(2026, 9, 15), email_kind="interview")["email_total"] == 1
    assert read(db, start=date(2026, 9, 16), end=date(2026, 9, 16), email_kind="interview")["email_total"] == 0


def test_verified_assessment_interview_and_rejection_keep_overlapping_history(pipeline):
    db, _, _ = pipeline
    for name, body, age in (("assessment", "Please complete your online assessment.", 35),
                            ("interview", "Please book your technical interview.", 25),
                            ("rejection", "Your application was rejected.", 2)):
        assert ingest(pipeline, name, "Req ID: SE-101. " + body, received=NOW-timedelta(days=age))[0] == "automatic"
    report = read(db)
    assert report["positive"] == report["assessments"] == report["interviews"] == 1
    assert report["evidence"]["rejected"] == report["cohort"]["rejected"] == 1
    assert report["classified_email_evidence"]["total"] == 3
    assert report["records"][0]["event_types"] == ["interview", "online_assessment", "rejection"]


def test_owner_manual_stage_without_optional_kind_survives_later_rejection(pipeline):
    db, _, key = pipeline
    _, receipt, _ = ingest(pipeline, "owner-interview-receipt", "Req ID: SE-101. Thank you for applying. We have received your application.")
    inbox.review(inbox.ManualDecision(message_id=receipt.id, application_key=key, status="interviewing",
                                     expected_status="applied", confirmed=True), owner_request(), db)
    assert receipt.classification == "application_confirmation"
    assert read(db)["interviews"] == read(db)["positive"] == 1
    _, rejection, _ = ingest(pipeline, "owner-later-rejection", "Your application was rejected.", unknown_employer=True)
    inbox.review(inbox.ManualDecision(message_id=rejection.id, application_key=key, status="rejected",
                                     expected_status="interviewing", confirmed=True, kind="rejection"), owner_request(), db)
    report = read(db)
    assert report["interviews"] == report["positive"] == report["evidence"]["rejected"] == 1
    assert report["cohort"]["rejected"] == 1 and report["statuses"] == {"rejected": 1}
    assert report["records"][0]["event_types"] == ["interview", "rejection"]
    categories = report["classified_email_evidence"]["categories"]
    assert categories["application_confirmation"] == categories["rejection"] == 1
    assert categories["interview"] == 0  # Email meaning and owner stage remain separate.
    assert receipt.classification == "application_confirmation"


def test_owner_receipt_override_uses_shared_meaning_and_retains_raw_audit(pipeline):
    db, _, _ = pipeline
    _, mail, _ = ingest(pipeline, "corrected", "Please book your technical interview.", unknown_employer=True)
    before_events = db.scalar(select(func.count()).select_from(Event))
    inbox.decide_message(mail.id, inbox.EmailDisposition(action="receipt"), owner_request(), db)
    report = read(db)
    categories = report["classified_email_evidence"]["categories"]
    assert categories["interview"] == 0 and categories["application_confirmation"] == 1
    assert mail.classification == "interview"  # Raw classifier history stays intact.
    assert db.scalar(select(func.count()).select_from(Event)) == before_events + 1


def test_existing_recheck_commit_replaces_effective_category_without_an_analytics_import(pipeline, monkeypatch):
    db, conn, _ = pipeline
    _, mail, _ = ingest(pipeline, "reclassified", "Req ID: SE-101. Thank you for applying. We have received your application.")
    assert read(db)["classified_email_evidence"]["categories"]["application_confirmation"] == 1
    mail.parser_version = "0"
    db.commit()
    monkeypatch.setenv("GMAIL_HISTORICAL_RECHECKS_ENABLED", "true")  # Isolated fictional grant only.
    get_settings.cache_clear()
    verified_scope(db, conn)
    corrected = message(mail.gmail_id, "Req ID: SE-101. Please complete your online assessment.",
                        received_at=mail.received_at)
    monkeypatch.setattr(inbox, "_access", lambda _: "fictional-token")
    monkeypatch.setattr(inbox, "_scoped_detail", lambda *args: corrected)
    result = inbox._recheck_locked(inbox.RecheckRequest(limit=10), db, conn)
    assert result["checked"] == 1
    report = read(db)
    assert report["classified_email_evidence"]["categories"]["application_confirmation"] == 0
    assert report["classified_email_evidence"]["categories"]["online_assessment"] == 1
    assert report["assessments"] == 0  # Preview policies still apply.
    assert db.scalar(select(func.count()).select_from(Mail)) == 1
    assert db.scalar(select(func.count()).select_from(Event)) == 2
    assert inbox._recheck_locked(inbox.RecheckRequest(limit=10), db, conn)["checked"] == 0


@pytest.mark.parametrize("kind,body", [("interview", "Please book your technical interview."),
                                       ("online_assessment", "Please complete your online assessment.")])
def test_unverified_source_is_visible_as_meaning_without_application_authority(pipeline, kind, body):
    db, _, _ = pipeline
    result, _, _ = ingest(pipeline, "unverified-"+kind, "Req ID: SE-101. "+body, authenticated=False)
    assert result == "classified_action"
    report = read(db)
    assert report["classified_email_evidence"]["categories"][kind] == 1
    assert report["classified_email_evidence"]["unverified_source_messages"] == 1
    assert report["positive"] == report["assessments"] == report["interviews"] == 0


@pytest.mark.parametrize("kind,body", [("assessment_completed", "Your coding assessment is completed."),
                                       ("assessment_cancelled", "Your coding assessment was cancelled."),
                                       ("interview_cancelled", "Your interview invitation has been withdrawn.")])
def test_completed_and_cancelled_correspondence_has_distinct_categories_not_invitation_counts(pipeline, kind, body):
    db, _, _ = pipeline
    result, _, _ = ingest(pipeline, "passive-"+kind, body, unknown_employer=True)
    assert result == "update"
    report = read(db, email_kind=kind)
    assert report["email_total"] == report["classified_email_evidence"]["categories"][kind] == 1
    assert report["positive"] == report["assessments"] == report["interviews"] == 0


def test_undo_and_reassignment_remove_only_superseded_effective_outcome(pipeline):
    db, _, first = pipeline
    other = app(db, 2, age=80, company="Fictional Other Labs")
    db.commit()
    _, mail, _ = ingest(pipeline, "reassigned", "Req ID: SE-101. Your application was rejected.")
    event = db.scalar(select(Event).where(Event.kind == "rejection"))
    inbox.undo(event.id, owner_request(), db)
    assert read(db)["evidence"]["rejected"] == read(db)["email_total"] == 0
    inbox.review(inbox.ManualDecision(message_id=mail.id, application_key=other, status="rejected",
                                     expected_status="applied", confirmed=True, kind="rejection"), owner_request(), db)
    report = read(db, evidence="rejection", email_kind="rejection")
    assert report["record_total"] == report["email_total"] == 1
    assert report["records"][0]["key"] == report["email_records"][0]["application_key"] == other
    assert db.get(JobMarkRecord, int(first.split(":")[1])).application_status == "applied"


@pytest.mark.parametrize("invalidation", ["meaning", "target", "unverified", "refiling"])
def test_current_effective_evidence_invalidates_email_stage_without_status_fallback(pipeline, invalidation):
    db, _, key = pipeline
    _, mail, _ = ingest(pipeline, "invalidated", "Req ID: SE-101. Please book your technical interview.")
    assert read(db)["interviews"] == 1
    if invalidation == "meaning":
        mail.classification = "application_confirmation"
    elif invalidation == "target":
        mail.selected_application_key = None
    elif invalidation == "unverified":
        mail.decision_reason = ACTION_PREFIX + UNVERIFIED_NOTE + "Current source no longer supports a verified event"
    else:
        mail.decision = "review"
    db.commit()
    report = read(db)
    assert report["interviews"] == report["positive"] == 0
    assert report["cohort"]["pending"] == 1
    assert report["cohort"]["positive"] == report["cohort"]["rejected"] == 0
    assert report["statuses"]["interviewing"] == 1  # Read does not alter tracking.
    assert db.scalar(select(func.count()).select_from(Event)) == 2
    # A later explicit owner status still supplies the established legacy
    # fallback; invalidation cannot erase independently recorded owner work.
    mark = db.get(JobMarkRecord, int(key.split(":")[1]))
    mark.status_changed_at = datetime.now(timezone.utc)+timedelta(seconds=1)
    db.commit()
    assert read(db)["interviews"] == 1


def test_invalidated_later_rejection_does_not_override_valid_assessment_cohort_or_timing(pipeline):
    db, _, _ = pipeline
    ingest(pipeline, "valid-earlier-assessment", "Req ID: SE-101. Please complete your online assessment.",
           received=NOW-timedelta(days=35))
    _, rejection, _ = ingest(pipeline, "invalidated-later-rejection", "Req ID: SE-101. Your application was rejected.")
    before = read(db)
    assert before["cohort"]["rejected"] == 1
    rejection.classification = "application_confirmation"
    db.commit()
    report = read(db)
    assert report["positive"] == report["assessments"] == 1
    assert report["evidence"]["rejected"] == 0
    assert report["cohort"]["positive"] == 1 and report["cohort"]["rejected"] == 0
    assert report["cohort"]["pending"] == report["cohort"]["unknown"] == 0
    assert report["statuses"] == {"rejected": 1}  # Stored tracking is preserved.
    assert report["median_days"] == before["median_days"] == 45
    assert report["timing_sample"] == before["timing_sample"] == 1
    assert report["records"][0]["event_types"] == ["online_assessment"]


def test_receipt_window_and_role_filters_use_verified_identity_outside_submission_cohort(pipeline):
    db, _, key = pipeline
    ingest(pipeline, "older-submission-recent-interview", "Req ID: SE-101. Please book your technical interview.")
    report = read(db, days="14", family="SOFTWARE_ENGINEERING", email_kind="interview")
    assert report["submitted"] == report["interviews"] == 0
    assert report["email_total"] == report["classified_email_evidence"]["categories"]["interview"] == 1
    assert report["email_records"][0]["application_key"] == key


def test_email_floor_future_and_local_midnight_are_shared_by_totals_and_drilldown(pipeline):
    db, _, _ = pipeline
    stamps = [datetime(2026, 7, 1, 6, 59, tzinfo=timezone.utc), datetime(2026, 7, 1, 7, tzinfo=timezone.utc),
              datetime(2026, 10, 25, 1, tzinfo=timezone.utc), NOW+timedelta(seconds=1)]
    for index, stamp in enumerate(stamps):
        ingest(pipeline, f"boundary-{index}", "Please book your technical interview.", received=stamp, unknown_employer=True)
    assert read(db, email_kind="interview")["email_total"] == 2
    one_day = read(db, start=date(2026, 10, 24), end=date(2026, 10, 24), email_kind="interview")
    assert one_day["email_total"] == one_day["classified_email_evidence"]["categories"]["interview"] == 1
    assert db.scalar(select(func.count()).select_from(Mail)) == 4


def test_email_drilldown_paginates_exact_types_and_preserves_unlinked_filter_limits(pipeline):
    db, _, _ = pipeline
    for index in range(3):
        ingest(pipeline, f"interview-{index}", "Please book your technical interview.", unknown_employer=True)
    ingest(pipeline, "assessment", "Please complete your online assessment.", unknown_employer=True)
    first = read(db, email_kind="interview", offset=0, limit=2)
    second = read(db, email_kind="interview", offset=2, limit=2)
    assert first["email_total"] == second["email_total"] == 3
    assert len({row["id"] for row in first["email_records"]+second["email_records"]}) == 3
    assert read(db, family="SOFTWARE_ENGINEERING")["email_total"] == 0
    assert read(db, company="Silverpine Labs")["classified_email_evidence"]["company_excluded_messages"] == 4
    assert set(first["classified_email_evidence"]["categories"]) == set(EMAIL_KINDS)


def test_analytics_snapshot_requests_postgres_repeatable_read_and_readonly_before_any_select():
    options = []
    fake = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
                           connection=lambda **kwargs: options.append(kwargs))
    dependency = analytics_session(fake)
    assert next(dependency) is fake
    assert options == [{"execution_options": {"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}}]
    with pytest.raises(StopIteration):
        next(dependency)
