"""Materialized job-evaluation persistence for ACE.

Eligibility is deterministic and depends only on a job's normalized
content. Storing the decision lets the web application query it in SQL
instead of re-running the gate over the whole corpus per request.

This module writes derived data only. Losing it costs nothing but a
rebuild:

    python -m backend.scripts.backfill_job_evaluations --apply
"""

from collections.abc import (
    Iterable,
    Sequence,
)
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.evaluation.types import EvaluatedJob
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
)
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)


def _values_from_decision(
    decision,
    *,
    content_hash: str,
    evaluated_at: datetime,
) -> dict:
    """Build the stored columns from one eligibility decision.

    Shared by the polling path and the stale-refresh backfill. Two
    copies of this mapping drifted immediately when they existed, so
    there is deliberately only one.
    """

    return {
        "eligibility_status": (
            decision.status.value
        ),
        "role_family": (
            decision.role_family.value
        ),
        "role_priority": (
            decision.role_priority.value
        ),
        "rule_version": (
            decision.rule_version
        ),
        "reason_codes": [
            code.value
            for code
            in decision.reason_codes
        ],
        "reasons": list(
            decision.reasons
        ),
        "required_experience_years": (
            decision
            .required_experience_years
        ),
        "content_hash": content_hash,
        "is_early_career": (
            EligibilityReasonCode
            .EARLY_CAREER_SIGNAL
            in decision.reason_codes
        ),
        "requirements_verified": (
            EligibilityReasonCode
            .REQUIREMENTS_NOT_VERIFIED
            not in decision.reason_codes
        ),
        "evaluated_at": evaluated_at,
    }


def _evaluation_values(
    candidate: EvaluatedJob,
    *,
    evaluated_at: datetime,
) -> dict:
    """Build the stored columns for one evaluated job."""

    return _values_from_decision(
        candidate.eligibility,
        content_hash=(
            compute_job_content_hash(
                candidate.job
            )
        ),
        evaluated_at=evaluated_at,
    )


def record_job_evaluations(
    session: Session,
    *,
    source: str,
    source_account: str,
    evaluated_jobs: Sequence[EvaluatedJob],
    evaluated_at: datetime,
) -> int:
    """Persist evaluation decisions for one source's changed jobs.

    Jobs are addressed by their durable external identity, so this runs
    correctly inside the same transaction that just created them.

    Returns:
        The number of evaluation rows written or refreshed.
    """

    if not evaluated_jobs:
        return 0

    external_ids = [
        candidate.job.external_id
        for candidate in evaluated_jobs
    ]

    job_ids_by_external_id = dict(
        session.execute(
            select(
                JobRecord.external_id,
                JobRecord.id,
            ).where(
                JobRecord.source == source,
                JobRecord.source_account
                == source_account,
                JobRecord.external_id.in_(
                    external_ids
                ),
            )
        ).all()
    )

    if not job_ids_by_external_id:
        return 0

    existing_by_job_id = {
        record.job_id: record
        for record in session.scalars(
            select(
                JobEvaluationRecord
            ).where(
                JobEvaluationRecord.job_id.in_(
                    job_ids_by_external_id.values()
                )
            )
        ).all()
    }

    written = 0

    for candidate in evaluated_jobs:
        job_id = (
            job_ids_by_external_id.get(
                candidate.job.external_id
            )
        )

        if job_id is None:
            continue

        values = _evaluation_values(
            candidate,
            evaluated_at=evaluated_at,
        )

        existing = (
            existing_by_job_id.get(
                job_id
            )
        )

        if existing is None:
            session.add(
                JobEvaluationRecord(
                    job_id=job_id,
                    **values,
                )
            )

        else:
            for (
                field,
                value,
            ) in values.items():
                setattr(
                    existing,
                    field,
                    value,
                )

        written += 1

    session.flush()

    return written


def iter_stale_job_ids(
    session: Session,
    *,
    rule_version: str,
    batch_size: int = 500,
) -> Iterable[int]:
    """Yield ids of jobs whose stored evaluation is missing or stale.

    An evaluation is stale when the job's content changed since it was
    evaluated, or when the eligibility rules themselves changed.
    """

    statement = (
        select(
            JobRecord.id
        )
        .outerjoin(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .where(
            (
                JobEvaluationRecord.job_id
                .is_(None)
            )
            | (
                JobEvaluationRecord.content_hash
                != JobRecord.content_hash
            )
            | (
                JobEvaluationRecord.rule_version
                != rule_version
            )
        )
        .order_by(
            JobRecord.id
        )
    )

    for row in session.execute(
        statement
    ).yield_per(
        batch_size
    ):
        yield row[0]


def refresh_stale_evaluations(
    session: Session,
    *,
    evaluated_at: datetime,
    batch_size: int = 500,
    limit: int | None = None,
) -> int:
    """Re-evaluate every job whose stored decision is out of date.

    Polling refreshes a job's evaluation only when that job appears in a
    snapshot, so a rule change would otherwise take a full cycle across
    every source to land, and jobs whose source has gone quiet would
    keep a decision made under rules that no longer exist.

    ``iter_stale_job_ids`` already described staleness precisely and had
    no caller. This is that caller.

    Returns:
        The number of evaluations rewritten.
    """

    from backend.app.intelligence.eligibility import (
        ELIGIBILITY_RULE_VERSION,
        evaluate_job,
    )
    from backend.app.models.job import (
        CanonicalJob,
    )

    stale_ids = list(
        iter_stale_job_ids(
            session,
            rule_version=(
                ELIGIBILITY_RULE_VERSION
            ),
            batch_size=batch_size,
        )
    )

    if limit is not None:
        stale_ids = stale_ids[:limit]

    refreshed = 0

    for start in range(
        0,
        len(stale_ids),
        batch_size,
    ):
        chunk = stale_ids[
            start : start + batch_size
        ]

        jobs = session.scalars(
            select(
                JobRecord
            ).where(
                JobRecord.id.in_(
                    chunk
                )
            )
        ).all()

        existing = {
            record.job_id: record
            for record in session.scalars(
                select(
                    JobEvaluationRecord
                ).where(
                    JobEvaluationRecord
                    .job_id.in_(
                        chunk
                    )
                )
            ).all()
        }

        for job in jobs:
            decision = evaluate_job(
                CanonicalJob(
                    source=job.source,
                    company=job.company,
                    external_id=(
                        job.external_id
                    ),
                    requisition_id=(
                        job.requisition_id
                    ),
                    title=job.title,
                    location=job.location,
                    description=(
                        job.description
                    ),
                    official_url=(
                        job.official_url
                    ),
                    posted_at=job.posted_at,
                    updated_at=(
                        job.source_updated_at
                    ),
                )
            )

            values = _values_from_decision(
                decision,
                content_hash=(
                    job.content_hash
                ),
                evaluated_at=evaluated_at,
            )

            record = existing.get(
                job.id
            )

            if record is None:
                session.add(
                    JobEvaluationRecord(
                        job_id=job.id,
                        **values,
                    )
                )
            else:
                for (
                    field,
                    value,
                ) in values.items():
                    setattr(
                        record,
                        field,
                        value,
                    )

            refreshed += 1

        session.flush()

    return refreshed
