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
    "2026-09-08-v24"
)


# The user has roughly 3.5 years of experience. A posting demanding four
# or more years is excluded outright rather than softened, because ACE
# now surfaces a single list meaning "apply to this".
MAX_REQUIRED_EXPERIENCE_YEARS = 4


# An open-ended bar at or above this is rejected, while the same figure
# stated as a bound is kept. "3+ years" and "1 to 3 years" both extract
# as three, and they are not the same posting: the first sets a floor
# and takes whoever is above it, so a graduate competes with someone
# who has five. The second describes the band the role sits in.
#
# The user drew this line themselves: anything between zero and three
# should be there, three-plus should not.
MAX_OPEN_ENDED_YEARS = 3


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

    SECURITY_ROLE = (
        "SECURITY_ROLE"
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


# Bare "US" as its own token, and the "US-CA-Menlo Park" shape several
# boards use. Matched on token boundaries rather than as a substring,
# because "us" sits inside Houston, Austin, Belarus and Mauritius.
US_TOKEN_PATTERN = re.compile(
    r"(?:^|[^a-z])u\.?s\.?a?(?:[^a-z]|$)",
    re.IGNORECASE,
)


# US cities written with no country, which several large boards do.
# Stripe posts "San Francisco" and "Chicago"; 1,231 San Francisco
# postings alone were being rejected as outside the US.
#
# Deliberately excludes names whose non-US reading is common in job
# postings: Cambridge, Birmingham, Manchester, Richmond, Vancouver,
# London, Hamilton, Windsor, Waterloo. A bare one of those is genuinely
# ambiguous and guessing wrong fills the queue with jobs the user
# cannot take.
US_CITY_NAMES = frozenset(
    {
        "san francisco",
        "san jose",
        "sunnyvale",
        "mountain view",
        "menlo park",
        "palo alto",
        "santa clara",
        "cupertino",
        "redwood city",
        "san mateo",
        "los angeles",
        "san diego",
        "sacramento",
        "irvine",
        "santa monica",
        "new york",
        "nyc",
        "brooklyn",
        "manhattan",
        "seattle",
        "bellevue",
        "redmond",
        "kirkland",
        "chicago",
        "boston",
        "somerville",
        "austin",
        "dallas",
        "houston",
        "denver",
        "boulder",
        "atlanta",
        "miami",
        "orlando",
        "tampa",
        "philadelphia",
        "pittsburgh",
        "baltimore",
        "washington dc",
        "arlington va",
        "detroit",
        "minneapolis",
        "phoenix",
        "tempe",
        "scottsdale",
        "salt lake city",
        "las vegas",
        "nashville",
        "charlotte",
        "raleigh",
        "durham",
        "st louis",
        "kansas city",
        "columbus ohio",
        "cleveland",
        "indianapolis",
        "milwaukee",
        "new jersey",
        "jersey city",
        "hoboken",
        "stamford",
        "hartford",
        "bay area",
        "silicon valley",
    }
)


# One alternation rather than a regex per city: this runs for every
# posting in the corpus, and sixty-four separate searches per call made
# a full re-evaluation take minutes.
US_CITY_PATTERN = re.compile(
    r"(?:^|[^a-z])(?:"
    + "|".join(
        re.escape(
            city
        )
        for city in sorted(
            US_CITY_NAMES,
            key=len,
            reverse=True,
        )
    )
    + r")(?:[^a-z]|$)",
    re.IGNORECASE,
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
    # Level II is the first rung above new grad: Amazon's SDE II asks
    # 2 to 4 years, and 89 of them were sitting in the queue. Measured
    # before adding: 370 active titles match, 89 were passing.
    # Written for any of the role nouns, because "Software Developer
    # II" and "Data Scientist II" are the same rung.
    r"\b(?:engineer|developer|scientist|architect|"
    r"programmer|analyst)\s+i{2,3}\b",
    r"\bengineer\s+iv\b",
    # Deliberately roman only. Numeric levels 1 to 3 were measured and
    # kept as early career, because Netflix and others number a normal
    # engineer "Software Engineer 3". "SDE II" is a different
    # convention: Amazon's level II asks 2 to 4 years.
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

# Security work is a specialism the user is not pursuing, so it is
# rejected on the title alone rather than left to be skipped by hand
# every day. Deliberately broad: a general engineering role sitting on
# a security team is still a security team, and the user asked for
# these out of the queue outright.
SECURITY_TITLE_PATTERNS = (
    r"\bsecurity\b",
    r"\bappsec\b",
    r"\binfosec\b",
    r"\bcyber\s*security\b",
    r"\bpenetration\s+test",
    r"\bvulnerability\b",
    r"\bcryptograph",
    r"\btrust\s+and\s+safety\b",
)


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
# The words between "years" and the experience noun are unbounded in
# real postings: "5+ years backend software engineering experience",
# "7+ years distributed systems experience". A whitelist of adjectives
# missed all of those, so 5+ year roles reached the queue with no
# requirement recorded at all. Any few words are allowed instead, and
# the requirement is the noun that follows.
EXPERIENCE_CONTEXT = (
    r"(?:of\s+|in\s+|with\s+)?"
    r"(?:[A-Za-z][\w/+#.\-]*[\s,]+){0,6}?"
    r"(?:experience|expertise|background|"
    r"building|shipping|working|developing|"
    r"designing|writing|programming|engineering|"
    r"managing|leading|operating|architecting|"
    r"maintaining|supporting|"
    # Real postings that slipped through with no figure recorded at
    # all: "5+ years of full software development life cycle",
    # "5+ years in software development", "7+ years of full-time
    # software engineering".
    r"development|engineer|software|"
    r"industry|professional|"
    r"roles?|positions?)"
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


# The figure also appears after the noun: "Relevant industry experience
# (6+ years)", "software engineering experience of 5+ years". Written
# that way it escaped the pattern above entirely and the posting was
# recorded as stating no requirement.
# A figure with no experience noun after it. Only trusted inside a
# qualifications section, where it is unambiguous.
EXPERIENCE_BARE_PATTERN = re.compile(
    r"(?P<years>\d{1,2})\s*\+\s*"
    r"(?:years?|yrs?)\b",
    re.IGNORECASE,
)


EXPERIENCE_TRAILING_PATTERN = re.compile(
    r"(?:experience|expertise|background)"
    r"[\s:]*[\(\[]?\s*(?:of\s+|at\s+least\s+)?"
    r"(?P<years>\d{1,2})\s*\+?\s*(?:years?|yrs?)",
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
    r"desired\s+capabilities",
    r"desired\s+skills",
    r"ideally\s+you",
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
    # Real headers found in the corpus that were unrecognised, so a
    # figure under them read as unsectioned and was not trusted.
    # NVIDIA writes "What we need to see:" and its 6+ years went
    # unrecorded.
    r"what\s+we\s+need\s+to\s+see",
    r"qualifications\s+we\s+need",
    r"what\s+you'?ll\s+bring",
    r"what\s+you\s+bring",
    r"your\s+(?:skills\s+and\s+)?experience",
    r"skills\s+and\s+experience",
    r"your\s+background",
    r"must\s+haves?",
    r"you\s+(?:will\s+)?have",
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

    if US_TOKEN_PATTERN.search(
        normalized
    ):
        return True

    if US_CITY_PATTERN.search(
        normalized
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


# Figures describing the company rather than the candidate. "Our team
# has 10+ years of combined experience building X" is a boast, and
# reading it as a requirement rejects a genuine early-career posting.
# The collective subject has to actually own the years. Matching any
# mention of "the team" within sixty characters suppressed a real
# requirement on a Sigma Computing posting whose text read "throughout
# the team and company Qualifications We Need 5+ years", where the
# team is the scope of the work and not the holder of the experience.
COLLECTIVE_EXPERIENCE_PATTERN = re.compile(
    r"(?:our|the)\s+(?:team|company|"
    r"founders?|leadership|group)\s+"
    r"(?:has|have|brings?|combines?|"
    r"bring|share)\b[^.]{0,30}$"
    r"|\bcombined\b[^.]{0,24}$"
    r"|\bcollectively\b[^.]{0,24}$"
    r"|\bwe\s+have\b[^.]{0,36}$",
    re.IGNORECASE,
)


def _describes_the_company(
    description: str,
    position: int,
) -> bool:
    """Return whether a figure is about the employer, not the reader."""

    return bool(
        COLLECTIVE_EXPERIENCE_PATTERN.search(
            description[
                max(
                    0,
                    position - 90,
                ):position
            ]
        )
    )


def _inside_a_qualifications_section(
    description: str,
    position: int,
) -> bool:
    """Return whether any qualifications header precedes this point.

    Used to trust a bare figure. "6+ years in EDA compute" and "5+
    years Unix / Linux" state a requirement with no experience noun
    after the number, so the noun-anchored patterns miss them entirely
    and the posting reads as stating no requirement at all. Inside a
    qualifications block that reading is wrong: a bare "N+ years" there
    is the bar.

    Outside such a block the same figure is untrustworthy, since "10+
    years of combined team experience" is about the company.
    """

    window = description[
        max(
            0,
            position
            - SECTION_LOOKBACK_CHARS,
        ):position
    ]

    return any(
        re.search(
            pattern,
            window,
            re.IGNORECASE,
        )
        for pattern in (
            REQUIRED_SECTION_PATTERNS
            + PREFERRED_SECTION_PATTERNS
        )
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

    # Kept so a required header sitting inside a preferred one can be
    # discarded. "Preferred qualifications" contains "qualifications",
    # which is itself a required header and starts ten characters
    # later, so the bare word won on position and every preferred
    # figure was recorded as required.
    preferred_spans: list[
        tuple[int, int]
    ] = []

    for pattern in (
        PREFERRED_SECTION_PATTERNS
    ):
        for match in re.finditer(
            pattern,
            window,
            re.IGNORECASE,
        ):
            preferred_spans.append(
                (
                    match.start(),
                    match.end(),
                )
            )

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
            if any(
                start
                <= match.start()
                < end
                for start, end in (
                    preferred_spans
                )
            ):
                continue

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
        list(
            EXPERIENCE_PATTERN.finditer(
                description
            )
        )
        + list(
            EXPERIENCE_TRAILING_PATTERN
            .finditer(
                description
            )
        )
        + [
            match
            for match in (
                EXPERIENCE_BARE_PATTERN
                .finditer(
                    description
                )
            )
            if _inside_a_qualifications_section(
                description,
                match.start(),
            )
        ]
    ):
        if match.start() in consumed:
            continue

        if _describes_the_company(
            description,
            match.start(),
        ):
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


def _experience_range_ceiling(
    description: str,
) -> int | None:
    """Return the highest upper bound any stated range reaches.

    A posting asking for "2 to 10+ years" sets its floor at two, so a
    candidate with three qualifies and it should pass. It is still not
    an early-career role, and calling it one puts senior work in a list
    that means "a new graduate can apply to this".
    """

    highs = [
        int(
            match.group(
                "high"
            )
        )
        for match in (
            EXPERIENCE_RANGE_PATTERN
            .finditer(
                description or ""
            )
        )
    ]

    return (
        max(
            highs
        )
        if highs
        else None
    )


# Wording that leaves the top of the range open. A figure with none of
# these around it is a bound, not a floor.
# Wording that caps experience instead of setting a floor. Checked
# first and decisively: "No more than 3 years of professional
# experience" contains "more than 3 years", and reading that as a floor
# inverts the meaning of the most explicit early-career signal a
# posting can carry. A real Aquatic Capital posting titled "Software
# Engineer, Early Career" was rejected by exactly that inversion.
CEILING_PREFIXES = re.compile(
    r"(?:no\s+more\s+than|not\s+more\s+than|"
    r"at\s+most|up\s+to|fewer\s+than|less\s+than|"
    r"under|within|maximum\s+of|max\.?)\s*$",
    re.IGNORECASE,
)


OPEN_ENDED_PREFIXES = re.compile(
    r"(?:at\s+least|minimum\s+of|minimum|min\.?|"
    r"over|more\s+than|no\s+less\s+than)\s*$",
    re.IGNORECASE,
)

# The "+" sits against the digits, but "or more" comes after the unit:
# "3+ years" and "3 years or more" mean the same thing.
OPEN_ENDED_SUFFIX = re.compile(
    r"^\s*(?:\+"
    r"|(?:years?|yrs?)?\s*"
    r"(?:or\s+more|or\s+greater|"
    r"or\s+above|and\s+above|plus\b))",
    re.IGNORECASE,
)


def _is_open_ended(
    description: str,
    match: re.Match,
) -> bool:
    """Return whether a figure sets a floor rather than a bound.

    The "+" is usually attached to the number, but the same meaning is
    written as "at least three years" and "three years or more", and a
    posting saying either is asking for three-or-anything.
    """

    start = match.start(
        "years"
    )

    end = match.end(
        "years"
    )

    before = description[
        max(
            0,
            start - 26,
        ):start
    ]

    if CEILING_PREFIXES.search(
        before
    ):
        return False

    if OPEN_ENDED_SUFFIX.search(
        description[end:end + 22]
    ):
        return True

    return bool(
        OPEN_ENDED_PREFIXES.search(
            before
        )
    )


def _open_ended_required_years(
    description: str,
) -> int | None:
    """Return the highest open-ended bar the posting sets as a
    requirement.

    Ranges are skipped entirely: they are bounded by construction, and
    "2-5+ years" is judged by its ceiling elsewhere.
    """

    if not description:
        return None

    consumed: set[int] = set()

    for match in (
        EXPERIENCE_RANGE_PATTERN.finditer(
            description
        )
    ):
        consumed.update(
            range(
                match.start(),
                match.end(),
            )
        )

    figures: list[int] = []

    for match in (
        list(
            EXPERIENCE_PATTERN.finditer(
                description
            )
        )
        + list(
            EXPERIENCE_TRAILING_PATTERN
            .finditer(
                description
            )
        )
        + list(
            EXPERIENCE_BARE_PATTERN
            .finditer(
                description
            )
        )
    ):
        if match.start() in consumed:
            continue

        if _describes_the_company(
            description,
            match.start(),
        ):
            continue

        if _nearest_section_is_preferred(
            description,
            match.start(),
        ):
            continue

        if not _is_open_ended(
            description,
            match,
        ):
            continue

        figures.append(
            int(
                match.group(
                    "years"
                )
            )
        )

    return (
        max(
            figures
        )
        if figures
        else None
    )


def _required_experience_years(
    description: str,
) -> int | None:
    """Extract the experience bar the posting actually sets.

    The maximum is used rather than the minimum. Taking the lowest
    figure read a posting's incidental requirements as its headline
    one: a real Workday posting stating "5+ years" alongside several
    "1+ year with <tool>" lines was recorded as a one-year role and
    reached the queue. The largest figure in the required section is
    the bar a recruiter actually applies; the small ones are sub-skills
    attached to it.

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
        return max(
            required
        )

    if optional:
        return max(
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

    # Checked before any early-career phrasing. A posting calling
    # itself a new-grad role while asking for seven years is
    # contradicting itself, and the years are the half a recruiter
    # applies. Boilerplate mentioning "new grad" elsewhere in a senior
    # posting used to override the bar entirely.
    if (
        required_years is not None
        and required_years
        > EARLY_CAREER_MAX_YEARS
    ):
        return False

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

    # A range reaching well past early career disqualifies it, even
    # though its floor is low enough to apply against.
    ceiling = _experience_range_ceiling(
        job.description
    )

    if (
        ceiling is not None
        and ceiling
        > MAX_REQUIRED_EXPERIENCE_YEARS
    ):
        return False

    return (
        required_years is not None
        and required_years
        <= EARLY_CAREER_MAX_YEARS
    )


def _is_security_role(
    job: CanonicalJob,
) -> bool:
    """Detect security-specialist postings.

    Title only. A general backend role that merely mentions security in
    its description is not a security role, and matching the body would
    reject most of the queue.
    """

    return _matches_any_regex(
        job.title,
        SECURITY_TITLE_PATTERNS,
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
    open_ended = _open_ended_required_years(
        job.description
    )

    # A range reaching well past the cap is a mid-level posting whose
    # floor happens to be low: "3 to 5+ years" wants someone with four.
    # Its floor alone kept it in a queue that means "a new graduate can
    # apply to this", which is the noise the user reported.
    ceiling = _experience_range_ceiling(
        job.description
    )

    if (
        ceiling is not None
        and ceiling
        > MAX_REQUIRED_EXPERIENCE_YEARS
    ):
        reject_codes.append(
            EligibilityReasonCode
            .EXPERIENCE_TOO_HIGH
        )

        reject_reasons.append(
            (
                "Posting asks for a range "
                f"reaching {ceiling} years."
            )
        )

    elif (
        open_ended is not None
        and open_ended
        >= MAX_OPEN_ENDED_YEARS
    ):
        reject_codes.append(
            EligibilityReasonCode
            .EXPERIENCE_TOO_HIGH
        )

        reject_reasons.append(
            (
                "Posting asks for "
                f"{open_ended}+ years, with "
                "no upper bound."
            )
        )

    elif (
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

    if _is_security_role(
        job
    ):
        reject_codes.append(
            EligibilityReasonCode
            .SECURITY_ROLE
        )

        reject_reasons.append(
            (
                "Posting is a security "
                "specialism, which is outside "
                "what the user is pursuing."
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