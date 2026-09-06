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

    resume_skills = frozenset(
        resume.extracted_skills or []
    )

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


def skills_gap(
    session: Session,
    *,
    resume: ResumeRecord,
    limit: int = 15,
) -> list[dict]:
    """Return the skills most often missing from qualifying postings.

    Restricted to postings that passed the gate, so the report describes
    the user's actual target market rather than the whole corpus.
    """

    rows = session.execute(
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
