"""Independent owner feedback represented with fictional correspondence."""
from datetime import datetime, timezone
import base64

import pytest

from backend.app.inbox.reconcile import EmailEvidence, read_intent, reconcile
from backend.app.api.routers.inbox import _message_evidence


def mail(body, subject='Your application at Fictional Systems'):
    return EmailEvidence('Fictional Recruiting <hiring@fictional.example>', subject, body,
                         datetime(2026,10,29,tzinfo=timezone.utc), sender_authenticated=True)


@pytest.mark.parametrize('policy', [
    'Only an authorized representative has authority to extend an offer of employment.',
    'No employee has authority to extend an offer of employment without a signed agreement.',
    'The hiring team has discretion to extend an offer of employment.',
    'Should we extend an offer of employment, we will contact you.',
    'When we extend an offer of employment, it will be in writing.',
    'Once we extend an offer of employment, you must sign it.',
    'We will be pleased to offer you a role after our review.',
    'We may extend an offer of employment after the interview.',
    'If selected, we will extend you an offer for the position of Systems Engineer.',
])
def test_receipt_with_generic_employment_policy_is_an_acknowledgement(policy):
    ev=mail('Thank you for applying. We have received your application. '+policy)
    assert read_intent(ev).classification=='application_confirmation'
    decision=reconcile(ev,[])
    assert decision.disposition=='receipt' and decision.target is None


@pytest.mark.parametrize('body', [
    'We are pleased to offer you the Software Engineer position.',
    'We are excited to extend you an offer for the position of Systems Engineer.',
    'We hereby extend an offer of employment to you.',
    'We are extending you an offer of employment.',
    "We're extending an offer of employment to you.",
    'Please review the attached employment offer letter.',
    'Congratulations on your new job offer with Fictional Systems! We are preparing the letter.',
    'We are pleased to offer you the Software Engineer position, contingent upon a background check.',
])
def test_actual_offer_still_requires_an_explicit_current_commitment(body):
    assert read_intent(mail(body)).classification=='offer'


def test_legal_policy_does_not_suppress_a_separate_actual_offer():
    ev=mail('We are pleased to offer you the Software Engineer position. '
            'Only an authorized representative has authority to extend an offer of employment.')
    assert read_intent(ev).classification=='offer'


def long_message(tail=''):
    body='Thank you for applying. We have received your application.\n'+('Privacy information about application processing.\n'*2300)+tail
    return {'id':'fictional-long','internalDate':'1793232000000','payload':{
        'mimeType':'text/plain','headers':[{'name':'From','value':'Fictional Hiring <hiring@fictional.example>'},
            {'name':'Subject','value':'Your application at Fictional Systems'}],
        'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}


def test_long_acknowledgement_is_read_completely_and_filed_without_a_task():
    ev=_message_evidence(long_message())
    assert 110000<len(ev.body)<256000 and ev.complete
    decision=reconcile(ev,[])
    assert decision.classification=='application_confirmation' and decision.disposition=='receipt'
    assert decision.target is None


def test_reading_a_long_message_does_not_hide_a_later_actual_rejection():
    ev=_message_evidence(long_message('Your application was rejected.'))
    assert ev.complete and ev.body.index('Your application was rejected.')>60000
    assert read_intent(ev).classification=='rejection'
    decision=reconcile(ev,[])
    assert decision.classification=='rejection' and decision.disposition!='receipt'


@pytest.mark.parametrize('process', [
    'Should your qualifications match our needs, we will contact you to schedule an interview.',
    'We will contact you to schedule an interview should your profile match the role.',
    'Should you be selected, we will invite you for a technical interview.',
    'Should we select your application, please schedule your interview through the portal.',
    'Those candidates who are selected for an interview will be contacted by the recruiting team.',
    'Candidates who are selected for an interview will receive further details.',
    'Selected candidates will be invited to interview.',
    'An interview will be scheduled by the hiring team later in the process.',
])
def test_conditional_future_interview_process_does_not_become_an_invitation(process):
    ev=mail('Thank you for applying. We have received your application. '+process)
    assert read_intent(ev).classification=='application_confirmation'


def test_should_as_a_current_instruction_is_still_an_assessment_request():
    assert read_intent(mail('You should complete your online assessment by Friday.')).classification=='online_assessment'


def test_personal_selection_is_distinct_from_generic_selected_candidates():
    assert read_intent(mail('You have been selected for an interview. Please share your availability.')).classification=='interview'


def test_personal_video_interview_reminder_is_a_hiring_stage():
    ev=mail('This is a reminder that we have invited you to complete a brief video interview '
            'for our engineering role. Start your interview here: https://interview.fictional.example/start')
    assert read_intent(ev).classification=='interview'
    decision=reconcile(ev,[])
    assert decision.classification=='interview' and decision.disposition=='classified_action'
    assert decision.target is None and decision.matched_target is None and decision.company is None
