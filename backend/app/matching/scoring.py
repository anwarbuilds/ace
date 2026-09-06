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

    score = matched skills / skills the posting asks for

Coverage of the posting's requirements is the right denominator, not
overlap with the whole resume. A resume listing thirty skills should not
score badly against a focused posting that names four of them.

Confidence
----------

A posting naming one or two recognised skills does not carry enough
signal to rank on, and a posting whose text ACE never read carries none
at all. Both are reported as unscored rather than as a low score, so an
absent match is never mistaken for a poor one.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.matching.skills import extract_skills


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

    @property
    def is_scored(self) -> bool:
        """Return whether the posting carried enough signal to rank."""

        return self.score is not None

    @property
    def matched_count(self) -> int:
        """Return how many required skills the resume evidences."""

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

    if len(
        job_skills
    ) < MIN_JOB_SKILLS_FOR_SCORE:
        return MatchResult(
            score=None,
            matched_skills=tuple(
                sorted(
                    job_skills
                    & resume_skills
                )
            ),
            missing_skills=tuple(
                sorted(
                    job_skills
                    - resume_skills
                )
            ),
        )

    matched = (
        job_skills & resume_skills
    )

    missing = job_skills - resume_skills

    return MatchResult(
        score=round(
            100
            * len(matched)
            / len(job_skills)
        ),
        matched_skills=tuple(
            sorted(
                matched
            )
        ),
        missing_skills=tuple(
            sorted(
                missing
            )
        ),
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
