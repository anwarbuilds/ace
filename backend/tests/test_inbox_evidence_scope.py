"""Independent owner search-window boundaries; all fixtures are fictional."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.app.api.routers import inbox
from backend.app.api.routers.analytics import analytics_read
from backend.app.db.models import ApplicationEventRecord as Event, GmailMessageRecord as Mail, JobMarkRecord
from backend.app.inbox import evidence_scope
from backend.app.inbox.company_outcomes import COMPANY_REASON, encode_reason
from backend.app.inbox.filed_evidence import ACTION_PREFIX, REJECTION_PREFIX
from backend.scripts.inbox_analytics_audit import audit
from backend.tests.test_inbox_persistence import (
    database, job_events, message, owner_request, row_for, statuses, stored, verified_scope,
)


BOUNDARY = datetime(2026, 7, 1, 7, tzinfo=timezone.utc)
BEFORE = BOUNDARY-timedelta(microseconds=1)
NOW = datetime(2026, 10, 29, 20, tzinfo=timezone.utc)
SCOPE = {'start': '2026-07-01', 'timezone': 'America/Los_Angeles',
         'start_at': '2026-07-01T07:00:00Z', 'application_cohort_unchanged': True}


def mail(session, conn, suffix, *, stamp=BOUNDARY, kind='online_assessment', decision='update', reason=None):
    prefix = REJECTION_PREFIX if kind == 'rejection' else ACTION_PREFIX
    row = stored(session, conn, suffix, decision, 'Search window fictional correspondence', version='0',
                 reason=reason or prefix + 'No application was selected')
    row.received_at = stamp
    row.classification = kind
    row.candidate_keys = []
    row.selected_application_key = None
    session.flush()
    return row


def company_event(session, conn, row):
    row.classification = 'rejection'
    row.decision_reason = COMPANY_REASON
    session.add(Event(application_key=f'email:{row.id}', gmail_message_id=row.id,
                      kind='company_rejection', actor='verified_automation',
                      previous_status=None, new_status=None,
                      reason=encode_reason('Silverpine Labs', 'Fictional employer rejection'),
                      occurred_at=row.received_at, dedupe_key=f'company-window-{row.id}'))
    session.flush()


@pytest.mark.parametrize('stamp,in_scope', [
    (BEFORE, False), (BOUNDARY, True), (BOUNDARY+timedelta(microseconds=1), True),
    (datetime.fromisoformat('2026-06-30T23:59:59.999999-07:00'), False),
    (datetime.fromisoformat('2026-07-01T00:00:00-07:00'), True),
    (datetime.fromisoformat('2026-07-01T00:00:00+00:00'), False),
    (datetime(2026, 7, 1, 7), True),
])
def test_owner_midnight_uses_la_summer_offset_and_accepts_exact_boundary(stamp, in_scope):
    assert evidence_scope.includes(stamp) is in_scope
    assert evidence_scope.metadata() == SCOPE


def test_all_category_lists_counts_search_pagination_and_latest_share_the_same_floor(database):
    session, conn = database
    old = []
    current = []
    for index, (kind, decision) in enumerate([
        ('online_assessment', 'update'), ('interview', 'update'), ('offer', 'update'),
        ('rejection', 'update'), ('application_confirmation', 'receipt'),
        ('unclear', 'review'), ('unclear', 'deferred'), ('unknown', 'ignored'),
    ]):
        reason = 'Fictional ambiguity' if decision != 'update' else None
        old.append(mail(session, conn, f'old-window-{index}', stamp=BEFORE, kind=kind, decision=decision, reason=reason))
        current.append(mail(session, conn, f'current-window-{index}', stamp=BOUNDARY+timedelta(minutes=index), kind=kind, decision=decision, reason=reason))
    session.commit()
    result = inbox.messages(owner_request(), session, None, 0, 100)
    assert result['evidence_scope'] == SCOPE
    assert result['total'] == result['counts']['stored'] == 8
    assert result['counts']['stored_all_dates'] == 16
    assert result['review_count'] == result['counts']['needs_review'] == 2
    assert (result['counts']['assessments'], result['counts']['interviews'], result['counts']['offers'], result['counts']['rejections']) == (1, 1, 1, 1)
    assert result['latest_received_at'] == current[-1].received_at.isoformat()
    allowed = {row.id for row in current}
    for view in (None, 'auto', 'pending', 'assessments', 'interviews', 'offers', 'rejections', 'filed',
                 'classified_action', 'classified_rejection', 'review', 'deferred', 'ignored', 'recruiting'):
        assert {item['id'] for item in inbox.messages(owner_request(), session, view, 0, 100)['items']} <= allowed
    first = inbox.messages(owner_request(), session, None, 0, 3)
    second = inbox.messages(owner_request(), session, None, 3, 100)
    assert first['has_more'] and not second['has_more']
    assert {item['id'] for item in first['items']+second['items']} == allowed
    assert inbox.messages(owner_request(), session, None, 0, 100, q='Search window')['total'] == 8
    assert session.scalar(select(func.count()).select_from(Mail)) == 16
    assert not job_events(session) and statuses(session) == ['applied']*3


def test_only_old_rows_have_no_visible_latest_or_pending_but_stay_accessible_by_id(database):
    session, conn = database
    row = mail(session, conn, 'old-only-window', stamp=BEFORE, kind='unclear', decision='review', reason='Fictional ambiguity')
    session.commit()
    result = inbox.messages(owner_request(), session, 'auto', 0, 100)
    assert result['total'] == result['counts']['stored'] == result['review_count'] == 0
    assert result['counts']['stored_all_dates'] == 1 and result['latest_received_at'] is None
    assert inbox.message(row.id, owner_request(), session)['id'] == row.id
    assert session.get(Mail, row.id).decision == 'review'


def test_hidden_historical_application_evidence_retains_direct_audit_and_undo(database):
    session, conn = database
    for mark in session.scalars(select(JobMarkRecord)):
        mark.applied_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session.commit()
    assert inbox._ingest(session, conn, message('old-exact-undo', 'Req ID: SE-101. Your application was rejected.', BEFORE),
                         inbox._identities(session), preview=True) == 'automatic'
    row = row_for(session, 'old-exact-undo')
    [event] = job_events(session)
    assert inbox.messages(owner_request(), session, None, 0, 100)['total'] == 0
    assert inbox.message(row.id, owner_request(), session)['decision'] == 'automatic'
    assert event.id in {item['id'] for item in inbox.events(owner_request(), session, row.id)['items']}
    inbox.undo(event.id, owner_request(), session)
    assert statuses(session) == ['applied']*3 and row.decision_reason.startswith('You undid')
    assert session.get(Event, event.id) is not None


def test_stale_count_uses_search_floor_without_rewriting_excluded_email(database):
    session, conn = database
    old = mail(session, conn, 'old-stale-window', stamp=BEFORE, kind='unclear', decision='review', reason='Fictional ambiguity')
    active = mail(session, conn, 'current-stale-window', stamp=BOUNDARY, kind='unclear', decision='review', reason='Fictional ambiguity')
    session.commit()
    verified_scope(session, conn)
    assert inbox.messages(owner_request(), session, None, 0, 100)['counts']['stale'] == 1
    assert session.scalars(inbox._eligible_stale_query(conn)).all() == [active]
    assert old.parser_version == '0' and old.decision == 'review'


@pytest.mark.parametrize('tz', ['America/Los_Angeles', 'UTC', 'Asia/Tokyo', 'America/Anchorage'])
def test_analytics_display_timezone_cannot_move_absolute_owner_search_floor(database, tz):
    session, conn = database
    for index, stamp in enumerate([BEFORE, BOUNDARY]):
        mail(session, conn, f'action-boundary-{index}', stamp=stamp)
        company_event(session, conn, mail(session, conn, f'company-boundary-{index}', stamp=stamp, kind='rejection'))
        mail(session, conn, f'pending-boundary-{index}', stamp=stamp, kind='unclear', decision='review', reason='Fictional ambiguity')
    session.commit()
    result = analytics_read(session, now=NOW, days='all', tz=tz)
    assert result['evidence_scope'] == SCOPE
    assert result['classified_email_evidence']['total'] == 2
    assert result['classified_email_evidence']['categories']['online_assessment'] == 1
    assert result['classified_email_evidence']['categories']['rejection'] == 1
    assert result['company_rejection_summary']['messages'] == 1
    assert result['review']['needs_review'] == 1 and result['inbox_audit']['stored_messages'] == 3
    assert session.scalar(select(func.count()).select_from(Mail)) == 6


def test_email_all_time_starts_july_first_without_changing_application_cohort_dates_or_confirmed_stages(database):
    session, conn = database
    target = session.get(JobMarkRecord, 2)
    target.applied_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    target.application_status = 'rejected'
    for index, (kind, stamp) in enumerate([('online_assessment', datetime(2026, 6, 10, tzinfo=timezone.utc)),
                                         ('interview', datetime(2026, 6, 20, tzinfo=timezone.utc)),
                                         ('rejection', datetime(2026, 6, 30, tzinfo=timezone.utc))]):
        row = mail(session, conn, f'old-confirmed-stage-{index}', stamp=stamp, kind=kind, decision='manual', reason='You recorded this fictional decision')
        row.selected_application_key = 'job:2'
        session.add(Event(application_key='job:2', gmail_message_id=row.id, kind=kind, actor='owner', reason='Fictional confirmed stage',
                          occurred_at=stamp, dedupe_key=f'old-confirmed-stage-{index}'))
    mail(session, conn, 'old-filed-stage', stamp=BEFORE)
    mail(session, conn, 'current-filed-stage', stamp=BOUNDARY)
    session.commit()
    result = analytics_read(session, now=NOW, days='all', tz='America/Los_Angeles', records=True)
    assert result['start'] == '2026-05-31'  # Existing application calendar remains independent.
    assert result['classified_email_evidence']['start'] == '2026-07-01'
    assert result['classified_email_evidence']['total'] == 1
    assert result['positive'] == result['assessments'] == result['interviews'] == 1
    assert result['statuses']['rejected'] == 1
    assert target.application_status == 'rejected'
    record = next(item for item in result['records'] if item['key'] == 'job:2')
    assert record['event_types'] == ['interview', 'online_assessment', 'rejection']


def test_custom_email_date_range_can_narrow_but_never_expand_search_floor(database):
    session, conn = database
    mail(session, conn, 'before-custom-floor', stamp=BEFORE)
    mail(session, conn, 'at-custom-floor', stamp=BOUNDARY)
    mail(session, conn, 'after-custom-floor', stamp=BOUNDARY+timedelta(days=1))
    session.commit()
    empty = analytics_read(session, now=NOW, start=date(2026, 6, 1), end=date(2026, 6, 30), tz='America/Los_Angeles')
    assert empty['classified_email_evidence']['total'] == 0
    one = analytics_read(session, now=NOW, start=date(2026, 6, 1), end=date(2026, 7, 1), tz='America/Los_Angeles')
    assert one['classified_email_evidence']['start'] == '2026-07-01'
    assert one['classified_email_evidence']['total'] == 1


def test_analytics_email_search_and_aggregate_audit_apply_the_same_scope(database):
    session, conn = database
    mail(session, conn, 'old-search-floor', stamp=BEFORE, kind='unclear', decision='review', reason='Fictional ambiguity')
    current = mail(session, conn, 'new-search-floor', stamp=BOUNDARY)
    session.commit()
    result = analytics_read(session, now=NOW, records=True, q='correspondence')
    assert result['not_listed']['email_total'] == 1
    assert [item['id'] for item in result['not_listed']['emails']] == [current.id]
    checked = audit(session, now=NOW)
    assert checked['evidence_scope'] == SCOPE
    assert checked['stored_mail_all_dates'] == 2 and checked['stored_mail_in_scope'] == 1
    assert checked['review_queue']['inbox_pending'] == checked['review_queue']['analytics_pending'] == 0
    assert checked['classified_email_evidence'] == {'inbox_messages': 1, 'analytics_messages': 1,
                                                  'categories': {'online_assessment': 1}, 'agrees': True}
    assert checked['projection_checks_pass']
