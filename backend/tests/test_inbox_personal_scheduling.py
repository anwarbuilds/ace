"""Personal hiring scheduling, using wholly fictional messages and identities."""
from datetime import datetime, timezone

import pytest

from backend.app.inbox.reconcile import EmailEvidence, read_intent, reconcile


NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def mail(body, subject="Interview with Fictional Robotics", *, complete=True):
    return EmailEvidence("Fictional Hiring <hiring@fictional.example>", subject, body,
                         NOW, sender_authenticated=True, complete=complete)


@pytest.mark.parametrize("body", [
    "We would like to speak with you about your background. Please select a time using the link below.",
    "I'd love to chat with you about your experience. Please book a convenient time.",
    "I am interested in having a call to meet you and discuss your background. Please choose a time below.",
    "We're excited to connect with you. Could you share your availability?",
    "We would be interested in a call to get to know you. Please send your availability.",
    "I am looking forward to speaking with you. Let me know what times work for you.",
    "We would like to set up a call with you about your background; please find a time that works for you.",
    "Please select a convenient time. We would love to meet with you about your experience.",
    "We would like to talk with you. Please use the link below to schedule some time.",
    "We would love the opportunity to meet with you and learn about your background. Please select a time below.",
    "We are a robotics team and would love a chance to meet you. Please select a time below.",
    "I would really love an opportunity to meet you. Please select a convenient time below.",
])
def test_personal_contact_and_current_scheduling_with_interview_context(body):
    reading = read_intent(mail(body))
    assert reading.classification == "interview"
    assert reading.variant == "invitation"


@pytest.mark.parametrize("subject,body", [
    ("Next steps at Fictional Robotics", "We would love to chat with you about the Software Engineer role. Please select a time below."),
    ("Your application at Fictional Robotics", "I would like to speak with you about your application. Please share your availability."),
    ("A conversation", "Our hiring team is interested in your background. I would like to meet with you. Please book a time below."),
    ("Next steps", "We would like to have a call with you about the engineering position. Please choose a time below."),
    ("A conversation", "We would like to speak with you for an interview about your background. Please select a time below."),
])
def test_hiring_context_can_come_from_current_body(subject, body):
    assert read_intent(mail(body, subject)).classification == "interview"


@pytest.mark.parametrize("choice", [
    "If you are interested, please select a time below.",
    "If you're interested, please select a time below.",
    "If you’re still interested, please select a time below.",
    "If interested, please select a time below.",
    "If still interested, please select a time below.",
    "If you are interested please select a time below.",
    "If you are available, please select a time below.",
    "If you're free, please choose a time below.",
])
def test_recipient_choice_does_not_turn_current_hiring_invitation_into_future_process(choice):
    ev = mail("We would love the opportunity to meet you and learn about your background. " + choice)
    reading = read_intent(ev)
    assert reading.classification == "interview"
    assert choice.rstrip(".") in reading.excerpt
    decision = reconcile(ev, [])
    assert decision.disposition == "classified_action" and decision.target is None


@pytest.mark.parametrize("choice", [
    "If we are interested, please select a time below.",
    "If the employer is interested, please select a time below.",
    "If selected, please select a time below.",
    "If your assessment passes, please select a time below.",
    "If you are interested and your application is selected, please select a time below.",
    "If you are interested, please select a time below if you pass the assessment.",
    "If you are interested in our course, please select a time below.",
])
def test_recipient_choice_exception_does_not_remove_employer_selection_or_other_conditions(choice):
    ev = mail("We would love to meet you and learn about your background. " + choice)
    assert read_intent(ev).classification != "interview"


@pytest.mark.parametrize("purpose", ["interview coaching webinar", "product demo", "public event", "mock interview course"])
def test_recipient_opt_in_does_not_make_other_scheduled_events_a_hiring_interview(purpose):
    ev = mail("We would love to meet you at our " + purpose + ". If you are interested, please select a time below.")
    assert read_intent(ev).classification != "interview"


def test_recipient_choice_does_not_change_assessment_or_rejection_assertion_guards():
    assert read_intent(mail("If you are interested, please complete your technical assessment.")).classification != "online_assessment"
    assert read_intent(mail("If you are interested, your application will not move forward.")).classification != "rejection"


def test_receipt_does_not_hide_a_later_personal_interview_request():
    ev = mail("Thank you for applying. We have received your application. "
              "We would like to speak with you about your background. Please select a time below.")
    assert read_intent(ev).classification == "interview"
    decision = reconcile(ev, [])
    assert decision.classification == "interview" and decision.disposition == "classified_action"
    assert decision.target is None and decision.matched_target is None


def test_hiring_conversation_is_still_filed_without_an_application_or_sender_authority():
    ev = EmailEvidence("Person <person@gmail.com>", "Fictional Robotics interview",
                       "I'd love to meet with you about your background. Please select a time below.",
                       NOW, sender_authenticated=False)
    decision = reconcile(ev, [])
    assert decision.classification == "interview" and decision.disposition == "classified_action"
    assert decision.target is None and decision.sender_verified is False
    assert "Unverified sender" in decision.reason


@pytest.mark.parametrize("subject,body", [
    ("Interview invitation", "Please select a convenient time using the link below."),
    ("Interview invitation", "We would like to speak with you about your background."),
    ("Meet Fictional Robotics", "We would like to chat with you. Please select a time below."),
    ("A call", "We would like to meet with you about your background. Please book a time below."),
    ("A conversation", "I'd love to speak with you. Please select a time at https://fictional.example/interview."),
    ("Fictional Robotics", "Please select a time for a call at https://fictional.example/interview."),
    ("Meeting invitation", "When: Thursday 2pm. Join with Google Meet. Guests: hiring@fictional.example and candidate@example.test."),
    ("Fictional Robotics interview", "The company is recruiting engineers. Here are our available calendars."),
])
def test_subject_or_url_or_generic_meeting_does_not_establish_personal_hiring_action(subject, body):
    assert read_intent(mail(body, subject)).classification != "interview"


@pytest.mark.parametrize("body", [
    "If selected, we would like to speak with you about your background. Please select a time below.",
    "We would like to speak with you after we review your application. Please book a time below.",
    "Should you qualify, we would like to meet with you. Please choose a time below.",
    "We would like to speak with you. If selected, please book a time below.",
    "If your application is selected. We would like to speak with you. Please select a time below.",
    "We would like to speak with you. We will select a time later in the process.",
    "We would like to speak with you. Selected candidates will choose a time later.",
    "We would like to speak with you. You will be asked to select a time later.",
    "After your assessment passes review, we would like to speak with you. Please choose a time below.",
    "We would like to speak with you after you complete an assessment. Please choose a time below.",
    "We do not want to speak with you. Please select a time below.",
    "We would not like to speak with you. Please select a time below.",
    "We never said we would like to meet you. Please select a time below.",
    "We cannot confirm we would like to meet you. Please select a time below.",
    "I did not say I would love to meet you. Please select a time below.",
    "We can't promise we would love to meet you. Please select a time below.",
    "It is not true that we would like to meet you. Please select a time below.",
    "We would like to speak with you. Please do not book a time yet.",
    "We would like to speak with you. There is no need to select a time yet.",
    'Example: We would like to speak with you. Please select a time below.',
    'Template invitation. We would like to speak with you. Please select a time below.',
    '"We would like to speak with you. Please select a time below."',
    "We would like to speak with you at a public event. Please select a time below.",
    "We would like to speak with you during our interview preparation webinar. Please select a time below.",
    "We would like to meet with you for a product demo. Please select a time below.",
    "We would like to chat with you for an optional mock interview. Please choose a time below.",
    "We would like to speak with you. Please select a time below. This call was cancelled.",
])
def test_conditional_negated_examples_and_unrelated_events_are_not_personal_interviews(body):
    assert read_intent(mail(body)).classification != "interview"


def test_scheduling_of_unrelated_action_cannot_use_distant_contact_interest():
    ev = mail("We would like to speak with you about your background. "
              "Here are the latest company updates. We make robots. Read our new article. "
              "Please select a time for an office tour.")
    assert read_intent(ev).classification != "interview"


def test_interview_description_can_connect_invitation_and_scheduling_across_paragraphs():
    ev = mail("We would love an opportunity to meet you and learn about your background.\n\n"
              "The interview is an individual conversation with two engineers. "
              "It takes about forty minutes. We will talk about your past work. "
              "You can ask questions about our team.\n\n"
              "If you are interested, please select a convenient time below.")
    reading = read_intent(ev)
    assert reading.classification == "interview"
    assert "The interview is an individual conversation" in reading.excerpt
    assert "If you are interested" in reading.excerpt


def test_strong_subject_does_not_link_distant_scheduling_without_body_interview_context():
    ev = mail("We would love an opportunity to meet you and learn about your background.\n\n"
              "Here are updates about our team. We are opening a new building. "
              "The facility is close to public transport. We have an open house.\n\n"
              "Please select a convenient time below.")
    assert read_intent(ev).classification != "interview"


def test_explanatory_interview_description_does_not_change_separate_office_tour_into_an_invitation():
    ev = mail("We would like to speak with you about your background. "
              "The interview process includes several stages. We will send more information later. "
              "We also invite you to see our building. Please select a time for an office tour.")
    assert read_intent(ev).classification != "interview"


def test_footer_interview_word_does_not_link_distant_ordinary_meetings():
    ev = mail("We would like to speak with you about your background. "
              "Here are the latest company updates. We make robots. Read our new article. "
              "Please select a time below.\n\nUnsubscribe from interview coaching updates.")
    assert read_intent(ev).classification != "interview"


@pytest.mark.parametrize("description", [
    "This is not an interview.",
    "No interview is required.",
    "Your interview has not been scheduled.",
    "An interview will be scheduled after we review your qualifications.",
    "Should you be selected, an interview will be scheduled.",
    "Onsite interviews by invitation only.",
    "A template says: interview details will follow.",
])
def test_long_passage_corroboration_requires_an_asserted_current_interview(description):
    ev = mail("We would like to meet you and hear about your background. " + description + " "
              "There are many things to discuss. Our team makes robots. "
              "We can share more details about the company. "
              "If you are interested, please select a convenient time below.")
    assert read_intent(ev).classification != "interview"


@pytest.mark.parametrize("earlier", [
    "We never said we would like to meet you.",
    "We cannot confirm we would like to meet you.",
])
def test_reported_desire_does_not_suppress_a_separate_current_request(earlier):
    ev = mail(earlier + " I would love to speak with you now about your background. Please select a time below.")
    assert read_intent(ev).classification == "interview"
    assert "I would love to speak" in read_intent(ev).excerpt


def test_personal_interview_request_conflicts_with_a_current_rejection():
    ev = mail("Your application was rejected. We would like to speak with you about your background. "
              "Please select a time below.")
    assert read_intent(ev).classification == "possible_rejection"


def test_a_current_assessment_retains_existing_priority():
    ev = mail("Please complete your coding assessment. We would like to speak with you about your background. "
              "Please select a time below.")
    assert read_intent(ev).classification == "online_assessment"


def test_completed_assessment_does_not_hide_new_personal_interview_request():
    ev = mail("Your coding assessment is completed. We would like to speak with you about your background. "
              "Please select a time below.")
    assert read_intent(ev).classification == "interview"


def test_cancelled_interview_does_not_recreate_a_current_invitation():
    ev = mail("Your interview was cancelled. The original message said we would like to speak with you. "
              "Please select a time below.")
    assert read_intent(ev).classification == "interview_cancelled"


def test_incomplete_evidence_does_not_file_automatically():
    ev = mail("We would like to speak with you about your background. Please select a time below.", complete=False)
    decision = reconcile(ev, [])
    assert decision.classification == "interview" and decision.disposition == "review"
    assert decision.target is None
