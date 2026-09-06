"""Resume-to-job scoring for ACE.

A score alone is not useful. "62%" tells the user nothing they can act
on, so every score travels with the two lists that explain it: which of
the posting's skills the resume already evidences, and which it does
not.

The missing list is the valuable half. Aggregated across many postings
it becomes a skills-gap report weighted by the user's actual target
market rather than by a listicle.

Scoring shape
-------------

    score = earned credit / skills the posting asks for

Coverage of the posting's requirements is the right denominator, not
overlap with the whole resume. A resume listing thirty skills should not
score badly against a focused posting that names four of them.

Credit is earned at two rates. Naming the skill outright earns full
credit. Naming a related skill -- "distributed systems" against a
posting asking for "scalability" -- earns partial credit, because
adjacent experience is real evidence but weaker than the thing itself.

Partial credit is reported as its own list rather than folded into the
matched list. Telling the user a skill counted only partially, and which
of their own skills earned it, is the difference between a score they
can act on and a number they have to trust.

Confidence
----------

A posting naming one or two recognised skills does not carry enough
signal to rank on, and a posting whose text ACE never read carries none
at all. Both are reported as unscored rather than as a low score, so an
absent match is never mistaken for a poor one.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.matching.skills import (
    extract_skills,
    related_skills,
)


# Identifies the scoring rules that produced a stored score. Bump this
# whenever a change would give the same resume and posting a different
# number, so rows written by the old rules are detectable as stale
# rather than silently mixed in with new ones.
MATCHING_ALGORITHM_VERSION = "2026-09-05-v2"


# What adjacent experience is worth against naming the skill outright.
# Half is a deliberate midpoint: high enough that a strong adjacent
# resume outranks an unrelated one, low enough that it never outranks a
# resume that actually names the requirement.
RELATED_SKILL_CREDIT = 0.5


# Below this many recognised skills a posting cannot be ranked
# meaningfully: one lucky keyword would swing the score.
MIN_JOB_SKILLS_FOR_SCORE = 3


@dataclass(
    frozen=True,
    slots=True,
)
class MatchResult:
    """One resume scored against one posting."""

    score: int | None

    matched_skills: tuple[str, ...]

    missing_skills: tuple[str, ...]

    # Posting skills earned at the partial rate.
    related_skills: tuple[str, ...] = ()

    # (posting skill, the resume skill that earned it). Computed rather
    # than stored, so the explanation can never drift from the graph
    # that produced it.
    related_evidence: tuple[
        tuple[str, str],
        ...,
    ] = ()

    @property
    def is_scored(self) -> bool:
        """Return whether the posting carried enough signal to rank."""

        return self.score is not None

    @property
    def matched_count(self) -> int:
        """Return how many required skills the resume names outright."""

        return len(
            self.matched_skills
        )


def score_job(
    *,
    resume_skills: frozenset[str],
    job_text: str,
    requirements_verified: bool = True,
) -> MatchResult:
    """Score one posting against a resume's skills.

    ``requirements_verified`` is honoured because a posting ACE could
    not read has no requirements to match. Scoring its title alone would
    manufacture a number with nothing behind it.
    """

    if not requirements_verified:
        return MatchResult(
            score=None,
            matched_skills=(),
            missing_skills=(),
        )

    job_skills = extract_skills(
        job_text
    )

    (
        matched,
        related,
        evidence,
        missing,
    ) = _classify_requirements(
        job_skills=job_skills,
        resume_skills=resume_skills,
    )

    scorable = (
        len(job_skills)
        >= MIN_JOB_SKILLS_FOR_SCORE
    )

    if scorable:
        credit = len(
            matched
        ) + (
            RELATED_SKILL_CREDIT
            * len(related)
        )

        score = round(
            100
            * credit
            / len(job_skills)
        )
    else:
        score = None

    return MatchResult(
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        related_skills=related,
        related_evidence=evidence,
    )


def _classify_requirements(
    *,
    job_skills: frozenset[str],
    resume_skills: frozenset[str],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[str, str], ...],
    tuple[str, ...],
]:
    """Sort a posting's skills into matched, related, and missing.

    A skill the resume names outright never falls through to the related
    check, so the two lists cannot overlap and credit is never counted
    twice for one requirement.
    """

    matched: list[str] = []

    related: list[str] = []

    evidence: list[
        tuple[str, str]
    ] = []

    missing: list[str] = []

    for skill in sorted(
        job_skills
    ):
        if skill in resume_skills:
            matched.append(
                skill
            )

            continue

        neighbours = (
            related_skills(
                skill
            )
            & resume_skills
        )

        if neighbours:
            related.append(
                skill
            )

            # Deterministic pick: the graph may offer several, and the
            # explanation must not change between identical runs.
            evidence.append(
                (
                    skill,
                    min(
                        neighbours
                    ),
                )
            )

            continue

        missing.append(
            skill
        )

    return (
        tuple(matched),
        tuple(related),
        tuple(evidence),
        tuple(missing),
    )


def build_skills_gap(
    missing_lists: list[
        tuple[str, ...]
    ],
) -> list[
    tuple[
        str,
        int,
    ]
]:
    """Aggregate missing skills across many postings, commonest first.

    This answers "what should I learn or add to my resume next", ranked
    by how often ACE's own qualifying postings ask for it.

    Only true misses are counted. A skill the resume covers by adjacency
    is weaker evidence but it is not a gap, and listing it here would
    send the user to learn something they can already speak to.
    """

    counts: dict[str, int] = {}

    for missing in missing_lists:
        for skill in missing:
            counts[skill] = (
                counts.get(
                    skill,
                    0,
                )
                + 1
            )

    return sorted(
        counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )
