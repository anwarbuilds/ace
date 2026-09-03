"""Tests for ACE source-registry configuration."""

import pytest

from backend.app.scheduling.registry import (
    SourceRegistry,
    build_default_source_registry,
)
from backend.app.scheduling.types import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    SourceDefinition,
    SourceType,
)


def make_source(
    *,
    source_account: str = "example",
    company_name: str = "Example Company",
    enabled: bool = True,
    poll_interval_seconds: int = (
        DEFAULT_POLL_INTERVAL_SECONDS
    ),
) -> SourceDefinition:
    """Create one synthetic Greenhouse source definition."""

    return SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=source_account,
        company_name=company_name,
        enabled=enabled,
        poll_interval_seconds=(
            poll_interval_seconds
        ),
    )


def test_source_definition_normalizes_identity() -> None:
    source = make_source(
        source_account=" databricks ",
        company_name=" Databricks ",
    )

    assert (
        source.source_account
        == "databricks"
    )

    assert (
        source.company_name
        == "Databricks"
    )

    assert source.identity == (
        SourceType.GREENHOUSE,
        "databricks",
    )


def test_source_definition_rejects_blank_source_account() -> None:
    with pytest.raises(
        ValueError,
        match="source_account",
    ):
        make_source(
            source_account="   ",
        )


def test_source_definition_rejects_blank_company_name() -> None:
    with pytest.raises(
        ValueError,
        match="company_name",
    ):
        make_source(
            company_name="   ",
        )


@pytest.mark.parametrize(
    "poll_interval_seconds",
    [
        0,
        -1,
    ],
)
def test_source_definition_rejects_non_positive_poll_interval(
    poll_interval_seconds: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="poll_interval_seconds",
    ):
        make_source(
            poll_interval_seconds=(
                poll_interval_seconds
            ),
        )


def test_registry_preserves_source_order() -> None:
    first = make_source(
        source_account="first",
        company_name="First",
    )

    second = make_source(
        source_account="second",
        company_name="Second",
    )

    registry = SourceRegistry(
        (
            first,
            second,
        )
    )

    assert registry.sources == (
        first,
        second,
    )

    assert tuple(
        registry
    ) == (
        first,
        second,
    )

    assert len(
        registry
    ) == 2


def test_registry_returns_only_enabled_sources() -> None:
    enabled = make_source(
        source_account="enabled",
        company_name="Enabled",
        enabled=True,
    )

    disabled = make_source(
        source_account="disabled",
        company_name="Disabled",
        enabled=False,
    )

    registry = SourceRegistry(
        (
            enabled,
            disabled,
        )
    )

    assert (
        registry.enabled_sources
        == (
            enabled,
        )
    )


def test_registry_rejects_duplicate_durable_identity() -> None:
    first = make_source(
        source_account="databricks",
        company_name="Databricks",
    )

    duplicate = make_source(
        source_account="databricks",
        company_name=(
            "Different Display Name"
        ),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate source identity",
    ):
        SourceRegistry(
            (
                first,
                duplicate,
            )
        )


def test_registry_get_returns_source_by_identity() -> None:
    source = make_source(
        source_account="databricks",
        company_name="Databricks",
    )

    registry = SourceRegistry(
        (
            source,
        )
    )

    result = registry.get(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=" databricks ",
    )

    assert result is source


def test_registry_get_returns_none_for_unknown_identity() -> None:
    registry = SourceRegistry(
        (
            make_source(),
        )
    )

    assert (
        registry.get(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account="missing",
        )
        is None
    )


def test_default_registry_contains_validated_databricks_source() -> None:
    registry = (
        build_default_source_registry()
    )

    assert len(
        registry
    ) == 1

    source = registry.sources[
        0
    ]

    assert (
        source.source_type
        == SourceType.GREENHOUSE
    )

    assert (
        source.source_account
        == "databricks"
    )

    assert (
        source.company_name
        == "Databricks"
    )

    assert source.enabled is True

    assert (
        source.poll_interval_seconds
        == DEFAULT_POLL_INTERVAL_SECONDS
    )

    assert (
        registry.enabled_sources
        == (
            source,
        )
    )