"""Tests for ACE's deterministic eligibility gate."""

import pytest

from backend.app.intelligence.eligibility import (
    ELIGIBILITY_RULE_VERSION,
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import (
    CanonicalJob,
)


def make_job(
    *,
    title: str = "Software Engineer",
    location: str = "Seattle, Washington",
    description: str = "",
) -> CanonicalJob:
    """Create a normalized test job."""

    return CanonicalJob(
        source="test",
        company="Example Company",
        external_id="test-123",
        title=title,
        location=location,
        description=description,
        official_url=(
            "https://example.com/jobs/test-123"
        ),
    )


def test_software_engineer_passes() -> None:
    decision = evaluate_job(
        make_job()
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.role_family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        decision.role_priority
        == RolePriority.PRIMARY
    )


def test_software_engineer_i_with_missing_experience_and_sponsorship_passes() -> None:
    decision = evaluate_job(
        make_job(
            title="Software Engineer I",
            description=(
                "Build and ship reliable "
                "software products."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.required_experience_years
        is None
    )


def test_new_grad_missing_experience_and_sponsorship_passes() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Software Engineer - New Grad"
            ),
            description=(
                "Join our engineering team "
                "and build customer-facing "
                "software."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.required_experience_years
        is None
    )


def test_ai_engineer_passes() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.role_family
        == RoleFamily.AI_ML_ENGINEERING
    )


def test_forward_deployed_engineer_passes() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Forward Deployed Engineer"
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.role_family
        == RoleFamily
        .FORWARD_DEPLOYED_ENGINEERING
    )

    assert (
        decision.role_priority
        == RolePriority.SECONDARY
    )


def test_remote_us_passes() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote - US",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_unknown_remote_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.STRETCH
    )

    assert (
        EligibilityReasonCode
        .LOCATION_UNCERTAIN
        in decision.reason_codes
    )


def test_worldwide_remote_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote - Worldwide",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.STRETCH
    )

    assert (
        EligibilityReasonCode
        .LOCATION_UNCERTAIN
        in decision.reason_codes
    )


def test_remote_europe_is_rejected() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote - Europe",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode.OUTSIDE_US
        in decision.reason_codes
    )


def test_non_us_location_rejected() -> None:
    decision = evaluate_job(
        make_job(
            location="Tokyo, Japan",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )


def test_non_target_role_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="Account Executive",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .NON_TARGET_ROLE
        in decision.reason_codes
    )


def test_senior_role_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Senior Software Engineer"
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )


def test_three_year_requirement_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Requires 3+ years of "
                "software engineering "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.STRETCH
    )

    assert (
        decision.required_experience_years
        == 3
    )


def test_four_year_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Requires 4+ years of "
                "software engineering "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )


def test_four_year_new_grad_role_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Software Engineer - New Grad"
            ),
            description=(
                "This early career role lists "
                "4+ years of related "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.STRETCH
    )


def test_seven_year_requirement_always_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
            description=(
                "Requires 7+ years of "
                "experience. Bachelor's "
                "degree or equivalent "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .EXPERIENCE_TOO_HIGH
        in decision.reason_codes
    )


def test_preferred_experience_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "4+ years of software "
                "engineering experience "
                "preferred."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_phd_in_title_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Software Engineer Intern - PhD"
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .PHD_TARGETED_ROLE
        in decision.reason_codes
    )


def test_phd_required_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Machine Learning Engineer"
            ),
            description=(
                "A PhD in Computer Science "
                "is required."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .PHD_TARGETED_ROLE
        in decision.reason_codes
    )


def test_doctoral_degree_required_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
            description=(
                "Doctoral degree required "
                "in computer science."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )


def test_phd_preferred_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Machine Learning Engineer"
            ),
            description=(
                "Bachelor's or Master's "
                "degree required. "
                "PhD preferred."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_bs_ms_phd_preferred_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "BS, MS, or PhD preferred "
                "in a relevant technical "
                "field."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_unknown_sponsorship_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Build scalable distributed "
                "systems using Python."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_explicit_no_sponsorship_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Candidates must be "
                "authorized to work without "
                "current or future "
                "sponsorship."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .SPONSORSHIP_BLOCKER
        in decision.reason_codes
    )


def test_ambiguous_remote_does_not_override_no_sponsorship_blocker() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote",
            description=(
                "The company cannot provide "
                "sponsorship for this role."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .SPONSORSHIP_BLOCKER
        in decision.reason_codes
    )


def test_citizenship_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Applicants must be "
                "a U.S. citizen."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )


def test_clearance_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Active security clearance "
                "required."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

# ----------------------------------------------------------------------
# Hardware-oriented embedded roles are out of scope
# ----------------------------------------------------------------------


def _job(
    *,
    title: str = "Software Engineer",
    description: str = (
        "Build reliable software systems."
    ),
    location: str = "Seattle, Washington",
) -> CanonicalJob:
    """Create one normalized job for gate tests."""

    return CanonicalJob(
        source="greenhouse",
        company="Example Co",
        external_id="1",
        title=title,
        location=location,
        description=description,
        official_url=(
            "https://example.com/jobs/1"
        ),
    )


def _codes(
    decision,
) -> set[str]:
    """Return reason codes as plain strings."""

    return {
        code.value
        for code in decision.reason_codes
    }


@pytest.mark.parametrize(
    "title",
    [
        "Embedded Software Engineer",
        "Embedded Software Engineer, Anti-Tamper",
        "Firmware Engineer",
        "Hardware Engineer",
        "FPGA Engineer",
        "Silicon Design Engineer",
        "Board Bring-Up Engineer",
    ],
)
def test_hardware_titles_are_rejected(
    title: str,
) -> None:
    """A hardware-oriented title is a decisive signal."""

    decision = evaluate_job(
        _job(
            title=title
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        in _codes(
            decision
        )
    )


def test_hardware_description_needs_multiple_signals() -> None:
    """Several distinct hardware signals reject a generic title."""

    decision = evaluate_job(
        _job(
            description=(
                "Develop mission software "
                "for microcontrollers using "
                "bare metal targets and an "
                "RTOS. Python tooling "
                "included."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        in _codes(
            decision
        )
    )


def test_two_hardware_mentions_are_not_enough() -> None:
    """An ML role that merely touches embedded targets stays in scope."""

    decision = evaluate_job(
        _job(
            title=(
                "Machine Learning Engineer"
            ),
            description=(
                "Build perception models in "
                "Python. Some exposure to "
                "embedded systems and UART "
                "interfaces is useful."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        not in _codes(
            decision
        )
    )


def test_hardware_markers_use_word_boundaries() -> None:
    """Short markers must not match ordinary words."""

    decision = evaluate_job(
        _job(
            description=(
                "You will report to Stuart "
                "and join quarterly planning "
                "in an inspired team writing "
                "Python."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        not in _codes(
            decision
        )
    )


def test_plural_hardware_markers_are_detected() -> None:
    """Plural forms are the same signal as their singular."""

    decision = evaluate_job(
        _job(
            description=(
                "Write device drivers for "
                "microcontrollers and read "
                "schematics."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        in _codes(
            decision
        )
    )


def test_single_passing_hardware_mention_still_passes() -> None:
    """A generic role that merely mentions firmware is not rejected."""

    decision = evaluate_job(
        _job(
            description=(
                "Experience with firmware is "
                "a plus, but we mostly write "
                "Python and Go services."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "HARDWARE_EMBEDDED_ROLE"
        not in _codes(
            decision
        )
    )


# ----------------------------------------------------------------------
# C / C++ only roles are out of scope
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "Strong C++ skills required.",
        "You will write C/C++ for our engine.",
        "Deep expertise in C and C++ required.",
        "We build everything in C++.",
    ],
)
def test_c_or_cpp_only_roles_are_rejected(
    description: str,
) -> None:
    """A role stating only C/C++ is excluded."""

    decision = evaluate_job(
        _job(
            description=description
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "SYSTEMS_LANGUAGE_ONLY"
        in _codes(
            decision
        )
    )


@pytest.mark.parametrize(
    "description",
    [
        "You will write C++ and Python services.",
        "Strong C++ and Go experience required.",
        "C/C++ plus Java on the platform team.",
        "CUDA C++ kernels alongside Python and PyTorch.",
        "C++ for the engine, TypeScript for tooling.",
        "Our stack is Go, Postgres and some C for hot paths.",
    ],
)
def test_c_or_cpp_with_another_language_passes(
    description: str,
) -> None:
    """Mixing C/C++ with any other language stays in scope."""

    decision = evaluate_job(
        _job(
            description=description
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "SYSTEMS_LANGUAGE_ONLY"
        not in _codes(
            decision
        )
    )


@pytest.mark.parametrize(
    "description",
    [
        "Build reliable distributed systems.",
        "Work across our backend services.",
    ],
)
def test_unstated_languages_are_not_rejection(
    description: str,
) -> None:
    """Silence about languages is unknown, not exclusion."""

    decision = evaluate_job(
        _job(
            description=description
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "SYSTEMS_LANGUAGE_ONLY"
        not in _codes(
            decision
        )
    )


def test_ordinary_prose_capital_c_is_not_the_c_language() -> None:
    """A stray capital letter must not read as a C requirement."""

    decision = evaluate_job(
        _job(
            description=(
                "You will work with Company C "
                "on Python services. "
                "Grade C candidates welcome."
            ),
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )


def test_rule_version_records_the_new_gate() -> None:
    """Stored evaluations can detect that the rules changed."""

    decision = evaluate_job(
        _job()
    )

    assert (
        decision.rule_version
        == ELIGIBILITY_RULE_VERSION
    )


# ----------------------------------------------------------------------
# Ambiguous country codes must not read as US states
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "location",
    [
        "Ottawa, ON, CA",
        "Vancouver, BC, CA",
        "Toronto, ON, Canada",
        "London, United Kingdom",
        "Bengaluru, India",
        "Berlin, Germany",
    ],
)
def test_explicit_non_us_locations_are_rejected(
    location: str,
) -> None:
    """A trailing 'CA' after a province code is Canada, not California."""

    decision = evaluate_job(
        _job(
            location=location
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )

    assert (
        "OUTSIDE_US"
        in _codes(
            decision
        )
    )


@pytest.mark.parametrize(
    "location",
    [
        "San Francisco, CA",
        "Ontario, California",
        "New York, NY",
        "Seattle, Washington",
        "Costa Mesa, California, United States",
        "Remote - US",
    ],
)
def test_us_locations_still_pass(
    location: str,
) -> None:
    """Disambiguation must not cost genuine US recall."""

    decision = evaluate_job(
        _job(
            location=location
        )
    )

    assert (
        "OUTSIDE_US"
        not in _codes(
            decision
        )
    )
