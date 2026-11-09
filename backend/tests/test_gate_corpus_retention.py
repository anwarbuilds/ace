"""Real wording shapes use fictional postings and preserve the existing policy."""
import pytest

from backend.app.intelligence.eligibility import PROFILES, EligibilityReasonCode, EligibilityStatus, evaluate_job
from backend.app.models.job import CanonicalJob


def decide(requirement, profile=None):
    job = CanonicalJob(
        source='test', company='Fictional Robotics', external_id='corpus-retention',
        title='Software Engineer', location='Seattle, WA', employment_type='full-time',
        description=('Build Python services and review code with our team. '
                     'Design reliable software and document the results. ' + requirement),
        official_url='https://jobs.fictional.example/corpus-retention',
    )
    return evaluate_job(job, profile) if profile else evaluate_job(job)


@pytest.mark.parametrize('requirement', (
    "Educational background\n- MS or BS in computer science, with 2+ years of work experience\n- PhD in computer science also considered\nDesired skills\nPython proficiency.",
    "Qualifications (Required): Bachelor's or Master's degree in computer science. Recent graduates are encouraged to apply. PhD candidates are welcome to apply, particularly for hands-on software work.",
    'Minimum Qualifications\n- B.S./M.S, degree in computer science with 2+ years of industry experience; Ph.D. degree and publication records can be an exception.',
    'Qualifications\nPhD graduates are welcome to apply. Experience building Python services.',
))
def test_optional_doctoral_choices_stay_eligible(requirement):
    d = decide(requirement)
    assert d.status is EligibilityStatus.PASS, d.reasons


@pytest.mark.parametrize('requirement', (
    'Minimum qualifications\nPhD in computer science is required; other candidates are welcome to apply for different openings.',
    'Requirements\nA PhD is required and PhD candidates are welcome to apply.',
    'Requirements\nPhD in computer science. Applicants with publications are also considered for research awards.',
    'Requirements\nPhD in computer science; publications are also considered for research awards.',
))
def test_required_doctorate_is_not_excused_by_an_unrelated_invitation(requirement):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in decide(requirement).reason_codes


@pytest.mark.parametrize('profile', PROFILES.values(), ids=lambda p: p.key)
@pytest.mark.parametrize('requirement,years,early_pass,sde2_pass', (
    ('Experience: Five or more years of professional experience in machine learning.', 5, False, False),
    ('You have at least three years of relevant experience in data science.', 3, False, True),
    ('Three or more years of hands-on experience in software engineering.', 3, False, True),
    ('A minimum of four years of software development experience.', 4, False, False),
    ('At least two years of relevant experience.', 2, True, True),
    ('Minimum twenty-three years of relevant experience.', 23, False, False),
    ('Minimum twenty\u00a0three years of relevant experience.', 23, False, False),
    ('Minimum thirty one years of relevant experience.', 31, False, False),
    ('5 or more years of relevant experience.', 5, False, False),
))
def test_written_minimums_reuse_the_existing_experience_limits(requirement, years, early_pass, sde2_pass, profile):
    d = decide(requirement, profile)
    assert d.required_experience_years == years
    expected = early_pass if profile.key == 'early-career' else sde2_pass
    assert (d.status is EligibilityStatus.PASS) is expected, d.reasons


@pytest.mark.parametrize('requirement', (
    'Requires 2 years of relevant experience. Our two co-founders have at least twelve years of combined experience.',
    'Requires 2 years of relevant experience. Preferred qualifications\nAt least five years of relevant experience.',
    'Requires 2 years of relevant experience. You think the next five years of software engineering will change our industry.',
    "Requires a bachelor's degree. Ten or more years of professional experience may be considered in place of a bachelor's degree.",
    "Requires a bachelor's degree. 10+ years of professional experience may be considered in place of a bachelor's degree.",
    "Requires a master's degree. Ten or more years of professional experience can be accepted in lieu of a master's degree.",
))
def test_written_figures_keep_company_preferred_and_degree_alternatives(requirement):
    d = decide(requirement)
    assert d.status is EligibilityStatus.PASS, d.reasons


def test_a_later_degree_alternative_does_not_excuse_the_real_experience_bar():
    d = decide("Requires 5+ years of relevant experience. Ten years may be considered in place of a bachelor's degree.")
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes


def test_a_second_figure_in_the_same_sentence_does_not_excuse_the_real_bar():
    d = decide("Requires 5+ years of professional experience and ten years may be considered in place of a bachelor's degree.")
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in d.reason_codes
