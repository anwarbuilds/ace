"""Recognized mail meaning is independent of optional application linkage."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.app.db.models import ApplicationEventRecord as Event, GmailMessageRecord as Mail
from backend.app.inbox.filed_evidence import ACTION_KINDS, ACTION_PREFIX, DECISIONS, LEGACY_ACTION_REASONS, REJECTION_PREFIX
from backend.app.inbox.queue import PENDING, decision_expression, projected_decision, workflow_expression, workflow_state
from backend.app.inbox.reconcile import ApplicationIdentity, Decision, EmailEvidence, file_recognized, read_intent, reconcile
from backend.tests.test_inbox_persistence import database, message, statuses


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
APP = ApplicationIdentity('job:1', 'Silverpine Labs', 'Software Engineer', 'SE-12345',
                          NOW-timedelta(days=8), 'applied', 'https://careers.silverpine.example/jobs/SE-12345')
BODIES = {
    'rejection': 'Your application was rejected.',
    'online_assessment': 'Please complete your online assessment.',
    'interview': 'Please book your technical interview.',
    'offer': 'We are pleased to offer you the Software Engineer position.',
    'recruiter_reply': 'We would like to speak with you about your application.',
    'action_required': 'Please upload your transcript for your application.',
}


def evidence(body, *, authenticated=True, complete=True, known_employer=False):
    sender = 'talent@careers.silverpine.example' if known_employer else 'talent@unrecorded-employer.example'
    return EmailEvidence(sender, 'Your application update', body, NOW, authenticated, complete)


@pytest.mark.parametrize('kind', sorted(BODIES))
def test_complete_authenticated_meaning_is_filed_without_guessing_an_application(kind):
    result = reconcile(evidence(BODIES[kind]), [APP])
    expected = 'classified_rejection' if kind == 'rejection' else 'classified_action'
    assert result.classification == kind and result.disposition == expected
    assert result.target is result.matched_target is result.company is None
    assert result.sender_verified and result.disposition not in PENDING
    assert result.reason.startswith(REJECTION_PREFIX if kind == 'rejection' else ACTION_PREFIX)
    assert 'No application could be matched' in result.reason or kind == 'action_required'


@pytest.mark.parametrize('kind', sorted(BODIES))
@pytest.mark.parametrize('missing', ['authentication', 'complete_body'])
def test_partial_or_unauthenticated_meaning_remains_review(kind, missing):
    result = reconcile(evidence(BODIES[kind], authenticated=missing != 'authentication',
                                complete=missing != 'complete_body'), [APP])
    assert result.disposition == 'review' and result.disposition not in DECISIONS
    assert result.target is None


def test_file_helper_removes_all_application_authority_but_keeps_candidates_and_explanation():
    original = Decision('online_assessment', 'SE-12345', ('job:1', 'job:2'), 'job:1', 'verified',
                        'Clear online assessment matched by its job ID', True, 'job:1', 'Silverpine Labs')
    result = file_recognized(original, evidence(BODIES['online_assessment']))
    assert result.classification == original.classification and result.requisition_id == original.requisition_id
    assert result.candidates == original.candidates
    assert result.target is result.matched_target is result.company is None
    assert result.reason == ACTION_PREFIX + original.reason
    assert result.disposition == 'classified_action'
    assert file_recognized(result, evidence(BODIES['online_assessment'])) == result


def test_file_helper_requires_current_meaning_instead_of_a_saved_classification():
    saved = Decision('interview', None, (), None, 'review', 'No application could be matched with confidence', False)
    assert file_recognized(saved, evidence('Your account has been created.')) == saved


@pytest.mark.parametrize('reason', [
    'You marked it a status update with no decision yet',
    "You undid ACE's change for this email",
    'Only part of this email could be read',
])
def test_file_helper_never_erases_owner_undo_or_a_failed_protection_reason(reason):
    saved = Decision('interview', None, (), None, 'review', reason, False)
    assert file_recognized(saved, evidence(BODIES['interview'])) == saved


def test_failed_sender_authentication_is_a_material_review_reason():
    saved = Decision('interview', None, (), None, 'review', 'Sender could not be authenticated', False)
    assert file_recognized(saved, evidence(BODIES['interview'], authenticated=False)) == saved


@pytest.mark.parametrize('applications', [[], [APP]])
def test_authenticated_personal_mail_can_be_classified_without_employer_authority(applications):
    ev = replace(evidence(BODIES['rejection']), sender='Recruiter <fixture@gmail.com>')
    decision = reconcile(ev, applications)
    assert decision.disposition == 'classified_rejection'
    assert decision.target is decision.matched_target is decision.company is None
    assert decision.reason.startswith(REJECTION_PREFIX)


def test_personal_sender_warning_describes_application_authority():
    saved = Decision('rejection', None, (), None, 'review', 'Sender could not be authenticated', False)
    filed = file_recognized(saved, evidence(BODIES['rejection']))
    assert filed.reason == REJECTION_PREFIX + 'The sender does not establish employer authority for an application status change'


def test_marker_and_original_reason_fit_the_existing_database_column():
    saved = Decision('interview', None, ('job:1',), None, 'review', 'Linkage uncertainty: ' + 'x' * 600, False)
    result = file_recognized(saved, evidence(BODIES['interview']))
    assert len(result.reason) == 300 and result.reason.startswith(ACTION_PREFIX + 'Linkage uncertainty: ')


@pytest.mark.parametrize('kind', ['rejection', 'online_assessment', 'interview', 'offer', 'recruiter_reply'])
def test_exact_verified_application_successes_keep_the_existing_path(kind):
    ev = evidence('Job ID: SE-12345. ' + BODIES[kind], known_employer=True)
    result = reconcile(ev, [APP])
    assert result.disposition == 'verified' and result.target == result.matched_target == APP.key
    assert result.company is None and not result.reason.startswith((ACTION_PREFIX, REJECTION_PREFIX))


def test_company_recording_remains_first_when_only_role_linkage_is_missing():
    second = replace(APP, key='job:2', title='Platform Engineer', requisition_id='SE-23456')
    result = reconcile(evidence(BODIES['rejection'], known_employer=True), [APP, second])
    assert result.disposition == 'company_rejection' and result.company == 'Silverpine Labs'
    assert result.target is result.matched_target is None


def test_a_protected_application_stage_files_the_action_without_overwriting_it():
    app = replace(APP, current_status='rejected')
    result = reconcile(evidence('Job ID: SE-12345. ' + BODIES['interview'], known_employer=True), [app])
    assert result.disposition == 'classified_action'
    assert result.target is result.matched_target is None and app.current_status == 'rejected'
    assert 'Existing final status is protected' in result.reason


@pytest.mark.parametrize('positive', ['online_assessment', 'interview', 'offer'])
def test_rejection_and_current_positive_request_cannot_file_or_reject_an_application(positive):
    ev = evidence('Job ID: SE-12345. ' + BODIES['rejection'] + ' ' + BODIES[positive], known_employer=True)
    reading = read_intent(ev)
    result = reconcile(ev, [APP])
    assert reading.classification == result.classification == 'possible_rejection'
    assert reading.variant == 'conflicting_outcomes'
    assert result.disposition == 'review' and result.target is None


def test_conflicting_assessment_cannot_automatically_reject_the_exact_application(database):
    from backend.app.api.routers import inbox
    session, conn = database
    data = message('fictional-conflicting-assessment',
                   'Job ID: SE-101. Your application was rejected. Please complete your online assessment.')
    assert inbox._ingest(session, conn, data, inbox._identities(session), preview=False) == 'review'
    row = session.scalar(select(Mail).where(Mail.gmail_id == data['id']))
    assert row.classification == 'possible_rejection'
    assert statuses(session) == ['applied'] * 3
    assert not list(session.scalars(select(Event).where(Event.actor == 'verified_automation')))


def test_future_or_example_assessment_does_not_create_a_conflict_with_a_real_rejection():
    for suffix in ['If you are invited to complete an assessment, follow the later instructions.',
                   'For example, please complete your online assessment is a template invitation.']:
        result = reconcile(evidence('Job ID: SE-12345. ' + BODIES['rejection'] + ' ' + suffix,
                                    known_employer=True), [APP])
        assert result.classification == 'rejection' and result.disposition == 'verified'


def test_pure_decisions_do_not_change_application_rows_or_append_outcome_events(database):
    session, conn = database
    before = statuses(session)
    for body in BODIES.values():
        reconcile(evidence(body), [APP])
    assert statuses(session) == before and not list(session.scalars(select(Event)))
    assert not session.new and not session.dirty and not session.deleted


def test_sql_python_projection_and_workflow_agree_without_promoting_legacy_or_owner_rows(database):
    session, conn = database
    samples = [('rejection', 'update', REJECTION_PREFIX + 'No recorded application', 'classified_rejection')]
    samples += [(kind, 'update', ACTION_PREFIX + 'Linking is optional', 'classified_action') for kind in sorted(ACTION_KINDS)]
    samples += [(kind, 'update', reason, 'classified_action') for kind, reason in LEGACY_ACTION_REASONS.items()]
    samples += [('offer', 'update', LEGACY_ACTION_REASONS['interview'], 'update')]
    samples += [
        ('interview', 'review', ACTION_PREFIX + 'Linking is optional', 'review'),
        ('interview', 'manual', ACTION_PREFIX + 'Linking is optional', 'manual'),
        ('interview', 'deferred', ACTION_PREFIX + 'Linking is optional', 'deferred'),
        ('interview', 'update', 'You marked it a status update with no decision yet', 'update'),
        ('interview', 'review', "You undid ACE's change for this email", 'review'),
        ('interview', 'review', 'No application could be matched with confidence', 'review'),
        ('assessment_completed', 'update', ACTION_PREFIX + 'Finished', 'update'),
        ('possible_rejection', 'update', REJECTION_PREFIX + 'Conflicting outcomes', 'update'),
        ('offer', 'update', REJECTION_PREFIX + 'Wrong marker', 'update'),
        ('rejection', 'update', ACTION_PREFIX + 'Wrong marker', 'update'),
        ('interview', 'update', ACTION_PREFIX.lower() + 'Wrong case marker', 'update'),
    ]
    rows = []
    for index, (kind, raw, reason, expected) in enumerate(samples):
        row = Mail(connection_id=conn.id, gmail_id=f'fictional-filed-{index}', received_at=NOW,
                   sender='talent@fictional.example', subject='Fictional evidence', snippet='Fictional evidence',
                   classification=kind, decision=raw, decision_reason=reason, parser_version='13', candidate_keys=[])
        session.add(row)
        rows.append((row, expected))
    session.commit()
    actual = {mid: (decision, workflow) for mid, decision, workflow in session.execute(
        select(Mail.id, decision_expression(), workflow_expression()))}
    for row, expected in rows:
        assert projected_decision(row) == actual[row.id][0] == expected
        assert workflow_state(row) == actual[row.id][1]
        if expected in DECISIONS:
            assert workflow_state(row) == expected and expected not in PENDING
