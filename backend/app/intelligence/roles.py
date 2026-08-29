"""Role-family classification for ACE.

This module determines which target engineering family a job belongs to.

Role classification is intentionally separate from:
- eligibility,
- work-authorization analysis,
- resume relevance,
- ranking,
- notifications.
"""

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict


ROLE_RULE_VERSION = "2026-08-28-v1"


class RoleFamily(str, Enum):
    """Engineering role families targeted by ACE."""

    SOFTWARE_ENGINEERING = "SOFTWARE_ENGINEERING"
    AI_ML_ENGINEERING = "AI_ML_ENGINEERING"
    FORWARD_DEPLOYED_ENGINEERING = "FORWARD_DEPLOYED_ENGINEERING"
    OTHER = "OTHER"


class RolePriority(str, Enum):
    """Relative priority of an ACE role family."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    NONE = "NONE"


class RoleClassification(BaseModel):
    """Explainable result returned by the role classifier."""

    model_config = ConfigDict(frozen=True)

    family: RoleFamily
    priority: RolePriority
    rule_version: str = ROLE_RULE_VERSION
    matched_pattern: str | None = None


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
)


SOFTWARE_ENGINEERING_PATTERNS = (
    r"\bsoftware engineer\b",
    r"\bsoftware development engineer\b",
    r"\bsoftware developer\b",
    r"\bsystems software engineer\b",
    r"\bbackend software engineer\b",
    r"\bbackend engineer\b",
    r"\bbackend developer\b",
    r"\bfull[- ]?stack software engineer\b",
    r"\bfull[- ]?stack engineer\b",
    r"\bplatform software engineer\b",
    r"\bplatform engineer\b",
    r"\binfrastructure software engineer\b",
    r"\binfrastructure engineer\b",
    r"\bdistributed systems engineer\b",
)


def _first_matching_pattern(
    title: str,
    patterns: tuple[str, ...],
) -> str | None:
    """Return the first regex pattern matching a title."""

    normalized_title = title.casefold()

    for pattern in patterns:
        if re.search(pattern, normalized_title):
            return pattern

    return None


def classify_role(title: str) -> RoleClassification:
    """Classify a job title into one ACE role family.

    Specific families are evaluated before general software engineering.

    For example:

        Machine Learning Software Engineer
            -> AI_ML_ENGINEERING

        Forward Deployed Software Engineer
            -> FORWARD_DEPLOYED_ENGINEERING

    rather than both being classified as generic software engineering.
    """

    fde_match = _first_matching_pattern(
        title,
        FORWARD_DEPLOYED_PATTERNS,
    )

    if fde_match:
        return RoleClassification(
            family=RoleFamily.FORWARD_DEPLOYED_ENGINEERING,
            priority=RolePriority.SECONDARY,
            matched_pattern=fde_match,
        )

    ai_ml_match = _first_matching_pattern(
        title,
        AI_ML_PATTERNS,
    )

    if ai_ml_match:
        return RoleClassification(
            family=RoleFamily.AI_ML_ENGINEERING,
            priority=RolePriority.PRIMARY,
            matched_pattern=ai_ml_match,
        )

    software_match = _first_matching_pattern(
        title,
        SOFTWARE_ENGINEERING_PATTERNS,
    )

    if software_match:
        return RoleClassification(
            family=RoleFamily.SOFTWARE_ENGINEERING,
            priority=RolePriority.PRIMARY,
            matched_pattern=software_match,
        )

    return RoleClassification(
        family=RoleFamily.OTHER,
        priority=RolePriority.NONE,
    )