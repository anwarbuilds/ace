"""Fictional posting, chronology and primary-content identity regressions."""
import base64
from dataclasses import replace
from datetime import timedelta

import pytest

from backend.app.api.routers import inbox
from backend.app.inbox.postings import contextual_links, posting_identity
from backend.app.inbox.reconcile import reconcile
from backend.app.inbox.company_outcomes import COMPANY_REASON, KIND, event_company
from backend.tests.test_inbox_backlog import APP, evidence
from backend.tests.test_inbox_persistence import message
from backend.tests.test_inbox_persistence import database, row_for

FIRST = 'https://jobs.lever.co/silverpine/aa111111-1111-1111-1111-111111111111'
SECOND = 'https://jobs.lever.co/silverpine/bb222222-2222-2222-2222-222222222222'


@pytest.mark.parametrize('url,key', [
    (FIRST + '/apply?utm_source=mail', ('lever','silverpine','aa111111-1111-1111-1111-111111111111')),
    ('https://job-boards.greenhouse.io/silverpine/jobs/987654321?gh_src=anything', ('greenhouse','silverpine','987654321')),
    ('https://boards.greenhouse.io/embed/job_app?for=silverpine&token=987654321', ('greenhouse','silverpine','987654321')),
    ('https://silverpine.wd5.myworkdayjobs.com/en-US/External/job/City/Software-Engineer_JR-123456/apply', ('workday','silverpine','jr123456')),
    ('https://wd5.myworkdaysite.com/recruiting/silverpine/External/job/City/Software-Engineer_JR-123456', ('workday','silverpine','jr123456')),
    ('https://jobs.smartrecruiters.com/Silverpine/744000123456789-engineer', ('smartrecruiters','silverpine','744000123456789')),
    ('https://jobs.ashbyhq.com/silverpine/aa111111-1111-1111-1111-111111111111', ('ashby','silverpine','aa111111-1111-1111-1111-111111111111')),
])
def test_posting_identity_is_scoped_and_ignores_tracking(url, key):
    assert posting_identity(url) == key


@pytest.mark.parametrize('url', [
    'https://evil.example/?gh_jid=987654321',
    'https://jobs.lever.co.evil.example/silverpine/aa111111-1111-1111-1111-111111111111',
    FIRST.replace('https://','https://user:password@'),
    FIRST.replace('lever.co/','lever.co:444/'),
    FIRST + '/candidate/session',
    'javascript:alert(987654321)',
    'https://boards.greenhouse.io/embed/job_app?for=silverpine&token=987654321&token=123456789',
    'https://silverpine.wd5.myworkdayjobs.com/candidate/home?jobId=987654321',
])
def test_tokens_redirects_and_lookalike_hosts_are_not_posting_identity(url):
    assert posting_identity(url) is None


def test_posting_link_disambiguates_same_title_without_using_recency():
    apps = [replace(APP, official_url=FIRST, requisition_id=None),
            replace(APP, key='job:2', official_url=SECOND, requisition_id=None)]
    ev = evidence('Your application was rejected. View your job details: ' + FIRST)
    result = reconcile(ev, apps)
    assert result.target == APP.key and result.reason.endswith('its posting link')
    assert reconcile(replace(ev, body='Your application was rejected. Other jobs recommended for you: '+FIRST), apps).target is None


def test_link_cannot_override_conflicting_requisition_or_employer():
    apps = [replace(APP, official_url=FIRST, requisition_id='SE-987654')]
    ev = evidence('Your application was rejected. Job ID: SE-123456. View job details: '+FIRST)
    assert reconcile(ev, apps).target is None
    conflict = replace(APP, key='job:2', company='Copperfin', official_url=SECOND)
    ev = evidence('Your application was rejected. View job details: '+SECOND)
    assert reconcile(ev, apps+[conflict]).target is None


def test_link_cannot_override_explicit_role_or_distant_recommendation_section():
    apps = [replace(APP, official_url=FIRST, requisition_id=None),
            replace(APP,key='job:2',title='Data Scientist',official_url=SECOND,requisition_id=None)]
    ev=evidence('Your application was rejected for the Data Scientist role. View job details: '+FIRST)
    assert reconcile(ev,apps).target is None
    ev=replace(ev,body='Your application was rejected. Other jobs recommended for you: '+('Explore our teams. '*40)+'View job details: '+FIRST)
    assert reconcile(ev,apps).target is None
    markup=f'<p>{ev.body[:ev.body.index("View job")]}</p><a href="{FIRST}">View job details</a>'
    assert not inbox._message_evidence(html_message(markup)).posting_links


def test_unmatched_explicit_link_does_not_fall_back_to_a_different_requisition_or_title():
    app=replace(APP,official_url=FIRST,requisition_id='SE-123456')
    for prefix in ['Your application was rejected for the Software Engineer role.', 'Job ID: SE-123456. Your application was rejected.']:
        assert reconcile(evidence(prefix+' View job details: '+SECOND),[app]).target is None


def test_workdaysite_tenant_prevents_same_requisition_across_employers_colliding():
    url='https://wd5.myworkdaysite.com/recruiting/silverpine/External/job/City/Engineer_R123456'
    assert posting_identity(url)!=posting_identity(url.replace('/silverpine/','/copperfin/'))


@pytest.mark.parametrize('role',['Data Engineer','Senior Software Engineer','Software Engineer Storage'])
def test_unrecorded_explicit_role_cannot_be_overridden_by_posting_or_requisition(role):
    app=replace(APP,official_url=FIRST,requisition_id='SE-123456')
    for ending in ['View job details: '+FIRST, 'Job ID: SE-123456.']:
        ev=evidence(f'Your application was rejected for the {role} role. '+ending)
        assert reconcile(ev,[app]).target is None


@pytest.mark.parametrize('subject,body', [
    ('Senior Software Engineer application update at Silverpine Labs','Your application was rejected.'),
    ('Software Engineer Storage | Silverpine Labs','Your application was rejected.'),
    ('Application update','Regarding Senior Software Engineer: your application was rejected.'),
    ('Application update','Role: Data Engineer. Your application was rejected.'),
])
def test_plain_subject_and_colon_role_claims_preserve_unknown_modifiers(subject,body):
    app=replace(APP,official_url=FIRST,requisition_id=None)
    ev=evidence(body+' View job details: '+FIRST,subject)
    assert reconcile(ev,[app]).target is None


def test_generic_subject_does_not_contradict_an_explicit_specific_posting():
    app=replace(APP,title='Software Engineer Storage',official_url=FIRST,requisition_id=None)
    ev=evidence('Your application was rejected. View job details: '+FIRST,'Software Engineer application update at Silverpine Labs')
    assert reconcile(ev,[app]).target==app.key


@pytest.mark.parametrize('footer', ['Data Scientist (SE-10202)', 'Job ID: SE-10202.', 'https://careers.silverpine.example/job/SE-10202'])
def test_recommended_job_ids_cannot_supply_identity(footer):
    from backend.app.inbox.reconcile import read_intent
    apps=[replace(APP,requisition_id='SE-10101'),replace(APP,key='job:2',title='Data Scientist',requisition_id='SE-10202')]
    ev=evidence('Your application was rejected. Other jobs recommended for you: '+footer)
    assert read_intent(ev).requisition_id is None
    assert reconcile(ev,apps).target is None


def test_multiple_postings_and_duplicate_records_stay_ambiguous():
    apps = [replace(APP, official_url=FIRST, requisition_id=None), replace(APP, key='job:2', official_url=SECOND, requisition_id=None)]
    ev = evidence('Your application was rejected. View job details: '+FIRST+' or '+SECOND)
    assert reconcile(ev, apps).target is None
    dup = replace(apps[0], key='external:3')
    ev = replace(ev, body='Your application was rejected. View job details: '+FIRST)
    assert reconcile(ev, apps+[dup]).target is None


def test_chronology_eliminates_future_roles_but_never_picks_nearest_past_role():
    past = replace(APP, requisition_id=None)
    future = replace(past, key='job:2', submitted_at=evidence('').received_at+timedelta(days=20))
    ev = evidence('Your application was rejected for the Software Engineer role.')
    assert reconcile(ev, [past, future]).target == past.key
    another_past = replace(past, key='job:3', submitted_at=past.submitted_at-timedelta(days=20))
    assert reconcile(ev, [past, another_past, future]).target is None
    assert reconcile(ev, [future]).target is None


def test_explicit_future_identity_is_a_conflict_not_permission_to_choose_another():
    future = replace(APP, key='job:2', requisition_id='SE-123456', submitted_at=evidence('').received_at+timedelta(days=20))
    ev = evidence('Job ID: SE-123456. Your application was rejected.')
    result = reconcile(ev, [APP, future])
    assert result.target is result.matched_target is None
    assert result.disposition == KIND and result.company == APP.company and result.reason == COMPANY_REASON


def test_future_specific_title_is_not_reinterpreted_as_a_past_generic_role():
    past=replace(APP,requisition_id=None)
    future=replace(past,key='job:2',title='Software Engineer Storage',submitted_at=evidence('').received_at+timedelta(days=20))
    ev=evidence('Your application was rejected for the Software Engineer Storage role.')
    result=reconcile(ev,[past,future])
    assert result.target is result.matched_target is None and result.disposition==KIND
    assert result.company==APP.company and result.reason==COMPANY_REASON


def test_marking_grace_and_unknown_date_remain_eligible():
    ev = evidence('Your application was rejected.')
    for at in [ev.received_at+timedelta(hours=23), None]:
        assert reconcile(ev, [replace(APP, submitted_at=at)]).target == APP.key


def html_message(body):
    data = message('posting-link', '')
    data['payload'].update(mimeType='text/html', body={'data':base64.urlsafe_b64encode(body.encode()).decode()})
    return data


def test_html_application_anchor_is_ephemeral_and_quotes_are_excluded():
    ev = inbox._message_evidence(html_message(f'<p>Your application was rejected.</p><a href="{FIRST}">View job details</a><blockquote><p>Your application</p><a href="{SECOND}">View position details</a></blockquote>'))
    assert ev.posting_links == (FIRST,) and SECOND not in ev.body
    assert FIRST not in ev.body


def test_mislabelled_html_preserves_primary_posting_evidence():
    data=message('mislabelled-link',f'<html><body><p>Your application was rejected.</p><a href="{FIRST}">View job details</a></body></html>')
    ev=inbox._message_evidence(data)
    assert ev.posting_links==(FIRST,) and '<html' not in ev.body


def test_unlabelled_recommendation_and_hidden_or_quoted_links_are_excluded():
    ev = inbox._message_evidence(html_message(f'<p>Your application was rejected.</p><p>Other jobs recommended for you:</p><a href="{FIRST}">Software Engineer</a><script><a href="{SECOND}">View job details</a></script>'))
    assert not ev.posting_links
    assert not contextual_links('Your application was rejected. Unsubscribe\n'+FIRST)


def test_machine_matching_reason_is_not_attributed_to_owner():
    from types import SimpleNamespace
    row = SimpleNamespace(decision='review', classification='rejection', selected_application_key=None, candidate_keys=['job:1','job:2'], decision_reason='You applied to several roles there and the email does not say which', snippet='')
    assert inbox.understanding(row)['decision_type'] == 'Automatic classification'


def test_authenticated_rejection_without_a_historical_application_is_company_evidence():
    ev = evidence('Your application was rejected for the Software Engineer role.')
    future = replace(APP, submitted_at=ev.received_at+timedelta(days=20))
    result = reconcile(ev, [future])
    assert result.classification == 'rejection' and result.disposition == KIND
    assert result.target is result.matched_target is None and result.candidates == (future.key,)
    assert result.company == APP.company
    # Company evidence requires actual meaning and employer identity. Missing
    # chronology does not prevent a separately safe exact application match.
    assert reconcile(replace(ev,sender_authenticated=False), [future]).disposition == 'review'
    assert reconcile(replace(ev,sender='Other Subsidiary <notice@greenhouse-mail.io>'), [future]).disposition == 'review'
    assert reconcile(ev, [replace(future,submitted_at=None)]).disposition == 'verified'
    assert reconcile(replace(ev,complete=False), [future]).disposition == 'review'


def test_historical_assessment_invitation_and_ambiguous_wording_are_not_silently_filed():
    future = replace(APP, submitted_at=evidence('').received_at+timedelta(days=20))
    for body in ['Please complete your online assessment.', 'We regret the delay. Other candidates are still under review.']:
        assert reconcile(evidence(body), [future]).disposition != 'unlinked'


def test_historical_company_ingestion_uses_a_rollback_compatible_persisted_decision(database):
    from backend.app.inbox.queue import projected_decision
    from backend.app.inbox.historical_cleanup import projection
    from backend.tests.test_inbox_persistence import NOW, statuses, job_events
    session,conn=database
    data=message('old-unlinked','Your application was rejected.',NOW-timedelta(days=100))
    assert inbox._ingest(session,conn,data,inbox._identities(session),preview=True)==KIND
    session.flush()
    row=row_for(session,'old-unlinked')
    assert row.decision=='update' and projected_decision(row)==KIND
    assert row.decision_reason==COMPANY_REASON
    assert inbox._message_rows(session,conn.id,KIND)==[row]
    assert inbox._message_rows(session,conn.id,'pending')==[]
    assert projection(session,conn,row,data)['patch']['decision']=='update'
    assert row.selected_application_key is None and statuses(session)==['applied']*3 and not job_events(session)
    from backend.tests.test_inbox_persistence import company_events
    assert [event_company(event) for event in company_events(session)]==['Silverpine Labs']


def test_unlinked_evidence_sql_python_and_analytics_agree_without_outcome_inflation():
    from sqlalchemy import select
    from backend.app.inbox.queue import workflow_expression, workflow_state
    from backend.app.db.models import GmailMessageRecord, GmailConnectionRecord
    from backend.app.api.routers.analytics import analytics_read
    from backend.tests.test_analytics_read import app, NOW
    # Use a fresh fixture-style DB here so no Gmail or owner account is needed.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.app.db.base import Base
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        app(session,1)
        conn=GmailConnectionRecord(owner_id=1,email='fictional@example.test',encrypted_refresh_token=b'',scope='gmail.readonly',state='disconnected')
        session.add(conn);session.flush()
        row=GmailMessageRecord(connection_id=conn.id,gmail_id='unlinked-fictional',received_at=NOW-timedelta(days=300),sender='Talent <talent@silverpine.example>',subject='Application decision',snippet='Your application was rejected.',classification='rejection',decision='unlinked',candidate_keys=[],decision_reason='Recognized historical rejection without an application',parser_version='11')
        session.add(row);session.flush()
        assert workflow_state(row)==session.scalar(select(workflow_expression()).where(GmailMessageRecord.id==row.id))=='unlinked_outcome'
        assert inbox._message_rows(session,conn.id,'unlinked_outcome')==[row]
        assert inbox._message_rows(session,conn.id,'pending')==[]
        assert inbox._message_rows(session,conn.id,None)==[row]
        result=analytics_read(session,now=NOW,days='all',tz='America/Los_Angeles')
        assert result['review']['unlinked']==1 and result['inbox_audit']['pending_messages']==0
        assert result['evidence']['rejected']==result['positive']==0
        assert result['cohort']['rejected']==0 and result['total_submitted']==1
