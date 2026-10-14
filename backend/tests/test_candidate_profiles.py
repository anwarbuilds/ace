"""Who the gate admits, under each candidate profile.

The owner has three years of experience. New grad roles are the primary
target; SDE II comes in under the "sde2" profile, which differs from
"early-career" in exactly one place: an open-ended "3+ years" bar. Every
other case in this table must decide the same way under both, because
the switch must not quietly change anything else.
"""

import pytest

from backend.app.intelligence.eligibility import (
    PROFILES,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    classify_role,
)
from backend.app.models.job import CanonicalJob


BODY = (
    "We build distributed systems with Python and Go. You will design, "
    "build and operate services used by millions of customers, working "
    "closely with product and design. This is a full-time role based in "
    "Seattle, WA. Benefits include health insurance and a 401k. "
)

PASS = EligibilityStatus.PASS
REJECT = EligibilityStatus.REJECT


def job(title: str, requirement: str = "") -> CanonicalJob:
    return CanonicalJob(
        source="greenhouse",
        company="Example Co",
        external_id="1",
        title=title,
        location="Seattle, WA",
        description=BODY + requirement,
        official_url="https://boards.example.com/1",
    )


# (title, requirement text, early-career, sde2)
CASES = [
    ("Software Engineer II", "2+ years of professional software development experience.", PASS, PASS),
    ("Software Engineer II", "3+ years of professional software development experience.", REJECT, PASS),
    ("SDE II", "3+ years of professional software development experience.", REJECT, PASS),
    ("SDE II", "2-4 years of professional software development experience.", PASS, PASS),
    ("Software Engineer", "3 years of experience with backend development required.", PASS, PASS),
    ("Software Engineer II", "4+ years of professional software development experience.", REJECT, REJECT),
    ("Software Engineer", "5+ years of professional software development experience.", REJECT, REJECT),
    ("Software Engineer III", "", REJECT, REJECT),
    ("Software Engineer III", "2+ years of professional software development experience.", PASS, PASS),
    ("Software Engineer (L4)", "", REJECT, REJECT),
    ("Software Engineer (L5)", "", REJECT, REJECT),
    ("Senior Software Engineer", "3+ years of professional software development experience.", REJECT, REJECT),
    ("Staff Software Engineer", "", REJECT, REJECT),
    ("Engineering Manager", "3+ years of professional software development experience.", REJECT, REJECT),
    ("Software Engineer, New Grad", "", PASS, PASS),
    # Silence about experience is unknown, never a rejection.
    ("Software Engineer II", "", PASS, PASS),
    # Preferred is not required.
    ("Software Engineer I", "3+ years of professional experience preferred, 1+ years required.", PASS, PASS),
    # An early-career label does not override an open-ended bar the
    # profile rejects; under sde2 the owner meets it.
    ("Software Engineer, Early Career", "3+ years of professional software development experience.", REJECT, PASS),
]


@pytest.mark.parametrize(("title", "requirement", "early", "sde2"), CASES)
def test_each_profile_decides_as_specified(title, requirement, early, sde2) -> None:
    posting = job(title, requirement)

    assert evaluate_job(posting, PROFILES["early-career"]).status is early
    assert evaluate_job(posting, PROFILES["sde2"]).status is sde2


def test_the_profiles_differ_only_on_the_open_ended_bar() -> None:
    a, b = PROFILES["early-career"], PROFILES["sde2"]

    assert a.experience_years == b.experience_years == 3
    assert a.max_required_years == b.max_required_years == 4
    assert (a.max_open_ended_years, b.max_open_ended_years) == (3, 4)


def test_a_decision_carries_its_profiles_rule_version() -> None:
    posting = job("Software Engineer, New Grad")

    for profile in PROFILES.values():
        assert evaluate_job(posting, profile).rule_version == profile.rule_version

    assert len({p.rule_version for p in PROFILES.values()}) == len(PROFILES)


@pytest.mark.parametrize(
    "title",
    ["SDE II", "SDE-II", "SDE 2", "SDE I", "SDE II, AWS", "Software Dev Engineer II"],
)
def test_sde_titles_are_software_engineering(title) -> None:
    assert classify_role(title).family is RoleFamily.SOFTWARE_ENGINEERING



def test_a_senior_sde_is_still_rejected() -> None:
    assert evaluate_job(job("Sr. SDE"), PROFILES["sde2"]).status is REJECT


def test_an_unknown_profile_name_is_an_error(monkeypatch) -> None:
    """A typo must not quietly change who the gate admits."""

    import backend.app.intelligence.eligibility as gate

    monkeypatch.setenv("ACE_TARGET_PROFILE", "sde-two")

    with pytest.raises(ValueError, match="ACE_TARGET_PROFILE"):
        gate._active_profile()


def test_the_default_profile_is_early_career(monkeypatch) -> None:
    import backend.app.intelligence.eligibility as gate

    monkeypatch.delenv("ACE_TARGET_PROFILE", raising=False)

    assert gate._active_profile().key == "early-career"


def test_the_switch_selects_sde2(monkeypatch) -> None:
    import backend.app.intelligence.eligibility as gate

    monkeypatch.setenv("ACE_TARGET_PROFILE", "sde2")

    assert gate._active_profile().key == "sde2"
