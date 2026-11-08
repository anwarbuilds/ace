"""Approved families retain the owner's trade, seniority and full-time limits."""
import pytest
from backend.app.intelligence.eligibility import EligibilityReasonCode,EligibilityStatus,evaluate_job
from backend.app.intelligence.roles import RoleFamily,classify_role
from backend.app.models.job import CanonicalJob


def posting(title,employment_type=None):
    return CanonicalJob(source='test',company='Fictional Labs',external_id='scope-guard',title=title,
        location='Seattle, WA',description='Build Python and Go software, review code and design reliable services. '*8,
        employment_type=employment_type,official_url='https://jobs.fictional.example/scope-guard')


@pytest.mark.parametrize('title',(
    'Chief Data Scientist','Analytics Engineering Supervisor','Data Engineering Leader',
    'Data Science and Analytics Leader','AI Data Scientist Technical Leader',
    'Managing Engineer, Data Engineering',
))
def test_explicit_leadership_remains_excluded(title):
    assert EligibilityReasonCode.SENIOR_TITLE in evaluate_job(posting(title)).reason_codes


@pytest.mark.parametrize('title',(
    'Founding IT Engineer','Founding Solutions Engineer','Solutions Engineer - Data Engineering',
    'IT Data Engineer and System Admin','Data Engineering/Analytics Support','Data Science Coach',
    'Product Owner - Data Engineering','Data Engineering Analyst - Data Engineering',
    'Medical Informaticist II - Institute for Computing, Data Science and Research',
    'Open Rank Faculty - Department of Data Science - Fictional University',
    'Member of Technical Staff - AI for Chip Design',
))
def test_explicit_other_trades_and_department_names_do_not_gain_target_families(title):
    assert classify_role(title).family is RoleFamily.OTHER


@pytest.mark.parametrize('title',(
    'Quality Automation Engineer II - Data Engineering','Test & Analytics Engineer',
    'Wireless Subsystem Test and Software Tools Engineer','Software Dev Engineer II-TEST',
))
def test_test_and_quality_occupations_remain_excluded(title):
    assert classify_role(title).family is RoleFamily.QUALITY_ASSURANCE


@pytest.mark.parametrize('title',(
    'Data Science Co Op - 2027','Data Science Student Assistant III',
))
def test_student_and_spaced_coop_titles_are_not_full_time_jobs(title):
    assert EligibilityReasonCode.INTERNSHIP_ROLE in evaluate_job(posting(title)).reason_codes


@pytest.mark.parametrize('title',(
    'Data Science and AI Postdoctoral Fellow','Postdoctoral Research Fellow - Data Science',
    'Applied Scientist - Postdoc',
))
def test_postdoctoral_titles_remain_doctorate_targeted(title):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in evaluate_job(posting(title)).reason_codes


@pytest.mark.parametrize('title',(
    'Member of Technical Staff - Research, Cyber','Data Scientist - Integrity and Safety',
    'Data Scientist - Trust & Safety','User and Entity Behavior Analytics Engineer',
))
def test_named_security_specialties_remain_excluded(title):
    assert EligibilityStatus.REJECT is evaluate_job(posting(title)).status


@pytest.mark.parametrize('title,kind',(
    ('Part-Time Data Scientist',None),('Data Engineer','part_time'),
    ('Data Scientist','part-time'),('Data Engineer','PART TIME'),
))
def test_explicit_part_time_roles_reject(title,kind):
    assert evaluate_job(posting(title,kind)).status is EligibilityStatus.REJECT


@pytest.mark.parametrize('title',(
    'Finance and Chief Data Office - Data Science Associate',
    'Technology Leadership Program - Data Science and AI',
    'Digital and IT Leadership Development Program - Data Science',
    'Data Scientist, Teacher Coaching','Data Scientist, Safety',
    'Data Scientist II - Institute for Computing, Data Science and Research',
    'Data Engineer/Analyst','Data Engineer, Technical Solutions',
    'Software Engineer, Product Owner Tools','Software Engineer, Support Tools',
    'Data Scientist, Cyber-Physical Systems','Software Engineer, Cyber Monday Systems',
    'Data Scientist (Full-Time or Part-Time)','Data Engineer II',
    'Member of Technical Staff, ML Infrastructure','Founding Engineer',
))
def test_explicit_allowed_work_and_department_qualifiers_stay_eligible(title):
    assert evaluate_job(posting(title)).status is EligibilityStatus.PASS
