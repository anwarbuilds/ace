"""Candidate action language, with entirely fictional correspondence."""

import pytest

from backend.app.inbox.reconcile import read_intent
from backend.tests.test_inbox_intelligence import evidence


@pytest.mark.parametrize('body', [
    'We invite you to complete a technical assessment.',
    'You have been selected to take our technical assessment.',
    'Please complete a CodeSignal General Coding Assessment within four days.',
    'Please complete our take-home assignment for this role.',
    'We invite you to take your coding test.',
    'You have been shortlisted for our technical assessment.',
    'Please start your online assessment for this application.',
])
def test_current_assessment_requests(body):
    assert read_intent(evidence(body)).classification == 'online_assessment'


@pytest.mark.parametrize('body', [
    'Your online assessment is due tomorrow.',
    'Your coding assessment expires tomorrow.',
    'This is a reminder that your coding assessment expires tomorrow.',
    'Your technical assessment is due within two days.',
])
def test_assessment_deadlines_remain_requested_actions(body):
    reading = read_intent(evidence(body))
    assert reading.classification == 'online_assessment'
    assert reading.variant == 'reminder'


@pytest.mark.parametrize('body', [
    'Please select a time for your phone screen using the link below.',
    'Choose a slot for a recruiter screen using the link below.',
    'Book your technical interview using the link below.',
    'Please book our virtual interview.',
    'Congratulations! You have been shortlisted for an interview.',
    'We would love to invite you for a technical interview.',
    'Please share your availability for an interview next week.',
    'Your phone interview is confirmed for Monday.',
])
def test_current_interview_requests(body):
    assert read_intent(evidence(body)).classification == 'interview'


@pytest.mark.parametrize('body', [
    'Once your assessment is completed, we will invite you to interview.',
    'After completing your assessment, we will invite you for a technical interview.',
    'We will invite you to interview once your coding assessment is completed.',
    'Your interview will be scheduled after we review your assessment.',
    'If you are shortlisted for an interview, we will contact you.',
    'You may be invited to complete a technical assessment later.',
    'For example, we invite you to complete a technical assessment.',
    'For instance, we invite you to complete a technical assessment.',
    'An example message says: book your technical interview.',
    'Sample: Your coding assessment is due tomorrow.',
    'You have not been invited to take our online assessment.',
    'Your online assessment is not due yet.',
    'Your interview has not been scheduled.',
    "Your phone interview isn't confirmed yet.",
    'Please do not complete the technical assessment until we contact you.',
    'Your technical assessment is due to be reviewed by our team.',
    'Please complete your practice coding assessment.',
    'Book your mock interview in our optional course.',
    'Your interview preparation webinar is confirmed for Monday.',
    'You have been shortlisted for a public interview workshop.',
])
def test_process_examples_negation_and_learning_are_not_candidate_actions(body):
    assert read_intent(evidence(body)).classification not in {'online_assessment', 'interview'}


@pytest.mark.parametrize('action_text', [
    'Please select a time for your phone screen using the link below.',
    'Book your technical interview using the link below.',
    'We invite you for a technical interview.',
])
def test_new_interview_request_follows_completed_assessment(action_text):
    reading = read_intent(evidence('Your coding assessment is completed. ' + action_text))
    assert reading.classification == 'interview'


def test_not_yet_completed_is_not_a_completion_or_new_invitation():
    reading = read_intent(evidence('You have not yet completed your online assessment.'))
    assert reading.classification not in {'assessment_completed', 'online_assessment'}


def test_deadline_does_not_inherit_a_later_conditional_process_sentence():
    reading = read_intent(evidence(
        'Your coding assessment is due tomorrow. After completion, we will invite you to interview.'
    ))
    assert reading.classification == 'online_assessment'


def test_new_interview_request_conflicts_with_an_asserted_rejection():
    reading = read_intent(evidence(
        'Your application was rejected. Book your technical interview using the link below.'
    ))
    assert reading.classification == 'possible_rejection'


@pytest.mark.parametrize('body', [
    'Your coding assessment is completed. Your interview has been cancelled; it was scheduled for Monday.',
    'Your coding assessment is completed. Your interview has been cancelled. The original interview was scheduled for Monday.',
])
def test_completed_assessment_and_cancelled_interview_do_not_recreate_invitation(body):
    assert read_intent(evidence(body)).classification not in {'interview', 'online_assessment'}


@pytest.mark.parametrize('body', [
    'There is no need to book your interview.',
    'You do not need to complete our assessment.',
    'You are not required to take the assessment.',
    'You have not been invited to an interview.',
    "You haven't been invited to an interview.",
    "We won't invite you to an interview.",
])
def test_negated_action_clause_is_not_an_invitation(body):
    assert read_intent(evidence(body)).classification not in {'interview', 'online_assessment'}


@pytest.mark.parametrize('body', [
    'You have not completed your assessment. Please book your interview.',
    'There is no need to complete our assessment; please book your interview.',
    "You haven't been invited to our assessment, but please book your interview.",
])
def test_negation_in_another_clause_does_not_hide_current_interview_request(body):
    assert read_intent(evidence(body)).classification == 'interview'
