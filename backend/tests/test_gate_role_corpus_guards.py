"""Fictional regressions for unwanted gains found by the corpus preview."""

import pytest

from backend.app.intelligence.eligibility import EligibilityStatus, evaluate_job
from backend.app.intelligence.roles import RoleFamily, classify_role
from backend.app.models.job import CanonicalJob


def posting(title):
    return CanonicalJob(
        source='test', company='Fictional Labs', external_id='corpus-guard',
        title=title, location='Seattle, WA',
        description=('Build software services using Python and Go. Review code, design APIs '
                     'and document changes with our team. This is a full-time position. ' * 3),
        official_url='https://jobs.fictional.example/corpus-guard',
    )


@pytest.mark.parametrize('title', (
    'Head of Data Science', 'Head of Data Engineering', 'Head of Analytics Engineering',
    'Member of Technical Staff - Head of Robotics',
    'Member of Technical Staff, TLM, Internal Tooling',
    'Data Science Level 3, BS+10 yrs or MS+8 yrs',
    'Data Science Level 3, BS+10 yrs or MS+8',
    'Data Scientist, BS AND MS + 5 yrs',
    'Data Scientist, BS+2 yrs and MS+5 yrs',
    'Member of Technical Staff - Platform Eng',
    'Member of Technical Staff, Platform Engineer',
    'Member of Technical Staff, Infrastructure Engineer',
    'Member of Technical Staff - Cloud Orchestration',
    'Member of Technical Staff, Platform',
    'Platform - Member of Technical Staff',
    'Member of Technical Staff - Product Eng',
    'Member of Technical Staff, IT',
    'Member of Technical Staff, Customer Success',
    'Member of Technical Staff, Brand Marketing Designer',
    'Member of Technical Staff, Product Design',
    'Member of Technical Staff, Web Design',
    'Member of Technical Staff, Business Systems',
    'Member of Technical Staff, Founding GTM',
    'Member of Technical Staff, Developer Relations',
    'Member of Technical Staff, Fleet Operations',
    'Member of Technical Staff, Analog Design Engineer',
    'Member of Technical Staff - Thin Films Engineer',
    'Member of Technical Staff, SoC Power and Physical Architect',
    'Member of Technical Staff - Physical Design',
    'Member of Technical Staff - Computational Biologist',
    'Member of Technical Staff, Statistical Genetics',
    'Member of Technical Staff, Translational Medicine',
    'Member of Technical Staff, Science',
))
def test_seniority_and_non_target_specialties_do_not_gain_through_new_families(title):
    assert evaluate_job(posting(title)).status is EligibilityStatus.REJECT


@pytest.mark.parametrize('title', (
    'Member of Technical Staff',
    'Member of Technical Staff - Make It Work',
    'Member of Technical Staff, Software Engineer',
    'Member of Technical Staff, Backend Engineer',
    'Member of Technical Staff, ML Infrastructure Engineer',
    'Member of Technical Staff - ML Infra',
    'Member of Technical Staff, LLM Infrastructure',
    'Member of Technical Staff - Post-Training Infrastructure',
    'Member of Technical Staff, Data Engineering',
    'Member of Technical Staff, Data Platform',
    'Member of Technical Staff, Software Engineer, Infrastructure',
    'Member of Technical Staff, Product Engineering',
    'Software Engineer, Product Engineering',
    'Software Engineer, Infrastructure',
    'Data Science Level 2, BS+3 yrs or MS+2 yrs',
    'Data Scientist, BS+5 yrs or MS+2 yrs',
    'Data Scientist, BS+10',  # No unit: this is not trusted as a years bar.
    'Data Scientist (3-5 years experience)',
    'AVP Data Science',  # Existing ordinary bank-title policy is retained.
))
def test_approved_core_and_data_roles_stay_eligible(title):
    assert evaluate_job(posting(title)).status is EligibilityStatus.PASS


def test_a_generic_staff_title_still_has_a_software_family():
    assert classify_role('Member of Technical Staff').family is RoleFamily.SOFTWARE_ENGINEERING


def test_paid_task_participation_is_outside_full_time_data_work():
    job = posting('Data Science & Analysis - AI Training').model_copy(update={
        'description': 'You are invited to join Fictional Labs as a participant. '
                       'You complete paid tasks to train and evaluate models.',
    })
    assert evaluate_job(job).status is EligibilityStatus.REJECT


def test_building_software_for_paid_studies_is_still_a_software_job():
    job = posting('Software Engineer').model_copy(update={
        'description': 'Build Python and Go software for researchers. Our platform '
                       'helps study participants find paid tasks. Join our engineering team.',
    })
    assert evaluate_job(job).status is EligibilityStatus.PASS
