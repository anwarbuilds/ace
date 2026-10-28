"""Fictional regressions for needless historical review, never owner mail."""
from dataclasses import replace

import pytest

from backend.app.api.routers import inbox
from backend.app.inbox.reconcile import read_intent, reassess, reconcile
from backend.tests.test_inbox_intelligence import APP, evidence
from backend.tests.test_inbox_persistence import message


@pytest.mark.parametrize('body', [
    'Improve your skills with this challenge recommended for you: Binary Lanterns. Solve Challenge. Happy coding!',
    'Day 4 of 20 Days of Code. Welcome to Day 4. Today we learn about arrays. Start Day 4 Now. Happy coding!',
    'Day 0 of 20 Days of Code. Each day you receive a tutorial to help you learn. Start Day 0 now.',
])
@pytest.mark.parametrize('old_kind', ['online_assessment', 'interview', 'offer', 'rejection'])
def test_explicit_learning_purpose_resolves_old_machine_outcomes(body, old_kind):
    ev = evidence(body, 'Your coding practice')
    result = reassess(ev, [APP], old_kind)
    assert result.disposition == 'ignored' and result.target is None
    reading = read_intent(ev)
    assert reading.variant == 'routine' and 'optional' in reading.explanation
    assert reading.excerpt


@pytest.mark.parametrize('body,kind', [
    ("You're invited to take our online assessment for the Backend Engineer role.", 'online_assessment'),
    ("You've just been invited by someone from Silverpine to take Silverpine Coding Assessment.", 'online_assessment'),
    ("You've just been invited by someone from Silverpine to take Silverpine 2030 Coding Assessment.", 'online_assessment'),
    ('A quick reminder: your coding assessment from Silverpine is due in 12 hours.', 'online_assessment'),
    ('We are excited to extend you an offer for the position of Systems Engineer.', 'offer'),
    ('Congratulations on your new job offer with Silverpine! We are preparing the letter.', 'offer'),
    ('We invite you to a virtual interview.', 'interview'),
])
def test_hiring_requests_and_asserted_offers_are_understood(body, kind):
    assert read_intent(evidence(body)).classification == kind


@pytest.mark.parametrize('body', [
    'If selected, we will extend you an offer for the position of Systems Engineer.',
    'You have not been invited to take our online assessment.',
    'Your practice coding assessment is due in 12 hours.',
    'If you are invited to take our online assessment, use the link sent later.',
    'For example, congratulations on your new job offer with an employer is a common message.',
])
def test_process_practice_and_negation_are_not_new_hiring_outcomes(body):
    assert read_intent(evidence(body)).classification not in {'offer', 'online_assessment'}


@pytest.mark.parametrize('body,kind', [
    ('Please complete your coding assessment for this application. You can use the optional practice course to prepare.', 'online_assessment'),
    ('Your application was rejected. Improve your skills with this challenge recommended for you.', 'rejection'),
    ('We invite you to a technical interview. Day 4 of 20 Days of Code is available as practice.', 'interview'),
    ('We are pleased to offer you the position. Improve your skills with this challenge recommended for you.', 'offer'),
])
def test_routine_material_cannot_suppress_real_hiring_evidence(body, kind):
    ev = evidence(body, 'Your practice update')
    assert read_intent(ev).classification == kind
    assert reassess(ev, [APP], kind).disposition != 'ignored'


@pytest.mark.parametrize('subject,body', [
    ('Verify your SkillBench account', 'Welcome! Click below to verify your email.'),
    ('Please confirm your email', 'There is just one step: confirm account.'),
])
def test_branded_account_notices_require_body_evidence(subject, body):
    assert reassess(evidence(body, subject), [APP], 'online_assessment').disposition == 'ignored'
    assert reassess(evidence('A new chapter awaits. Visit the candidate portal.', subject), [APP], 'offer').disposition == 'review'


def test_html_document_mislabelled_as_plain_text_is_read_as_visible_content():
    data = message('mislabelled', '<html><head><style>.offer { color:red }</style></head><body><p>We are excited to extend you an offer for the position of Systems Engineer.</p><blockquote>Your application was rejected.</blockquote></body></html>')
    ev = inbox._message_evidence(data)
    assert '<html' not in ev.body and 'color:red' not in ev.body
    assert read_intent(ev).classification == 'offer'


def test_ats_display_does_not_create_an_application_at_the_platform_employer():
    apps = [APP, replace(APP, key='job:2', company='Workday')]
    ev = replace(evidence('Your application was rejected for the Software Engineer role.'), sender='Silverpine Labs Workday Notifications <silverpinelabs@myworkday.com>')
    result = reconcile(ev, apps)
    assert result.target == APP.key and result.candidates == (APP.key,)


def test_workday_as_actual_employer_is_not_discarded():
    app = replace(APP, company='Workday', official_url=None)
    ev = replace(evidence('Your application was rejected.', 'Your application'), sender='Workday <workday@myworkday.com>')
    assert reconcile(ev, [app]).target == app.key


def test_department_words_do_not_turn_employer_brand_into_a_subsidiary():
    ev = replace(evidence('Your application was rejected for the Software Engineer role.'), sender='Silverpine Labs Talent Acquisition <no-reply@us.greenhouse-mail.io>')
    assert reconcile(ev, [APP]).target == APP.key
    subsidiary = replace(ev, sender='Silverpine Labs Health Talent Acquisition <no-reply@us.greenhouse-mail.io>')
    assert reconcile(subsidiary, [APP]).target is None


def test_longer_exact_title_eliminates_only_nested_generic_title_mentions():
    generic = replace(APP, requisition_id=None)
    specific = replace(APP, key='job:2', title='Software Engineer, Storage', requisition_id=None)
    ev = evidence('Thank you for applying to Software Engineer, Storage. Your application was rejected.')
    assert reconcile(ev, [generic, specific]).target == specific.key
    two_roles = replace(ev, body='Software Engineer, Storage and Software Engineer are separate roles. Your application was rejected.')
    assert reconcile(two_roles, [generic, specific]).target is None
    duplicate = replace(specific, key='job:3')
    assert reconcile(ev, [generic, specific, duplicate]).target is None


@pytest.mark.parametrize('subject,body', [
    ('Customer reward', 'Refer friends and earn rewards per calendar year.'),
    ('Your account data', 'You used Sign in with Acme to access a coding platform.'),
    ('Document ready', 'Your Social Security Letter has been generated and is available for pickup.'),
    ('Writing report', 'Your Weekly Writing Update. Your writing streak and words analyzed are available.'),
    ('Public session', 'We invite you to our upcoming webinar. Register and join us to discuss technology.'),
    ('Competition report', 'We hired 45 students. See the list of selected candidates.'),
    ('Public competition', 'We bring to you a challenge with a cash prize. Apply to enter the competition.'),
    ('Transaction dispute', 'We are unable to proceed further with the dispute. The chargeback was denied. Credit applied to your account was reversed.'),
])
def test_affirmative_non_hiring_purpose_resolves_old_false_outcomes(subject, body):
    result = reassess(evidence(body, subject), [APP], 'rejection')
    assert result.disposition == 'ignored' and result.target is None
    assert read_intent(evidence(body, subject)).variant == 'routine'


def test_digest_articles_are_not_personal_interview_evidence():
    ev = evidence('Explore another developer\'s experience. Top Picks For You. In my story, we invite you to a technical interview was the message I received.', 'Developer Weekly Digest')
    result = reassess(ev, [APP], 'interview')
    assert result.disposition == 'ignored' and read_intent(ev).variant == 'routine'
    actual = replace(ev, body='Your application was rejected. Top Picks For You. More articles follow.')
    assert read_intent(actual).classification == 'rejection'


def test_public_speaker_registration_without_webinar_keyword_is_routine():
    ev=evidence('Join us on 18 January 2030 as we talk to a technology leader about distributed systems. Register now. We hope to see you there!', 'Technology speaker session')
    assert reassess(ev,[APP],'online_assessment').disposition=='ignored'
    actual=evidence('Please complete your online assessment for this application. '+ev.body,'Application next steps')
    assert read_intent(actual).classification=='online_assessment'


def test_named_test_completion_needs_completed_submission_and_delivery():
    ev = evidence("Thanks for completing LanternSWE. We've sent your submission to Silverpine.")
    assert read_intent(ev).classification == 'assessment_completed'
    assert read_intent(replace(ev, body="When you finish, we will send your submission to Silverpine.")).classification != 'assessment_completed'


def test_interview_coordination_does_not_ask_owner_to_classify_another_invitation():
    ev = evidence("It can take days to coordinate the details for your virtual interview. Once confirmed, we'll send the schedule.")
    assert read_intent(ev).variant == 'interview_coordination'
    assert reassess(ev, [APP], 'interview').disposition == 'update'


def test_actual_application_receipt_survives_an_account_or_referral_footer():
    ev = evidence('We received your application. Verify your email to access your account.', 'Verify your account')
    result = reassess(ev, [APP], 'online_assessment')
    assert result.classification == 'application_confirmation' and result.disposition == 'receipt'

