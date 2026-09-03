"""Tests for provider host routing metadata."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobSourceRecord,
)
from backend.app.discovery.types import (
    SourceCandidate,
)
from backend.app.scheduling.catalog import (
    SqlAlchemySourceCatalogRepository,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


def test_source_definition_normalizes_source_host() -> None:
    source = SourceDefinition(
        source_type=SourceType.LEVER,
        source_account="example",
        company_name="Example",
        source_host=" Jobs.EU.Lever.CO. ",
    )

    assert (
        source.source_host
        == "jobs.eu.lever.co"
    )


def test_discovery_candidate_preserves_source_host() -> None:
    candidate = SourceCandidate(
        source_type=SourceType.LEVER,
        source_account="example",
        company_name="Example",
        discovery_source="test",
        source_host="jobs.eu.lever.co",
    )

    source = (
        candidate
        .to_source_definition()
    )

    assert (
        source.source_host
        == "jobs.eu.lever.co"
    )

    assert (
        source.source_account
        == "example"
    )


def test_catalog_round_trips_source_host() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    JobSourceRecord.__table__.create(
        engine
    )

    with Session(engine) as session:
        repository = (
            SqlAlchemySourceCatalogRepository(
                session
            )
        )

        inserted = repository.upsert(
            SourceDefinition(
                source_type=SourceType.LEVER,
                source_account="example",
                company_name="Example",
                source_host="jobs.eu.lever.co",
            ),
            discovery_source="test",
        )

        session.commit()

        assert inserted is True

        definitions = (
            repository
            .list_enabled_definitions()
        )

        assert len(definitions) == 1

        source = definitions[0]

        assert (
            source.source_type
            == SourceType.LEVER
        )

        assert (
            source.source_account
            == "example"
        )

        assert (
            source.source_host
            == "jobs.eu.lever.co"
        )