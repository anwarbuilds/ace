"""Measured title shapes retain the approved role and ordinary hard blockers."""
import pytest

from backend.app.intelligence.eligibility import PROFILES, EligibilityReasonCode, EligibilityStatus, evaluate_job
from backend.app.intelligence.roles import RoleFamily, classify_role
from backend.app.models.job import CanonicalJob

TITLES = (
    ('Software Mach. Learn Engr (GNSS, Software Defined Radio)', RoleFamily.AI_ML_ENGINEERING),
    ('Software Mach Learn Engr', RoleFamily.AI_ML_ENGINEERING),
    ('Software Machine Learning Engr', RoleFamily.AI_ML_ENGINEERING),
    ('Leadership Development Program - Engineering, Software Discipline (Starts June 2027)', RoleFamily.SOFTWARE_ENGINEERING),
    ('Leadership Development Program \u2013 Engineering, Software Discipline (Starts June 2027)', RoleFamily.SOFTWARE_ENGINEERING),
    ('Development Programme: Engineering / Software Discipline', RoleFamily.SOFTWARE_ENGINEERING),
)


def posting(title, requirement=''):
    return CanonicalJob(
        source='test', company='Fictional Systems', external_id='measured-shape',
        title=title, location='Seattle, WA', employment_type='full-time',
        description=('Build Python services and review code with our engineering team. '
                     'This full-time software role includes testing, documentation and design work. '
                     'We offer paid leave and health insurance. ' + requirement),
        official_url='https://jobs.fictional.example/measured-shape',
    )


@pytest.mark.parametrize('title,family', TITLES)
def test_measured_alias_has_the_approved_family(title, family):
    assert classify_role(title).family is family


@pytest.mark.parametrize('profile', PROFILES.values(), ids=lambda p: p.key)
@pytest.mark.parametrize('title,family', TITLES)
def test_measured_alias_passes_under_common_experience_rules(title, family, profile):
    decision = evaluate_job(posting(title, 'Requires 2 years of relevant experience.'), profile)
    assert decision.status is EligibilityStatus.PASS, decision.reasons


@pytest.mark.parametrize('title,family', TITLES)
@pytest.mark.parametrize('requirement,code', (
    ('Requires 5 years of relevant experience.', EligibilityReasonCode.EXPERIENCE_TOO_HIGH),
    ('We cannot provide visa sponsorship for this role.', EligibilityReasonCode.SPONSORSHIP_BLOCKER),
    ('A PhD in computer science is required.', EligibilityReasonCode.PHD_TARGETED_ROLE),
))
def test_measured_alias_does_not_excuse_hard_blockers(title, family, requirement, code):
    decision = evaluate_job(posting(title, requirement))
    assert decision.status is EligibilityStatus.REJECT
    assert code in decision.reason_codes


@pytest.mark.parametrize('title', (
    'Leadership Development Program - Engineering, Mechanical Discipline',
    'Leadership Development Program - Sales, Software Discipline',
    'Software Mach Learn Technician',
))
def test_other_trades_do_not_inherit_the_alias(title):
    assert classify_role(title).family is RoleFamily.OTHER
