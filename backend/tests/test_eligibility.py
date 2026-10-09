"""Tests for ACE's deterministic eligibility gate."""

import pytest

from backend.app.intelligence.eligibility import (
    _is_us_location,
    ELIGIBILITY_RULE_VERSION,
    EligibilityReasonCode,
    EligibilityStatus,
    _is_clearly_senior,
    evaluate_job,
    is_internship,
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


def test_not_eligible_for_sponsorship_is_rejected() -> None:
    """A Qualcomm posting read "not eligible for Qualcomm immigration
    sponsorship" and passed the gate, because none of the literal
    SPONSORSHIP_BLOCKERS phrases contain "not eligible for" -- that
    construction reads nothing like "will not sponsor" or "no
    sponsorship available", the phrases the list already covered.

    Measured against the live corpus before this existed: 104 postings
    used this construction and not one was caught. Five of them were
    sitting in the queue as PASS.
    """

    decision = evaluate_job(
        make_job(
            description=(
                "This position is not "
                "eligible for Qualcomm "
                "immigration sponsorship."
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


def test_every_real_wording_of_not_eligible_is_caught() -> None:
    """Every distinct wording found in the live corpus, so a future
    edit cannot narrow the pattern back down to the one case above
    without this file noticing."""

    for description in (
        "This position is not eligible for visa sponsorship.",
        "This role is generally not eligible for new visa sponsorship.",
        "Remote roles are not eligible for U.S. visa sponsorship.",
        "Please note this role is not eligible for sponsorship.",
        "This position is not eligible for Intel immigration "
        "sponsorship.",
        "This role is not eligible for visa or immigration "
        "sponsorship.",
        "Applicants are ineligible for visa sponsorship.",
    ):
        decision = evaluate_job(
            make_job(
                description=description,
            )
        )

        assert (
            decision.status
            == EligibilityStatus.REJECT
        ), description

        assert (
            EligibilityReasonCode
            .SPONSORSHIP_BLOCKER
            in decision.reason_codes
        ), description


def test_the_positive_form_is_not_mistaken_for_a_refusal() -> None:
    """"Eligible for sponsorship" without "not" is the opposite claim,
    and the pattern must not fire on it. This is the real trap: the
    two differ by one word."""

    decision = evaluate_job(
        make_job(
            description=(
                VERIFIABLE_PAD
                + " Must hold existing US work "
                "authorization or be eligible "
                "for available sponsorship "
                "routes."
            ),
        )
    )

    assert (
        EligibilityReasonCode
        .SPONSORSHIP_BLOCKER
        not in decision.reason_codes
    )


def test_a_refusal_does_not_bleed_into_the_next_sentence() -> None:
    """The gap between "for" and "sponsorship" is bounded and cannot
    cross a paragraph break, which is where this file's own text
    flattening already puts a boundary between one claim and the
    next.

    Without the bound, "not eligible for the referral bonus" followed
    much later by an unrelated mention of "sponsorship" would read as
    a refusal that was never made.
    """

    decision = evaluate_job(
        make_job(
            description=(
                VERIFIABLE_PAD
                + " This role is not eligible "
                "for the annual refresher "
                "bonus.\n\nSponsorship: this "
                "team sponsors an annual "
                "hackathon that the whole "
                "org is welcome to attend."
            ),
        )
    )

    assert (
        EligibilityReasonCode
        .SPONSORSHIP_BLOCKER
        not in decision.reason_codes
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
        "Vaughan, Ontario, CA",
        "St. Thomas – Formet, Ontario, CA",
        "Montreal, Quebec, CA",
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


def test_every_way_a_title_says_internship_is_caught() -> None:
    """Both live leaks were the plural of the longer word.

    The patterns covered "intern", "interns" and "internship" -- every
    plural but the one that mattered. "internships" ends in an "s" that
    \\b will not sit before, so two internships were sitting in the
    queue as full-time roles: Esri's "Software Development Engineer
    Internships" and "NVIDIA 2027 Internships: Software Engineering".

    The NVIDIA one had been invisible until the classifier learned to
    read "Software Engineering", which is the argument for checking
    what a fix newly admits rather than only what it newly matches.
    """

    for title in (
        "Software Engineering Intern, Summer 2027",
        "Software Engineering Interns",
        "Software Engineering Internship",
        "Software Development Engineer Internships",
        "NVIDIA 2027 Internships: Software Engineering",
    ):
        assert is_internship(
            make_job(
                title=title,
            )
        ), title


def test_a_student_role_by_another_name_is_not_full_time() -> None:
    """Each of these was in the queue as a full-time role. The user is
    scoped to full-time early-career work, and a part-time student
    position is a placement whatever its title calls it."""

    for title in (
        "Software Engineer Part-Time Student",
        "IT Software Engineer Part-Time Student - Technology",
        "Part-Time Student IT - Infrastructure Engineer - Dubuque, IA",
        "Part-Time Student - IT Software Engineer - Chicago, IL",
        "Part Time Student Software Developer",
        "Contract Student Worker Software Engineer "
        "(6-month Contract) (20/hrs week)",
        "Software Engineer: Intership Opportunities, Azure Databases",
    ):
        assert is_internship(
            make_job(
                title=title,
            )
        ), title

    # A new-grad programme is full-time, and a team named after the
    # people it serves is not a student role.
    for title in (
        "Software Engineer \u2013 2027 Graduate Program (August Start)",
        "Software Engineer, Student Success Platform",
        "Software Engineer, Student Loans",
    ):
        assert not is_internship(
            make_job(
                title=title,
            )
        ), title


def test_a_word_that_merely_starts_with_intern_is_not_one() -> None:
    """The reason the boundaries are there at all.

    Widening the pattern must not start rejecting full-time roles for
    the first six letters of an unrelated word.
    """

    for title in (
        "Internal Tools Engineer",
        "International Payments Engineer",
        "Internationalization Engineer",
    ):
        assert not is_internship(
            make_job(
                title=title,
            )
        ), title


def test_clearance_shorthand_in_a_title_is_rejected() -> None:
    """The user named clearance roles as noise, and five sat in the
    queue anyway. Each came through the curated feed with a placeholder
    description, so the requirement lived only in the title -- written
    in shorthand the description patterns were never built for."""

    placeholder = (
        "Sourced from a curated new-graduate listing. Full "
        "requirements are on the employer's posting."
    )

    for title in (
        "Software Engineer - Cleared",
        "Software Engineer - Ctj - Poly",
        "AI/ML Engineer - Multiple levels - Cleared",
        "JavaScript Software Engineer 1 - TS/SCI with Poly",
        "Software Engineer - TS-SCI",
        "Software Engineer (Secret Clearance Required)",
    ):
        decision = evaluate_job(
            make_job(
                title=title,
                description=placeholder,
            )
        )

        assert (
            EligibilityReasonCode
            .CLEARANCE_BLOCKER
            in decision.reason_codes
        ), title


def test_cleared_in_a_description_is_not_a_clearance_role() -> None:
    """Why the shorthand is title-only. In prose "cleared" also means a
    background check that has come back, which every ordinary job runs,
    and rejecting on it would cost the user roles they can take."""

    decision = evaluate_job(
        make_job(
            description=(
                VERIFIABLE_PAD
                + " Once your background check has cleared, "
                "you will join the platform team."
            ),
        )
    )

    assert (
        EligibilityReasonCode
        .CLEARANCE_BLOCKER
        not in decision.reason_codes
    )


def test_a_word_that_only_starts_with_poly_is_not_a_polygraph() -> None:
    """Polyglot, Polymer, Polygon: none of them is a clearance."""

    for title in (
        "Software Engineer, Polyglot Persistence",
        "Software Engineer - Polygon Integrations",
    ):
        decision = evaluate_job(
            make_job(
                title=title,
            )
        )

        assert (
            EligibilityReasonCode
            .CLEARANCE_BLOCKER
            not in decision.reason_codes
        ), title


def test_a_posting_that_names_the_us_is_open_to_the_us() -> None:
    """The foreign-country check ran first and won, so a posting open
    in the US *and* elsewhere was rejected for mentioning elsewhere.
    Nine live software roles -- GitLab, Mercury, Cerebras -- were being
    hidden this way."""

    for location in (
        "Remote, Canada; Remote, United States",
        "United States and Canada",
        "Austin, Texas, United States; Toronto, Ontario, Canada",
        "Remote in the United States or Canada",
        "Canada; United Kingdom; United States",
        "Los Angeles, USA; Sydney, Australia",
        "Remote U.S. or Canada",
    ):
        assert _is_us_location(
            location
        ), location


def test_new_mexico_is_a_state_not_a_country() -> None:
    """"\\bmexico\\b" matched inside "New Mexico", so Albuquerque, Santa
    Fe and Los Lunas were all rejected as outside the US."""

    for location in (
        "Santa Fe, New Mexico",
        "Albuquerque, New Mexico",
        "Albuquerque, New Mexico, USA",
    ):
        assert _is_us_location(
            location
        ), location

    # The country is still the country.
    assert not _is_us_location(
        "Mexico City, Mexico"
    )


def test_usa_inside_a_foreign_place_name_is_not_the_usa() -> None:
    """The markers were raw substrings, and "usa" sits inside b-USA-n,
    jer-USA-lem and l-USA-ka."""

    for location in (
        "Busan",
        "Busan, Busan, KR",
        "Jerusalem",
        "Lusaka, Zambia",
    ):
        assert not _is_us_location(
            location
        ), location


@pytest.mark.parametrize(
    "location",
    [
        "US / Canada",
        "SF or Remote (US/Canada)",
        "Remote, Canada; Remote, US",
        "Remote in the US, Remote in Canada",
        "Chicago, US-Remote, Canada-Remote",
        "Remote (US + Canada Only)",
        "San Mateo, CA / Remote (Continental US + Hawaii + Canada Only)",
        "Toronto, Canada; US",
        "Remote - Americas",
        "Home Based - Americas; Home based - EMEA",
        "North America",
    ],
)
def test_us_named_beside_canada_is_still_the_us(
    location: str,
) -> None:
    """Stripe's "US / Canada" and GitLab's "Remote, Canada; Remote, US"
    were read as Canada alone."""

    assert _is_us_location(
        location
    ), location


@pytest.mark.parametrize(
    "location",
    [
        "Shah Alam, Selangor, Non-US, Malaysia",
        "US Expat - A363 Italy Sigonella",
        "Remote - Latin America",
        "Toronto, Ontario, Canada (North America)",
        "Remote - Canada",
        "Campus, Malaysia",
    ],
)
def test_us_and_americas_do_not_reach_past_their_meaning(
    location: str,
) -> None:
    assert not _is_us_location(
        location
    ), location


def test_contract_freelance_and_temporary_titles_are_not_full_time() -> None:
    for title in (
        "Software Development Engineer in Test - Contractor",
        "ML Engineer Specialist - Freelance AI Trainer Project",
        "Software Developer Leaders for Workflow Tools - (Freelance - Remote)",
        "Software Engineer, C++ - EA SPORTS FC (12 Month Temporary)",
        "Forward Deployed Engineer — Associate (Contract-to-Hire)",
    ):
        assert (
            EligibilityReasonCode.CONTRACT_ROLE
            in evaluate_job(
                make_job(
                    title=title,
                )
            ).reason_codes
        ), title

    assert (
        EligibilityReasonCode.CONTRACT_ROLE
        not in evaluate_job(
            make_job(
                title="Smart Contract Engineer",
            )
        ).reason_codes
    )


def test_the_ambiguous_code_override_still_holds() -> None:
    """What the foreign-country check was written for, and still does:
    in "Ottawa, ON, CA" the CA is Canada, not California. Only the words
    "United States", "USA" and "U.S." jump ahead of it."""

    assert not _is_us_location(
        "Ottawa, ON, CA"
    )

    assert not _is_us_location(
        "Toronto, ON, Canada"
    )

    # Ontario, California, is still California.
    assert _is_us_location(
        "Ontario, CA"
    )


def test_a_parenthesised_plus_still_states_a_minimum() -> None:
    """"5 (+) years of java based software development experience"
    passed as stating no requirement: only the bare "+" was read."""

    for description, years in (
        ("5 (+) years of java based software development experience", 5),
        ("6 ( + ) years of software engineering experience", 6),
        ("2-3 (+) years of software engineering experience", 2),
    ):
        decision = evaluate_job(
            make_job(
                description=description,
            )
        )

        assert decision.required_experience_years == years, description


def test_citizenship_shorthand_is_a_citizenship_requirement() -> None:
    """Staffing postings say it in shorthand the spelled-out patterns
    never matched."""

    for description in (
        "GC/CITIZEN can apply. Responsibilities: develop apps.",
        "USC/GC only.",
        "US Citizens or GC holders.",
        "Multiple Openings for GC/Citizen.",
        "Green Card / Citizen.",
    ):
        decision = evaluate_job(
            make_job(
                description=description,
            )
        )

        assert (
            EligibilityReasonCode.CITIZENSHIP_BLOCKER
            in decision.reason_codes
        ), description


def test_shorthand_that_admits_work_permits_is_not_a_blocker() -> None:
    """"Only GC/Citizen, OPT, EAD, H4" admits an F-1 student on OPT --
    and "GC" alone, in a Java posting, is garbage collection."""

    for description in (
        "Only GC/Citizen, OPT, EAD, H4 can apply.",
        "Only GC OR Citizen/OPT/EAD.",
        "Experience with JVM GC tuning and Java concurrency.",
        "We hire citizens of every country and sponsor visas.",
    ):
        decision = evaluate_job(
            make_job(
                description=description,
            )
        )

        assert (
            EligibilityReasonCode.CITIZENSHIP_BLOCKER
            not in decision.reason_codes
        ), description


def test_level_two_is_judged_by_the_years_it_asks() -> None:
    """With about 3.5 years, a role asking 2 to 3 is the sweet spot. 250
    were rejected for "II" in the title alone -- Microsoft's, American
    Express's, JPMorgan's -- and none of those stating years asked 4."""

    for title in (
        "Software Engineer II",
        "Software Development Engineer II",
        "Software Engineering II",
        "Software Engineer 2",
    ):
        asks_two = evaluate_job(
            make_job(
                title=title,
                description="Requires 2+ years of software engineering experience.",
            )
        )

        assert asks_two.status == EligibilityStatus.PASS, title

        asks_five = evaluate_job(
            make_job(
                title=title,
                description="Requires 5+ years of software engineering experience.",
            )
        )

        assert (
            EligibilityReasonCode.EXPERIENCE_TOO_HIGH
            in asks_five.reason_codes
        ), title


def test_level_three_and_above_are_still_senior() -> None:
    for title in (
        "Software Engineer III",
        "Data Scientist III",
        "Software Engineer IV",
        "Software Engineer 4",
    ):
        assert (
            EligibilityReasonCode.SENIOR_TITLE
            in evaluate_job(
                make_job(
                    title=title,
                )
            ).reason_codes
        ), title


def test_a_distinguished_engineer_is_senior() -> None:
    assert (
        EligibilityReasonCode.SENIOR_TITLE
        in evaluate_job(
            make_job(
                title="Distinguished Engineer, AI Infrastructure",
            )
        ).reason_codes
    )


def test_an_abbreviated_manager_title_is_senior() -> None:
    """"Mgr Software Engineering" passed: only the full word was read."""

    assert (
        EligibilityReasonCode.SENIOR_TITLE
        in evaluate_job(
            make_job(
                title="Mgr Software Engineering",
            )
        ).reason_codes
    )


def test_a_bank_vice_president_is_senior() -> None:
    """40 of BNY's "Vice President, Full-Stack Engineer" were passing."""

    for title in (
        "Vice President, Full-Stack Engineer",
        "Java Backend Developer, Vice President",
        "Liquid Financing Data/AI Engineer – VP",
        "VP Software Engineering",
    ):
        assert (
            EligibilityReasonCode.SENIOR_TITLE
            in evaluate_job(
                make_job(
                    title=title,
                )
            ).reason_codes
        ), title


def test_an_assistant_vice_president_is_not_senior() -> None:
    """Two to five years at Citi and State Street."""

    for title in (
        "Full Stack Developer - Assistant Vice President",
        "Infrastructure Engineer - Azure Cloud, AVP",
        "Associate Vice President, Software Engineer",
    ):
        assert (
            EligibilityReasonCode.SENIOR_TITLE
            not in evaluate_job(
                make_job(
                    title=title,
                )
            ).reason_codes
        ), title


def test_every_product_engineer_title_is_excluded() -> None:
    """The user asked for the title to be cleared "strictly": the
    hardware ones and the startup software ones alike."""

    for title, description in (
        (
            "Product Engineer II",
            "Own wafer yield and test program development. ",
        ),
        (
            "Product Engineer",
            "Ship features across our React and TypeScript frontend. ",
        ),
        (
            "Full Stack Product Engineer",
            "",
        ),
        (
            "Product Engineer (Software Engineer)",
            "",
        ),
    ):
        decision = evaluate_job(
            make_job(
                title=title,
                description=description,
            )
        )

        assert decision.status != EligibilityStatus.PASS, title

        assert (
            EligibilityReasonCode.NON_TARGET_ROLE
            in decision.reason_codes
        ), title


def test_a_team_named_product_engineering_is_not_the_title() -> None:
    assert (
        EligibilityReasonCode.NON_TARGET_ROLE
        not in evaluate_job(
            make_job(
                title=(
                    "New Grad Software Engineer, "
                    "Product Engineering"
                ),
            )
        ).reason_codes
    )


def test_an_indian_location_ending_in_in_is_not_indiana() -> None:
    """47 roles in India passed as American: "Bengaluru, KA, IN"."""

    for location in (
        "Bengaluru, KA, IN",
        "hosur road bangalore, IN",
        "Chennai, TN, IN",
        "Pune, IN",
        "Chennai, TN, IND",
        "Mostar, Bosnia and Herzegowina",
        "Montevideo, Uruguay",
    ):
        assert (
            EligibilityReasonCode.OUTSIDE_US
            in evaluate_job(
                make_job(
                    location=location,
                )
            ).reason_codes
        ), location


def test_indiana_is_still_indiana() -> None:
    for location in (
        "Indianapolis, IN",
        "Plainfield, IN",
        "Delhi, NY",
        "Austin, TX, USA",
    ):
        assert (
            EligibilityReasonCode.OUTSIDE_US
            not in evaluate_job(
                make_job(
                    location=location,
                )
            ).reason_codes
        ), location


SERVICENOW_EXPORT_PARAGRAPH = (
    "Export Control Regulations For positions requiring access to "
    "controlled technology subject to export control regulations, "
    "including the U.S. Export Administration Regulations (EAR), "
    "ServiceNow may be required to obtain export control approval from "
    "government authorities for certain individuals. All employment is "
    "contingent upon ServiceNow obtaining any export license or other "
    "approval that may be required by relevant export control "
    "authorities. "
)


def test_an_employer_that_will_seek_an_export_licence_is_not_a_citizenship_bar() -> None:
    """Every ServiceNow posting ends with this paragraph, and read as a
    citizenship requirement it hid its new-grad Moveworks role."""

    assert (
        EligibilityReasonCode.CITIZENSHIP_BLOCKER
        not in evaluate_job(
            make_job(
                title="Software Engineer, Core Infrastructure (New Grad)",
                description=SERVICENOW_EXPORT_PARAGRAPH,
            )
        ).reason_codes
    )


def test_a_demand_for_us_person_status_is_still_a_bar() -> None:
    for text in (
        # General Motors
        "The position is subject to export control restrictions and "
        "requires the successful candidate to be a U.S. Person (U.S. "
        "citizen, U.S. permanent resident, asylee or refugee). ",
        # GrayMatter Robotics
        "it is required that the applicant must fall under one of the "
        "following categories: (i) U.S. citizen or national, (ii) U.S. "
        "lawful permanent resident. ",
        # K2 Space
        "Export Compliance: As defined in the ITAR, U.S. Persons include "
        "U.S. citizens, lawful permanent residents. ",
        # Microsoft
        "As a condition of employment, the successful candidate's "
        "citizenship will be verified with a valid passport. ",
        "Applicants must be able to access export-controlled technology "
        "without a license. ",
    ):
        assert (
            EligibilityReasonCode.CITIZENSHIP_BLOCKER
            in evaluate_job(
                make_job(
                    description=text,
                )
            ).reason_codes
        ), text[:60]


EXPORT_CASES = {
    # The employer will seek the licence: the role is open.
    "keep": (
        "ServiceNow may be required to obtain export control approval "
        "from government authorities for certain individuals. All "
        "employment is contingent upon ServiceNow obtaining any export "
        "license or other approval. ",
        "Any offer is contingent on the Company verifying that you are "
        "authorized for access to export-controlled technology or, if "
        "you are not already authorized, our ability to successfully "
        "obtain any necessary export license(s). ",
        "The person hired will have access to information subject to "
        "U.S. export controls, and therefore, must either be a “U.S. "
        "person” as defined by 22 C.F.R. 120.62 or otherwise eligible "
        "for deemed export licensing. ",
        "This role may require access to information subject to U.S. "
        "export control laws. Applicants must be authorized to access "
        "such information or eligible for government authorization. ",
    ),
    # The applicant must already be a US person: rejected.
    "reject": (
        "Any offer of employment may be conditioned on your authorization "
        "to receive software or technology controlled under these U.S. "
        "export laws without sponsorship for an export license. ",
        "This offer is contingent upon the applicant's capacity to "
        "perform job functions in compliance with U.S. export control "
        "laws without obtaining a license. ",
        "This role requires use of technical data subject to U.S. "
        "Government export restrictions and this posting is only for "
        "U.S. Persons (U.S. Citizens, lawful permanent residents). ",
        "It requires access to export-controlled information or items "
        "that require “U.S. Person” status. ",
    ),
    # Neither: passes, with a caveat on the role.
    "caveat": (
        "To comply with U.S. export control laws and regulations, "
        "candidates for this role may need to meet certain legal status "
        "requirements as provided in those laws and regulations. ",
        "This position involves access to technology that is subject to "
        "U.S. export controls. Any job offer made will be contingent upon "
        "the applicant’s capacity to serve in compliance with U.S. "
        "export controls. ",
    ),
}


def test_export_control_is_read_for_who_carries_the_licence() -> None:
    """The user: reject a role that wants applicants to already be US
    persons, keep one whose employer will apply for the licence, and
    miss nothing genuine in between."""

    for expected, texts in EXPORT_CASES.items():
        for text in texts:
            decision = evaluate_job(
                make_job(
                    description=text,
                )
            )

            codes = set(
                decision.reason_codes
            )

            blocked = (
                EligibilityReasonCode.CITIZENSHIP_BLOCKER
                in codes
            )

            caveat = (
                EligibilityReasonCode.EXPORT_CONTROL_CAVEAT
                in codes
            )

            assert blocked == (expected == "reject"), (expected, text[:50])
            assert caveat == (expected == "caveat"), (expected, text[:50])
