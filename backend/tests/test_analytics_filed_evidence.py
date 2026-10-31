"""Recognized email history is visible without fabricated application counts."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from backend.app.api.routers.analytics import EMAIL_KINDS, analytics_read
from backend.app.db.models import ApplicationEventRecord as Event, GmailConnectionRecord, GmailMessageRecord as Mail, JobMarkRecord
from backend.app.inbox.filed_evidence import ACTION_PREFIX, REJECTION_PREFIX, UNVERIFIED_NOTE
from backend.tests.test_analytics_read import NOW, app, db, outcome


def read(db, **kwargs):
    db.flush()
    return analytics_read(db, now=NOW, tz='America/Los_Angeles', **kwargs)


def filed(db, index, kind='online_assessment', received=None, **changes):
    conn = db.scalar(select(GmailConnectionRecord).limit(1))
    if conn is None:
        conn = GmailConnectionRecord(owner_id=1, email='fictional@example.test', encrypted_refresh_token=b'', scope='gmail.readonly', state='disconnected')
        db.add(conn)
        db.flush()
    row = Mail(connection_id=conn.id, gmail_id=f'filed-analytics-{index}', received_at=received or NOW-timedelta(days=2),
               sender='talent@unrecorded-employer.example', subject='Fictional application update', snippet='Fictional current reading',
               classification=kind, decision='update', decision_reason=(REJECTION_PREFIX if kind == 'rejection' else ACTION_PREFIX)+'No role was selected',
               selected_application_key=None, candidate_keys=[], parser_version='13')
    for key, value in changes.items():
        setattr(row, key, value)
    db.add(row)
    db.flush()
    return row


def test_all_recognized_categories_are_visible_without_changing_confirmed_application_metrics(db):
    key = app(db, 1)
    baseline = read(db, records=True)
    kinds = ['rejection', 'online_assessment', 'interview', 'offer', 'recruiter_reply', 'action_required']
    for index, kind in enumerate(kinds):
        filed(db, index, kind)
    result = read(db, records=True)
    assert result['classified_email_evidence'] == {
        'total': 6, 'categories': {kind: int(kind in kinds) for kind in EMAIL_KINDS}, 'date_basis': 'email_received',
        'application_status_changed': False, 'start': '2026-07-01', 'end': '2026-10-25',
        'family_excluded_messages': 0, 'company_excluded_messages': 0,
        'unverified_source_messages': 0,
        'linked_messages': 0, 'unlinked_messages': 6, 'company_messages': 0,
    }
    for field in ('total_submitted', 'submitted', 'statuses', 'positive', 'assessments', 'interviews',
                  'cohort', 'roles', 'timing', 'median_days', 'timing_sample', 'records', 'rejected_companies'):
        assert result[field] == baseline[field], field
    assert db.get(JobMarkRecord, int(key.split(':')[1])).application_status == 'applied'
    assert not list(db.scalars(select(Event)))


def test_recognized_history_is_independent_of_later_rejection_and_preserves_confirmed_stages(db):
    key = app(db, 1, status='rejected')
    outcome(db, key, 'online_assessment', stamp=NOW-timedelta(days=35))
    outcome(db, key, 'interview', stamp=NOW-timedelta(days=30))
    outcome(db, key, 'rejection', stamp=NOW-timedelta(days=20))
    filed(db, 1, 'online_assessment', received=NOW-timedelta(days=35))
    filed(db, 2, 'interview', received=NOW-timedelta(days=30))
    filed(db, 3, 'rejection', received=NOW-timedelta(days=20))
    result = read(db)
    assert result['assessments'] == result['interviews'] == result['positive'] == 1
    assert result['statuses']['rejected'] == 1 and result['cohort']['rejected'] == 1
    assert result['classified_email_evidence']['total'] == 3
    assert result['classified_email_evidence']['categories']['online_assessment'] == 1
    assert result['classified_email_evidence']['categories']['interview'] == 1
    assert db.get(JobMarkRecord, int(key.split(':')[1])).application_status == 'rejected'


def test_all_time_includes_email_before_first_application_but_finite_range_uses_receipt_date(db):
    app(db, 1, age=1)
    filed(db, 1, received=NOW-timedelta(days=60))
    filed(db, 2, received=NOW-timedelta(days=300))  # Retained storage outside this search.
    assert read(db)['classified_email_evidence']['total'] == 1
    assert read(db, days='30')['classified_email_evidence']['total'] == 0


def test_receipt_calendar_date_is_local_and_future_evidence_is_excluded(db):
    from datetime import datetime, timezone
    filed(db, 1, received=datetime(2026, 10, 25, 1, tzinfo=timezone.utc))  # October 24 Pacific.
    filed(db, 2, received=datetime(2026, 10, 25, 8, tzinfo=timezone.utc))
    filed(db, 3, received=NOW+timedelta(minutes=1))
    result = read(db, start=date(2026, 10, 24), end=date(2026, 10, 24))['classified_email_evidence']
    assert result['total'] == 1 and result['start'] == result['end'] == '2026-10-24'
    assert read(db)['classified_email_evidence']['total'] == 2


@pytest.mark.parametrize('changes', [
    {'decision': 'review'}, {'decision': 'deferred'}, {'decision': 'manual'}, {'decision': 'unrelated'},
    {'decision_reason': "You undid ACE's change for this email"},
    {'decision_reason': 'You marked it a status update with no decision yet'},
    {'selected_application_key': 'job:1'},
    {'classification': 'possible_rejection'}, {'classification': 'assessment_completed'},
    {'decision_reason': REJECTION_PREFIX + 'Wrong marker'},
])
def test_unrecognized_owner_deferred_undone_or_linked_rows_are_not_filed_analytics_evidence(db, changes):
    filed(db, 1, **changes)
    assert read(db)['classified_email_evidence']['total'] == 0


@pytest.mark.parametrize('filters', [{'company': 'Silverpine Labs'}, {'family': 'SOFTWARE_ENGINEERING'},
                                    {'company': 'Silverpine Labs', 'family': 'SOFTWARE_ENGINEERING'}])
def test_unknown_application_identity_is_excluded_from_company_and_family_attribution(db, filters):
    app(db, 1)
    filed(db, 1)
    filed(db, 2, 'interview')
    result = read(db, **filters)['classified_email_evidence']
    assert result['total'] == 0 and not any(result['categories'].values())
    assert result['company_excluded_messages'] == (2 if filters.get('company') else 0)
    assert result['family_excluded_messages'] == (2 if filters.get('family') else 0)


def test_unverified_source_count_follows_active_visible_evidence_and_selected_receipt_dates(db):
    filed(db, 1, decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'No role was selected')
    filed(db, 2, 'rejection', decision_reason=REJECTION_PREFIX + UNVERIFIED_NOTE + 'No role was selected')
    filed(db, 3, 'interview')
    filed(db, 4, received=NOW-timedelta(days=100), decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'Older evidence')
    filed(db, 5, received=NOW+timedelta(days=1), decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'Future evidence')
    filed(db, 6, decision='review', decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'Unresolved')
    filed(db, 7, selected_application_key='job:1', decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'Linked')
    all_time = read(db)['classified_email_evidence']
    assert all_time['total'] == 4 and all_time['unverified_source_messages'] == 3
    recent = read(db, days='30')['classified_email_evidence']
    assert recent['total'] == 3 and recent['unverified_source_messages'] == 2
    assert recent['categories']['rejection'] == 1 and recent['categories']['interview'] == 1
    assert not list(db.scalars(select(Event)))


@pytest.mark.parametrize('filters', [{'company': 'Silverpine Labs'}, {'family': 'SOFTWARE_ENGINEERING'}])
def test_unverified_source_metadata_cannot_assign_filtered_application_identity(db, filters):
    app(db, 1)
    filed(db, 1, decision_reason=ACTION_PREFIX + UNVERIFIED_NOTE + 'No role was selected')
    result = read(db, **filters)['classified_email_evidence']
    assert result['total'] == result['unverified_source_messages'] == 0

