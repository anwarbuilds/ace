"""Domain types for ACE source discovery.

Discovery finds potential ATS accounts before they become scheduler
sources.

A discovered company is only a candidate until ACE successfully verifies
that its ATS endpoint can actually be fetched.
"""

from dataclasses import dataclass
from datetime import datetime

from backend.app.scheduling.types import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    SourceDefinition,
    SourceType,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SourceCandidate:
    """Potential external job source discovered by ACE."""

    source_type: SourceType

    source_account: str

    company_name: str

    discovery_source: str

    source_host: str | None = None

    poll_interval_seconds: int = (
        DEFAULT_POLL_INTERVAL_SECONDS
    )

    evidence_url: str | None = None

    def __post_init__(
        self,
    ) -> None:
        """Validate discovery candidate invariants."""

        if not self.source_account.strip():
            raise ValueError(
                "source_account must not be blank."
            )

        if not self.company_name.strip():
            raise ValueError(
                "company_name must not be blank."
            )

        if not self.discovery_source.strip():
            raise ValueError(
                "discovery_source must not be blank."
            )

        if self.source_host is not None:
            normalized_source_host = (
                self.source_host
                .strip()
                .lower()
                .rstrip(".")
            )

            if not normalized_source_host:
                raise ValueError(
                    "source_host must not be blank."
                )

            object.__setattr__(
                self,
                "source_host",
                normalized_source_host,
            )

        if self.poll_interval_seconds <= 0:
            raise ValueError(
                (
                    "poll_interval_seconds "
                    "must be positive."
                )
            )

    @property
    def identity(
        self,
    ) -> tuple[
        SourceType,
        str,
    ]:
        """Return stable ATS identity for deduplication."""

        return (
            self.source_type,
            self.source_account,
        )

    def to_source_definition(
        self,
    ) -> SourceDefinition:
        """Convert the candidate into scheduler configuration."""

        return SourceDefinition(
            source_type=self.source_type,
            source_account=self.source_account,
            company_name=self.company_name,
            source_host=self.source_host,
            enabled=True,
            poll_interval_seconds=(
                self.poll_interval_seconds
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class SourceVerification:
    """Result of live validation for one discovery candidate."""

    candidate: SourceCandidate

    verified: bool

    job_count: int = 0

    detected_at: datetime | None = None

    error_type: str | None = None

    error_message: str | None = None

    def __post_init__(
        self,
    ) -> None:
        """Validate verification result consistency."""

        if self.job_count < 0:
            raise ValueError(
                "job_count must not be negative."
            )

        if self.verified:
            if self.detected_at is None:
                raise ValueError(
                    (
                        "Verified source must "
                        "have detected_at."
                    )
                )

            if self.error_type is not None:
                raise ValueError(
                    (
                        "Verified source must "
                        "not contain error_type."
                    )
                )

            if self.error_message is not None:
                raise ValueError(
                    (
                        "Verified source must "
                        "not contain error_message."
                    )
                )


@dataclass(
    frozen=True,
    slots=True,
)
class SourceDiscoveryRunResult:
    """Summary of one ACE source-discovery pass."""

    discovered_count: int

    unique_count: int

    verified_count: int

    failed_count: int

    inserted_count: int

    updated_count: int

    verifications: tuple[
        SourceVerification,
        ...,
    ]

    @property
    def catalogued_count(
        self,
    ) -> int:
        """Return number of verified catalog writes."""

        return (
            self.inserted_count
            + self.updated_count
        )