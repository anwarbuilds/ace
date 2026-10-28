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
