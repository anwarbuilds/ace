"""SQLAlchemy repository for ACE job persistence."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    func,
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobRecord,
    SourceState,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


class JobRepository:
    """Persistence operations for normalized jobs and source state.

    The repository deliberately does not commit transactions.

    Transaction boundaries belong to callers so a complete source
    snapshot can succeed or fail atomically.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def is_source_initialized(
        self,
        *,
        source: str,
        source_account: str,
    ) -> bool:
        """Return whether ACE has established a baseline for a source."""

        source_state = self._session.get(
            SourceState,
            (
                source,
                source_account,
            ),
        )

        return source_state is not None

    def observe_jobs(
        self,
        *,
        source: str,
        source_account: str,
        jobs: Sequence[CanonicalJob],
        observed_at: datetime,
    ) -> dict[str, JobObservationStatus]:
        """Persist observed jobs and classify their current state.

        Existing records are fetched in one query to avoid an N+1
        database-query pattern.
        """

        if not jobs:
            return {}

        external_ids = [
            job.external_id
            for job in jobs
        ]

        statement = select(
            JobRecord
        ).where(
            JobRecord.source == source,
            JobRecord.source_account == source_account,
            JobRecord.external_id.in_(
                external_ids
            ),
        )

        existing_records = (
            self._session.scalars(
                statement
            ).all()
        )

        existing_by_external_id = {
            record.external_id: record
            for record in existing_records
        }

        statuses: dict[
            str,
            JobObservationStatus,
        ] = {}

        for job in jobs:
            content_hash = (
                compute_job_content_hash(
                    job
                )
            )

            existing_record = (
                existing_by_external_id.get(
                    job.external_id
                )
            )

            if existing_record is None:
                record = JobRecord(
                    source=source,
                    source_account=source_account,
                    external_id=job.external_id,
                    company=job.company,
                    requisition_id=job.requisition_id,
                    title=job.title,
                    location=job.location,
                    description=job.description,
                    official_url=job.official_url,
                    posted_at=job.posted_at,
                    source_updated_at=job.updated_at,
                    content_hash=content_hash,
                    first_seen_at=observed_at,
                    last_seen_at=observed_at,
                    is_active=True,
                    closed_at=None,
                )

                self._session.add(
                    record
                )

                statuses[
                    job.external_id
                ] = JobObservationStatus.NEW

                continue

            was_inactive = (
                not existing_record.is_active
            )

            content_changed = (
                existing_record.content_hash
                != content_hash
            )

            existing_record.company = (
                job.company
            )

            existing_record.requisition_id = (
                job.requisition_id
            )

            existing_record.title = (
                job.title
            )

            existing_record.location = (
                job.location
            )

            existing_record.description = (
                job.description
            )

            existing_record.official_url = (
                job.official_url
            )

            existing_record.posted_at = (
                job.posted_at
            )

            existing_record.source_updated_at = (
                job.updated_at
            )

            existing_record.content_hash = (
                content_hash
            )

            existing_record.last_seen_at = (
                observed_at
            )

            existing_record.is_active = True
            existing_record.closed_at = None

            if was_inactive:
                statuses[
                    job.external_id
                ] = (
                    JobObservationStatus.REOPENED
                )

            elif content_changed:
                statuses[
                    job.external_id
                ] = (
                    JobObservationStatus.UPDATED
                )

            else:
                statuses[
                    job.external_id
                ] = (
                    JobObservationStatus.UNCHANGED
                )

        self._session.flush()

        return statuses

    def mark_missing_jobs_inactive(
        self,
        *,
        source: str,
        source_account: str,
        observed_external_ids: Sequence[str],
        observed_at: datetime,
    ) -> int:
        """Close active jobs missing from a complete source snapshot."""

        statement = (
            update(
                JobRecord
            )
            .where(
                JobRecord.source == source,
                JobRecord.source_account == source_account,
                JobRecord.is_active.is_(True),
            )
        )

        if observed_external_ids:
            statement = statement.where(
                JobRecord.external_id.not_in(
                    observed_external_ids
                )
            )

        statement = statement.values(
            is_active=False,
            closed_at=observed_at,
        )

        result = self._session.execute(
            statement
        )

        self._session.flush()

        return int(
            result.rowcount or 0
        )

    def record_source_success(
        self,
        *,
        source: str,
        source_account: str,
        observed_at: datetime,
        job_count: int,
    ) -> None:
        """Create or update successful source-snapshot state."""

        source_state = self._session.get(
            SourceState,
            (
                source,
                source_account,
            ),
        )

        if source_state is None:
            source_state = SourceState(
                source=source,
                source_account=source_account,
                initialized_at=observed_at,
                last_success_at=observed_at,
                last_job_count=job_count,
            )

            self._session.add(
                source_state
            )

        else:
            source_state.last_success_at = (
                observed_at
            )

            source_state.last_job_count = (
                job_count
            )

        self._session.flush()

    def count_jobs_for_source(
        self,
        *,
        source: str,
        source_account: str,
    ) -> int:
        """Return the persisted job count for one source account."""

        statement = select(
            func.count(
                JobRecord.id
            )
        ).where(
            JobRecord.source == source,
            JobRecord.source_account == source_account,
        )

        result = self._session.scalar(
            statement
        )

        return int(
            result or 0
        )

    def count_active_jobs_for_source(
        self,
        *,
        source: str,
        source_account: str,
    ) -> int:
        """Return the currently active job count for a source account."""

        statement = select(
            func.count(
                JobRecord.id
            )
        ).where(
            JobRecord.source == source,
            JobRecord.source_account == source_account,
            JobRecord.is_active.is_(True),
        )

        result = self._session.scalar(
            statement
        )

        return int(
            result or 0
        )