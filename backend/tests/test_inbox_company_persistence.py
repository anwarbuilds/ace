"""Company-scoped evidence never mutates an arbitrary role; corrections stay auditable."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.api.routers import inbox
from backend.app.config import get_settings
from backend.app.db.models import ApplicationEventRecord as Event
from backend.app.inbox.company_outcomes import COMPANY_REASON, KIND, event_company
from backend.app.inbox import historical_cleanup as cleanup
from backend.app.inbox.queue import projected_decision, projected_reason
from backend.app.inbox.reconcile import Decision, EmailEvidence
from backend.tests.test_inbox_persistence import database, stored, message, statuses, job_events, owner_request, NOW


def record(session, conn, suffix='company-fixture', **changes):
    row = stored(session, conn, suffix, 'review', 'Application decision', version='11', reason='Several applications fit')
    row.classification = 'rejection'
    decision = SimpleNamespace(disposition=KIND, company='Silverpine Labs', reason=COMPANY_REASON)
    evidence = EmailEvidence('talent@careers.silverpine.example', 'Application update',
                             'Your application was rejected.', NOW, sender_authenticated=True)
    for name, value in changes.items():
        evidence = __import__('dataclasses').replace(evidence, **{name: value})
    inbox._apply(session, conn, row, decision, evidence, preview=True)
    session.commit()
    return row, decision, evidence


def test_company_record_is_searchable_with_no_application_status_or_target(database):
    session, conn = database
    row, decision, evidence = record(session, conn)
    assert statuses(session) == ['applied'] * 3 and not job_events(session)
    assert row.decision == 'update' and row.selected_application_key is None
    assert projected_decision(row) == KIND and projected_reason(row) == COMPANY_REASON
    events = list(session.scalars(select(Event)))
    from backend.scripts.inbox_analytics_audit import audit
    assert audit(session)["company_evidence"] == {"inbox_messages":1,"analytics_messages":1,"agrees":True}
    assert len(events) == 1 and event_company(events[0]) == 'Silverpine Labs'
    assert events[0].application_key == f'email:{row.id}'
    for view in (KIND, 'company_recorded', 'automatic'):
        response = inbox.messages(owner_request(), session, decision=view, offset=0, limit=50, q=None)
        assert response['total'] == 1 and response['counts']['automatic'] == 1
        assert response['counts']['company_rejections'] == 1 and response['counts']['needs_review'] == 0
        assert response['items'][0]['understanding']['matching_state'] == 'company'
    inbox._apply(session, conn, row, decision, evidence, preview=True)
    session.commit()
    assert len(list(session.scalars(select(Event)))) == 1


def test_company_undo_restores_only_email_and_prevents_replay(database):
    session, conn = database
    row, decision, evidence = record(session, conn)
    event = session.scalars(select(Event)).one()
    response = inbox.undo(event.id, owner_request(), session)
    assert response['scope'] == 'company' and response['status'] is None
    assert row.decision == 'review' and row.decision_reason.startswith('You undid')
    assert statuses(session) == ['applied'] * 3 and not job_events(session)
    assert not cleanup.eligible(session, row)
    with pytest.raises(HTTPException):
        inbox.undo(event.id, owner_request(), session)
    with pytest.raises(ValueError):
        inbox._apply(session, conn, row, decision, evidence, preview=True)
    session.rollback()
    assert len(list(session.scalars(select(Event)))) == 2


def test_owner_refiling_is_authoritative_and_blocks_company_undo(database):
    session, conn = database
    row, _, _ = record(session, conn)
    event = session.scalars(select(Event)).one()
    inbox.decide_message(row.id, inbox.EmailDisposition(action='update'), owner_request(), session)
    assert projected_decision(row) == 'update' and not cleanup.eligible(session, row)
    with pytest.raises(HTTPException):
        inbox.undo(event.id, owner_request(), session)
    assert statuses(session) == ['applied'] * 3


@pytest.mark.parametrize('changes', [{'complete':False}, {'sender_authenticated':False}])
def test_incomplete_or_unauthenticated_evidence_does_not_record(database, changes):
    session, conn = database
    row, _, _ = record(session, conn, **changes)
    assert row.decision == 'review' and not list(session.scalars(select(Event)))
    assert statuses(session) == ['applied'] * 3


def test_company_recording_obeys_existing_automatic_rejection_switch(database, monkeypatch):
    session, conn = database
    monkeypatch.setenv('GMAIL_AUTO_REJECTIONS', 'false');get_settings.cache_clear()
    row, _, _ = record(session, conn)
    assert row.decision == 'review' and not list(session.scalars(select(Event)))


@pytest.mark.parametrize('reason', ['[]', 'null', 'false', '"text"', '{', '{}'])
def test_company_metadata_is_validated_before_use(reason):
    event = SimpleNamespace(kind=KIND, actor='verified_automation', gmail_message_id=1, application_key='email:1', reason=reason)
    assert event_company(event) is None


def test_company_historical_apply_and_rollback_are_status_preserving_and_guarded(database):
    session, conn = database
    row = stored(session, conn, 'historical-company', 'review', 'Application update', version='11', reason='Several applications fit')
    row.classification='rejection';session.commit()
    data = message('historical-company', 'Thank you for applying to Silverpine Labs. We will not be moving forward with your application.')
    entry = cleanup.projection(session, conn, row, data)
    assert entry['would_record_company_outcome'] and entry['company']=='Silverpine Labs'
    assert not entry['would_change_status'] and not entry['would_record_outcome']
    before = cleanup.row_state(row)
    event = cleanup.apply_prepared(session, conn, entry, cleanup.projection(session, conn, row, data), 'companyscope01')
    session.commit()
    assert projected_decision(row)==KIND and statuses(session)==['applied']*3
    assert cleanup.apply_prepared(session, conn, entry, entry, 'companyscope01').id==event.id
    cleanup.revert_prepared(session, conn, entry, 'companyscope01');session.commit()
    assert cleanup.row_state(row)==before and not job_events(session)
    records=list(session.scalars(select(Event)));assert len(records)==4
    company_event=next(e for e in records if e.kind==KIND)
    assert any(e.undo_of_id==company_event.id for e in records)


def test_changed_company_plan_cannot_be_applied(database):
    session, conn = database
    row = stored(session, conn, 'changed-company', 'review', 'Application update', version='11', reason='Several applications fit')
    row.classification='rejection';session.commit()
    data = message('changed-company', 'We will not be moving forward with your application.')
    entry=cleanup.projection(session, conn, row, data);changed=deepcopy(entry);changed['company']='Different Company'
    with pytest.raises(ValueError):cleanup.apply_prepared(session, conn, entry, changed, 'companyscope02')
    assert statuses(session)==['applied']*3


def test_assessment_interview_filters_include_action_and_passive_variants(database):
    session, conn = database
    kinds=['online_assessment','assessment_completed','assessment_cancelled','interview','interview_cancelled','application_confirmation']
    for index, kind in enumerate(kinds):
        row=stored(session,conn,f'category-{index}','update','Fictional subject',version='12',reason='Saved correspondence')
        row.classification=kind
    session.commit()
    for view, expected in [('assessments',set(kinds[:3])),('interviews',set(kinds[3:5]))]:
        result=inbox.messages(owner_request(),session,decision=view,offset=0,limit=50,q=None)
        assert {r['classification'] for r in result['items']}==expected
        assert result['counts']['needs_review']==0
    assert statuses(session)==['applied']*3
