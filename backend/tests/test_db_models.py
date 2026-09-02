"""Structural tests for ACE SQLAlchemy database models."""

from sqlalchemy import (
    UniqueConstraint,
)

from backend.app.db import (
    models as database_models,
)
from backend.app.db.base import Base


def test_database_metadata_contains_expected_tables() -> None:
    """ACE metadata should expose all durable system tables."""

    assert (
        "jobs"
        in Base.metadata.tables
    )

    assert (
        "source_states"
        in Base.metadata.tables
    )

    assert (
        "notification_outbox"
        in Base.metadata.tables
    )

    assert (
        database_models
        .NotificationOutboxRecord
        .__tablename__
        == "notification_outbox"
    )


def test_jobs_identity_is_unique_per_source_account() -> None:
    """Job identity must be source + source account + external ID."""

    jobs_table = (
        Base.metadata.tables[
            "jobs"
        ]
    )

    unique_constraints = [
        constraint
        for constraint
        in jobs_table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    ]

    identity_constraints = [
        constraint
        for constraint
        in unique_constraints
        if (
            constraint.name
            == "uq_jobs_source_identity"
        )
    ]

    assert (
        len(
            identity_constraints
        )
        == 1
    )

    identity_constraint = (
        identity_constraints[
            0
        ]
    )

    column_names = tuple(
        column.name
        for column
        in identity_constraint.columns
    )

    assert column_names == (
        "source",
        "source_account",
        "external_id",
    )


def test_source_state_uses_source_identity_as_primary_key() -> None:
    """Each ATS source account should have exactly one state record."""

    table = (
        Base.metadata.tables[
            "source_states"
        ]
    )

    primary_key_columns = tuple(
        column.name
        for column
        in table.primary_key.columns
    )

    assert primary_key_columns == (
        "source",
        "source_account",
    )


def test_notification_outbox_has_unique_dedupe_key() -> None:
    """PostgreSQL must reject duplicate logical notification events."""

    table = (
        Base.metadata.tables[
            "notification_outbox"
        ]
    )

    constraints = [
        constraint
        for constraint
        in table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    ]

    matches = [
        constraint
        for constraint
        in constraints
        if (
            constraint.name
            == (
                "uq_notification_outbox_"
                "dedupe_key"
            )
        )
    ]

    assert len(
        matches
    ) == 1

    columns = tuple(
        column.name
        for column
        in matches[
            0
        ].columns
    )

    assert columns == (
        "dedupe_key",
    )