"""Deterministic eligibility gate for ACE.

The eligibility gate determines whether a normalized opportunity belongs
in ACE's candidate set.

Core invariants:

1. Role classification determines the target role family.
2. Eligibility determines inclusion.
3. Ranking and resume relevance only control ordering.
4. Missing sponsorship information is unknown, not rejection.
5. Missing experience information is unknown, not rejection.
6. Explicitly PhD-targeted roles are excluded.
7. Ambiguous remote geography is retained as STRETCH to protect recall.
8. Explicit non-US geography remains excluded.
9. Explicit non-US country names override ambiguous state codes.
10. Hardware-oriented embedded/firmware roles are excluded.
11. Roles whose only stated languages are C and/or C++ are excluded.
    A C/C++ role that also uses Python, Java, Go, or any other language
    remains in scope.
"""

import re
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
)

from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
    classify_role,
)
from backend.app.models.job import (
    CanonicalJob,
)


ELIGIBILITY_RULE_VERSION = (
    "2026-09-05-v7"
)


class EligibilityStatus(
    str,
    Enum,
):
    """Possible eligibility outcomes."""

    PASS = "PASS"
    STRETCH = "STRETCH"
    REJECT = "REJECT"


class EligibilityReasonCode(
    str,
    Enum,
):
    """Machine-readable explanation codes."""

    OUTSIDE_US = "OUTSIDE_US"

    LOCATION_UNCERTAIN = (
        "LOCATION_UNCERTAIN"
    )

    NON_TARGET_ROLE = (
        "NON_TARGET_ROLE"
    )

    SENIOR_TITLE = "SENIOR_TITLE"

    PHD_TARGETED_ROLE = (
        "PHD_TARGETED_ROLE"
    )

    EXPERIENCE_TOO_HIGH = (
        "EXPERIENCE_TOO_HIGH"
    )

    EXPERIENCE_STRETCH = (
        "EXPERIENCE_STRETCH"
    )

    CITIZENSHIP_BLOCKER = (
        "CITIZENSHIP_BLOCKER"
    )

    CLEARANCE_BLOCKER = (
        "CLEARANCE_BLOCKER"
    )

    SPONSORSHIP_BLOCKER = (
        "SPONSORSHIP_BLOCKER"
    )

    HARDWARE_EMBEDDED_ROLE = (
        "HARDWARE_EMBEDDED_ROLE"
    )

    SYSTEMS_LANGUAGE_ONLY = (
        "SYSTEMS_LANGUAGE_ONLY"
    )

    NO_HARD_BLOCKER = (
        "NO_HARD_BLOCKER"
    )


class EligibilityDecision(
    BaseModel
):
    """Explainable result of ACE's deterministic gate."""

    model_config = ConfigDict(
        frozen=True
    )

    status: EligibilityStatus

    role_family: RoleFamily

    role_priority: RolePriority

    rule_version: str = (
        ELIGIBILITY_RULE_VERSION
    )

    reason_codes: tuple[
        EligibilityReasonCode,
        ...,
    ]

    reasons: tuple[
        str,
        ...,
    ]

    required_experience_years: (
        int | None
    ) = None


US_STATE_NAMES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
}


US_STATE_ABBREVIATIONS = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}


US_LOCATION_MARKERS = (
    "united states",
    "usa",
    "u.s.",
    "remote - us",
    "remote us",
    "remote, us",
    "remote / us",
    "remote (us",
    "remote - united states",
    "remote, united states",
    "remote / united states",
)


# Explicit non-US signals, checked before the US-state match.
#
# Two-letter codes are genuinely ambiguous: "CA" is California in a US
# address and Canada in an international one. A preceding Canadian
# province code disambiguates it, which is why these run first.
NON_US_LOCATION_PATTERNS = (
    r",\s*(?:ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|YT|NT|NU)\s*,\s*CA\b",
    r"\bcanada\b",
    r"\bunited\s+kingdom\b",
    r"\bengland\b",
    r"\bscotland\b",
    r"\bwales\b",
    r"\bireland\b",
    r"\bindia\b",
    r"\bgermany\b",
    r"\bfrance\b",
    r"\bspain\b",
    r"\bportugal\b",
    r"\bnetherlands\b",
    r"\bpoland\b",
    r"\bromania\b",
    r"\bisrael\b",
    r"\bsingapore\b",
    r"\baustralia\b",
    r"\bnew\s+zealand\b",
    r"\bjapan\b",
    r"\bchina\b",
    r"\bbrazil\b",
    r"\bmexico\b",
    r"\bargentina\b",
    r"\bcolombia\b",
    r"\bswitzerland\b",
    r"\bsweden\b",
    r"\bnorway\b",
    r"\bdenmark\b",
    r"\bfinland\b",
    r"\bitaly\b",
    r"\bcroatia\b",
    r"\bserbia\b",
    r"\bukraine\b",
    r"\bturkey\b",
    r"\bkorea\b",
    r"\btaiwan\b",
    r"\bhong\s+kong\b",
    r"\bvietnam\b",
    r"\bphilippines\b",
    r"\bindonesia\b",
    r"\bthailand\b",
    r"\bmalaysia\b",
    r"\bnigeria\b",
    r"\bkenya\b",
    r"\begypt\b",
    r"\bsouth\s+africa\b",
    r"\buae\b",
    r"\bdubai\b",
)


AMBIGUOUS_REMOTE_PATTERNS = (
    r"^\s*remote\s*$",
    r"^\s*remote\s*[-,/()]?\s*anywhere\s*\)?\s*$",
    r"^\s*remote\s*[-,/()]?\s*worldwide\s*\)?\s*$",
    r"^\s*anywhere\s*$",
    r"^\s*worldwide\s*$",
    r"^\s*distributed\s*$",
    r"^\s*distributed\s+team\s*$",
)


SENIOR_TITLE_PATTERNS = (
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\blead\b",
    r"\bmanager\b",
    r"\bdirector\b",
    r"\bengineer\s+iii\b",
    r"\bengineer\s+iv\b",
)


EARLY_CAREER_MARKERS = (
    "new grad",
    "new graduate",
    "university graduate",
    "recent graduate",
    "early career",
    "entry level",
    "entry-level",
    "university hire",
)


PREFERRED_CONTEXT_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "ideally",
)


PHD_TITLE_PATTERNS = (
    r"\bph\.?\s*d\.?\b",
    r"\bdoctoral\b",
    r"\bdoctorate\b",
)


PHD_REQUIRED_PATTERNS = (
    r"\bph\.?\s*d\.?\s+(?:is\s+)?required\b",

    r"\bph\.?\s*d\.?\s+in\s+[^.;]{1,100}\s+(?:is\s+)?required\b",

    r"\brequires?\s+(?:an?\s+)?ph\.?\s*d\.?\b",

    r"\bmust\s+(?:have|hold|possess)\s+(?:an?\s+)?ph\.?\s*d\.?\b",

    r"\bdoctoral\s+degree\s+(?:is\s+)?required\b",

    r"\brequires?\s+(?:an?\s+)?doctoral\s+degree\b",

    r"\bdoctorate\s+(?:is\s+)?required\b",

    r"\brequires?\s+(?:an?\s+)?doctorate\b",
)


SPONSORSHIP_BLOCKERS = (
    "without current or future sponsorship",
    "without the need for current or future sponsorship",
    "will not sponsor",
    "will not provide sponsorship",
    "unable to provide sponsorship",
    "unable to sponsor",
    "cannot provide sponsorship",
    "cannot sponsor",
    "no visa sponsorship",
    "no sponsorship available",
    "sponsorship is not available",
)


CITIZENSHIP_BLOCKERS = (
    "must be a u.s. citizen",
    "must be a us citizen",
    "u.s. citizenship required",
    "us citizenship required",
    "requires u.s. citizenship",
    "requires us citizenship",
    "only u.s. citizens",
    "only us citizens",
    "must be a u.s. person",
    "must be a us person",
    "u.s. person required",
    "us person required",
)


CLEARANCE_BLOCKERS = (
    "active security clearance required",
    "must possess a security clearance",
    "must hold a security clearance",
    "active secret clearance",
    "active top secret clearance",
)


# ----------------------------------------------------------------------
# Hardware-oriented embedded roles
# ----------------------------------------------------------------------
#
# These are excluded by explicit user preference. The target is roles
# whose work is fundamentally about hardware: firmware, boards, silicon,
# and bare-metal targets.
#
# Title signals are treated as decisive because a hardware title is a
# reliable statement of what the job is.

HARDWARE_TITLE_PATTERNS = (
    r"\bembedded\b",
    r"\bfirmware\b",
    r"\bhardware\b",
    r"\bfpga\b",
    r"\basic\b",
    r"\brtos\b",
    r"\bverilog\b",
    r"\bvhdl\b",
    r"\bsilicon\b",
    r"\bpcb\b",
    r"\bbring-?up\b",
    r"\bdevice\s+driver",
    r"\belectrical\s+engineer",
    r"\bmechatronics\b",
    r"\bboard\s+support\b",
)


# Description signals are individually weaker: a general software role
# may mention firmware once in passing. Several distinct signals are
# therefore required before the description alone rejects a posting.
HARDWARE_DESCRIPTION_MARKERS = (
    "bare metal",
    "bare-metal",
    "microcontroller",
    "device driver",
    "board support package",
    "board bring-up",
    "real-time operating system",
    "rtos",
    "firmware",
    "fpga",
    "verilog",
    "vhdl",
    "embedded linux",
    "embedded systems",
    "oscilloscope",
    "logic analyzer",
    "soldering",
    "schematic",
    "i2c",
    "spi bus",
    "uart",
    "can bus",
)


# The title carries the decisive signal, so the description-only path is
# deliberately conservative. Three distinct markers keeps genuinely
# embedded work out while letting an ML or platform role that merely
# mentions embedded targets remain in scope.
MINIMUM_HARDWARE_DESCRIPTION_MARKERS = 3


# ----------------------------------------------------------------------
# Programming-language scope
# ----------------------------------------------------------------------
#
# A role that states C and/or C++ and nothing else is excluded.
# A role that pairs C/C++ with any other language stays in scope.
#
# Detecting "other" languages generously is the safe direction: a false
# positive here keeps a job, which matches ACE's recall-first stance.

SYSTEMS_LANGUAGE_PATTERNS = (
    r"c\+\+",
    r"\bcpp\b",
    r"\bc/c\+\+",
    r"(?<![A-Za-z0-9+#])C(?![A-Za-z0-9+#])",
)


# Case-insensitive, unambiguous language names.
OTHER_LANGUAGE_PATTERNS = (
    r"\bpython\b",
    r"\bjava\b",
    r"\bjavascript\b",
    r"\btypescript\b",
    r"\bgolang\b",
    r"\brust\b",
    r"\bscala\b",
    r"\bkotlin\b",
    r"\bswift\b",
    r"\bruby\b",
    r"\bc#",
    r"\bc\s?sharp\b",
    r"\bphp\b",
    r"\bmatlab\b",
    r"\bjulia\b",
    r"\bperl\b",
    r"\bhaskell\b",
    r"\belixir\b",
    r"\berlang\b",
    r"\bclojure\b",
    r"\bdart\b",
    r"\blua\b",
    r"\bobjective-?c\b",
    r"\bsql\b",
    r"\bshell\s+script",
    r"\bbash\b",
    r"\bterraform\b",
    r"\bgroovy\b",
    r"\bf#",
    r"\bocaml\b",
    r"\bzig\b",
)


# Case-sensitive, because the lowercase forms are ordinary English.
CASE_SENSITIVE_OTHER_LANGUAGE_PATTERNS = (
    r"\bGo\b",
    r"\bR\b",
)


EXPERIENCE_PATTERN = re.compile(
    (
        r"(?P<years>\d{1,2})"
        r"\s*\+?\s*"
        r"(?:years|yrs)\b"
    ),
    re.IGNORECASE,
)


def _contains_any(
    text: str,
    phrases: tuple[str, ...],
) -> bool:
    """Return whether text contains any configured phrase."""

    normalized = (
        text.casefold()
    )

    return any(
        phrase.casefold()
        in normalized
        for phrase in phrases
    )


def _matches_any_regex(
    text: str,
    patterns: tuple[str, ...],
) -> bool:
    """Return whether any configured regex matches text."""

    return any(
        re.search(
            pattern,
            text,
            re.IGNORECASE,
        )
        is not None
        for pattern in patterns
    )


def _is_explicitly_non_us_location(
    location: str,
) -> bool:
    """Identify locations that explicitly name a non-US country.

    This runs before the US-state match because a bare two-letter code
    is ambiguous: "Ottawa, ON, CA" is Canada, not California.
    """

    if not location.strip():
        return False

    return _matches_any_regex(
        location,
        NON_US_LOCATION_PATTERNS,
    )


def _is_us_location(
    location: str,
) -> bool:
    """Identify explicit US and Remote-US locations."""

    normalized = (
        location.casefold().strip()
    )

    if not normalized:
        return False

    if _is_explicitly_non_us_location(
        location
    ):
        return False

    if any(
        marker in normalized
        for marker
        in US_LOCATION_MARKERS
    ):
        return True

    if any(
        re.search(
            rf"\b{re.escape(state)}\b",
            normalized,
        )
        for state
        in US_STATE_NAMES
    ):
        return True

    abbreviation_pattern = (
        r",\s*("
        + "|".join(
            sorted(
                US_STATE_ABBREVIATIONS
            )
        )
        + r")\b"
    )

    return bool(
        re.search(
            abbreviation_pattern,
            location,
            re.IGNORECASE,
        )
    )


def _is_ambiguous_remote_location(
    location: str,
) -> bool:
    """Identify remote locations whose geography is not specified.

    These locations are not assumed to be US-based. They are retained as
    STRETCH opportunities so ACE does not silently lose startup roles
    whose postings simply say "Remote", "Worldwide", or "Anywhere".
    """

    if not location.strip():
        return False

    return _matches_any_regex(
        location,
        AMBIGUOUS_REMOTE_PATTERNS,
    )


def _is_clearly_senior(
    title: str,
) -> bool:
    """Detect titles clearly outside ACE's early-career scope."""

    return _matches_any_regex(
        title,
        SENIOR_TITLE_PATTERNS,
    )


def _is_phd_targeted_role(
    job: CanonicalJob,
) -> bool:
    """Detect explicitly PhD-targeted opportunities.

    ACE rejects a posting when:
    - the title explicitly targets PhD/doctoral candidates, or
    - the description explicitly requires a PhD/doctoral degree.

    ACE does not reject postings where a PhD is merely preferred,
    optional, or listed alongside other acceptable degrees.
    """

    if _matches_any_regex(
        job.title,
        PHD_TITLE_PATTERNS,
    ):
        return True

    return _matches_any_regex(
        job.description,
        PHD_REQUIRED_PATTERNS,
    )


def _has_early_career_signal(
    job: CanonicalJob,
) -> bool:
    """Detect explicit new-grad or early-career language."""

    combined_text = (
        f"{job.title} "
        f"{job.description}"
    ).casefold()

    return any(
        marker in combined_text
        for marker
        in EARLY_CAREER_MARKERS
    )


def _required_experience_years(
    description: str,
) -> int | None:
    """Extract the largest non-preferred experience requirement.

    Experience numbers in clearly optional or preferred context are
    ignored by the hard eligibility gate to protect recall.

    No detected experience requirement means unknown, not rejection.
    """

    if not description:
        return None

    required_years: list[int] = []

    for match in (
        EXPERIENCE_PATTERN.finditer(
            description
        )
    ):
        context_start = max(
            0,
            match.start() - 100,
        )

        context_end = min(
            len(description),
            match.end() + 100,
        )

        context = description[
            context_start:
            context_end
        ].casefold()

        if any(
            marker in context
            for marker
            in PREFERRED_CONTEXT_MARKERS
        ):
            continue

        required_years.append(
            int(
                match.group(
                    "years"
                )
            )
        )

    if not required_years:
        return None

    return max(
        required_years
    )


def _is_hardware_embedded_role(
    job: CanonicalJob,
) -> bool:
    """Detect roles whose work is fundamentally about hardware.

    A hardware-oriented title is treated as decisive. A description
    alone must show several distinct hardware signals, so a general
    software role that merely mentions firmware once is not rejected.
    """

    if _matches_any_regex(
        job.title,
        HARDWARE_TITLE_PATTERNS,
    ):
        return True

    if not job.description:
        return False

    # Word-boundary matching, not substring. Short markers such as
    # "uart" and "spi" otherwise match ordinary words like "Stuart"
    # and "inspired". A trailing plural is still the same marker.
    distinct_markers = sum(
        1
        for marker
        in HARDWARE_DESCRIPTION_MARKERS
        if re.search(
            (
                r"\b"
                + re.escape(
                    marker
                )
                + r"s?\b"
            ),
            job.description,
            re.IGNORECASE,
        )
    )

    return (
        distinct_markers
        >= MINIMUM_HARDWARE_DESCRIPTION_MARKERS
    )


def _mentions_systems_language(
    text: str,
) -> bool:
    """Detect a stated C or C++ requirement."""

    for pattern in (
        SYSTEMS_LANGUAGE_PATTERNS
    ):
        # The bare-C pattern is case-sensitive so ordinary prose does
        # not register as the C language.
        flags = (
            0
            if pattern.startswith(
                "(?<!"
            )
            else re.IGNORECASE
        )

        if re.search(
            pattern,
            text,
            flags,
        ):
            return True

    return False


def _mentions_other_language(
    text: str,
) -> bool:
    """Detect any stated language other than C or C++."""

    if _matches_any_regex(
        text,
        OTHER_LANGUAGE_PATTERNS,
    ):
        return True

    return any(
        re.search(
            pattern,
            text,
        )
        is not None
        for pattern
        in CASE_SENSITIVE_OTHER_LANGUAGE_PATTERNS
    )


def _is_systems_language_only_role(
    job: CanonicalJob,
) -> bool:
    """Detect roles stating only C and/or C++ as their languages.

    Silence is not rejection. A posting that names no language at all is
    unknown, not excluded, consistent with ACE's recall-first stance.
    """

    combined_text = (
        f"{job.title}\n{job.description}"
    )

    if not _mentions_systems_language(
        combined_text
    ):
        return False

    return not _mentions_other_language(
        combined_text
    )


def evaluate_job(
    job: CanonicalJob,
) -> EligibilityDecision:
    """Evaluate one normalized job against ACE eligibility rules."""

    role = classify_role(
        job.title
    )

    reject_codes: list[
        EligibilityReasonCode
    ] = []

    reject_reasons: list[
        str
    ] = []

    stretch_codes: list[
        EligibilityReasonCode
    ] = []

    stretch_reasons: list[
        str
    ] = []

    if (
        role.family
        == RoleFamily.OTHER
    ):
        reject_codes.append(
            EligibilityReasonCode
            .NON_TARGET_ROLE
        )

        reject_reasons.append(
            (
                "Role is outside ACE "
                "target role families."
            )
        )

    if _is_us_location(
        job.location
    ):
        pass

    elif (
        _is_ambiguous_remote_location(
            job.location
        )
    ):
        stretch_codes.append(
            EligibilityReasonCode
            .LOCATION_UNCERTAIN
        )

        stretch_reasons.append(
            (
                "Posting is remote but does "
                "not specify geographic scope; "
                "retained to protect discovery "
                "recall."
            )
        )

    else:
        reject_codes.append(
            EligibilityReasonCode
            .OUTSIDE_US
        )

        reject_reasons.append(
            (
                "Location is outside US / "
                "Remote-US scope."
            )
        )

    if _is_clearly_senior(
        job.title
    ):
        reject_codes.append(
            EligibilityReasonCode
            .SENIOR_TITLE
        )

        reject_reasons.append(
            (
                "Title is clearly "
                "senior-level."
            )
        )

    if _is_phd_targeted_role(
        job
    ):
        reject_codes.append(
            EligibilityReasonCode
            .PHD_TARGETED_ROLE
        )

        reject_reasons.append(
            (
                "Posting is explicitly "
                "targeted to or requires "
                "PhD-level candidates."
            )
        )

    required_years = (
        _required_experience_years(
            job.description
        )
    )

    early_career_signal = (
        _has_early_career_signal(
            job
        )
    )

    if (
        required_years is not None
        and required_years >= 5
    ):
        reject_codes.append(
            EligibilityReasonCode
            .EXPERIENCE_TOO_HIGH
        )

        reject_reasons.append(
            (
                "Posting requires "
                f"approximately "
                f"{required_years}+ "
                "years experience."
            )
        )

    elif required_years == 4:
        if early_career_signal:
            stretch_codes.append(
                EligibilityReasonCode
                .EXPERIENCE_STRETCH
            )

            stretch_reasons.append(
                (
                    "Posting requests "
                    "approximately 4 years "
                    "experience but contains "
                    "an explicit early-career "
                    "signal."
                )
            )

        else:
            reject_codes.append(
                EligibilityReasonCode
                .EXPERIENCE_TOO_HIGH
            )

            reject_reasons.append(
                (
                    "Posting requires "
                    "approximately 4 years "
                    "experience."
                )
            )

    elif required_years == 3:
        stretch_codes.append(
            EligibilityReasonCode
            .EXPERIENCE_STRETCH
        )

        stretch_reasons.append(
            (
                "Posting requests "
                "approximately 3 years "
                "experience."
            )
        )

    if _is_hardware_embedded_role(
        job
    ):
        reject_codes.append(
            EligibilityReasonCode
            .HARDWARE_EMBEDDED_ROLE
        )

        reject_reasons.append(
            (
                "Posting is a hardware-"
                "oriented embedded/firmware "
                "role."
            )
        )

    if _is_systems_language_only_role(
        job
    ):
        reject_codes.append(
            EligibilityReasonCode
            .SYSTEMS_LANGUAGE_ONLY
        )

        reject_reasons.append(
            (
                "Posting states C/C++ as its "
                "only programming languages."
            )
        )

    if _contains_any(
        job.description,
        CITIZENSHIP_BLOCKERS,
    ):
        reject_codes.append(
            EligibilityReasonCode
            .CITIZENSHIP_BLOCKER
        )

        reject_reasons.append(
            (
                "Posting contains an "
                "explicit US citizenship / "
                "US-person requirement."
            )
        )

    if _contains_any(
        job.description,
        CLEARANCE_BLOCKERS,
    ):
        reject_codes.append(
            EligibilityReasonCode
            .CLEARANCE_BLOCKER
        )

        reject_reasons.append(
            (
                "Posting contains an "
                "explicit security-clearance "
                "blocker."
            )
        )

    if _contains_any(
        job.description,
        SPONSORSHIP_BLOCKERS,
    ):
        reject_codes.append(
            EligibilityReasonCode
            .SPONSORSHIP_BLOCKER
        )

        reject_reasons.append(
            (
                "Posting explicitly states "
                "sponsorship is unavailable."
            )
        )

    if reject_codes:
        return EligibilityDecision(
            status=(
                EligibilityStatus.REJECT
            ),
            role_family=(
                role.family
            ),
            role_priority=(
                role.priority
            ),
            reason_codes=tuple(
                reject_codes
            ),
            reasons=tuple(
                reject_reasons
            ),
            required_experience_years=(
                required_years
            ),
        )

    if stretch_codes:
        return EligibilityDecision(
            status=(
                EligibilityStatus.STRETCH
            ),
            role_family=(
                role.family
            ),
            role_priority=(
                role.priority
            ),
            reason_codes=tuple(
                stretch_codes
            ),
            reasons=tuple(
                stretch_reasons
            ),
            required_experience_years=(
                required_years
            ),
        )

    return EligibilityDecision(
        status=EligibilityStatus.PASS,
        role_family=role.family,
        role_priority=role.priority,
        reason_codes=(
            EligibilityReasonCode
            .NO_HARD_BLOCKER,
        ),
        reasons=(
            (
                "No hard eligibility "
                "blocker detected."
            ),
        ),
        required_experience_years=(
            required_years
        ),
    )