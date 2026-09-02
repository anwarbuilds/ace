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
    "2026-09-02-v5"
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


def _is_us_location(
    location: str,
) -> bool:
    """Identify explicit US and Remote-US locations."""

    normalized = (
        location.casefold().strip()
    )

    if not normalized:
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