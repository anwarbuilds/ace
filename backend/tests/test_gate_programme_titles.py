"""Gate v68 / roles v9: an underscore reads as a space, technology programme titles that name no occupation read as
software, and "Software Engr" is software. Nothing that was out comes in by another trade, level or place."""
import pytest

from backend.app.intelligence.eligibility import PROFILES, EligibilityReasonCode, EligibilityStatus, evaluate_job
from backend.app.intelligence.roles import RoleFamily, classify_role
from backend.app.models.job import CanonicalJob


def posting(title, requirement='', location='Atlanta, GA', description=None):
    return CanonicalJob(
        source='test', company='Fictional Systems', external_id='programme-shape',
        title=title, location=location, employment_type='full-time',
        description=description if description is not None else (
            'Build Python services and review code with our engineering team. '
            'This full-time role includes testing, documentation and design work. ' + requirement),
        official_url='https://jobs.fictional.example/programme-shape',
    )


UNDERSCORE = (
    ('Data Scientist_ ANALYTICS', RoleFamily.DATA_SCIENCE),
    ('Software Engineer_Python (Hybrid Baltimore, MD)', RoleFamily.SOFTWARE_ENGINEERING),
    ('React Developer_Riverton, RI', RoleFamily.SOFTWARE_ENGINEERING),
    ('VT_Software Engineer - APD000 - Template', RoleFamily.SOFTWARE_ENGINEERING),
)

PROGRAMMES = (
    'Tech Accelarate Graduate Program',
    '2027 Technology Graduate Programme',
    'University Direct Hire Program - Technology',
    '2027 Technology Developer Graduate Programme',
    'Technology Rotational Development Program Associate',
    'Engineering Graduate Programme - Backend',
    '2027 Early Career Program-Software Engr I',
    'LINK 2027: Software Development Intensive Program',
    'Software Engr II',
)

STILL_OUT = (
    'Tech Accelerate Graduate Program - Business Analyst',
    'Technology Early Career Talent Program Manager',
    'Information Technology Rotational Development Program',
    'EDGE, IT Rotational Program',
    'Engineering Graduate Programme - Civil',
    'Graduate Leadership Program - Copywriter',
    'Technology Apprenticeship Program',
    '2027 Early Career Program-Tech Supp Professional',
    'Mission Technology Acceleration Program Lead',
    'Technical Art Graduate Program',
    'Technology Graduate',
    'Commercial Graduate Program - Sales Technology Path',
    '2027 Technology Development Program - Infrastructure Automation',
    '2027 Technology Development Program - Cloud Storage & Data Protection Engineer',
    '2027 Technology Development Program - Operating Systems Engineer',
    '2027 Technology Development Program - Application Observability',
)


@pytest.mark.parametrize('title,family', UNDERSCORE)
def test_underscore_reads_as_a_space(title, family):
    assert classify_role(title).family is family


def test_underscore_does_not_hide_seniority():
    decision = evaluate_job(posting('Senior_Software Engineer'))
    assert decision.status is EligibilityStatus.REJECT
    assert EligibilityReasonCode.SENIOR_TITLE in decision.reason_codes


@pytest.mark.parametrize('title', PROGRAMMES)
def test_technology_programme_is_software(title):
    assert classify_role(title).family is RoleFamily.SOFTWARE_ENGINEERING


@pytest.mark.parametrize('profile', PROFILES.values(), ids=lambda p: p.key)
@pytest.mark.parametrize('title', PROGRAMMES)
def test_technology_programme_passes_without_a_description(title, profile):
    decision = evaluate_job(posting(title, description=''), profile)
    assert decision.status is EligibilityStatus.PASS, decision.reasons


@pytest.mark.parametrize('title', STILL_OUT)
def test_other_programmes_stay_out(title):
    assert classify_role(title).family is RoleFamily.OTHER


@pytest.mark.parametrize('requirement,code', (
    ('Requires 5 years of relevant experience.', EligibilityReasonCode.EXPERIENCE_TOO_HIGH),
    ('We cannot provide visa sponsorship for this role.', EligibilityReasonCode.SPONSORSHIP_BLOCKER),
))
def test_programme_does_not_excuse_hard_blockers(requirement, code):
    decision = evaluate_job(posting('Tech Accelarate Graduate Program', requirement))
    assert decision.status is EligibilityStatus.REJECT
    assert code in decision.reason_codes


def test_programme_outside_the_us_stays_out():
    decision = evaluate_job(posting('2027 Technology Graduate Programme', location='London, United Kingdom'))
    assert decision.status is EligibilityStatus.REJECT
    assert EligibilityReasonCode.OUTSIDE_US in decision.reason_codes


def test_programme_internship_stays_out():
    decision = evaluate_job(posting('Technology Rotational Development Program Intern Summer 2027'))
    assert decision.status is EligibilityStatus.REJECT
