"""Tests for ACE persistent multi-company source catalog."""
from collections.abc import Generator

from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import (
    Session,
)

from backend.app.db.models import (
    JobSourceRecord,
)
from backend.app.scheduling.catalog import (
    SqlAlchemySourceCatalogRepository,
    load_source_registry,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


VERIFIED_AT = datetime(
    2026,
    9,
    3,
    6,
    0,
    tzinfo=timezone.utc,
)

@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Create a minimal in-memory source-catalog database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    JobSourceRecord.__table__.create(
        engine
    )

    with Session(
        engine
    ) as database_session:
        yield database_session


def add_record(
    session: Session,
    *,
    record_id: int,
    source_type: str = "greenhouse",
    source_account: str,
    company_name: str,
    enabled: bool = True,
    poll_interval_seconds: int = 300,
) -> JobSourceRecord:
    """Insert one source catalog row."""

    record = JobSourceRecord(
        id=record_id,
        source_type=source_type,
        source_account=source_account,
        company_name=company_name,
        enabled=enabled,
        poll_interval_seconds=(
            poll_interval_seconds
        ),
    )

    session.add(
        record
    )

    session.commit()

    return record


def test_catalog_lists_only_enabled_sources(
    session: Session,
) -> None:
    add_record(
        session,
        record_id=1,
        source_account="databricks",
        company_name="Databricks",
    )

    add_record(
        session,
        record_id=2,
        source_account="disabled",
        company_name="Disabled Company",
        enabled=False,
    )

    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    sources = (
        repository
        .list_enabled_definitions()
    )

    assert len(
        sources
    ) == 1

    assert (
        sources[0].source_account
        == "databricks"
    )


def test_catalog_preserves_poll_interval(
    session: Session,
) -> None:
    add_record(
        session,
        record_id=1,
        source_account="fast-company",
        company_name="Fast Company",
        poll_interval_seconds=90,
    )

    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    source = (
        repository
        .list_enabled_definitions()[
            0
        ]
    )

    assert (
        source.poll_interval_seconds
        == 90
    )


def test_catalog_rejects_unsupported_source_type(
    session: Session,
) -> None:
    add_record(
        session,
        record_id=1,
        source_type="unsupported-ats",
        source_account="example",
        company_name="Example",
    )

    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    with pytest.raises(
        ValueError,
        match="Unsupported source_type",
    ):
        repository.list_enabled_definitions()


def test_catalog_upsert_inserts_new_source(
    session: Session,
) -> None:
    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    source = SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account="new-company",
        company_name="New Company",
        poll_interval_seconds=120,
    )

    inserted = repository.upsert(
        source,
        discovery_source="test",
        verified_at=VERIFIED_AT,
    )

    session.commit()

    assert inserted is True

    records = (
        session.query(
            JobSourceRecord
        )
        .all()
    )

    assert len(
        records
    ) == 1

    assert (
        records[0].source_account
        == "new-company"
    )

    assert (
        records[0].discovery_source
        == "test"
    )


def test_catalog_upsert_updates_existing_source_without_duplicate(
    session: Session,
) -> None:
    add_record(
        session,
        record_id=1,
        source_account="company",
        company_name="Old Name",
        poll_interval_seconds=300,
    )

    repository = (
        SqlAlchemySourceCatalogRepository(
            session
        )
    )

    source = SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account="company",
        company_name="New Name",
        poll_interval_seconds=60,
    )

    inserted = repository.upsert(
        source,
        verified_at=VERIFIED_AT,
    )

    session.commit()

    assert inserted is False

    records = (
        session.query(
            JobSourceRecord
        )
        .all()
    )

    assert len(
        records
    ) == 1

    assert (
        records[0].company_name
        == "New Name"
    )

    assert (
        records[0].poll_interval_seconds
        == 60
    )


def test_registry_reflects_new_database_row_without_code_change(
    session: Session,
) -> None:
    add_record(
        session,
        record_id=1,
        source_account="company-a",
        company_name="Company A",
    )

    first_registry = (
        load_source_registry(
            session
        )
    )

    assert (
        len(
            first_registry.enabled_sources
        )
        == 1
    )

    add_record(
        session,
        record_id=2,
        source_account="company-b",
        company_name="Company B",
    )

    second_registry = (
        load_source_registry(
            session
        )
    )

    assert (
        len(
            second_registry.enabled_sources
        )
        == 2
    )

    assert {
        source.company_name
        for source
        in second_registry.enabled_sources
    } == {
        "Company A",
        "Company B",
    }