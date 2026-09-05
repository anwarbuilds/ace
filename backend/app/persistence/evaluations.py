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
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)


def _evaluation_values(
    candidate: EvaluatedJob,
    *,
    evaluated_at: datetime,
) -> dict:
    """Build the stored columns for one evaluated job."""

    decision = candidate.eligibility

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
        "content_hash": (
            compute_job_content_hash(
                candidate.job
            )
        ),
        "evaluated_at": evaluated_at,
    }


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
