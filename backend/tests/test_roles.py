"""Tests for ACE role-family classification."""

from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
    classify_role,
)


def test_software_engineer_is_primary() -> None:
    result = classify_role(
        "Software Engineer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.PRIMARY
    )


def test_software_engineer_i_is_primary() -> None:
    result = classify_role(
        "Software Engineer I"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.PRIMARY
    )


def test_sde_is_software_engineering() -> None:
    result = classify_role(
        "Software Development Engineer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_backend_engineer_is_software_engineering() -> None:
    result = classify_role(
        "Backend Engineer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_full_stack_developer_is_software_engineering() -> None:
    result = classify_role(
        "Full Stack Developer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_product_engineer_is_software_engineering() -> None:
    result = classify_role(
        "Product Engineer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_founding_engineer_is_software_engineering() -> None:
    result = classify_role(
        "Founding Engineer"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_member_of_technical_staff_is_software_engineering() -> None:
    result = classify_role(
        "Member of Technical Staff"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )


def test_swe_new_grad_is_software_engineering() -> None:
    result = classify_role(
        "SWE - New Grad"
    )

    assert (
        result.family
        == RoleFamily.SOFTWARE_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.PRIMARY
    )


def test_ai_engineer_is_primary() -> None:
    result = classify_role(
        "AI Engineer"
    )

    assert (
        result.family
        == RoleFamily.AI_ML_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.PRIMARY
    )


def test_engineer_ai_is_primary() -> None:
    result = classify_role(
        "Engineer, AI"
    )

    assert (
        result.family
        == RoleFamily.AI_ML_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.PRIMARY
    )


def test_machine_learning_engineer_is_primary() -> None:
    result = classify_role(
        "Machine Learning Engineer"
    )

    assert (
        result.family
        == RoleFamily.AI_ML_ENGINEERING
    )


def test_ml_infrastructure_is_ai_ml() -> None:
    result = classify_role(
        "ML Infrastructure Engineer"
    )

    assert (
        result.family
        == RoleFamily.AI_ML_ENGINEERING
    )


def test_machine_learning_software_engineer_prefers_ai_family() -> None:
    result = classify_role(
        "Machine Learning Software Engineer"
    )

    assert (
        result.family
        == RoleFamily.AI_ML_ENGINEERING
    )


def test_forward_deployed_engineer_is_secondary() -> None:
    result = classify_role(
        "Forward Deployed Engineer"
    )

    assert (
        result.family
        == RoleFamily
        .FORWARD_DEPLOYED_ENGINEERING
    )

    assert (
        result.priority
        == RolePriority.SECONDARY
    )


def test_forward_deployed_software_engineer_prefers_fde() -> None:
    result = classify_role(
        "Forward Deployed Software Engineer"
    )

    assert (
        result.family
        == RoleFamily
        .FORWARD_DEPLOYED_ENGINEERING
    )


def test_account_executive_is_other() -> None:
    result = classify_role(
        "Account Executive"
    )

    assert (
        result.family
        == RoleFamily.OTHER
    )


# --- titles written as a discipline rather than a role --------------


def test_engineering_as_a_discipline_is_still_the_role() -> None:
    """University recruiting titles the req by discipline.

    Found from a Plaid "Software Engineering, New Grad" posting the
    user reached by hand. ACE had fetched and stored it, then rejected
    it as NON_TARGET_ROLE, because the pattern was written
    \bsoftware engineer\b and there is no word boundary inside
    "engineering". The titles it silently dropped were exactly the
    early-career ones.
    """

    for title in (
        "Software Engineering, New Grad",
        "Software Engineering AMTS (College Grad)",
        "Associate Software Engineering",
        "Software Engineering - Associate",
        "Backend Engineering, New Grad",
        "Platform Engineering",
        "Full Stack Engineering",
    ):
        assert classify_role(
            title
        ).family is RoleFamily.SOFTWARE_ENGINEERING, title


def test_the_engineer_form_still_classifies() -> None:
    """The change must widen the rule, not move it."""

    for title in (
        "Software Engineer",
        "Software Engineer, New Grad",
        "Software Development Engineer",
        "Backend Engineer",
        "Full-Stack Engineer",
    ):
        assert classify_role(
            title
        ).family is RoleFamily.SOFTWARE_ENGINEERING, title


def test_a_discipline_named_inside_another_role_is_not_claimed() -> None:
    """"Engineering" often names the team, not the job.

    An analyst sitting in a data-engineering group is an analyst, and
    a sales engineer is not in scope however the title is spelled.
    """

    for title in (
        "Data Engineering Analyst",
        "Specialist Solutions Architect - Data Engineering",
        "Sales Engineer",
        "Support Engineer",
        "Field Engineer",
        "Hardware Engineer",
    ):
        assert classify_role(
            title
        ).family is not RoleFamily.SOFTWARE_ENGINEERING, title
