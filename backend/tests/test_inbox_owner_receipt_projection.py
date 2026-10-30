"""Explicit owner receipt decisions outrank retained classifier labels, read-only."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from backend.app.api.routers import inbox
from backend.app.api.routers.analytics import analytics_read
from backend.app.db.models import ApplicationEventRecord as Event, GmailMessageRecord as Mail
from backend.app.inbox.historical_cleanup import row_state
from backend.app.inbox.queue import (
    OWNER_RECEIPT_REASON, classification_expression, projected_classification,
)
from backend.tests.test_inbox_persistence import NOW, database, owner_request, statuses, stored


def receipt(session, conn, key='fictional-owner-receipt', *, kind='offer', raw='receipt', reason=OWNER_RECEIPT_REASON):
    row = stored(session, conn, key, raw, 'Fictional received application', reason=reason, version='2')
    row.classification = kind
    session.commit()
    return row


def test_owner_receipt_effective_acknowledgement_preserves_saved_offer_and_original_evidence(database):
    session, conn = database
    row = receipt(session, conn)
    before = row_state(row)
    item = inbox.message(row.id, owner_request(), session)
    assert item['classification'] == projected_classification(row) == 'application_confirmation'
    assert item['saved_classification'] == 'offer' and item['decision'] == 'receipt'
    assert item['reason'] == OWNER_RECEIPT_REASON
    assert item['understanding']['decision_type'] == 'Owner decision'
    assert item['understanding']['classification_source'] == 'owner_decision'
    assert 'earlier classifier reading is retained for audit' in item['understanding']['classification_reason']
    assert item['understanding']['classification_state'] == 'recognized'
    assert item['understanding']['update_policy'] == 'no_status_change'
    assert row_state(row) == before and row.classification == 'offer' and row.parser_version == '2'
    assert not session.new and not session.dirty and not session.deleted
    assert not session.scalars(select(Event)).all() and statuses(session) == ['applied']*3


@pytest.mark.parametrize('kind', ['offer', 'interview', 'online_assessment', 'rejection', 'possible_rejection', 'unknown', 'application_confirmation'])
def test_every_explicit_owner_receipt_uses_the_same_sql_and_python_acknowledgement(kind, database):
    session, conn = database
    row = receipt(session, conn, kind=kind)
    assert projected_classification(row) == session.scalar(select(classification_expression()).where(Mail.id == row.id)) == 'application_confirmation'
    assert inbox._item(row)['saved_classification'] == kind
    assert 'CASE WHEN' in str(classification_expression().compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize('raw,reason', [
    ('receipt', 'Application receipt; no status change'),
    ('receipt', 'Saved application correspondence; no confirmed outcome to record'),
    ('receipt', OWNER_RECEIPT_REASON + ' additional wording'),
    ('receipt', OWNER_RECEIPT_REASON.lower()),
    ('update', OWNER_RECEIPT_REASON),
    ('update', 'You marked it a status update with no decision yet'),
    ('deferred', 'You chose to decide later'),
    ('unrelated', 'You marked it not about your applications'),
    ('manual', 'You recorded a confirmed offer'),
    ('review', "You undid ACE's change for this email"),
])
def test_other_owner_or_automatic_filing_does_not_change_saved_classification(database, raw, reason):
    session, conn = database
    row = receipt(session, conn, raw=raw, reason=reason)
    assert projected_classification(row) == session.scalar(select(classification_expression()).where(Mail.id == row.id)) == 'offer'
    assert inbox._item(row)['classification'] == 'offer'
    assert inbox._item(row)['understanding']['classification_source'] == 'classifier'
    assert row.classification == 'offer'


def test_category_counts_and_sql_filtering_before_pagination_respect_owner_receipts(database):
    session, conn = database
    owner_ids = set()
    real_offer_ids = set()
    for index in range(5):
        row = receipt(session, conn, f'owner-old-offer-{index}')
        row.received_at = NOW-timedelta(minutes=index)
        owner_ids.add(row.id)
    for index in range(3):
        row = receipt(session, conn, f'fictional-offer-{index}', raw='review', reason='No application could be matched with confidence')
        row.received_at = NOW-timedelta(minutes=30+index)
        real_offer_ids.add(row.id)
    session.commit()
    all_rows = {row.id: row_state(row) for row in session.scalars(select(Mail))}
    all_messages = inbox.messages(owner_request(), session, None, 0, 100)
    assert all_messages['counts']['offers'] == 3 and all_messages['counts']['receipts'] == 5
    first = inbox.messages(owner_request(), session, 'offers', 0, 2)
    second = inbox.messages(owner_request(), session, 'offers', 2, 2)
    assert first['total'] == second['total'] == 3 and first['has_more'] and not second['has_more']
    assert {item['id'] for item in first['items']+second['items']} == real_offer_ids
    acknowledgements = inbox.messages(owner_request(), session, 'receipt', 0, 100)
    assert {item['id'] for item in acknowledgements['items']} == owner_ids
    assert all(item['classification'] == 'application_confirmation' for item in acknowledgements['items'])
    assert inbox.messages(owner_request(), session, 'offers', 0, 100, q='received')['total'] == 3
    assert {row.id: row_state(row) for row in session.scalars(select(Mail))} == all_rows


def test_owner_receipts_are_absent_from_assessment_interview_and_rejection_categories(database):
    session, conn = database
    for kind in ['online_assessment', 'interview', 'rejection']:
        receipt(session, conn, 'owner-receipt-' + kind, kind=kind)
    result = inbox.messages(owner_request(), session, None, 0, 100)
    assert all(result['counts'][name] == 0 for name in ['assessments', 'interviews', 'rejections', 'offers'])
    assert result['counts']['receipts'] == 3
    for category in ['assessments', 'interviews', 'rejections']:
        assert inbox.messages(owner_request(), session, category, 0, 100)['total'] == 0


def test_analytics_related_email_display_uses_owner_acknowledgement_without_claiming_application_offer(database):
    session, conn = database
    row = receipt(session, conn)
    before = row_state(row)
    result = analytics_read(session, now=NOW+timedelta(seconds=1), records=True, q='received')
    assert result['not_listed']['email_total'] == 1
    [display] = result['not_listed']['emails']
    assert display['id'] == row.id and display['classification'] == 'application_confirmation'
    assert display['saved_classification'] == 'offer' and display['decision'] == 'receipt'
    assert result['positive'] == 0 and result['classified_email_evidence']['categories']['offer'] == 0
    assert result['statuses'] == {'applied': 3}
    assert row_state(row) == before and session.scalar(select(func.count()).select_from(Event)) == 0
