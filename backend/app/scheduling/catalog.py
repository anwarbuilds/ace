"""Persistent source catalog for ACE scheduling.

The catalog separates the set of companies/sources ACE monitors from
Python source code.

Adding another employer therefore becomes a database operation rather
than a scheduler code change.
"""

from datetime import datetime
from typing import Iterable

from sqlalchemy import (
    select,
)
from sqlalchemy.orm import (
    Session,
)

from backend.app.db.models import (
    JobSourceRecord,
)
from backend.app.scheduling.registry import (
    SourceRegistry,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


def _record_to_definition(
    record: JobSourceRecord,
) -> SourceDefinition:
    """Convert one persistent catalog row into scheduling configuration."""

    try:
        source_type = SourceType(
            record.source_type
        )

    except ValueError as exc:
        raise ValueError(
            (
                "Unsupported source_type "
                "in source catalog: "
                f"{record.source_type!r}."
            )
        ) from exc

    return SourceDefinition(
        source_type=source_type,
        source_account=(
            record.source_account
        ),
        company_name=(
            record.company_name
        ),
        source_host=(
            record.source_host
        ),
        enabled=record.enabled,
        poll_interval_seconds=(
            record.poll_interval_seconds
        ),
    )


class SqlAlchemySourceCatalogRepository:
    """SQLAlchemy-backed persistent source catalog."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def list_enabled_definitions(
        self,
    ) -> tuple[
        SourceDefinition,
        ...,
    ]:
        """Return every enabled source in deterministic order."""

        statement = (
            select(
                JobSourceRecord
            )
            .where(
                JobSourceRecord.enabled
                .is_(True)
            )
            .order_by(
                JobSourceRecord.company_name,
                JobSourceRecord.source_type,
                JobSourceRecord.source_account,
            )
        )

        records = (
            self._session
            .scalars(
                statement
            )
            .all()
        )

        return tuple(
            _record_to_definition(
                record
            )
            for record
            in records
        )

    def upsert(
        self,
        source: SourceDefinition,
        *,
        discovery_source: str | None = None,
        verified_at: datetime | None = None,
    ) -> bool:
        """Insert or update one source definition.

        Returns True when a new catalog row was created.

        Returns False when an existing source row was updated.
        """

        statement = (
            select(
                JobSourceRecord
            )
            .where(
                JobSourceRecord.source_type
                == source.source_type.value,
                JobSourceRecord.source_account
                == source.source_account,
            )
        )

        record = (
            self._session.scalar(
                statement
            )
        )

        if record is None:
            self._session.add(
                JobSourceRecord(
                    source_type=(
                        source.source_type.value
                    ),
                    source_account=(
                        source.source_account
                    ),
                    company_name=(
                        source.company_name
                    ),
                    source_host=(
                        source.source_host
                    ),
                    enabled=(
                        source.enabled
                    ),
                    poll_interval_seconds=(
                        source.poll_interval_seconds
                    ),
                    discovery_source=(
                        discovery_source
                    ),
                    last_verified_at=(
                        verified_at
                    ),
                )
            )

            return True

        record.company_name = (
            source.company_name
        )

        record.source_host = (
            source.source_host
        )

        record.enabled = (
            source.enabled
        )

        record.poll_interval_seconds = (
            source.poll_interval_seconds
        )

        if discovery_source is not None:
            record.discovery_source = (
                discovery_source
            )

        if verified_at is not None:
            record.last_verified_at = (
                verified_at
            )

        return False


def build_source_registry_from_records(
    records: Iterable[
        JobSourceRecord
    ],
) -> SourceRegistry:
    """Build a registry from persistent source rows."""

    return SourceRegistry(
        tuple(
            _record_to_definition(
                record
            )
            for record
            in records
            if record.enabled
        )
    )


def load_source_registry(
    session: Session,
) -> SourceRegistry:
    """Load the scheduler registry from PostgreSQL."""

    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    return SourceRegistry(
        repository
        .list_enabled_definitions()
    )