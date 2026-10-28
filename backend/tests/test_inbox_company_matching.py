"""Company evidence never guesses an application; every example is fictional."""
from dataclasses import asdict, replace
from datetime import timedelta

import pytest

from backend.app.inbox.company_outcomes import COMPANY_REASON
from backend.app.inbox.reconcile import reconcile
from backend.tests.test_inbox_intelligence import APP, evidence


def roles():
    return [APP, replace(APP, key='job:2', title='Data Scientist', requisition_id='DS-987654')]


def assert_company(decision, apps, company=APP.company):
    assert decision.classification == 'rejection'
    assert decision.disposition == 'company_rejection'
    assert decision.company == company and decision.reason == COMPANY_REASON
    assert decision.target is decision.matched_target is None
    assert decision.sender_verified
    assert set(decision.candidates) == {app.key for app in apps if app.company == company}


def test_role_ambiguity_records_company_evidence_without_picking_or_changing_roles():
    apps = roles()
    before = [asdict(app) for app in apps]
    assert_company(reconcile(evidence('Your application was rejected.'), apps), apps)
    assert [asdict(app) for app in apps] == before


def test_safe_exact_application_matches_still_record_application_outcomes():
    apps = roles()
    for body in ['Job ID: SE-102. Your application was rejected.', 'Your application for Software Engineer was rejected.']:
        decision = reconcile(evidence(body), apps)
        assert decision.disposition == 'verified' and decision.target == APP.key
        assert decision.company is None


@pytest.mark.parametrize('case', ['future', 'offer', 'accepted', 'withdrawn', 'newer_interview', 'different_role', 'different_id', 'duplicate_id'])
def test_application_conflicts_can_be_company_evidence_without_application_authority(case):
    apps = [APP]
    body = 'Your application for Software Engineer was rejected.'
    if case == 'future':
        apps = [replace(APP, submitted_at=evidence('').received_at + timedelta(days=30))]
    elif case in {'offer', 'accepted', 'withdrawn'}:
        apps = [replace(APP, current_status=case)]
    elif case == 'newer_interview':
        apps = [replace(APP, current_status='interviewing', status_changed_at=evidence('').received_at + timedelta(days=1))]
    elif case == 'different_role':
        body = 'Your application for Senior Data Engineer was rejected.'
    elif case == 'different_id':
        body = 'Job ID: SE-987654. Your application was rejected.'
    elif case == 'duplicate_id':
        apps += [replace(APP, key='external:2')]
        body = 'Job ID: SE-102. Your application was rejected.'
    assert_company(reconcile(evidence(body), apps), apps)


@pytest.mark.parametrize('sender', [
    'Silverpine Labs <talent@careers.silverpine.example>',
    'Hiring Desk <notice@recruiting-platform.example>',
])
def test_explicit_primary_employer_supports_company_scope_without_owned_domain(sender):
    apps = roles()
    ev = replace(evidence('Your application to Silverpine Labs was rejected.'), sender=sender, subject='Application decision')
    assert_company(reconcile(ev, apps), apps)


def test_named_role_interest_establishes_company_for_authenticated_recruiting_sender():
    ev = replace(evidence('We appreciate your interest in the Backend Developer position at Silverpine Labs. Your application was rejected.'),
                 sender='Hiring Desk <notice@recruiting-platform.example>', subject='Decision')
    assert_company(reconcile(ev, roles()), roles())


def test_exact_primary_claim_resolves_a_subject_with_a_role_after_the_company():
    ev = replace(evidence('Your application to Silverpine Labs was rejected.'),
                 sender='Hiring Desk <notice@recruiting-platform.example>',
                 subject='Your application at Silverpine Labs - Software Engineer')
    assert_company(reconcile(ev, roles()), roles())


def test_full_primary_subsidiary_claim_does_not_select_the_parent():
    parent = replace(APP, company='Silverpine', official_url='https://careers.silverpine.example/jobs')
    child = replace(APP, key='job:2', company='Silverpine Health', official_url='https://jobs.lever.co/silverpinehealth/fictional')
    ev = replace(evidence('Your application to Silverpine Health was rejected.'),
                 sender='Silverpine Talent <talent@careers.silverpine.example>', subject='Application decision')
    assert_company(reconcile(ev, [parent, child]), [parent, child], child.company)


def test_legal_suffix_normalization_returns_a_real_canonical_company_name():
    app = replace(APP, company='Silverpine Labs Ltd')
    ev = replace(evidence('Your application to Silverpine Labs, Inc. was rejected.'),
                 sender='Hiring Desk <notice@recruiting-platform.example>', subject='Decision')
    # Use an independent personal assertion so punctuation in the legal suffix
    # cannot accidentally provide or remove semantic decision evidence.
    ev = replace(ev, body='Your application to Silverpine Labs, Inc. is being considered. Your application was rejected.')
    assert_company(reconcile(ev, [app]), [app], app.company)


@pytest.mark.parametrize('body', [
    'Your application to Silverpine Labs and Copperfin was rejected.',
    'Your application to Silverpine Labs was received. Your application with Copperfin was rejected.',
])
def test_competing_primary_employers_remain_unresolved(body):
    other = replace(APP, key='job:2', company='Copperfin', official_url='https://careers.copperfin.example/jobs')
    result = reconcile(evidence(body), roles() + [other])
    assert result.disposition != 'company_rejection' and result.company is None


def test_conflicting_subject_and_body_application_employers_are_not_collapsed():
    other = replace(APP, key='job:2', company='Copperfin', official_url='https://careers.copperfin.example/jobs')
    ev = evidence('Your application to Copperfin was rejected.', 'Your application at Silverpine Labs')
    assert reconcile(ev, roles() + [other]).company is None


def test_untracked_subsidiary_never_becomes_its_parent_by_substring():
    ev = evidence('Your application to Silverpine Labs Health was rejected.')
    result = reconcile(ev, roles())
    assert result.company is None and result.disposition != 'company_rejection'


@pytest.mark.parametrize('body', [
    'Your application was rejected. Silverpine Labs has several openings.',
    'Your application was rejected. We are interested in new roles at Silverpine Labs.',
    'Your application was rejected. Our interest in research at Silverpine Labs continues.',
    'Your application was rejected. If your application is at Silverpine Labs, contact us.',
    'Your application was rejected. For example, your application at Silverpine Labs may need attention.',
    'Your application was rejected. "Your application at Silverpine Labs" is sample wording.',
])
def test_generic_conditional_and_quoted_mentions_do_not_establish_company(body):
    ev = replace(evidence(body), sender='Hiring Desk <notice@recruiting-platform.example>', subject='Decision')
    result = reconcile(ev, roles())
    assert result.company is None and result.disposition != 'company_rejection'


@pytest.mark.parametrize('change', ['unauthenticated', 'personal', 'partial', 'contradiction', 'positive', 'unknown_employer', 'no_applications'])
def test_company_scope_does_not_bypass_evidence_and_sender_guards(change):
    apps = roles()
    ev = evidence('Your application was rejected.')
    if change == 'unauthenticated':
        ev = replace(ev, sender_authenticated=False)
    elif change == 'personal':
        ev = replace(ev, sender='Silverpine Labs <recruiter@gmail.com>', body='Your application to Silverpine Labs was rejected.')
    elif change == 'partial':
        ev = replace(ev, complete=False)
    elif change == 'contradiction':
        ev = replace(ev, body='Your application was rejected. Your application remains under review.')
    elif change == 'positive':
        ev = replace(ev, body='Your application to Silverpine Labs led to an interview. We invite you to a technical interview.')
    elif change == 'unknown_employer':
        ev = replace(ev, sender='Hiring Desk <notice@recruiting-platform.example>', subject='Application decision', body='Your application to Untracked Systems was rejected.')
    elif change == 'no_applications':
        apps = []
    result = reconcile(ev, apps)
    assert result.disposition != 'company_rejection' and result.company is None
