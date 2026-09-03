"""Source registry for ACE automatic job monitoring.

The registry is intentionally independent from source execution.
It answers only:

    Which sources should ACE know about?

Later scheduler modules will consume this registry and dispatch each
source to the appropriate runner.
"""

from collections.abc import (
    Iterable,
    Iterator,
)

from backend.app.scheduling.types import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    SourceDefinition,
    SourceType,
)


class SourceRegistry:
    """Immutable collection of uniquely identified job sources."""

    def __init__(
        self,
        sources: Iterable[
            SourceDefinition
        ],
    ) -> None:
        normalized_sources = tuple(
            sources
        )

        by_identity: dict[
            tuple[
                SourceType,
                str,
            ],
            SourceDefinition,
        ] = {}

        for source in normalized_sources:
            if (
                source.identity
                in by_identity
            ):
                raise ValueError(
                    (
                        "Duplicate source identity: "
                        f"{source.source_type.value}:"
                        f"{source.source_account}"
                    )
                )

            by_identity[
                source.identity
            ] = source

        self._sources = (
            normalized_sources
        )

        self._by_identity = (
            by_identity
        )

    def __len__(self) -> int:
        """Return the number of configured sources."""

        return len(
            self._sources
        )

    def __iter__(
        self,
    ) -> Iterator[
        SourceDefinition
    ]:
        """Iterate over sources in deterministic registry order."""

        return iter(
            self._sources
        )

    @property
    def sources(
        self,
    ) -> tuple[
        SourceDefinition,
        ...,
    ]:
        """Return all configured sources."""

        return self._sources

    @property
    def enabled_sources(
        self,
    ) -> tuple[
        SourceDefinition,
        ...,
    ]:
        """Return only sources currently enabled for polling."""

        return tuple(
            source
            for source in self._sources
            if source.enabled
        )

    def get(
        self,
        *,
        source_type: SourceType,
        source_account: str,
    ) -> SourceDefinition | None:
        """Return one source by durable identity."""

        normalized_source_account = (
            source_account.strip()
        )

        if not normalized_source_account:
            return None

        return self._by_identity.get(
            (
                source_type,
                normalized_source_account,
            )
        )


def build_default_source_registry() -> (
    SourceRegistry
):
    """Build ACE's currently configured default source registry.

    Module 6A begins with the Databricks Greenhouse board that ACE has
    already validated end-to-end.

    Additional employers will later become registry entries rather than
    requiring new scheduler orchestration code.
    """

    return SourceRegistry(
        (
            SourceDefinition(
                source_type=(
                    SourceType.GREENHOUSE
                ),
                source_account=(
                    "databricks"
                ),
                company_name=(
                    "Databricks"
                ),
                enabled=True,
                poll_interval_seconds=(
                    DEFAULT_POLL_INTERVAL_SECONDS
                ),
            ),
        )
    )