"""Deterministic eligibility gate for ACE.

The eligibility gate determines whether a normalized opportunity belongs
in ACE's candidate set.

Core invariants:

1. Role classification determines the target role family.
2. Eligibility determines inclusion.
3. A surfaced job means "apply to this". There is no partial tier.
   An unlabelled role is included; only seniority and a high experience
   bar exclude.
12. Internships and placements are out of scope; full-time only.
4. Missing sponsorship information is unknown, not rejection.
5. Missing experience information is unknown, not rejection.
6. Explicitly PhD-targeted roles are excluded.
7. Ambiguous remote geography qualifies rather than forming a tier.
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
    "2026-09-06-v16"
)


# The user has roughly 3.5 years of experience. A posting demanding four
# or more years is excluded outright rather than softened, because ACE
# now surfaces a single list meaning "apply to this".
MAX_REQUIRED_EXPERIENCE_YEARS = 4


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

    EARLY_CAREER_SIGNAL = (
        "EARLY_CAREER_SIGNAL"
    )

    REQUIREMENTS_NOT_VERIFIED = (
        "REQUIREMENTS_NOT_VERIFIED"
    )

    INTERNSHIP_ROLE = (
        "INTERNSHIP_ROLE"
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
    # Numeric career levels, as Netflix and others write them:
    # "Software Engineer 4", "AI Engineer 6 - Ads Platform". Level 4
    # and above is senior at every company that numbers this way, and
    # the level is the only signal available: 66 of 67 qualifying
    # Netflix postings never state years of experience at all, so the
    # experience rules cannot see them.
    #
    # Threshold is 4 because 1 to 3 are genuinely early career, and
    # those must keep passing ("Software Engineer 1", "Software
    # Engineer 3"). Measured against the stored corpus before adding:
    # 85 of 31,323 active titles match and none of them were passing,
    # so no queue entry is lost to this rule.
    # The lookaheads stop a duration reading as a level: a co-op titled
    # "Project Engineer - 8 to 12 months" is not a level 8 engineer.
    r"\b(?:engineer|developer|scientist|architect|programmer)"
    r"\s*[-\u2013,]?\s*[4-9]\b"
    r"(?!\s*(?:to|[-\u2013])\s*\d)"
    r"(?!\s*(?:month|week|year|day|hour)s?\b)",
    r"\blevel\s*[-\u2013]?\s*[4-9]\b",
    # Netflix also writes the level as "(L5)" or "Engineer L5". Both
    # forms are anchored deliberately: a bare \bL[4-9]\b would also
    # match "L4 Autonomous Vehicles" and "L7 load balancer", where the
    # number is a domain term and says nothing about seniority.
    r"\(\s*L[4-9]\s*\)",
    r"\b(?:engineer|developer|scientist|architect|programmer)"
    r"\s+L[4-9]\b",
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


# Regex citizenship/export-control blockers.
#
# Exact-phrase matching was not enough. The standard ITAR clause reads:
#
#     "applicant must be a (i) U.S. citizen or national"
#
# The enumerator between "a" and "U.S." defeats a literal phrase match,
# which let 316 defense and aerospace postings through the gate.
#
# ITAR and EAR require "US person" status. A candidate needing visa
# sponsorship is not a
# US person, so these roles are closed regardless of sponsorship policy.
CITIZENSHIP_BLOCKER_PATTERNS = (
    r"\bitar\s+requirements?\b",
    r"\bitar[-\s]controlled\b",
    r"subject\s+to\s+(?:the\s+)?itar\b",
    r"conform\s+to\s+u\.?\s?s\.?\s+government\s+export",
    r"\bexport\s+control(?:led)?\s+"
    r"(?:laws|regulations|requirements|restrictions)\b",
    r"\bexport\s+administration\s+regulations\b",

    # "must be a (i) U.S. citizen or national"
    r"must\s+be\s+(?:an?\s+)?"
    r"(?:\(\s*[ivx\d]{1,4}\s*\)\s*)?"
    r"(?:an?\s+)?"
    r"(?:u\.?\s?s\.?|united\s+states)\s*"
    r"(?:citizen|national|person)\b",

    r"(?:u\.?\s?s\.?|united\s+states)\s+citizenship"
    r"[^.]{0,80}?required\b",

    r"requires?\s+(?:u\.?\s?s\.?|united\s+states)\s+citizenship\b",
    r"only\s+(?:u\.?\s?s\.?|united\s+states)\s+citizens\b",
    r"restricted\s+to\s+(?:u\.?\s?s\.?|united\s+states)\s+citizens\b",
    r"(?:u\.?\s?s\.?|united\s+states)\s+persons?\s+"
    r"(?:only|required|as\s+defined)\b",
    r"due\s+to\s+federal\s+contract\s+requirements"
    r"[^.]{0,90}citizenship",
    r"citizenship[^.]{0,40}(?:is\s+)?(?:a\s+)?requirement\b",

    # "U.S. Person status is required"
    r"(?:u\.?\s?s\.?|united\s+states)\s+person\s+status"
    r"[^.]{0,30}required\b",

    # "are a U.S. Person because of required access to..."
    r"\bare\s+a\s+(?:u\.?\s?s\.?|united\s+states)\s+person\b",

    # "access to export controlled data / information / technology"
    r"export\s+control(?:led)?\s+"
    r"(?:data|information|technology|technical\s+data)\b",

    # Bulleted eligibility: "US citizen or permanent resident"
    r"\b(?:u\.?\s?s\.?|united\s+states)\s+citizen\s+or\s+"
    r"(?:lawful\s+)?permanent\s+resident\b",
)


CLEARANCE_BLOCKERS = (
    "active security clearance required",
    "must possess a security clearance",
    "must hold a security clearance",
    "active secret clearance",
    "active top secret clearance",
)


# Any clearance requirement is a blocker. A US security clearance
# requires US citizenship, so "eligibility and willingness to obtain"
# excludes an international candidate just as firmly as holding one.
CLEARANCE_BLOCKER_PATTERNS = (
    r"\bsecurity\s+clearance\b",
    r"\bsecret\s+clearance\b",
    r"\bts\s*/\s*sci\b",
    r"\btop\s+secret\b",
    r"\bpolygraph\b",
    r"\bdod\s+clearance\b",
    r"\bclearable\b",
    r"\bq\s+clearance\b",
)


# ----------------------------------------------------------------------
# Early-career scope
# ----------------------------------------------------------------------
#
# ACE surfaces new-grad and early-career roles only. Anything else is
# noise for this user, who is finishing a Master's and needs roles that
# realistically sponsor international candidates.
EARLY_CAREER_TITLE_PATTERNS = (
    r"\bnew\s?grad(?:uate)?\b",
    r"\brecent\s+graduate\b",
    r"\buniversity\s+(?:graduate|hire|program|recruiting)\b",
    r"\bcollege\s+(?:grad|graduate|hire)\b",
    r"\bentry[-\s]level\b",
    r"\bearly\s+career\b",
    r"\bearly[-\s]in[-\s]career\b",
    r"\bcampus\b",
    r"\brotational\b",
    r"\bgraduate\s+(?:software|engineer|program|scheme)\b",
    r"\bjunior\b",
    r"\bassociate\s+(?:software\s+)?engineer\b",
    r"\b20\d\d\s+(?:grad|start|graduate)\b",
    # "Software Engineer I" / "SDE 1" but not "Engineer II"
    r"\b(?:software\s+engineer|sde|swe|engineer|developer)\s*"
    r"(?:i|1)\b(?![iv\d])",
)


# A role stating two years or less is an early-career role even when it
# never uses the words.
EARLY_CAREER_MAX_YEARS = 2


# Internships are excluded: the user is targeting full-time early-career
# roles only. Kept as a flag rather than deleted rules, because a search
# strategy changes more often than code should.
INCLUDE_INTERNSHIPS = False


INTERNSHIP_TITLE_PATTERNS = (
    r"\bintern\b",
    r"\binterns\b",
    r"\binternship\b",
    r"\bco-?op\b",
    r"\bsummer\s+analyst\b",
    r"\bindustrial\s+placement\b",
    r"\bplacement\s+year\b",
    r"\bworking\s+student\b",
    r"\bwerkstudent\b",
    r"\bapprentice(?:ship)?\b",
    r"\bpraktikum\b",
)


def is_internship(
    job: CanonicalJob,
) -> bool:
    """Detect internship and placement roles.

    Title only. A full-time posting that merely mentions an internship
    programme elsewhere in its text is still a full-time posting.
    """

    return _matches_any_regex(
        job.title,
        INTERNSHIP_TITLE_PATTERNS,
    )


# A posting shorter than this cannot state its own requirements, so the
# rules that read requirement text never had anything to read.
#
# Measured against the live corpus this separates cleanly: curated-feed
# entries run 93 to 172 characters, real postings 2000 and up. The few
# genuine postings it catches are threadbare ones where requirements
# were equally unverifiable, so the label is accurate there too.
MIN_VERIFIABLE_DESCRIPTION_CHARS = 400


def has_verifiable_requirements(
    job: CanonicalJob,
) -> bool:
    """Return whether the posting stated enough to be checked.

    This is not an eligibility question. A job with unverifiable
    requirements still belongs in ACE and still appears in the web
    application; it is simply not something to put in an email as
    "ready to apply", because the experience, clearance and language
    rules could not run on it.
    """

    return (
        len(
            (
                job.description or ""
            ).strip()
        )
        >= MIN_VERIFIABLE_DESCRIPTION_CHARS
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


# ----------------------------------------------------------------------
# Experience extraction
# ----------------------------------------------------------------------
#
# A number is only an experience requirement when it is actually
# attached to experience language. Matching bare digits picked up
# unrelated figures such as salary bands and founding years.
EXPERIENCE_CONTEXT = (
    r"(?:of\s+)?"
    r"(?:relevant\s+|professional\s+|industry\s+|"
    r"hands-?on\s+|work\s+|software\s+|engineering\s+|"
    r"full-?time\s+)*"
    r"(?:experience|building|shipping|working|developing|"
    r"designing|writing|programming)"
)


# "2-5+ years of experience" states a minimum of two, not five.
EXPERIENCE_RANGE_PATTERN = re.compile(
    rf"(?P<low>\d{{1,2}})\s*(?:-|\u2013|\u2014|\s+to\s+)\s*"
    rf"(?P<high>\d{{1,2}})\s*\+?\s*(?:years?|yrs?)\s+"
    rf"{EXPERIENCE_CONTEXT}",
    re.IGNORECASE,
)


EXPERIENCE_PATTERN = re.compile(
    rf"(?P<years>\d{{1,2}})\s*\+?\s*(?:years?|yrs?)\s+"
    rf"{EXPERIENCE_CONTEXT}",
    re.IGNORECASE,
)


# Section headers decide whether a figure is required or merely wanted.
#
# The previous implementation scanned a fixed 100-character window for
# words like "preferred" or "ideally". Real postings almost always have
# such a word near any number -- "ideally in fields such as Computer
# Science ... 4+ years building backend" -- so genuine requirements were
# being discarded and senior roles reached the queue.
PREFERRED_SECTION_PATTERNS = (
    r"preferred\s+qualifications",
    r"nice[-\s]to[-\s]have",
    r"bonus\s+points",
    r"desired\s+qualifications",
    r"good\s+to\s+have",
    r"pluses",
    r"it'?s\s+a\s+plus",
)


REQUIRED_SECTION_PATTERNS = (
    r"minimum\s+qualifications",
    r"basic\s+qualifications",
    r"required\s+qualifications",
    r"requirements",
    r"what\s+you'?ll\s+need",
    r"what\s+we'?re\s+looking\s+for",
    r"who\s+you\s+are",
    r"about\s+you",
    r"qualifications",
)


SECTION_LOOKBACK_CHARS = 1200


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


def _nearest_section_is_preferred(
    description: str,
    position: int,
) -> bool:
    """Classify a match by its nearest preceding section header.

    Returns True when the closest header before ``position`` marks an
    optional section, meaning the figure is wanted rather than required.
    """

    window_start = max(
        0,
        position - SECTION_LOOKBACK_CHARS,
    )

    window = description[
        window_start:position
    ]

    nearest_preferred = -1

    nearest_required = -1

    for pattern in (
        PREFERRED_SECTION_PATTERNS
    ):
        for match in re.finditer(
            pattern,
            window,
            re.IGNORECASE,
        ):
            nearest_preferred = max(
                nearest_preferred,
                match.start(),
            )

    for pattern in (
        REQUIRED_SECTION_PATTERNS
    ):
        for match in re.finditer(
            pattern,
            window,
            re.IGNORECASE,
        ):
            nearest_required = max(
                nearest_required,
                match.start(),
            )

    return (
        nearest_preferred
        > nearest_required
    )


def _experience_figures(
    description: str,
) -> tuple[
    list[int],
    list[int],
]:
    """Return (required, optional) stated experience figures."""

    required: list[int] = []

    optional: list[int] = []

    consumed: set[int] = set()

    # Ranges first, so "2-5 years" is read as a minimum of two rather
    # than as two separate figures.
    for match in (
        EXPERIENCE_RANGE_PATTERN.finditer(
            description
        )
    ):
        for offset in range(
            match.start(),
            match.end(),
        ):
            consumed.add(
                offset
            )

        years = int(
            match.group(
                "low"
            )
        )

        if _nearest_section_is_preferred(
            description,
            match.start(),
        ):
            optional.append(
                years
            )

        else:
            required.append(
                years
            )

    for match in (
        EXPERIENCE_PATTERN.finditer(
            description
        )
    ):
        if match.start() in consumed:
            continue

        years = int(
            match.group(
                "years"
            )
        )

        if _nearest_section_is_preferred(
            description,
            match.start(),
        ):
            optional.append(
                years
            )

        else:
            required.append(
                years
            )

    return (
        required,
        optional,
    )


def _required_experience_years(
    description: str,
) -> int | None:
    """Extract the lowest experience bar the posting actually sets.

    The minimum is used rather than the maximum: a posting listing both
    "3+ years" and "7+ years" will consider a candidate with three.

    When a posting states experience only in an optional section, that
    figure is still used. A role whose sole stated experience bar is
    "8+ years preferred" is not an early-career role, and surfacing it
    would waste the user's application time.

    No detected requirement means unknown, not rejection.
    """

    if not description:
        return None

    required, optional = (
        _experience_figures(
            description
        )
    )

    if required:
        return min(
            required
        )

    if optional:
        return min(
            optional
        )

    return None


def _is_early_career_role(
    job: CanonicalJob,
    *,
    required_years: int | None,
) -> bool:
    """Detect roles open to a new graduate.

    Either an explicit early-career signal, or an experience bar low
    enough that a graduating candidate clearly qualifies.

    A posting that states no experience requirement and carries no
    early-career language is treated as NOT early-career. ACE surfaces a
    single list meaning "apply to this", so an unlabelled senior-leaning
    role is noise rather than opportunity.
    """

    if _matches_any_regex(
        job.title,
        EARLY_CAREER_TITLE_PATTERNS,
    ):
        return True

    if _matches_any_regex(
        job.description,
        EARLY_CAREER_TITLE_PATTERNS,
    ):
        return True

    return (
        required_years is not None
        and required_years
        <= EARLY_CAREER_MAX_YEARS
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

    # Informational only. These never change the outcome; they travel
    # with a qualifying decision so the UI can show a caveat.
    note_codes: list[
        EligibilityReasonCode
    ] = []

    note_reasons: list[
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
        # Remote without stated geography qualifies. ACE surfaces one
        # actionable list, so an ambiguous-but-plausible US remote role
        # belongs in it rather than in a separate tier the user has to
        # reason about. The caveat is still recorded so the card can say
        # the posting never stated its geography.
        note_codes.append(
            EligibilityReasonCode
            .LOCATION_UNCERTAIN
        )

        note_reasons.append(
            (
                "Posting is remote but does "
                "not state geographic scope; "
                "confirm US eligibility "
                "before applying."
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

    # The user has ~3.5 years of experience and wants only roles they
    # can credibly apply to. Four or more years is therefore a hard
    # exclusion rather than a soft penalty, unless the posting also
    # carries an explicit early-career signal.
    # An explicit early-career label does not override a high experience
    # bar. A posting that calls itself a new-grad role while demanding
    # seven years is contradicting itself, and the years are the part
    # that survives contact with a recruiter.
    if (
        required_years is not None
        and required_years
        >= MAX_REQUIRED_EXPERIENCE_YEARS
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

    # An unlabelled role is not excluded. A terse startup posting that
    # states no experience bar and never says "new grad" is frequently
    # open to one, and silence has always meant unknown in ACE rather
    # than rejection. Seniority and experience rules still exclude the
    # roles that genuinely are not open.
    #
    # The signal is kept as information so the queue can lead with
    # explicitly labelled new-grad roles.
    is_early_career = (
        _is_early_career_role(
            job,
            required_years=required_years,
        )
    )

    if not has_verifiable_requirements(
        job
    ):
        note_codes.append(
            EligibilityReasonCode
            .REQUIREMENTS_NOT_VERIFIED
        )

        note_reasons.append(
            (
                "Posting text was not "
                "available, so experience, "
                "clearance and language "
                "requirements could not be "
                "checked. Confirm them on the "
                "employer's posting."
            )
        )

    if is_early_career:
        note_codes.append(
            EligibilityReasonCode
            .EARLY_CAREER_SIGNAL
        )

        note_reasons.append(
            (
                "Posting is explicitly a "
                "new-grad or early-career "
                "role."
            )
        )

    if (
        not INCLUDE_INTERNSHIPS
        and is_internship(
            job
        )
    ):
        reject_codes.append(
            EligibilityReasonCode
            .INTERNSHIP_ROLE
        )

        reject_reasons.append(
            (
                "Posting is an internship or "
                "placement; ACE is scoped to "
                "full-time early-career roles."
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

    # Title and description are searched together. Curated feeds and
    # some employers put clearance or citizenship requirements in the
    # title, where a description-only scan would miss them.
    blocker_text = (
        f"{job.title}\n{job.description}"
    )

    if _contains_any(
        blocker_text,
        CITIZENSHIP_BLOCKERS,
    ) or _matches_any_regex(
        blocker_text,
        CITIZENSHIP_BLOCKER_PATTERNS,
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
        blocker_text,
        CLEARANCE_BLOCKERS,
    ) or _matches_any_regex(
        blocker_text,
        CLEARANCE_BLOCKER_PATTERNS,
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
        blocker_text,
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

    return EligibilityDecision(
        status=EligibilityStatus.PASS,
        role_family=role.family,
        role_priority=role.priority,
        reason_codes=tuple(
            [
                EligibilityReasonCode
                .NO_HARD_BLOCKER,
                *note_codes,
            ]
        ),
        reasons=tuple(
            [
                (
                    "No hard eligibility "
                    "blocker detected."
                ),
                *note_reasons,
            ]
        ),
        required_experience_years=(
            required_years
        ),
    )