"""Employer history and applicant history are not role requirements."""

import pytest

from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    _open_ended_required_years,
    _required_experience_years,
    evaluate_job,
    is_internship,
)
from backend.app.models.job import CanonicalJob


def job(title="Software Engineer (New Grad)", description=""):
    return CanonicalJob(
        source="test", company="Fictional Labs", external_id="history-context",
        title=title, location="Tallahassee FL + 1 more",
        description=description or (
            "Build full-time software services using Python and Go. Review code and "
            "design reliable APIs with our engineering team. " * 3
        ),
        official_url="https://jobs.fictional.example/history-context",
    )


@pytest.mark.parametrize("history", (
    "Our three co-founders have worked together for 12+ years, across two companies.",
    "Our founders have worked together for 12+ years.",
    "The founders have worked together for 12+ years.",
))
def test_founder_history_is_not_an_open_ended_requirement(history):
    description = history + "\nRequirements\nExceptional college graduates welcome."
    assert _open_ended_required_years(description) is None
    assert _required_experience_years(description) is None
    decision = evaluate_job(job(description=description + " Build Python and Go services." * 8))
    assert decision.status is EligibilityStatus.PASS


@pytest.mark.parametrize("requirements,years", (
    ("Requirements\nYou have 5+ years of software engineering experience.", 5),
    ("Requirements\n5+ years in distributed systems.", 5),
    ("Qualifications\n12+ years of professional experience.", 12),
    ("Work with our founders. Requirements: 5+ years of experience.", 5),
    ("Our founders have worked together for 12+ years.\nRequirements\n5+ years of software engineering experience.", 5),
    ("Our three co-founders have worked together for 12+ years.\nRequirements\n5+ years in distributed systems.", 5),
))
def test_actual_candidate_requirement_stays_visible(requirements, years):
    assert _open_ended_required_years(requirements) == years
    assert _required_experience_years(requirements) == years
    assert EligibilityReasonCode.EXPERIENCE_TOO_HIGH in evaluate_job(
        job(description=requirements + " Build Python and Go services." * 8)
    ).reason_codes


@pytest.mark.parametrize("title", (
    "Returning New Grad Software Engineer I (For Current/Previous Fictional Labs Interns ONLY)",
    "Software Engineer (For Previous Interns Only)",
    "Software Engineer (For Former Interns Only)",
))
def test_previous_intern_eligibility_does_not_make_the_role_an_internship(title):
    assert not is_internship(job(title=title))
    assert evaluate_job(job(title=title)).status is EligibilityStatus.PASS


@pytest.mark.parametrize("title", (
    "Software Engineer Intern", "Software Engineer Internship", "Software Engineering Internships",
    "Intern Software Engineer (For Previous Interns Only)",
    "Software Engineer (Internship Only)", "Software Engineer Co-op",
    "Software Engineer Part-Time Student",
))
def test_genuine_internship_roles_stay_excluded(title):
    assert is_internship(job(title=title))
    assert EligibilityReasonCode.INTERNSHIP_ROLE in evaluate_job(job(title=title)).reason_codes


def test_past_internships_in_description_do_not_reject_full_time_role():
    description = (
        "Full-time software role. Requirements: experience from internships or bootcamps "
        "is welcome. Build production services in Python and Go. " * 3
    )
    assert not is_internship(job(description=description))
    assert evaluate_job(job(description=description)).status is EligibilityStatus.PASS
