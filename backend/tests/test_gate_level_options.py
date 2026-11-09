"""Alternative job levels retain a lower route without excusing shared requirements."""
import pytest

from backend.app.intelligence.eligibility import PROFILES, EligibilityReasonCode, EligibilityStatus, evaluate_job
from backend.app.models.job import CanonicalJob

LEVELS = (
    'A minimum of two years of experience in software development. '
    'Knowledge of Python for a Software Engineer 2.\n'
    'A minimum of five years of experience in software development. '
    'Knowledge of Python for a Software Engineer 3.\n'
)
MENU = (
    "This position may be filled at multiple career levels based on the candidate's qualifications.\n"
    'Junior (0 to 4 years)\nMid-Level (5 to 9 years)\n'
    'Senior (10 to 14 years)\nPrincipal (15 or more years)\n'
    'These ranges are guidelines for the level at which this position is filled.\n'
)


def decide(title, requirements, profile=None):
    job = CanonicalJob(
        source='test', company='Fictional Software', external_id='level-options',
        title=title, location='Seattle, WA', employment_type='full-time',
        description=('Build services in Python and Go. Work with our engineering team, '
                     'review code, document designs and support production software.\n' + requirements),
        official_url='https://jobs.fictional.example/level-options',
    )
    return evaluate_job(job, profile) if profile else evaluate_job(job)


@pytest.mark.parametrize('title,requirements', (
    ('Software Engineer 2/3', LEVELS),
    ('Software Engineer II/III', LEVELS),
    ('Software Engineer', 'This is a multi-level posting.\n' + LEVELS),
    ('Software Engineer 2/3', LEVELS.replace('two', '2').replace('five', '5')),
))
def test_explicit_level_options_keep_the_lower_requirements(title, requirements):
    d = decide(title, requirements)
    assert d.status is EligibilityStatus.PASS, d.reasons
    assert d.required_experience_years == 2


@pytest.mark.parametrize('title', ('Software Engineer', 'Software Engineer 3'))
def test_other_levels_in_the_description_do_not_change_a_single_level_role(title):
    d = decide(title, LEVELS)
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes


@pytest.mark.parametrize('shared', (
    'All candidates require at least six years of professional experience.',
    'Requires 6+ years of professional experience.',
))
def test_shared_experience_is_still_required(shared):
    d = decide('Software Engineer 2/3', LEVELS + shared)
    assert d.status is EligibilityStatus.REJECT
    assert d.required_experience_years == 6


@pytest.mark.parametrize('profile', PROFILES.values(), ids=lambda p: p.key)
def test_lower_level_still_uses_the_same_three_plus_policy(profile):
    d = decide('Software Engineer 2/3', LEVELS.replace('two', 'three'), profile)
    assert d.required_experience_years == 3
    assert (d.status is EligibilityStatus.PASS) is (profile.key == 'sde2')


@pytest.mark.parametrize('menu', (MENU, MENU.replace('15 or more', '15+')))
def test_explicit_multilevel_menu_retains_the_junior_range(menu):
    d = decide('AI/ML Engineer', menu + 'Qualifications\nPython proficiency and software engineering experience.')
    assert d.status is EligibilityStatus.PASS, d.reasons
    assert d.required_experience_years == 0
    assert EligibilityReasonCode.EARLY_CAREER_SIGNAL in d.reason_codes


def test_a_level_menu_does_not_remove_a_shared_minimum():
    d = decide('AI/ML Engineer', MENU + 'All candidates require at least five years of software development experience.')
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes


def test_a_menu_with_no_lower_route_keeps_the_high_bar():
    d = decide('AI/ML Engineer', MENU.replace('Junior (0 to 4 years)\n', '').replace('Mid-Level (5 to 9 years)\n', ''))
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes


def test_a_salary_legend_does_not_imply_this_role_offers_a_junior_route():
    d = decide('AI/ML Engineer', MENU.replace("This position may be filled at multiple career levels based on the candidate's qualifications.\n", '') + 'Requires 5+ years of software experience.')
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes


@pytest.mark.parametrize('wording', (
    "We're not considering applicants that need any type of immigration sponsorship now or in the future.",
    'We are not considering applicants who require visa sponsorship for this position.',
))
def test_lower_level_does_not_override_explicit_sponsorship_refusal(wording):
    d = decide('Software Engineer 2/3', LEVELS + wording)
    assert EligibilityReasonCode.SPONSORSHIP_BLOCKER in d.reason_codes


@pytest.mark.parametrize('wording', (
    'We are considering applicants who require visa sponsorship for this position.',
    'We are not considering applicants who do not require visa sponsorship for this position.',
))
def test_positive_and_opposite_sponsorship_wording_are_not_refusals(wording):
    d = decide('Software Engineer', 'Requires 2 years of software experience. ' + wording)
    assert d.status is EligibilityStatus.PASS, d.reasons
