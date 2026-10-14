"""Resume storage and corpus re-scoring for ACE.

Uploading a resume re-scores every stored job. That is cheap because
scoring is keyword overlap over already-extracted text, not a model
call, so the whole corpus is re-ranked in one pass rather than as a
background job the user waits on.

Scores are derived data. Losing them costs a rebuild, which is why they
live in their own table rather than on the job.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import hashlib

from sqlalchemy import (
    delete,
    func,
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
    ResumeRecord,
)
from backend.app.matching.scoring import (
    MATCHING_ALGORITHM_VERSION,
    build_skills_gap,
    score_job,
)
from backend.app.matching.skills import (
    extract_skills,
)


SCORE_BATCH_SIZE = 1000


def content_hash(
    text: str,
) -> str:
    """Return a stable identity for resume content."""

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def get_active_resume(
    session: Session,
) -> ResumeRecord | None:
    """Return the resume currently used for scoring."""

    return session.scalars(
        select(
            ResumeRecord
        )
        .where(
            ResumeRecord.is_active.is_(
                True
            )
        )
        .order_by(
            ResumeRecord.uploaded_at.desc(),
            ResumeRecord.id.desc(),
        )
        .limit(1)
    ).first()


def store_resume(
    session: Session,
    *,
    label: str,
    filename: str,
    raw_text: str,
    now: datetime | None = None,
) -> ResumeRecord:
    """Store a resume and make it the active one.

    Previous resumes are deactivated rather than deleted, so a later
    score change can be attributed to a resume edit.
    """

    uploaded_at = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    skills = sorted(
        extract_skills(
            raw_text
        )
    )

    session.execute(
        update(
            ResumeRecord
        )
        .where(
            ResumeRecord.is_active.is_(
                True
            )
        )
        .values(
            is_active=False
        )
    )

    record = ResumeRecord(
        label=label.strip()
        or filename,
        filename=filename,
        content_hash=content_hash(
            raw_text
        ),
        raw_text=raw_text,
        extracted_skills=skills,
        is_active=True,
        uploaded_at=uploaded_at,
    )

    session.add(
        record
    )

    session.flush()

    return record


def rescore_corpus(
    session: Session,
    *,
    resume: ResumeRecord,
) -> int:
    """Score every stored job against one resume.

    Returns:
        The number of jobs scored.
    """

    # Re-extract rather than trusting the stored list. The skills on the
    # record were extracted by whatever vocabulary existed at upload
    # time, so after the vocabulary grows they under-report what the
    # resume actually evidences -- and every score built on them would
    # inherit that gap silently.
    resume_skills = extract_skills(
        resume.raw_text or ""
    )

    refreshed = sorted(
        resume_skills
    )

    if refreshed != list(
        resume.extracted_skills or []
    ):
        resume.extracted_skills = (
            refreshed
        )

        session.flush()

    # Captured before the delete below, so a re-score can say what each
    # posting moved from. Without this the ranking reshuffles silently
    # and the user cannot tell improvement from drift.
    prior_scores = {
        job_id: score
        for job_id, score in session.execute(
            select(
                JobResumeScoreRecord.job_id,
                JobResumeScoreRecord.score,
            ).where(
                JobResumeScoreRecord.resume_id
                == resume.id
            )
        ).all()
    }

    session.execute(
        delete(
            JobResumeScoreRecord
        ).where(
            JobResumeScoreRecord.resume_id
            == resume.id
        )
    )

    rows = session.execute(
        select(
            JobRecord.id,
            JobRecord.title,
            JobRecord.description,
            JobEvaluationRecord
            .requirements_verified,
        ).join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
    ).all()

    scored = 0

    pending: list[
        JobResumeScoreRecord
    ] = []

    for (
        job_id,
        title,
        description,
        verified,
    ) in rows:
        result = score_job(
            resume_skills=resume_skills,
            job_text=(
                f"{title}\n{description}"
            ),
            requirements_verified=bool(
                verified
            ),
        )

        pending.append(
            JobResumeScoreRecord(
                job_id=job_id,
                resume_id=resume.id,
                score=result.score,
                matched_skills=list(
                    result.matched_skills
                ),
                missing_skills=list(
                    result.missing_skills
                ),
                related_skills=list(
                    result.related_skills
                ),
                previous_score=(
                    prior_scores.get(
                        job_id
                    )
                ),
                algorithm_version=(
                    MATCHING_ALGORITHM_VERSION
                ),
            )
        )

        scored += 1

        if (
            len(pending)
            >= SCORE_BATCH_SIZE
        ):
            session.add_all(
                pending
            )

            session.flush()

            pending = []

    if pending:
        session.add_all(
            pending
        )

        session.flush()

    return scored


def score_unscored_jobs(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = 2000,
) -> int:
    """Score queue jobs the active resume has no current score for.

    ``rescore_corpus`` runs only when a resume is uploaded, so before
    this existed every job found afterwards had no score row at all: on
    2026-10-10 that was 1,238 of the 1,249 jobs in the queue. The
    scheduler calls this after each cycle.

    Two kinds of row are written. A job with no row for the active
    resume is scored for the first time. A job whose evaluation was
    rewritten after its score was taken (its posting changed, or the
    rules did) is scored again, and remembers what it moved from.

    Bounded to active jobs that passed the gate, the ones the queue
    shows, so a cycle costs what it found rather than the corpus; an
    upload still rescores everything. ``limit`` caps one sweep so a
    backlog drains over a few cycles instead of stalling one.

    Returns:
        The number of jobs scored.
    """

    resume = get_active_resume(
        session
    )

    if resume is None:
        return 0

    stamp = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    rows = session.execute(
        select(
            JobRecord.id,
            JobRecord.title,
            JobRecord.description,
            JobEvaluationRecord
            .requirements_verified,
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .outerjoin(
            JobResumeScoreRecord,
            (
                JobResumeScoreRecord.job_id
                == JobRecord.id
            )
            & (
                JobResumeScoreRecord.resume_id
                == resume.id
            ),
        )
        .where(
            JobRecord.is_active.is_(
                True
            ),
            JobEvaluationRecord
            .eligibility_status
            == "PASS",
            (
                JobResumeScoreRecord.job_id
                .is_(None)
            )
            | (
                JobResumeScoreRecord.scored_at
                < JobEvaluationRecord.evaluated_at
            ),
        )
        .order_by(
            JobRecord.id
        )
        .limit(
            limit
        )
    ).all()

    if not rows:
        return 0

    resume_skills = extract_skills(
        resume.raw_text or ""
    )

    existing = {
        record.job_id: record
        for record in session.scalars(
            select(
                JobResumeScoreRecord
            ).where(
                JobResumeScoreRecord.resume_id
                == resume.id,
                JobResumeScoreRecord.job_id.in_(
                    [
                        row[0]
                        for row in rows
                    ]
                ),
            )
        )
    }

    for (
        job_id,
        title,
        description,
        verified,
    ) in rows:
        result = score_job(
            resume_skills=resume_skills,
            job_text=(
                f"{title}\n{description}"
            ),
            requirements_verified=bool(
                verified
            ),
        )

        values = {
            "score": result.score,
            "matched_skills": list(
                result.matched_skills
            ),
            "missing_skills": list(
                result.missing_skills
            ),
            "related_skills": list(
                result.related_skills
            ),
            "algorithm_version": (
                MATCHING_ALGORITHM_VERSION
            ),
            "scored_at": stamp,
        }

        record = existing.get(
            job_id
        )

        if record is None:
            session.add(
                JobResumeScoreRecord(
                    job_id=job_id,
                    resume_id=resume.id,
                    previous_score=None,
                    **values,
                )
            )

            continue

        values["previous_score"] = (
            record.score
        )

        for (
            field,
            value,
        ) in values.items():
            setattr(
                record,
                field,
                value,
            )

    session.flush()

    return len(
        rows
    )


def stale_score_count(
    session: Session,
    *,
    resume: ResumeRecord,
) -> int:
    """Return how many of a resume's scores predate the current rules.

    Scores are derived data that nothing invalidates on its own: a
    scoring change leaves every stored row in place, still looking
    authoritative. This is what lets the application notice and offer a
    re-score instead of ranking on rules that no longer exist.
    """

    return int(
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                JobResumeScoreRecord
            )
            .where(
                JobResumeScoreRecord
                .resume_id
                == resume.id,
                (
                    JobResumeScoreRecord
                    .algorithm_version
                    .is_distinct_from(
                        MATCHING_ALGORITHM_VERSION
                    )
                ),
            )
        )
        or 0
    )


def skills_gap(
    session: Session,
    *,
    resume: ResumeRecord,
    limit: int = 15,
    role_family: str | None = None,
    min_match: int | None = None,
) -> list[dict]:
    """Return the skills most often missing from qualifying postings.

    ``role_family`` and ``min_match`` narrow the market the report
    describes. "What am I missing for backend roles" and "what am I
    missing for the roles I already fit well" are different questions,
    and one unfiltered list answers neither.

    Restricted to postings that passed the gate, so the report describes
    the user's actual target market rather than the whole corpus.
    """

    rows = (
        select(
            JobResumeScoreRecord
            .missing_skills
        )
        .join(
            JobRecord,
            JobRecord.id
            == JobResumeScoreRecord.job_id,
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .where(
            JobResumeScoreRecord.resume_id
            == resume.id,
            JobRecord.is_active.is_(
                True
            ),
            JobEvaluationRecord
            .eligibility_status
            == "PASS",
        )
    )

    if role_family:
        rows = rows.where(
            JobEvaluationRecord.role_family
            == role_family
        )

    if min_match is not None:
        rows = rows.where(
            JobResumeScoreRecord.score
            >= min_match
        )

    rows = session.execute(
        rows
    ).all()

    missing_lists: list[
        tuple[str, ...]
    ] = []

    total = 0

    for (missing,) in rows:
        total += 1

        if isinstance(
            missing,
            list,
        ):
            missing_lists.append(
                tuple(
                    str(
                        item
                    )
                    for item in missing
                )
            )

    gap = build_skills_gap(
        missing_lists
    )

    return [
        {
            "skill": skill,
            "count": count,
            "share": (
                round(
                    100 * count / total
                )
                if total
                else 0
            ),
        }
        for skill, count in gap[:limit]
    ]
