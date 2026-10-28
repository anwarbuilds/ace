"""Transactional safeguards for explicitly approved classification-only cleanup."""
from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.app.api.routers import inbox
from backend.app.db.models import ApplicationEventRecord as Event
from backend.app.inbox import historical_cleanup as cleanup
from backend.tests.test_inbox_persistence import database, stored, message, statuses, job_events


def prepare(session, conn, body='Improve your skills with this challenge recommended for you: Lantern Trees.'):
    row = stored(session, conn, 'guarded-cleanup', 'review', 'Your coding message', version='7', reason='No application could be matched with confidence')
    row.classification = 'online_assessment'
    session.commit()
    data = message('guarded-cleanup', body)
    return row, cleanup.projection(session, conn, row, data), data


def test_preview_is_pure_and_apply_changes_only_email_fields_with_audit(database):
    session, conn = database
    row, plan, data = prepare(session, conn)
    assert plan['patch']['decision'] == 'ignored' and row.decision == 'review'
    assert not plan['would_change_status'] and not plan['would_record_outcome']
    original = cleanup.row_state(row)
    event = cleanup.apply_prepared(session, conn, plan, cleanup.projection(session, conn, row, data), 'fixture01')
    session.commit()
    assert statuses(session) == ['applied'] * 3 and not job_events(session)
    assert event.application_key == f'email:{row.id}' and event.actor == 'classifier'
    assert {key: value for key, value in cleanup.row_state(row).items() if key not in cleanup.FIELDS} == {
        key: value for key, value in original.items() if key not in cleanup.FIELDS}
    assert cleanup.apply_prepared(session, conn, plan, plan, 'fixture01').id == event.id
    assert len(list(session.scalars(select(Event)))) == 1


def test_even_a_verified_rejection_does_not_change_or_record_an_application(database):
    session, conn = database
    row, plan, data = prepare(session, conn, 'Req ID: SE-101. Your application was rejected.')
    assert plan['patch']['classification'] == 'rejection'
    assert plan['patch']['selected_application_key'] == 'job:2'
    assert plan['patch']['decision'] == 'review' and 'preserves application statuses' in plan['patch']['decision_reason']
    cleanup.apply_prepared(session, conn, plan, cleanup.projection(session, conn, row, data), 'fixture02')
    session.commit()
    assert statuses(session) == ['applied'] * 3 and not job_events(session)


@pytest.mark.parametrize('decision,reason', [
    ('manual', 'You recorded an outcome'), ('automatic', 'Clear rejection'),
    ('deferred', 'You chose to decide later'), ('review', 'You undid ACE\'s change for this email'),
    ('update', 'You marked it a status update with no decision yet'),
])
def test_owner_decisions_undo_recordings_and_deferred_mail_are_protected(database, decision, reason):
    session, conn = database
    row, plan, data = prepare(session, conn)
    row.decision, row.decision_reason = decision, reason
    session.commit()
    assert not cleanup.eligible(session, row)
    with pytest.raises(ValueError):
        cleanup.apply_prepared(session, conn, plan, plan, 'fixture03')
    session.rollback()
    assert statuses(session) == ['applied'] * 3 and not job_events(session)


def test_any_owner_event_blocks_cleanup_even_when_the_saved_reason_is_old(database):
    session, conn = database
    row, plan, data = prepare(session, conn)
    inbox._append_event(session, f'email:{row.id}', 'email_review', 'review', 'review', actor='owner', reason='Owner decision', message_id=row.id)
    session.commit()
    assert not cleanup.eligible(session, row)
    with pytest.raises(ValueError):
        cleanup.apply_prepared(session, conn, plan, plan, 'fixture04')


def test_changed_source_evidence_or_reconciliation_cannot_apply_an_old_plan(database):
    session, conn = database
    row, plan, data = prepare(session, conn)
    changed = deepcopy(plan)
    changed['patch']['selected_application_key'] = 'job:1'
    with pytest.raises(ValueError):
        cleanup.apply_prepared(session, conn, plan, changed, 'fixture05')
    session.rollback()
    row.subject = 'Owner changed evidence'
    session.commit()
    with pytest.raises(ValueError):
        cleanup.apply_prepared(session, conn, plan, plan, 'fixture05')


def test_row_rollback_preserves_old_events_and_application_statuses(database):
    session, conn = database
    row, plan, data = prepare(session, conn)
    original = {name: getattr(row, name) for name in cleanup.FIELDS}
    event = cleanup.apply_prepared(session, conn, plan, plan, 'fixture06')
    session.commit()
    correction = cleanup.revert_prepared(session, conn, plan, 'fixture06')
    session.commit()
    assert {name: getattr(row, name) for name in cleanup.FIELDS} == original
    assert correction.undo_of_id == event.id and session.get(Event, event.id)
    assert statuses(session) == ['applied'] * 3 and not job_events(session)


def test_row_rollback_refuses_later_owner_work(database):
    session, conn = database
    row, plan, data = prepare(session, conn)
    cleanup.apply_prepared(session, conn, plan, plan, 'fixture07')
    session.commit()
    inbox._append_event(session, f'email:{row.id}', 'email_review', 'ignored', 'ignored', actor='owner', reason='Owner decision', message_id=row.id)
    session.commit()
    with pytest.raises(ValueError):
        cleanup.revert_prepared(session, conn, plan, 'fixture07')

