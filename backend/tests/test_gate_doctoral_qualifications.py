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
