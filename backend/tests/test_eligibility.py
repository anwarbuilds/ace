"""Tests for ACE's deterministic eligibility gate."""

from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import CanonicalJob


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
        official_url="https://example.com/jobs/test-123",
    )


def test_software_engineer_passes() -> None:
    decision = evaluate_job(
        make_job()
    )

    assert decision.status == EligibilityStatus.PASS
    assert decision.role_family == RoleFamily.SOFTWARE_ENGINEERING
    assert decision.role_priority == RolePriority.PRIMARY


def test_ai_engineer_passes() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
        )
    )

    assert decision.status == EligibilityStatus.PASS
    assert decision.role_family == RoleFamily.AI_ML_ENGINEERING


def test_forward_deployed_engineer_passes() -> None:
    decision = evaluate_job(
        make_job(
            title="Forward Deployed Engineer",
        )
    )

    assert decision.status == EligibilityStatus.PASS
    assert (
        decision.role_family
        == RoleFamily.FORWARD_DEPLOYED_ENGINEERING
    )
    assert decision.role_priority == RolePriority.SECONDARY


def test_remote_us_passes() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote - US",
        )
    )

    assert decision.status == EligibilityStatus.PASS


def test_unknown_remote_not_assumed_us() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote",
        )
    )

    assert decision.status == EligibilityStatus.REJECT
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

    assert decision.status == EligibilityStatus.REJECT


def test_non_target_role_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="Account Executive",
        )
    )

    assert decision.status == EligibilityStatus.REJECT
    assert (
        EligibilityReasonCode.NON_TARGET_ROLE
        in decision.reason_codes
    )


def test_senior_role_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="Senior Software Engineer",
        )
    )

    assert decision.status == EligibilityStatus.REJECT


def test_three_year_requirement_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Requires 3+ years of software engineering experience."
            ),
        )
    )

    assert decision.status == EligibilityStatus.STRETCH
    assert decision.required_experience_years == 3


def test_four_year_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Requires 4+ years of software engineering experience."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT


def test_four_year_new_grad_role_is_stretch() -> None:
    decision = evaluate_job(
        make_job(
            title="Software Engineer - New Grad",
            description=(
                "This early career role lists "
                "4+ years of related experience."
            ),
        )
    )

    assert decision.status == EligibilityStatus.STRETCH


def test_seven_year_requirement_always_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
            description=(
                "Requires 7+ years of experience. "
                "Bachelor's degree or equivalent experience."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT
    assert (
        EligibilityReasonCode.EXPERIENCE_TOO_HIGH
        in decision.reason_codes
    )


def test_preferred_experience_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "4+ years of software engineering experience preferred."
            ),
        )
    )

    assert decision.status == EligibilityStatus.PASS


def test_phd_in_title_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="Software Engineer Intern - PhD",
        )
    )

    assert decision.status == EligibilityStatus.REJECT
    assert (
        EligibilityReasonCode.PHD_TARGETED_ROLE
        in decision.reason_codes
    )


def test_phd_required_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="Machine Learning Engineer",
            description=(
                "A PhD in Computer Science is required."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT
    assert (
        EligibilityReasonCode.PHD_TARGETED_ROLE
        in decision.reason_codes
    )


def test_doctoral_degree_required_rejected() -> None:
    decision = evaluate_job(
        make_job(
            title="AI Engineer",
            description=(
                "Doctoral degree required in computer science."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT


def test_phd_preferred_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            title="Machine Learning Engineer",
            description=(
                "Bachelor's or Master's degree required. "
                "PhD preferred."
            ),
        )
    )

    assert decision.status == EligibilityStatus.PASS


def test_bs_ms_phd_preferred_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "BS, MS, or PhD preferred in a relevant technical field."
            ),
        )
    )

    assert decision.status == EligibilityStatus.PASS


def test_unknown_sponsorship_does_not_reject() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Build scalable distributed systems using Python."
            ),
        )
    )

    assert decision.status == EligibilityStatus.PASS


def test_explicit_no_sponsorship_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Candidates must be authorized to work "
                "without current or future sponsorship."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT
    assert (
        EligibilityReasonCode.SPONSORSHIP_BLOCKER
        in decision.reason_codes
    )


def test_citizenship_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Applicants must be a U.S. citizen."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT


def test_clearance_requirement_rejected() -> None:
    decision = evaluate_job(
        make_job(
            description=(
                "Active security clearance required."
            ),
        )
    )

    assert decision.status == EligibilityStatus.REJECT