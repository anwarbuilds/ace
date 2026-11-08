"""Doctorate-only qualifications differ from optional and alternative degrees."""

import pytest
from backend.app.intelligence.eligibility import EligibilityReasonCode,EligibilityStatus,evaluate_job
from backend.app.models.job import CanonicalJob


def decide(requirement):
    return evaluate_job(CanonicalJob(
        source='test',company='Fictional Labs',external_id='doctoral-qualification',
        title='Applied Scientist',location='Seattle, WA',
        description='Build production models using Python and Go. '+requirement+
                    '\nWork with our software team to design models, review code and document results. '*3,
        official_url='https://jobs.fictional.example/doctoral-qualification',
    ))


@pytest.mark.parametrize('requirement',(
    'Minimum requirements\n- Ph.D. in Computer Science or a closely related field.',
    'Qualifications PhD in computer science, electrical engineering, or related field.',
    'About you\nRequired:\n- PhD in Computer Science, Robotics or Machine Learning.',
    'What you have\nPhD in robotics or computer science, with research publications.',
    'Requirements\nA PhD in computer science or mathematics.',
    'Qualifications\nYou hold a PhD in Machine Learning.',
    'Qualifications\nPhD or equivalent research experience in machine learning.',
    'YOU\u2019LL HAVE\n- PhD or equivalent research experience in machine learning.',
    'WHAT WE\u2019RE LOOKING FOR\n- PhD in computer science.',
    'WHAT ARE WE LOOKING FOR?\n- PhD in machine learning or a related field.',
    "What You'll Need to Succeed PhD in computer science or a related field.",
    'What You\u2019ll Need to Succeed PhD in computer science or a related field.',
    'Requirements\nCurrently enrolled in or recently graduated from a PhD program in computer science.',
    'Qualifications\nPhD in computer science or mathematics, based in MA.',
    'We are looking for Computer Science and Math PhD researchers to build our models.',
))
def test_doctorate_targeted_qualifications_reject(requirement):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in decide(requirement).reason_codes


def test_plural_phds_in_the_title_still_names_a_doctoral_role():
    from backend.app.intelligence.eligibility import _is_phd_targeted_role
    assert _is_phd_targeted_role(CanonicalJob(
        source='test',company='Fictional Labs',external_id='plural-doctoral-title',
        title='Algorithm Developer - 2027 PhDs',location='Seattle, WA',
        description='Build software using Python and Go.',
        official_url='https://jobs.fictional.example/plural-doctoral-title',
    ))


@pytest.mark.parametrize('requirement',(
    "Qualifications\nBachelor's, Master's, or PhD in computer science.",
    'Qualifications\nB.S., M.S., Ph.D. in computer science or related fields.',
    'Requirements\nMS or PhD in computer science or mathematics.',
    "Qualifications\nPhD or Master's degree in computer science.",
    'Preferred qualifications\nPh.D. in computer science.',
    'Preferred requirements\nPhD in computer science.',
    'Qualifications\nPh.D. in computer science preferred.',
    'Requirements\nA PhD is not required. Strong research instincts matter.',
    "Qualifications\nCandidates don't need a PhD or extensive publications.",
    'Requirements\nExperience working with PhD scientists on software products.',
    'Requirements\nCollaborate with researchers. Nice to have\nPhD in computer science.',
    'Requirements\nDegree (BS, MS, or PhD) in computer science or equivalent practical experience.',
    'Qualifications\n2 years of coding experience or a relevant PhD degree.',
    'Requirements\nWe are not looking for PhD researchers. We welcome graduates.',
    'Qualifications\nPhD in computer science is a plus.',
    'Qualifications\nPh.D. in computer science is not essential.',
    'Requirements\nIt would be great if you have a PhD in computer science.',
))
def test_optional_alternative_or_incidental_doctorate_mentions_stay_eligible(requirement):
    decision=decide(requirement)
    assert decision.status is EligibilityStatus.PASS,decision.reasons


@pytest.mark.parametrize('requirement',(
    'Build and review algorithms with our software team. - PhD in computer science - Experience programming in Python.',
    'Build and review algorithms with our software team. - PhD or equivalent research experience - Experience programming in Python.',
    'Required Qualifications Education. Doctoral degree (PhD) in computer science. Programming experience in Python.',
    'Qualifications\n- Currently has, or is in the process of obtaining, a PhD in computer science.',
    "What You'll Bring\n- Research Pedigree: PhD in computer science or equivalent research experience.",
))
def test_flattened_or_labelled_doctoral_requirements_reject(requirement):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in decide(requirement).reason_codes


@pytest.mark.parametrize('requirement',(
    'Build our models. - PhD or Master\'s degree in computer science - Experience programming in Python.',
    'Build our models. - PhD in computer science preferred - Experience programming in Python.',
    'Our collaborators include PhD researchers. Work with them to build production software.',
    'Our research community\n- PhD students collaborate with our software team.',
    'Preferred qualifications\nYou have a PhD in computer science.',
))
def test_flattened_optional_alternative_and_team_degree_mentions_stay_eligible(requirement):
    decision=decide(requirement)
    assert decision.status is EligibilityStatus.PASS,decision.reasons


@pytest.mark.parametrize('requirement',(
    'Sourced from a curated new-graduate listing. Degrees considered: PhD.',
    'Responsibilities Build models About You Required Qualifications PhD in computer science Preferred Qualifications Experience with deployment.',
))
def test_single_doctoral_degree_and_flattened_required_section_reject(requirement):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in decide(requirement).reason_codes


@pytest.mark.parametrize('requirement',(
    "Sourced from a curated new-graduate listing. Degrees considered: Master's, PhD.",
    'Preferred qualifications You have a PhD in computer science Required qualifications Experience programming in Python.',
))
def test_flattened_optional_and_alternate_degree_sections_remain_eligible(requirement):
    decision=decide(requirement)
    assert decision.status is EligibilityStatus.PASS,decision.reasons


@pytest.mark.parametrize('requirement',(
    "Qualifications\nBachelor's degree and 2 years of software experience.\nOR\nPhD in computer science.",
    "Qualifications\nMaster's degree and 1 year of software experience.\nOR\nPhD in computer science.",
    "Qualifications\nPhD in computer science.\nOR\nMaster's degree and 2 years of software experience.",
    "Qualifications\nBachelor's degree and 2+ years of software experience.\nOR\nMaster's degree and 1+ years of software experience.\nOR\nPhD in computer science.",
    "Required qualifications\nMaster's degree\nin computer science with 2 years of software experience.\nOR\nPhD in computer science.",
    "Required qualifications\nPhD in computer science.\nOR\nMaster's degree\nin computer science with 2 years of software experience.",
    'Minimum qualifications\nExperience building Python services.\nThe Extras That Set You Apart\nPhD in computer science.',
    'Requirements\nExperience building Python services.\nExtras that set you apart\nPhD in computer science.',
    "Requirements\nMaster's degree in computer science.\n\nOR\n\nPhD in computer science.",
))
def test_separate_degree_alternatives_and_extras_stay_eligible(requirement):
    decision=decide(requirement)
    assert decision.status is EligibilityStatus.PASS,decision.reasons


@pytest.mark.parametrize('requirement',(
    'Qualifications\nPhD in computer science.\nOR\nEquivalent advanced research experience.',
    "We support master's degree programs for employees.\n\nRequirements\nPhD in computer science.",
    'Required qualifications\nPhD in computer science.\nThe Extras That Set You Apart\nPython proficiency.',
))
def test_linked_degrees_do_not_excuse_a_doctoral_only_requirement(requirement):
    assert EligibilityReasonCode.PHD_TARGETED_ROLE in decide(requirement).reason_codes
