"""Contextual intent and reconciliation contracts, all fictional mail."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import base64

import pytest
from sqlalchemy import select
from backend.app.inbox.reconcile import EmailEvidence, ApplicationIdentity, read_intent, reconcile, MAX_CLASSIFIER_BODY
from backend.app.api.routers import inbox
from backend.app.db.models import GmailMessageRecord
from backend.tests.test_inbox_persistence import database, gmail_reads, message, stored, row_for, statuses, job_events, owner_request, verified_scope

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
APP = ApplicationIdentity('job:1', 'Silverpine Labs', 'Software Engineer', 'SE-102', NOW-timedelta(days=8), 'applied', 'https://careers.silverpine.example/jobs')

def evidence(body, subject='Your Silverpine Labs application'):
    return EmailEvidence('Silverpine Labs <talent@careers.silverpine.example>', subject, body, NOW, True)

@pytest.mark.parametrize('body,kind', [
    ('We have decided to move forward with other candidates.', 'rejection'),
    ('Your application was not selected.', 'rejection'),
    ('We will not be proceeding with your candidacy.', 'rejection'),
    ('We have chosen to pursue other applicants.', 'rejection'),
    ('We are unable to advance your application.', 'rejection'),
    ('After careful consideration, we have decided not to move forward.', 'rejection'),
    ('We will not be considering you further for this position.', 'rejection'),
    ('Unfortunately, we cannot proceed with your application.', 'rejection'),
    ('We have selected other candidates for this position.', 'rejection'),
    ('Your application is not eligible for this role.', 'rejection'),
    ('We cannot proceed with your application because we are unable to sponsor this role.', 'rejection'),
    ('We have received your application.', 'application_confirmation'),
    ('Your application has been submitted successfully.', 'application_confirmation'),
    ('Your application is under consideration.', 'application_confirmation'),
    ('We are reviewing your qualifications.', 'application_confirmation'),
    ('Your application has been selected for further review.', 'application_confirmation'),
    ('Thank you for applying. We regret the delay; other candidates are still being reviewed.', 'application_confirmation'),
    ('Please complete the coding challenge for this role.', 'online_assessment'),
    ('You have been selected for an assessment for this application.', 'online_assessment'),
    ('Your online assessment deadline is tomorrow.', 'online_assessment'),
    ('Reminder: please complete your technical assessment.', 'online_assessment'),
    ('We received your completed coding test.', 'assessment_completed'),
    ('Your online assessment has been cancelled.', 'assessment_cancelled'),
    ('We invite you to a technical interview.', 'interview'),
    ('Please schedule a recruiter screen.', 'interview'),
    ('Your phone interview is scheduled for Monday.', 'interview'),
    ('Your interview has been rescheduled for Thursday.', 'interview'),
    ('Your interview has been cancelled. We will contact you about another time.', 'interview_cancelled'),
    ('We would like to speak with you about your application.', 'recruiter_reply'),
    ('We are pleased to offer you the Software Engineer position.', 'offer'),
    ('Please review the attached employment offer letter.', 'offer'),
    ('Please upload your transcript for your application.', 'action_required'),
    ('Please provide additional information for your application.', 'action_required'),
    ('The job posting has been closed. Your application remains active.', 'status_update'),
    ('Our policy does not include visa sponsorship for this role.', 'status_update'),
    ('If we cannot proceed with your application, we will notify you.', 'unknown'),
    ('You have not been rejected. Your application is under review.', 'application_confirmation'),
    ('We may extend an offer of employment after the interview.', 'unknown'),
    ('Your offer letter will be prepared if you pass the next round.', 'status_update'),
    ('Please complete our practice coding challenge in the training course.', 'unknown'),
    ('Your CodeSignal account is ready. Verify your email.', 'unknown'),
    ('Here are new recommended jobs for you.', 'unknown'),
    ('Your loan application was received by our bank.', 'unknown'),
    ('Great profile. We look forward to the next stage of the application.', 'status_update'),
])
def test_contextual_intents(body, kind):
    reading = read_intent(evidence(body))
    assert reading.classification == kind
    assert reading.explanation
    if kind not in {'unknown'}:
        assert reading.excerpt and reading.excerpt in ' '.join(body.split())

@pytest.mark.parametrize('body', [
    'If you are not eligible for this position, please withdraw your application.',
    'We will not proceed with your application unless you submit the requested documents.',
    'For example, some messages say "we have selected other candidates". This is a process guide.',
    'Your application has not been rejected.',
    'Your application was not selected yet; it remains under review.',
    'We have selected other candidates to interview. Your application remains under review.',
    'We are not pleased to offer you the position. We are still discussing the application.',
    'If selected, your offer letter will be available.',
])
def test_process_negation_and_conditions_do_not_automate(body):
    assert reconcile(evidence(body), [APP]).disposition != 'verified'

@pytest.mark.parametrize('delimiter', ['On Monday our recruiter wrote:', '----- Original Message -----', '----- Forwarded message -----', '>'])
def test_quoted_outcome_is_not_current_intent(delimiter):
    result = read_intent(evidence('Your application is under review.\n'+delimiter+'\nYour application was rejected.'))
    assert result.classification == 'application_confirmation'

@pytest.mark.parametrize('quote', ['<blockquote>', '<div class="gmail_quote">'])
def test_html_quotes_cannot_supply_a_current_outcome(quote):
    close = '</blockquote>' if 'blockquote' in quote else '</div>'
    data=message('quote', '')
    data['payload'].update(mimeType='text/html',body={'data':base64.urlsafe_b64encode(('<p>We received your application.</p>'+quote+'<p>Your application was rejected.</p>'+close).encode()).decode()})
    assert read_intent(inbox._message_evidence(data)).classification=='application_confirmation'


def test_contradictory_outcomes_require_a_specific_review():
    result=read_intent(evidence('Your application was rejected. We are pleased to offer you the position.'))
    assert result.classification=='possible_rejection' and result.variant=='conflicting_outcomes'
    assert reconcile(evidence('Your application was rejected. We are pleased to offer you the position.'),[APP]).target is None


def test_classification_survives_identity_ambiguity_and_policy_restrictions():
    mail=evidence('Req ID: SE-102. We invite you to interview.')
    positive=reconcile(mail,[APP])
    assert positive.classification=='interview' and positive.matched_target=='job:1'
    ambiguous=reconcile(mail,[APP,replace(APP,key='job:2')])
    assert ambiguous.classification=='interview' and ambiguous.target is None and ambiguous.matched_target is None
    wrong=reconcile(evidence('Req ID: AA-123. Your application was rejected.'),[APP,replace(APP,key='job:2',company='Other Employer',requisition_id='AA-123')])
    assert wrong.target is None and 'different applications' in wrong.reason


def test_long_content_limit_is_shared_and_incomplete_outcomes_remain_reviewable():
    body='Thank you for applying.\n'+'Details. '*4000+'\nYour application was rejected.'
    assert len(body)>10000
    result=read_intent(evidence(body))
    assert result.classification=='rejection'
    partial=replace(evidence(body+'x'*MAX_CLASSIFIER_BODY),complete=False)
    assert reconcile(partial,[APP]).disposition=='review'


def test_passive_completion_never_creates_a_screening_event(database):
    session,conn=database
    result=inbox._ingest(session,conn,message('complete','Req ID: SE-101. Your coding assessment has been completed.'),inbox._identities(session),preview=False)
    assert result=='update' and statuses(session)==['applied']*3 and not job_events(session)
    row=row_for(session,'complete')
    assert row.classification=='assessment_completed' and 'completed' in row.snippet
    assert inbox._item(row)['understanding']['update_policy']=='no_status_change'


def test_unknown_automatic_correspondence_is_rechecked_but_owner_updates_are_protected(database,gmail_reads,monkeypatch):
    session,conn=database
    auto=stored(session,conn,'unknown-update','update','Your application',version='8',reason='Saved application correspondence; no confirmed outcome to record')
    owner=stored(session,conn,'owner-update','update','Your application',version='8',reason='You marked it an application update')
    verified_scope(session,conn)
    monkeypatch.setattr(inbox.gmail,'get_json',lambda path,*a,**k:message(path.rsplit('/',1)[-1],'Req ID: SE-101. Your application was rejected.'))
    inbox.recheck(inbox.RecheckRequest(),owner_request(),session)
    session.refresh(auto);session.refresh(owner)
    assert auto.decision=='automatic' and owner.decision=='update' and owner.parser_version=='8'


def test_reference_evaluator_reports_denominators_errors_and_no_private_text():
    import json
    from backend.app.inbox.evaluation import evaluate
    result=evaluate([
        {'expected_classification':'rejection','classification':'rejection','expected_target':'job:1','target':'job:1','would_change_status':True,'excerpt':'Private fixture text'},
        {'expected_classification':'application_confirmation','classification':'rejection','expected_target':None,'target':'job:2','would_change_status':True},
        {'classification':'unknown'},
    ])
    assert result['labelled']==2 and result['unlabelled']==1
    assert result['false_automatic_rejections']==1 and result['wrong_application_updates']==1
    assert result['release_blocking_errors']==2
    assert result['per_category']['rejection']['precision']==.5
    assert result['per_category']['application_confirmation']['precision'] is None
    assert 'Private fixture' not in json.dumps(result)


def test_dry_run_is_a_proposal_without_status_or_ledger_mutations(database):
    from backend.scripts.inbox_classification_audit import preview,summary
    session,conn=database
    inbox._ingest(session,conn,message('dry-run-source','Req ID: SE-101. Thank you for applying.'),inbox._identities(session),preview=True)
    row=row_for(session,'dry-run-source')
    before=(row.classification,row.decision,statuses(session),len(job_events(session)))
    ev=inbox._message_evidence(message('dry-run-source','Req ID: SE-101. Your application was rejected.'))
    proposal=preview(row,ev,inbox._identities(session),protected=False)
    assert proposal['classification']=='rejection' and proposal['would_change_status']
    assert (row.classification,row.decision,statuses(session),len(job_events(session)))==before
    assert not preview(row,ev,inbox._identities(session),protected=True)['would_change_status']
    output=summary([proposal])
    assert 'excerpt' not in str(output) and 'SE-101' not in str(output)



def test_completed_assessment_cannot_hide_a_new_interview_invitation():
    mail=evidence('Your coding assessment is completed. We invite you to a technical interview.')
    assert read_intent(mail).classification=='interview'


def test_future_completion_instructions_are_not_a_completion_receipt():
    process = 'Upon completion of the assessment, our team will review your results.'
    assert read_intent(evidence(process)).classification != 'assessment_completed'
    invitation = 'Please complete your technical assessment. ' + process
    assert read_intent(evidence(invitation)).classification == 'online_assessment'


def test_conflicting_interview_and_rejection_cannot_automatically_end_candidacy():
    mail=evidence('Your application was rejected. We invite you to a technical interview.')
    assert read_intent(mail).classification=='possible_rejection'
    assert reconcile(mail,[APP]).target is None


def test_inability_to_hold_a_scheduled_interview_is_not_application_rejection():
    mail=evidence('We are unable to proceed with the interview at the scheduled time due to technical difficulties.')
    assert reconcile(mail,[APP]).target is None



def test_self_closing_html_elements_do_not_expose_a_quoted_rejection():
    data=message('quote-void','')
    markup='<div class><p>We received your application.</p><blockquote><br/><p>Your application was rejected.</p></blockquote></div>'
    data['payload'].update(mimeType='text/html',body={'data':base64.urlsafe_b64encode(markup.encode()).decode()})
    assert read_intent(inbox._message_evidence(data)).classification=='application_confirmation'



@pytest.mark.parametrize('body,kind',[
    ('We cannot proceed\nwith your application.','rejection'),
    ('We invite you to\na technical interview.','interview'),
    ('Your online assessment\nhas been completed.','assessment_completed'),
    ('If you do not qualify,\nwe cannot proceed with your application.','unknown'),
])
def test_soft_wrapped_sentences_keep_their_meaning(body,kind):
    assert read_intent(evidence(body)).classification==kind



def test_an_old_recognized_outcome_cannot_silently_become_unknown_correspondence():
    from backend.app.inbox.reconcile import reassess
    mail=evidence('A new chapter awaits. Please visit our portal for details.')
    assert reconcile(mail,[APP]).disposition=='update'
    for previous in ('rejection','interview','offer','online_assessment'):
        result=reassess(mail,[APP],previous)
        assert result.disposition=='review' and result.target is None
        assert "earlier reading found" in result.reason


def test_clear_practice_account_and_alert_messages_can_resolve_old_false_outcomes():
    from backend.app.inbox.reconcile import reassess
    for subject,body in [('Your CodeSignal report','Your practice score is ready.'),
                         ('Verify your account','Please verify your email to use your account.'),
                         ('Your job recommendations','New jobs for you are available.')]:
        result=reassess(evidence(body,subject),[APP],'online_assessment')
        assert result.disposition=='ignored' and result.target is None


def test_a_routine_subject_needs_substantive_routine_body_evidence():
    from backend.app.inbox.reconcile import reassess
    result=reassess(evidence('A new chapter awaits. Please visit our candidate portal for details.','Verify your account'),[APP],'offer')
    assert result.disposition=='review' and 'earlier reading found' in result.reason



def test_unresolved_previous_outcome_survives_another_parser_revision():
    from backend.app.inbox.reconcile import reassess
    mail=evidence('A new chapter awaits. Please visit our portal for details.')
    first=reassess(mail,[APP],'offer')
    again=reassess(mail,[APP],first.classification,previous_reason=first.reason)
    assert again.disposition=='review' and again.reason==first.reason
    routine=reassess(evidence('Your practice score is ready.','Your CodeSignal report'),[APP],first.classification,previous_reason=first.reason)
    assert routine.disposition=='ignored'



def test_workflow_filters_and_item_states_agree_without_hiding_any_evidence(database):
    from backend.app.inbox.queue import workflow_state,workflow_expression
    from sqlalchemy.dialects import postgresql
    session,conn=database
    cases=[('review','rejection','No application could be matched with confidence','awaiting_link'),
           ('review','rejection','Sender could not be authenticated','owner_review'),
           ('review','unclear','An earlier reading found offer; confirm the actual decision','owner_review'),
           ('review','online_assessment','Only part of this email could be read','owner_review'),
           ('update','assessment_completed','The assessment was completed','filed'),
           ('receipt','application_confirmation','Application receipt; no status change','filed'),
           ('automatic','rejection','Clear rejection matched by its job ID','recorded'),
           ('deferred','interview','You deferred this email','deferred'),
           ('ignored','unknown','Routine account notification or job alert','routine')]
    expected={}
    for index,(decision,kind,reason,state) in enumerate(cases):
        row=stored(session,conn,f'workflow-{index}',decision,'Application message',reason=reason)
        row.classification=kind
        expected[row.id]=state
    session.commit()
    sql=dict(session.execute(select(GmailMessageRecord.id,workflow_expression())).all())
    assert sql==expected=={row.id:workflow_state(row) for row in session.scalars(select(GmailMessageRecord))}
    assert 'CASE WHEN' in str(workflow_expression().compile(dialect=postgresql.dialect()))
    for state in ('awaiting_link','owner_review','filed','routine'):
        data=inbox.messages(owner_request(),session,state,0,100)
        assert data['total']==sum(value==state for value in expected.values())
        assert all(item['understanding']['workflow_state']==state for item in data['items'])
    assert inbox.messages(owner_request(),session,None,0,100)['total']==len(cases)
    assert inbox.messages(owner_request(),session,'pending',0,100)['review_count']==5



@pytest.mark.parametrize('sender',[
    'Silverpine Health <careers@silverpinehealth.example>',
    'Silverpine Health <no-reply@us.greenhouse-mail.io>',
    'Silverpine <silverpinehealth@myworkday.com>',
])
def test_a_subsidiary_cannot_update_the_only_parent_application(sender):
    parent=replace(APP,company='Silverpine',official_url='https://careers.silverpine.example/jobs')
    mail=replace(evidence('Your application was rejected.','Your Silverpine Health application'),sender=sender)
    result=reconcile(mail,[parent])
    assert result.classification=='rejection' and result.disposition=='review' and result.target is None
    assert 'employer identity' in result.reason and result.matched_target is None


def test_authenticated_third_party_recruiter_does_not_establish_employer_origin():
    mail=replace(evidence('Req ID: SE-102. Your application was rejected.'),sender='Silverpine Labs <recruiter@independent-agency.example>')
    assert reconcile(mail,[APP]).target is None



@pytest.mark.parametrize('host',['jobs.smartrecruiters.com','tenant.oraclecloud.com','apply.workable.com'])
def test_shared_ats_host_is_never_employer_origin_for_positive_automation(host):
    app=replace(APP,official_url=f'https://{host}/employer/SE-102')
    mail=replace(evidence('Req ID: SE-102. We invite you to interview.'),sender=f'Silverpine Labs <no-reply@{host}>')
    result=reconcile(mail,[app])
    assert result.classification=='interview' and result.disposition=='review' and result.target is None


def test_shared_ats_host_and_parent_name_cannot_establish_a_subsidiary_application():
    parent=replace(APP,company='Silverpine',official_url='https://jobs.smartrecruiters.com/silverpine/SE-102')
    mail=replace(evidence('Your application was rejected.','Your Silverpine Health application'),sender='Silverpine Health <no-reply@jobs.smartrecruiters.com>')
    assert reconcile(mail,[parent]).target is None



def test_a_subsidiary_display_cannot_inherit_the_parents_shared_corporate_host():
    parent=replace(APP,company='Silverpine',official_url='https://careers.silverpine.example/jobs')
    mail=replace(evidence('Your application was rejected.','Your Silverpine Health application'),sender='Silverpine Health <talent@careers.silverpine.example>')
    assert reconcile(mail,[parent]).target is None


def test_a_domain_first_word_does_not_establish_a_different_longer_employer():
    parent=replace(APP,company='Silverpine Finance',official_url=None)
    mail=replace(evidence('Your application was rejected.','Your application'),sender='Silverpine Health <talent@silverpine.example>')
    assert reconcile(mail,[parent]).target is None



def test_wrong_outcome_recording_blocks_release_even_without_a_stage_change():
    from backend.app.inbox.evaluation import evaluate
    result=evaluate([{'expected_classification':'application_confirmation','classification':'rejection',
                      'expected_target':'job:1','target':'job:2','would_change_status':False,'would_record_outcome':True}])
    assert result['false_automatic_rejections']==1 and result['wrong_application_updates']==1
    assert result['release_blocking_errors']==2
