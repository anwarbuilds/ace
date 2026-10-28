"""Applicant-specific decision assertions, using fictional correspondence only."""
from dataclasses import replace

import pytest

from backend.app.api.routers import inbox
from backend.app.inbox.reconcile import read_intent, reconcile
from backend.tests.test_inbox_intelligence import APP, evidence
from backend.tests.test_inbox_persistence import database, job_events, message, row_for, statuses


@pytest.mark.parametrize('body', [
    'Your application for Software Engineer was rejected.',
    'Your application for the Backend Developer role has been declined.',
    'Your candidacy for the Systems Engineer position is unsuccessful.',
    'Your application to Silverpine Labs for Software Engineer was not successful.',
    'Your application for Software Engineer, Storage (SE-102) is not selected.',
    'Your application for the 2030 Software Engineer / Platform role has been unsuccessful.',
    'Your application for Software Engineer was unfortunately rejected.',
    'Your application for Software Engineer was ultimately declined.',
    'Thank you for applying. Your application for Software Engineer has been rejected.',
    'Your application for\nSoftware Engineer\nwas rejected.',
])
def test_role_qualified_application_decisions_are_recognized(body):
    reading = read_intent(evidence(body))
    assert reading.classification == 'rejection'
    assert 'your application' in reading.excerpt.lower() or 'your candidacy' in reading.excerpt.lower()
    assert reading.excerpt in ' '.join(body.split())


@pytest.mark.parametrize('body', [
    'Your application for Software Engineer was not rejected.',
    'Your application for Software Engineer has not been declined.',
    'Your application for Software Engineer was never rejected.',
    'Your application for Software Engineer is not unsuccessful.',
    'It is not true that your application for Software Engineer was rejected.',
    'We cannot confirm your application for Software Engineer was rejected.',
    'We are not sure your application for Software Engineer was rejected.',
    'Your application for Software Engineer was not selected yet; review continues.',
    'Your application for Software Engineer was not successful yet; review continues.',
    'Your application for Software Engineer may be rejected later.',
    'Your application for Software Engineer could have been rejected.',
])
def test_negated_uncertain_and_not_yet_decisions_do_not_establish_rejection(body):
    assert read_intent(evidence(body)).classification != 'rejection'
    assert reconcile(evidence(body), [APP]).target is None


@pytest.mark.parametrize('body', [
    'If your application for Software Engineer was rejected, you can apply again.',
    'Your application for Software Engineer was rejected unless a correction follows.',
    'We will check whether your application for Software Engineer was rejected.',
    'Until your application for Software Engineer is declined, it remains active.',
    'In case your application for Software Engineer was unsuccessful, contact support.',
    'This does not mean your application for Software Engineer was rejected.',
])
def test_qualified_conditions_and_process_descriptions_do_not_automate(body):
    assert read_intent(evidence(body)).classification != 'rejection'
    assert reconcile(evidence(body), [APP]).disposition != 'verified'


@pytest.mark.parametrize('outcome', ['rejected', 'declined', 'not selected'])
@pytest.mark.parametrize('wrapper', [
    'Learn why your application for Software Engineer was {outcome}. Read our career guide.',
    'Five reasons your application for Software Engineer was {outcome}. Join our webinar.',
    'Your application for Software Engineer was {outcome}? Register for our careers event.',
    'Here is a sample letter: your application for Software Engineer was {outcome}.',
    'Example message: your application for Software Engineer was {outcome}.',
    'Our rejection template: your application for Software Engineer was {outcome}.',
    'The quoted message says your application for Software Engineer was {outcome}.',
])
def test_career_advice_questions_and_samples_are_not_personal_outcomes(outcome, wrapper):
    ev = evidence(wrapper.format(outcome=outcome), 'Career advice from Silverpine Labs')
    assert read_intent(ev).classification != 'rejection'
    assert reconcile(ev, [APP]).disposition != 'verified'


@pytest.mark.parametrize('outcome', ['rejected', 'not selected'])
@pytest.mark.parametrize('quotes', [('"', '"'), ('“', '”'), ("'", "'"), ('‘', '’')])
def test_quoted_qualified_decision_is_not_the_current_assertion(outcome, quotes):
    opening, closing = quotes
    ev = evidence(f'The example reads {opening}Your application for Software Engineer was {outcome}{closing}.')
    assert read_intent(ev).classification != 'rejection'


@pytest.mark.parametrize('delimiter', ['On Monday our recruiter wrote:', '----- Original Message -----', '>'])
def test_quoted_history_cannot_override_the_current_receipt(delimiter):
    ev = evidence('We received your application.\n' + delimiter + '\nYour application for Software Engineer was rejected.')
    assert read_intent(ev).classification == 'application_confirmation'


def test_qualified_outcome_keeps_conflicting_progress_and_corrections_in_review():
    for suffix in [
        'Your application remains under review.',
        'We are pleased to offer you the position.',
        'Disregard that decision; it was sent in error.',
    ]:
        ev = evidence('Your application for Software Engineer was rejected. ' + suffix)
        assert read_intent(ev).classification == 'possible_rejection'
        assert reconcile(ev, [APP]).target is None


def test_role_qualifier_is_bounded_and_cannot_bridge_another_clause():
    for qualifier in ['the role; the message', 'Software Engineer. The application', ' '.join(['Platform'] * 30)]:
        ev = evidence(f'Your application for {qualifier} was rejected.')
        assert read_intent(ev).classification != 'rejection'


def test_qualified_rejection_still_requires_authenticated_complete_evidence():
    ev = evidence('Your application for Software Engineer was rejected.')
    assert reconcile(ev, [APP]).target == APP.key
    assert reconcile(replace(ev, sender_authenticated=False), [APP]).target is None
    assert reconcile(replace(ev, complete=False), [APP]).target is None


def test_qualified_rejection_reaches_the_application_and_audit_without_new_submission(database):
    session, conn = database
    body = 'Job ID: SE-101. Your application for Software Engineer has been declined.'
    assert inbox._ingest(session, conn, message('qualified-decision', body), inbox._identities(session), preview=False) == 'automatic'
    session.commit()
    assert statuses(session) == ['applied', 'rejected', 'applied']
    row = row_for(session, 'qualified-decision')
    assert row.classification == 'rejection' and row.decision == 'automatic'
    assert 'application for Software Engineer has been declined' in row.snippet
    [event] = job_events(session)
    assert event.application_key == row.selected_application_key
    assert event.gmail_message_id == row.id and event.actor == 'verified_automation'


RECEIPT = 'Thank you for applying for the Software Engineer position.'
COMPARISON = 'However, we have received other candidates whose experience more closely matches our requirements.'
DECISION = 'This decision applies only to this specific Software Engineer position.'


@pytest.mark.parametrize('comparison', [
    COMPARISON,
    'Unfortunately we received other applicants who better match our needs.',
    'But we found other candidates who match more closely the requirements.',
    'However we have received applications from other applicants whose qualifications more closely match our needs.',
])
def test_contrastive_closer_fit_is_a_rejection_with_an_explicit_actual_decision(comparison):
    ev = evidence(' '.join([RECEIPT, comparison, DECISION]))
    reading = read_intent(ev)
    assert reading.classification == 'rejection'
    assert comparison.rstrip('.') in reading.excerpt and DECISION.rstrip('.') in reading.excerpt
    assert reconcile(ev, [APP]).target == APP.key


@pytest.mark.parametrize('context', [
    'We appreciate your interest in the Software Engineer position at Silverpine Labs.',
    'Thank you for your interest in our Software Engineer role with Silverpine Labs.',
])
def test_named_candidate_interest_provides_context_without_a_receipt(context):
    body = ' '.join([context, 'You considered building your career with our team.', COMPARISON, DECISION])
    ev = evidence(body)
    assert read_intent(ev).classification == 'rejection'
    assert reconcile(ev, [APP]).target == APP.key


@pytest.mark.parametrize('variant', ['asserted', 'conditional', 'quoted', 'under_review'])
def test_specific_decision_supports_comma_in_named_role_without_losing_guards(variant):
    title = 'Software Engineer III, Data Infrastructure'
    context = f'We appreciate your interest in the {title} position at Silverpine Labs.'
    decision = f'This decision pertains only to this specific {title} role.'
    if variant == 'conditional':
        decision = 'If ' + decision[0].lower() + decision[1:-1] + ', please contact us.'
    body = ' '.join([context, COMPARISON, decision])
    if variant == 'quoted':
        body = '"' + body + '"'
    elif variant == 'under_review':
        body += ' Your application remains under review.'
    ev = evidence(body)
    app = replace(APP, title=title)
    reading = read_intent(ev)
    if variant == 'asserted':
        assert reading.classification == 'rejection'
        assert decision.rstrip('.') in reading.excerpt
        assert reconcile(ev, [app]).target == app.key
    else:
        assert reading.classification != 'rejection'
        assert reconcile(ev, [app]).disposition != 'verified'


@pytest.mark.parametrize('body', [
    RECEIPT + ' ' + COMPARISON,
    COMPARISON + ' ' + DECISION,
    RECEIPT + ' We received many other applications for this position. ' + DECISION,
    RECEIPT + ' We received other candidates whose experience more closely matches our requirements. ' + DECISION,
    RECEIPT + ' ' + COMPARISON + ' We will make a decision about this role next week.',
    RECEIPT + ' ' + COMPARISON + ' This decision will apply only to this role.',
    RECEIPT + ' ' + COMPARISON + ' This decision does not apply to this application.',
    RECEIPT + ' If we receive other candidates who better match our needs, we will let you know. ' + DECISION,
    RECEIPT + ' However, if we have received other candidates whose experience more closely matches our requirements, we will contact you. ' + DECISION,
    RECEIPT + ' ' + COMPARISON + ' If this decision applies only to this role, please contact us.',
    RECEIPT + ' ' + COMPARISON + ' We are discussing whether this decision applies only to this position.',
    RECEIPT + ' ' + COMPARISON + ' This decision applies only to this specific role?',
    RECEIPT + ' ' + COMPARISON + ' We cannot confirm this decision applies only to this role.',
    RECEIPT + ' ' + COMPARISON + ' It is not true that this decision applies only to this position.',
    DECISION + ' ' + RECEIPT + ' ' + COMPARISON,
    'We appreciate your interest in Silverpine Labs. ' + COMPARISON + ' ' + DECISION,
    'We appreciate your impressive background. ' + COMPARISON + ' ' + DECISION,
    'We appreciate your interest in the position at Silverpine Labs. ' + COMPARISON + ' ' + DECISION,
    'If we appreciate your interest in the Software Engineer position at Silverpine Labs, we will respond. ' + COMPARISON + ' ' + DECISION,
])
def test_comparisons_volumes_and_possible_future_decisions_are_insufficient(body):
    assert read_intent(evidence(body)).classification != 'rejection'
    assert reconcile(evidence(body), [APP]).disposition != 'verified'


@pytest.mark.parametrize('wrapper', [
    'Example letter: {body}',
    'The sample message follows. {body}',
    '"{body}"',
    "'{body}'",
    'For example: {body}',
])
def test_quoted_or_sample_comparative_decisions_do_not_automate(wrapper):
    body = ' '.join([RECEIPT, COMPARISON, DECISION])
    ev = evidence(wrapper.format(body=body))
    assert read_intent(ev).classification != 'rejection'
    assert reconcile(ev, [APP]).disposition != 'verified'


def test_quoted_named_interest_cannot_supply_candidate_context():
    body = '"We appreciate your interest in the Software Engineer position at Silverpine Labs." ' + COMPARISON + ' ' + DECISION
    assert read_intent(evidence(body)).classification != 'rejection'


@pytest.mark.parametrize('where', ['before', 'after'])
@pytest.mark.parametrize('progress', [
    'Your application remains under consideration.',
    'Your candidacy is still under review.',
    'Your application for the Software Engineer position remains under review.',
    'We are still reviewing your application.',
])
def test_current_review_prevents_comparative_decision_from_being_recorded(where, progress):
    parts = [RECEIPT, COMPARISON, DECISION]
    parts.insert(1 if where == 'before' else len(parts), progress)
    ev = evidence(' '.join(parts))
    assert read_intent(ev).classification == 'possible_rejection'
    assert reconcile(ev, [APP]).target is None


def test_comparative_reference_does_not_override_current_offer_or_interview():
    for suffix in ['We invite you to a technical interview.', 'We are pleased to offer you the position.']:
        ev = evidence(' '.join([RECEIPT, COMPARISON, DECISION, suffix]))
        assert read_intent(ev).classification == 'possible_rejection'
        assert reconcile(ev, [APP]).target is None


def test_comparative_decision_in_quoted_history_is_not_current():
    ev = evidence('We received your application.\n----- Original Message -----\n' + ' '.join([RECEIPT, COMPARISON, DECISION]))
    assert read_intent(ev).classification == 'application_confirmation'
