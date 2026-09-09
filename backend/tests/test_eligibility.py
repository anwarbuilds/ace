"""Tests for ACE's deterministic eligibility gate."""

import pytest

from backend.app.intelligence.eligibility import (
    _is_us_location,
    ELIGIBILITY_RULE_VERSION,
    EligibilityReasonCode,
    EligibilityStatus,
    _is_clearly_senior,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import (
    CanonicalJob,
)


# Every gate test job is early-career unless the test is specifically
# about the early-career rule. Appending the marker keeps each test
# focused on the single rule it is exercising.
# Gate tests exercise postings whose text ACE could actually
# read; a description too short to state requirements is treated
# as unverified and never becomes an alert candidate.
VERIFIABLE_PAD = (
    "We are a team building reliable distributed systems at scale. You will collaborate across product and platform groups, write and review code, and help operate what you ship. We value clear written communication and steady engineering judgement over heroics. Benefits include health cover, paid leave and a learning budget. We are a team building reliable distributed systems at scale. You will collaborate across product and platform groups, write and review code, and help operate what you ship. We value clear written communication and steady engineering judgement over heroics. Benefits include health cover, paid leave and a learning budget."
)


EARLY_CAREER_NOTE = "This is a new grad role. "


def make_job(
    *,
    title: str = "Software Engineer",
    location: str = "Seattle, Washington",
    description: str = "",
    early_career: bool = True,
    employment_type: str | None = None,
) -> CanonicalJob:
    """Create a normalized test job."""

    if early_career:
        description = (
            EARLY_CAREER_NOTE
            + description
            + VERIFIABLE_PAD
        )

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
        employment_type=employment_type,
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


def test_unknown_remote_qualifies() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        EligibilityReasonCode
        .LOCATION_UNCERTAIN
        in decision.reason_codes
    )


def test_worldwide_remote_qualifies() -> None:
    decision = evaluate_job(
        make_job(
            location="Remote - Worldwide",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
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


def test_an_open_ended_three_year_bar_is_rejected() -> None:
    """"3+ years" sets a floor and takes whoever clears it.

    This reverses an earlier decision that let three-year postings
    through. The user drew the line themselves after reading the
    dashboard: anything between zero and three should be there,
    three-plus should not. A floor of three means competing with
    someone who has five; a band of one to three does not.
    """

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
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .EXPERIENCE_TOO_HIGH
        in decision.reason_codes
    )


def test_an_explicit_contract_role_is_rejected() -> None:
    """A real Vestwell posting and a real T-Mobile posting both stated
    "contract" through Adzuna's own contract_type field, with nothing
    in the title or description saying so, and both passed the gate
    before this field was read at all."""

    decision = evaluate_job(
        make_job(
            employment_type="contract",
        )
    )

    assert (
        decision.status
        == EligibilityStatus.REJECT
    )

    assert (
        EligibilityReasonCode
        .CONTRACT_ROLE
        in decision.reason_codes
    )


def test_an_unstated_employment_type_is_not_assumed_contract() -> (
    None
):
    """Most postings, and every source except Adzuna, never say. None
    means the source did not report it, never "full-time assumed" --
    and never "contract assumed" either."""

    for employment_type in (
        None,
        "permanent",
        "full_time",
    ):
        decision = evaluate_job(
            make_job(
                employment_type=(
                    employment_type
                ),
            )
        )

        assert (
            decision.status
            == EligibilityStatus.PASS
        ), employment_type


def test_a_capped_three_years_is_not_a_floor() -> None:
    """"No more than 3 years of professional experience" contains the
    words "more than 3 years", and reading that as a floor inverts the
    most explicit early-career signal a posting can carry.

    A real Aquatic Capital posting titled "Software Engineer, Early
    Career" was rejected by exactly that inversion.
    """

    decision = evaluate_job(
        make_job(
            title=(
                "Software Engineer, "
                "Early Career"
            ),
            description=(
                "No more than 3 years of "
                "professional "
                "(post-education) "
                "experience. "
                + VERIFIABLE_PAD
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_a_bounded_three_year_band_qualifies() -> None:
    """The same figure as a bound describes the band the role sits in,
    and a graduate is inside it."""

    decision = evaluate_job(
        make_job(
            description=(
                "Requires 1 to 3 years of "
                "software engineering "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_an_open_ended_two_year_bar_still_qualifies() -> None:
    """The line is at three. "2+ years" is inside the range the user
    asked for and must keep passing."""

    decision = evaluate_job(
        make_job(
            description=(
                "Requires 2+ years of "
                "software engineering "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
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


def test_a_new_grad_title_does_not_excuse_four_years() -> None:
    """The number wins over the label.

    This previously passed, but only because the extractor could not
    read "4+ years of related experience" at all: "related" was not in
    a whitelist of adjectives. Once the figure is actually seen, four
    or more years is excluded, which is what
    MAX_REQUIRED_EXPERIENCE_YEARS has always documented.
    """

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
        == EligibilityStatus.REJECT
    )


def test_a_new_grad_role_below_the_bar_qualifies() -> None:
    decision = evaluate_job(
        make_job(
            title=(
                "Software Engineer - New Grad"
            ),
            description=(
                "This early career role lists "
                "2+ years of related "
                "experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_experience_is_read_through_any_adjectives() -> None:
    """Real postings do not use a fixed vocabulary.

    A whitelist of adjectives between "years" and "experience" missed
    "5+ years backend software engineering experience" and every
    phrasing like it, so senior roles reached the queue with no
    requirement recorded at all.
    """

    for phrasing in (
        "5+ years backend software "
        "engineering experience",
        "7+ years distributed systems "
        "experience",
        "6+ years of professional "
        "full-stack development experience",
        "8+ years in roles such as "
        "software engineering",
    ):
        decision = evaluate_job(
            make_job(
                title="Software Engineer",
                description=(
                    "We are hiring. "
                    + phrasing
                    + " is required."
                ),
            )
        )

        assert (
            decision.status
            == EligibilityStatus.REJECT
        ), phrasing


def test_company_age_is_not_an_experience_requirement() -> None:
    """"Founded 18 years ago" is not a demand for 18 years of work."""

    for phrasing in (
        "Before founding Sierra, Clay "
        "spent 18 years at Google.",
        "We have been transforming "
        "computing for more than 25 years.",
    ):
        decision = evaluate_job(
            make_job(
                title=(
                    "Software Engineer, "
                    "New Grad"
                ),
                description=(
                    phrasing
                    + " Join our team."
                ),
            )
        )

        assert (
            decision.status
            == EligibilityStatus.PASS
        ), phrasing


def test_a_wide_range_passes_on_its_floor() -> None:
    """"2 to 10+ years" is judged by the two, not the ten.

    This rule has now moved twice, so the reasoning is recorded rather
    than the conclusion. It first passed on the floor. It was then made
    to reject, because the user reported a queue meaning "a graduate
    can apply to this" full of postings wanting four or more years. It
    passes again now, because that change turned out to throw away
    twenty-five software postings whose floors were one or two years,
    including one titled "Software Engineer I".

    The two instructions are not in conflict once open-ended and
    bounded are separated. "3+ years" sets a floor and takes whoever
    clears it, so a graduate competes with someone who has five: that
    is rejected. "2 to 10 years" is a band a candidate with two is
    inside, and Stripe writes exactly that under the heading "Minimum
    requirements".

    The ceiling still decides the early-career label, because a range
    reaching ten years is not a graduate posting even when a graduate
    may apply.
    """

    decision = evaluate_job(
        make_job(
            title="Full Stack Engineer",
            early_career=False,
            description=(
                "Minimum requirements: 2-10+ "
                "years of industry software "
                "engineering experience. "
                + VERIFIABLE_PAD
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    # The ceiling still withholds the early-career label, so the
    # posting is reachable without claiming to be a graduate role.
    assert (
        EligibilityReasonCode
        .EARLY_CAREER_SIGNAL
        not in decision.reason_codes
    )


def test_a_range_inside_the_cap_still_passes() -> None:
    """The ceiling rule must not swallow genuine early-career ranges."""

    decision = evaluate_job(
        make_job(
            title="Software Engineer",
            early_career=False,
            description=(
                "Minimum requirements: 1-3 "
                "years of software engineering "
                "experience. "
                + VERIFIABLE_PAD
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )


def test_security_titles_are_rejected() -> None:
    """A specialism the user is not pursuing, filtered on title alone."""

    for title in (
        "Security Platform Engineer",
        "Software Engineer, Security",
        "Security Software Engineer, "
        "Vulnerability Operations",
        "Application Security Engineer",
    ):
        decision = evaluate_job(
            make_job(
                title=title,
            )
        )

        assert (
            decision.status
            == EligibilityStatus.REJECT
        ), title


def test_ordinary_engineering_titles_survive_the_security_rule() -> None:
    for title in (
        "Software Engineer, Backend",
        "Software Engineer, New Grad",
        "Backend Engineer, Payments",
        "Full Stack Engineer",
    ):
        decision = evaluate_job(
            make_job(
                title=title,
            )
        )

        assert (
            decision.status
            == EligibilityStatus.PASS
        ), title


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


def test_four_years_even_when_only_preferred_is_excluded() -> None:
    """A role whose sole stated bar is 4+ years is not early-career.

    The user has ~3.5 years and asked for a single actionable list, so
    an optional-section figure is still used when it is the only
    experience signal the posting gives.
    """

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
        == EligibilityStatus.REJECT
    )


def test_low_requirement_wins_over_high_preference() -> None:
    """A stated minimum outranks a higher preferred figure."""

    decision = evaluate_job(
        make_job(
            description=(
                "MINIMUM QUALIFICATIONS 2+ "
                "years of experience. "
                "PREFERRED QUALIFICATIONS 8+ "
                "years of experience."
            ),
        )
    )

    assert (
        decision.status
        == EligibilityStatus.PASS
    )

    assert (
        decision.required_experience_years
        == 2
    )


def test_a_bare_us_token_is_a_us_location() -> None:
    """A real Stripe posting the user found on their own carried the
    location "US" and was rejected as outside the US. The markers list
    held "usa" and "united states" and matched by substring, so bare
    "US" reached none of them."""

    for location in (
        "US",
        "US-Remote",
        "US-CA-Menlo Park",
    ):
        assert _is_us_location(
            location
        ), location


def test_a_bare_us_city_is_a_us_location() -> None:
    """Several large boards post a city with no country. 1,231 San
    Francisco postings were being thrown away."""

    for location in (
        "San Francisco",
        "San Francisco Bay Area",
        "Chicago",
        "Seattle",
        "NYC",
        "Sunnyvale",
    ):
        assert _is_us_location(
            location
        ), location


def test_a_country_ending_in_us_is_not_the_us() -> None:
    """The token has to stand alone. Belarus, Cyprus and Mauritius all
    end in the two letters, and Houston contains them."""

    for location in (
        "Belarus",
        "Cyprus",
        "Mauritius",
    ):
        assert not _is_us_location(
            location
        ), location


def test_an_unknown_location_is_not_assumed_us() -> None:
    """Guessing would fill the queue with jobs the user cannot take."""

    for location in (
        "Unknown",
        "2 Locations",
        "Hybrid",
        "Home based - EMEA",
        "Dublin",
        "Singapore",
    ):
        assert not _is_us_location(
            location
        ), location


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


def test_bare_ts_clearance_without_sci_is_rejected() -> None:
    # "TS/SCI" was already caught; a posting that drops the SCI half
    # and just says "TS clearance" carries the same requirement.
    decision = evaluate_job(
        make_job(
            description=(
                "Candidates must be able to obtain "
                "a TS clearance within 6 months."
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
    early_career: bool = True,
) -> CanonicalJob:
    """Create one normalized job for gate tests."""

    if early_career:
        description = (
            EARLY_CAREER_NOTE
            + description
            + VERIFIABLE_PAD
        )

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


# ----------------------------------------------------------------------
# Citizenship / export-control blockers
#
# Each string below is real posting text that previously passed the gate.
# Exact-phrase matching missed them because the standard ITAR clause
# reads "must be a (i) U.S. citizen" -- the enumerator between "a" and
# "U.S." defeats a literal match.
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        (
            "ITAR REQUIREMENTS: To conform to U.S. "
            "Government export regulations, applicant "
            "must be a (i) U.S. citizen or national, "
            "(ii) U.S. lawful, permanent resident."
        ),
        (
            "Due to federal contract requirements, "
            "United States Citizenship and position "
            "appropriate security clearance is required."
        ),
        (
            "U.S. Person status is required as this "
            "position needs to access export controlled "
            "data."
        ),
        (
            "Are a U.S. Person because of required "
            "access to U.S. export controlled "
            "information."
        ),
        (
            "Eligibility - US citizen or permanent "
            "resident, and based in the US."
        ),
        (
            "This role is ITAR controlled and requires "
            "US citizenship."
        ),
        (
            "Applicants must be a U.S. citizen to be "
            "considered."
        ),
    ],
)
def test_citizenship_and_export_control_are_rejected(
    description: str,
) -> None:
    """Export-controlled roles are closed to a non-US-person candidate."""

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
        "CITIZENSHIP_BLOCKER"
        in _codes(
            decision
        )
    )


@pytest.mark.parametrize(
    "description",
    [
        # "military" contains the substring "itar" -- word boundaries
        # must prevent this from reading as ITAR.
        (
            "We bring advanced technology to allied "
            "military capabilities. We write Python."
        ),
        (
            "Supportive leave of absence program "
            "including time off for military service."
        ),
        # Sponsorship-friendly language must not trip a citizenship rule.
        (
            "We welcome applicants of any citizenship "
            "status and provide visa sponsorship."
        ),
    ],
)
def test_incidental_mentions_do_not_block(
    description: str,
) -> None:
    """A passing mention of the military is not an ITAR requirement."""

    decision = evaluate_job(
        _job(
            description=description
        )
    )

    assert (
        "CITIZENSHIP_BLOCKER"
        not in _codes(
            decision
        )
    )


# ----------------------------------------------------------------------
# Unlabelled roles are included
#
# A terse startup posting that states no experience bar and never says
# "new grad" is frequently open to one. Silence means unknown, not
# rejection. Seniority and a high experience bar still exclude.
# ----------------------------------------------------------------------


def test_unlabelled_role_is_included() -> None:
    """A plain posting with no experience bar is not excluded."""

    decision = evaluate_job(
        _job(
            title="Software Engineer",
            description=(
                "Build software in Python."
            ),
            early_career=False,
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )


def test_labelled_role_carries_early_career_signal() -> None:
    """An explicit new-grad label is recorded for ordering."""

    decision = evaluate_job(
        _job(
            title=(
                "Software Engineer, New Grad"
            ),
            description=(
                "Build software in Python."
            ),
            early_career=False,
        )
    )

    assert (
        decision.status
        is EligibilityStatus.PASS
    )

    assert (
        "EARLY_CAREER_SIGNAL"
        in _codes(
            decision
        )
    )


def test_unlabelled_role_carries_no_signal() -> None:
    """The signal marks labelled roles only."""

    decision = evaluate_job(
        _job(
            title="Software Engineer",
            description=(
                "Build software in Python."
            ),
            early_career=False,
        )
    )

    assert (
        "EARLY_CAREER_SIGNAL"
        not in _codes(
            decision
        )
    )


def test_low_experience_bar_counts_as_early_career() -> None:
    """Two years or less is early-career even without the words."""

    decision = evaluate_job(
        _job(
            description=(
                "MINIMUM QUALIFICATIONS 2+ "
                "years of experience."
            ),
            early_career=False,
        )
    )

    assert (
        "EARLY_CAREER_SIGNAL"
        in _codes(
            decision
        )
    )


@pytest.mark.parametrize(
    "title,description",
    [
        (
            "Senior Software Engineer",
            "Build software in Python.",
        ),
        (
            "Software Engineer",
            "MINIMUM QUALIFICATIONS 6+ "
            "years of experience.",
        ),
        (
            "Software Engineer",
            "Top Secret security clearance "
            "required.",
        ),
    ],
)
def test_genuinely_closed_roles_still_excluded(
    title: str,
    description: str,
) -> None:
    """Including unlabelled roles must not weaken the real blockers."""

    decision = evaluate_job(
        _job(
            title=title,
            description=description,
            early_career=False,
        )
    )

    assert (
        decision.status
        is EligibilityStatus.REJECT
    )


def test_numeric_career_levels_are_treated_as_senior() -> None:
    """Level 4 and above is senior wherever companies number roles.

    This is the only signal available for them: 66 of 67 qualifying
    Netflix postings never state years of experience, so the experience
    rules cannot see their seniority at all.
    """

    for title in (
        "Software Engineer 4- Ink",
        "AI Engineer 6 - Ads Platform",
        "Full Stack Software Engineer 5",
        "Software Engineer, Level 5",
        "Data Scientist 4",
    ):
        assert _is_clearly_senior(
            title
        ), title


def test_low_numeric_levels_remain_early_career() -> None:
    """1 to 3 are genuinely early career and must keep passing."""

    for title in (
        "Software Engineer 1",
        "Software Engineer 1 - Java",
        "Software Engineer 3",
        "Software Engineer 2",
    ):
        assert not _is_clearly_senior(
            title
        ), title


def test_a_year_in_a_title_is_not_a_career_level() -> None:
    """"2024 Cohort" must not be read as level 2024."""

    assert not _is_clearly_senior(
        "Backend Engineer 2024 Cohort"
    )


def test_parenthesised_career_levels_are_senior() -> None:
    """Netflix also writes the level as "(L5)" or "Engineer L5"."""

    for title in (
        "Software Engineer L5 - Audio Tools",
        "Distributed Systems Engineer (L5) - Compute",
        "Software Engineer (L7) - Networking",
    ):
        assert _is_clearly_senior(
            title
        ), title


def test_autonomy_levels_are_not_career_levels() -> None:
    """"L4 autonomous driving" is a domain term, not a seniority.

    A bare L-number rule would reject early-career self-driving roles
    for saying what the car does.
    """

    for title in (
        "L4 Autonomous Driving Perception Engineer",
        "Software Engineer, L4 Autonomous Vehicles",
        "L7 Load Balancer Engineer",
    ):
        assert not _is_clearly_senior(
            title
        ), title


def test_a_duration_is_not_a_career_level() -> None:
    """"Engineer - 8 to 12 months" is a contract length, not a level 8."""

    for title in (
        "Co-op Winter 2027 - Project "
        "Engineer - 8 to 12 months",
        "Software Engineer - 6 month contract",
    ):
        assert not _is_clearly_senior(
            title
        ), title
