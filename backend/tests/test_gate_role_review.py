"""The approved role list uses fictional postings and the ordinary gate."""

import pytest

from backend.app.intelligence.eligibility import (
    PROFILES,
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import RoleFamily, classify_role
from backend.app.models.job import CanonicalJob


BODY = (
    "Build software in Python and Go with a small engineering team. "
    "Design services, review code and document changes for our users. "
    "This full-time position is based in Seattle, WA. Our team offers "
    "paid leave, health insurance and a learning budget. "
)

SOFTWARE_TITLES = (
    "Software Developer Engineer 1",
    "Software Engineering Rotation Program",
    "Software Rotation Program",
    "Software Rotational Development Program",
    "Software Development Program",
    "Software Development Rotational Program",
    "Software Tools Developer",
    "Software Tools Engineer",
    "Software Integration Engineer",
    "Software Systems Engineer",
    "Software Systems Integration Engineer",
    "Algorithm Developer New Grad",
    "Software Engineer, Infrastructure",
    "Software Engineer, Product Engineering",
    "Founding Engineer",
    "Member of Technical Staff",
    "Real-Time Software Engineer",
)
AI_TITLES = (
    "Software Machine Learning Engineer",
    "Associate Engineer - Analytical AI Engineering",
    "Computer Vision/Machine Learning/Deep Learning Algorithm Developer",
    "ML Infrastructure Engineer",
    "AI Platform Engineer",
)
DATA_TITLES = (
    ("Data Engineer", RoleFamily.DATA_ENGINEERING),
    ("Data Engineer II", RoleFamily.DATA_ENGINEERING),
    ("Analytics Engineer", RoleFamily.DATA_ENGINEERING),
    ("Data Scientist", RoleFamily.DATA_SCIENCE),
    ("Data Scientist II", RoleFamily.DATA_SCIENCE),
    ("Applied Scientist II", RoleFamily.DATA_SCIENCE),
)


def posting(title, requirement=""):
    return CanonicalJob(
        source="test", company="Fictional Labs",
        external_id="role-review", title=title, location="Seattle, WA",
        description=BODY + requirement,
        official_url="https://jobs.fictional.example/role-review",
        employment_type="full-time",
    )


@pytest.mark.parametrize("title", SOFTWARE_TITLES)
def test_approved_software_titles_are_recognized(title):
    assert classify_role(title).family is RoleFamily.SOFTWARE_ENGINEERING


@pytest.mark.parametrize("title", AI_TITLES)
def test_approved_ai_titles_are_recognized(title):
    assert classify_role(title).family is RoleFamily.AI_ML_ENGINEERING


@pytest.mark.parametrize("title,family", DATA_TITLES)
def test_approved_data_titles_reuse_the_existing_families(title, family):
    assert classify_role(title).family is family


@pytest.mark.parametrize("profile", PROFILES.values(), ids=lambda p: p.key)
@pytest.mark.parametrize("title", SOFTWARE_TITLES + AI_TITLES + tuple(t for t, _ in DATA_TITLES))
def test_kept_roles_use_the_same_experience_gate(title, profile):
    decision = evaluate_job(posting(title, "Requires 2 years of relevant experience."), profile)
    assert decision.status is EligibilityStatus.PASS, decision.reasons


@pytest.mark.parametrize("title", (
    "Compiler Engineer", "Software Engineer, Compilers", "ML Compiler Engineer",
    "AI Engineer - Compiler Development", "Software Engineer, Compilation",
    "Runtime Engineer", "Software Engineer, Runtime", "ML Runtime Engineer",
    "Software Engineer, Run-Time Systems",
    "QA Engineer", "SDET", "Software Development Engineer in Test",
    "Software Engineer in Test", "Software Test Engineer",
    "Software Quality Engineer", "Software Engineer - Test Automation",
    "ML Engineer, Quality Assurance",
))
def test_excluded_trades_cannot_pass_through_a_generic_or_ml_title(title):
    decision = evaluate_job(posting(title))
    assert decision.status is EligibilityStatus.REJECT
    assert EligibilityReasonCode.NON_TARGET_ROLE in decision.reason_codes


@pytest.mark.parametrize("title", (
    "Engineering Development Program", "Manufacturing Rotation Program",
    "Hardware Algorithm Developer", "Software Integration Sales Engineer",
    "Software Systems Support Engineer", "Senior Software Tools Developer",
    "Data Engineering Manager", "Lead Data Scientist", "Infrastructure Engineer",
    "Senior Member of Technical Staff", "Staff Member of Technical Staff",
    "Principal Member of Technical Staff", "Member of Technical Staff (L5)",
    "Member of Technical Staff 4",
    "Platform Engineer", "Cloud Engineer", "DevOps Software Engineer",
    "Site Reliability Engineer", "Android Software Engineer", "Security Software Engineer",
    "Embedded Software Engineer", "Product Engineer",
))
def test_role_additions_do_not_admit_other_trades_or_seniority(title):
    assert evaluate_job(posting(title)).status is EligibilityStatus.REJECT


@pytest.mark.parametrize("title", (
    "Software Systems Engineer", "Software Integration Engineer", "Algorithm Developer",
    "Data Engineer II", "Analytics Engineer", "Data Scientist II", "Applied Scientist II",
))
@pytest.mark.parametrize("requirement,reason", (
    ("A PhD is required for this position.", EligibilityReasonCode.PHD_TARGETED_ROLE),
    ("Requires 4 years of professional experience.", EligibilityReasonCode.EXPERIENCE_TOO_HIGH),
    ("Requires 3+ years of professional experience.", EligibilityReasonCode.EXPERIENCE_TOO_HIGH),
    ("We will not sponsor candidates.", EligibilityReasonCode.SPONSORSHIP_BLOCKER),
    ("Must be a U.S. citizen.", EligibilityReasonCode.CITIZENSHIP_BLOCKER),
))
def test_new_families_keep_phd_and_other_hard_requirements(title, requirement, reason):
    decision = evaluate_job(posting(title, requirement))
    assert decision.status is EligibilityStatus.REJECT
    assert reason in decision.reason_codes


@pytest.mark.parametrize("title", ("Data Engineer", "Data Scientist II", "Applied Scientist II"))
def test_silence_about_years_does_not_exclude_a_data_role(title):
    assert evaluate_job(posting(title)).status is EligibilityStatus.PASS
