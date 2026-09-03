"""Domain types for ACE source scheduling.

These types describe which external job sources ACE should monitor and
provide the provider-neutral snapshot representation consumed by the
scheduler.

Provider-specific fetching remains owned by source adapters/runners.
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum

from backend.app.models.job import (
    CanonicalJob,
)


DEFAULT_POLL_INTERVAL_SECONDS = 300


class SourceType(StrEnum):
    """External job-source families supported by ACE."""

    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"


def _require_non_empty(
    value: str,
    *,
    field_name: str,
) -> str:
    """Normalize and validate a required textual configuration value."""

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def _require_positive_integer(
    value: int,
    *,
    field_name: str,
) -> int:
    """Validate a strictly positive integer configuration value."""

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(
            f"{field_name} must be a positive integer."
        )

    return value


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            (
                f"{field_name} must be "
                "timezone-aware."
            )
        )

    return value.astimezone(
        timezone.utc
    )


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Configuration for one independently pollable ACE job source.

    `source_type` identifies the ATS/provider family.

    `source_account` is the provider-specific durable account identity.
    For Greenhouse this is the board token.

    The pair:

        source_type + source_account

    must be globally unique within an ACE source registry.
    """

    source_type: SourceType

    source_account: str

    company_name: str

    source_host: str | None = None

    enabled: bool = True

    poll_interval_seconds: int = (
        DEFAULT_POLL_INTERVAL_SECONDS
    )

    def __post_init__(self) -> None:
        """Normalize and validate immutable source configuration."""

        normalized_source_account = (
            _require_non_empty(
                self.source_account,
                field_name="source_account",
            )
        )

        normalized_company_name = (
            _require_non_empty(
                self.company_name,
                field_name="company_name",
            )
        )

        normalized_source_host: str | None = None

        if self.source_host is not None:
            normalized_source_host = (
                self.source_host
                .strip()
                .lower()
                .rstrip(".")
            )

            if not normalized_source_host:
                raise ValueError(
                    "source_host must not be empty."
                )

        normalized_poll_interval = (
            _require_positive_integer(
                self.poll_interval_seconds,
                field_name=(
                    "poll_interval_seconds"
                ),
            )
        )

        object.__setattr__(
            self,
            "source_account",
            normalized_source_account,
        )

        object.__setattr__(
            self,
            "company_name",
            normalized_company_name,
        )

        object.__setattr__(
            self,
            "source_host",
            normalized_source_host,
        )

        object.__setattr__(
            self,
            "poll_interval_seconds",
            normalized_poll_interval,
        )

    @property
    def identity(
        self,
    ) -> tuple[
        SourceType,
        str,
    ]:
        """Return the durable registry identity for this source."""

        return (
            self.source_type,
            self.source_account,
        )


@dataclass(frozen=True, slots=True)
class FetchedSourceSnapshot:
    """Provider-neutral result of fetching one configured job source.

    The scheduler should not need to know whether jobs came from
    Greenhouse, Lever, Ashby, or another provider.

    Provider-specific runners normalize their output into this type.
    """

    source_definition: SourceDefinition

    detected_at: datetime

    jobs: tuple[
        CanonicalJob,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate cross-provider snapshot invariants."""

        normalized_detected_at = (
            _require_aware_datetime(
                self.detected_at,
                field_name="detected_at",
            )
        )

        for job in self.jobs:
            if (
                job.source
                != self.source_definition
                .source_type.value
            ):
                raise ValueError(
                    (
                        "Fetched job source does not "
                        "match source definition: "
                        f"{job.source!r} != "
                        f"{self.source_definition.source_type.value!r}."
                    )
                )

        object.__setattr__(
            self,
            "detected_at",
            normalized_detected_at,
        )

    @property
    def source_type(
        self,
    ) -> SourceType:
        """Return the configured provider family."""

        return (
            self.source_definition
            .source_type
        )

    @property
    def source(
        self,
    ) -> str:
        """Return the canonical source identifier used by persistence."""

        return self.source_type.value

    @property
    def source_account(
        self,
    ) -> str:
        """Return the durable provider account identity."""

        return (
            self.source_definition
            .source_account
        )

    @property
    def company_name(
        self,
    ) -> str:
        """Return the human-readable company name."""

        return (
            self.source_definition
            .company_name
        )

    @property
    def job_count(
        self,
    ) -> int:
        """Return the number of jobs observed in this snapshot."""

        return len(
            self.jobs
        )