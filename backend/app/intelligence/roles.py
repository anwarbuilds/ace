"""Role-family classification for ACE.

This module determines which target engineering family a job belongs to.

Role classification is intentionally separate from:
- eligibility,
- work-authorization analysis,
- resume relevance,
- ranking,
- notifications.

The classifier is recall-oriented for early-career and startup hiring.
A title should only fall outside the target set when ACE does not have
reasonable evidence that it belongs to a supported engineering family.
"""

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict


ROLE_RULE_VERSION = "2026-09-02-v2"


class RoleFamily(str, Enum):
    """Engineering role families targeted by ACE."""

    SOFTWARE_ENGINEERING = "SOFTWARE_ENGINEERING"
    AI_ML_ENGINEERING = "AI_ML_ENGINEERING"
    FORWARD_DEPLOYED_ENGINEERING = (
        "FORWARD_DEPLOYED_ENGINEERING"
    )
    OTHER = "OTHER"


class RolePriority(str, Enum):
    """Relative priority of an ACE role family."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    NONE = "NONE"


class RoleClassification(BaseModel):
    """Explainable result returned by the role classifier."""

    model_config = ConfigDict(
        frozen=True
    )

    family: RoleFamily

    priority: RolePriority

    rule_version: str = (
        ROLE_RULE_VERSION
    )

    matched_pattern: str | None = None


# Domain qualifiers that make an otherwise-software title a different
# job. "Infrastructure Engineer" is a software role; "Factory
# Infrastructure Engineer" maintains a building.
#
# Checked before family matching, because the qualifier is what the role
# actually is and the software-sounding noun is incidental.
NON_SOFTWARE_DOMAIN_PATTERNS = (
    r"\bfactory\b",
    r"\bmanufacturing\b",
    r"\bfacilities\b",
    r"\bfacility\b",
    r"\bdata\s?cent(?:er|re)\b",
    r"\bmechanical\b",
    r"\belectrical\b",
    r"\bcivil\b",
    r"\bchemical\b",
    r"\bindustrial\b",
    r"\bprocess\s+engineer\b",
    r"\bfield\s+engineer\b",
    r"\bsales\s+engineer\b",
    r"\bsolutions?\s+architect\b",
    r"\bcustomer\s+engineer\b",
    r"\bsupport\s+engineer\b",
    r"\bnetwork\s+operations\b",
    r"\bhelp\s?desk\b",
    r"\bdesktop\b",
    r"\bhardware\s+engineer\b",
    r"\bpackaging\b",
    r"\bsupply\s+chain\s+engineer\b",
    r"\bhvac\b",
)


FORWARD_DEPLOYED_PATTERNS = (
    r"\bforward deployed engineer\b",
    r"\bforward-deployed engineer\b",
    r"\bforward deployed software engineer\b",
    r"\bforward-deployed software engineer\b",
    r"\bforward deployed ai engineer\b",
)


AI_ML_PATTERNS = (
    r"\bai engineer\b",
    r"\bartificial intelligence engineer\b",
    r"\bmachine learning engineer\b",
    r"\bml engineer\b",
    r"\bai/ml engineer\b",
    r"\bml/ai engineer\b",
    r"\bapplied ai engineer\b",
    r"\bapplied ml engineer\b",
    r"\bgenerative ai engineer\b",
    r"\bgenai engineer\b",
    r"\bllm engineer\b",
    r"\bai software engineer\b",
    r"\bmachine learning software engineer\b",
    r"\bai infrastructure engineer\b",
    r"\bml infrastructure engineer\b",
    r"\bai platform engineer\b",
    r"\bml platform engineer\b",
    r"\bai research engineer\b",
    r"\bmachine learning research engineer\b",

    # Startup-style inverted titles.
    r"\bengineer[\s,/-]+ai\b",
    r"\bengineer[\s,/-]+ml\b",
    r"\bengineer[\s,/-]+machine learning\b",
)


# The trailing "(?:ing)?" is the difference between reading a title and
# reading only half of them. University recruiting routinely titles a
# req by discipline rather than by role -- "Software Engineering, New
# Grad", "Software Engineering AMTS (College Grad)", "Associate
# Software Engineering" -- and \bsoftware engineer\b does not match
# "engineering", because the word boundary is not there.
#
# Found from a Plaid "Software Engineering, New Grad" posting the user
# reached by hand. It had been fetched, stored and then rejected as
# NON_TARGET_ROLE: not a coverage gap, a reading gap, and one that hit
# exactly the early-career titles this user is looking for.
#
# It admits some noise ("Admin Assistant, Ads Platform Engineering"),
# which is the recall-first trade ACE already makes elsewhere: a false
# positive keeps a job the user can dismiss, a false negative hides one
# they never learn existed. Most of what it newly matches is senior or
# managerial and is still rejected, just for the accurate reason.
SOFTWARE_ENGINEERING_PATTERNS = (
    r"\bsoftware engineer(?:ing)?\b",
    r"\bsoftware development engineer(?:ing)?\b",
    r"\bsoftware developer\b",
    r"\bsystems software engineer(?:ing)?\b",
    r"\bbackend software engineer(?:ing)?\b",
    r"\bbackend engineer(?:ing)?\b",
    r"\bbackend developer\b",
    r"\bfull[- ]?stack software engineer(?:ing)?\b",
    r"\bfull[- ]?stack engineer(?:ing)?\b",
    r"\bfull[- ]?stack developer\b",
    r"\bplatform software engineer(?:ing)?\b",
    r"\bplatform engineer(?:ing)?\b",
    r"\binfrastructure software engineer(?:ing)?\b",
    r"\binfrastructure engineer(?:ing)?\b",
    r"\bdistributed systems engineer(?:ing)?\b",

    # The rest of the software trade, by its own names. On 2026-10-08,
    # 411 active roles with titles like these were rejected as outside
    # the target families and nothing else: IBM's "Entry Level Back End
    # Developer - Poughkeepsie, NY - 2027" and "Associate Application
    # Developer ... 2027", xAI's "Mobile Android Engineer", 79 Site
    # Reliability Engineers, 69 Java Developers. A narrower title is
    # still judged by every other rule; only the family was wrong.
    r"\bfront[- ]?end (?:software )?(?:engineer(?:ing)?|developer)\b",
    r"\bback[- ]?end (?:software )?(?:engineer(?:ing)?|developer)\b",
    r"\b(?:ios|android) (?:software )?(?:engineer|developer)\b",
    r"\bmobile (?:ios|android) (?:engineer|developer)\b",
    # "Mobile" alone is not the trade: in facilities, a Mobile Engineer
    # is a building engineer who travels between sites -- Jones Lang
    # LaSalle's "Mobile Engineer" and "Union Mobile Engineer" filled the
    # queue under the bare rule. Software when the title says so.
    r"\bmobile (?:software|app(?:lication)?s?) (?:engineer|developer)\b",
    r"\bmobile developer\b",
    r"\bmobile engineer\b(?=.*\b(?:ios|android|react native|flutter|app)\b)",
    r"\b(?:android|ios) and (?:android|ios) (?:engineer|developer)\b",
    r"\bweb (?:software |application )?(?:engineer|developer)\b",
    r"\bapplications? developer\b",
    # Bare "Applications Development Engineer" is KLA's and Applied
    # Materials' semiconductor process role; only the software one counts.
    r"\b(?:software|sw|ai) applications? development engineer\b",
    r"\bsite reliability engineer(?:ing)?\b",
    r"\bsre\b",
    r"\bcloud (?:software )?developer\b",
    r"\bsw (?:engineer|developer)\b",
    r"\b(?:java|python|golang|go|ruby|scala|kotlin|swift|react|javascript|"
    r"typescript|node(?:\.js)?|php) (?:software )?(?:engineer|developer)\b",
    # Led by a symbol, where no word boundary can sit.
    r"(?:^|[^a-z0-9])(?:(?:vb|asp)?\.net|c#|c\+\+) (?:software )?"
    r"(?:engineer|developer|programmer)\b",
    r"\bfull[- ]?stack\b",
    r"\b(?:associate|junior|entry[- ]level) (?:software )?developer\b",

    # Interfaces, games and graphics, by their own names: Cisco's and
    # Nokia's "UI Engineer", Disney's "Advanced Gameplay Engineer",
    # Caterpillar's "Rendering Engineer", Epic's "Build Programmer".
    r"\bui(?:/ux)? (?:software )?(?:engineer|developer)\b",
    r"\bgameplay (?:software )?(?:engineer|developer|programmer)\b",
    r"\bgame (?:software )?(?:engineer|developer|programmer)\b",
    r"\b(?:graphics|rendering) (?:software )?engineer\b",
    # A programmer is software only when the title says which kind: a
    # CNC, CMM or PLC programmer runs machines.
    r"\b(?:software|application|web|php|java|python|research|engine|tools|"
    r"graphics|rendering|animation(?: systems)?|physics|audio|network|"
    r"online|build|ui|ai|gameplay) programmer\b",
    r"\b(?:associate|junior|entry[- ]level) programmer\b",
    # Citi's developers are "Apps Dev Programmer Analysts".
    r"\bprogrammer[/ ]analyst\b",
    r"\banalyst[/ ]programmer\b",

    # Common startup titles.
    r"\bfounding engineer\b",
    r"\bmember of technical staff\b",

    # Common compact recruiting title.
    r"\bswe\b",
)


def _first_matching_pattern(
    title: str,
    patterns: tuple[str, ...],
) -> str | None:
    """Return the first regex pattern matching a title."""

    normalized_title = (
        title.casefold()
    )

    for pattern in patterns:
        if re.search(
            pattern,
            normalized_title,
        ):
            return pattern

    return None


def _is_non_software_domain(
    title: str,
) -> bool:
    """Detect a domain qualifier that overrides a software-sounding noun.

    Infrastructure Engineer is a software role. Factory Infrastructure
    Engineer is not, and the qualifier is what decides.
    """

    return any(
        re.search(
            pattern,
            title,
            re.IGNORECASE,
        )
        is not None
        for pattern
        in NON_SOFTWARE_DOMAIN_PATTERNS
    )


def classify_role(
    title: str,
) -> RoleClassification:
    """Classify a job title into one ACE role family.

    Specific families are evaluated before general software engineering.

    For example:

        Machine Learning Software Engineer
            -> AI_ML_ENGINEERING

        Forward Deployed Software Engineer
            -> FORWARD_DEPLOYED_ENGINEERING

    rather than both being classified as generic software engineering.

    Startup-oriented titles such as Founding Engineer, Full Stack
    Developer, Member of Technical Staff, and SWE are included
    to protect discovery recall. Eligibility remains responsible for
    rejecting explicit seniority or experience blockers.
    """

    if _is_non_software_domain(
        title
    ):
        return RoleClassification(
            family=RoleFamily.OTHER,
            priority=RolePriority.NONE,
            matched_pattern=None,
        )

    fde_match = (
        _first_matching_pattern(
            title,
            FORWARD_DEPLOYED_PATTERNS,
        )
    )

    if fde_match:
        return RoleClassification(
            family=(
                RoleFamily
                .FORWARD_DEPLOYED_ENGINEERING
            ),
            priority=(
                RolePriority.SECONDARY
            ),
            matched_pattern=fde_match,
        )

    ai_ml_match = (
        _first_matching_pattern(
            title,
            AI_ML_PATTERNS,
        )
    )

    if ai_ml_match:
        return RoleClassification(
            family=(
                RoleFamily.AI_ML_ENGINEERING
            ),
            priority=(
                RolePriority.PRIMARY
            ),
            matched_pattern=ai_ml_match,
        )

    software_match = (
        _first_matching_pattern(
            title,
            SOFTWARE_ENGINEERING_PATTERNS,
        )
    )

    if software_match:
        return RoleClassification(
            family=(
                RoleFamily
                .SOFTWARE_ENGINEERING
            ),
            priority=(
                RolePriority.PRIMARY
            ),
            matched_pattern=software_match,
        )

    return RoleClassification(
        family=RoleFamily.OTHER,
        priority=RolePriority.NONE,
    )