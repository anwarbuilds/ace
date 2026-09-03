"""Tests for ACE source discovery orchestration."""

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.app.discovery import (
    DispatcherSourceVerifier,
    SourceCandidate,
    run_source_discovery,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


DETECTED_AT = datetime(
    2026,
    9,
    3,
    7,
    0,
    tzinfo=timezone.utc,
)


@dataclass(
    frozen=True,
    slots=True,
)
class FakeFetchedSnapshot:
    """Minimal fetched snapshot required by discovery verification.

    Discovery verification only needs:

        detected_at
        job_count

    The test intentionally does not instantiate ACE's production
    FetchedSourceSnapshot because that object belongs to the scheduling
    boundary and may contain additional constructor requirements.
    """

    detected_at: datetime

    job_count: int


class FakeProvider:
    """Deterministic discovery provider used by tests."""

    def __init__(
        self,
        candidates,
    ) -> None:
        self._candidates = tuple(
            candidates
        )

    def discover(
        self,
    ):
        return self._candidates


class FakeFetcher:
    """Fake ATS fetcher with configurable failures."""

    def __init__(
        self,
        *,
        failing_accounts=(),
        job_count: int = 3,
    ) -> None:
        self.failing_accounts = set(
            failing_accounts
        )

        self.job_count = job_count

        self.calls: list[
            str
        ] = []

    def fetch(
        self,
        source: SourceDefinition,
    ) -> FakeFetchedSnapshot:
        self.calls.append(
            source.source_account
        )

        if (
            source.source_account
            in self.failing_accounts
        ):
            raise RuntimeError(
                (
                    "Synthetic discovery "
                    "verification failure."
                )
            )

        return FakeFetchedSnapshot(
            detected_at=(
                DETECTED_AT
            ),
            job_count=(
                self.job_count
            ),
        )


class FakeCatalog:
    """In-memory catalog writer used by tests."""

    def __init__(
        self,
        *,
        existing_accounts=(),
    ) -> None:
        self.existing_accounts = set(
            existing_accounts
        )

        self.calls = []

    def upsert(
        self,
        source: SourceDefinition,
        *,
        discovery_source=None,
        verified_at=None,
    ) -> bool:
        self.calls.append(
            {
                "source": source,
                "discovery_source": (
                    discovery_source
                ),
                "verified_at": (
                    verified_at
                ),
            }
        )

        if (
            source.source_account
            in self.existing_accounts
        ):
            return False

        self.existing_accounts.add(
            source.source_account
        )

        return True


def candidate(
    account: str,
    company: str,
    *,
    discovery_source: str = "test-provider",
) -> SourceCandidate:
    """Build one Greenhouse discovery candidate."""

    return SourceCandidate(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=account,
        company_name=company,
        discovery_source=(
            discovery_source
        ),
    )


def test_candidate_requires_non_blank_source_account() -> None:
    with pytest.raises(
        ValueError,
        match="source_account",
    ):
        SourceCandidate(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account=" ",
            company_name="Example",
            discovery_source="test",
        )


def test_candidate_requires_positive_poll_interval() -> None:
    with pytest.raises(
        ValueError,
        match="poll_interval_seconds",
    ):
        SourceCandidate(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account="example",
            company_name="Example",
            discovery_source="test",
            poll_interval_seconds=0,
        )


def test_verified_candidate_is_inserted_into_catalog() -> None:
    provider = FakeProvider(
        [
            candidate(
                "company-a",
                "Company A",
            ),
        ]
    )

    fetcher = FakeFetcher()

    catalog = FakeCatalog()

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                fetcher
            )
        ),
        catalog=catalog,
    )

    assert result.discovered_count == 1
    assert result.unique_count == 1

    assert result.verified_count == 1
    assert result.failed_count == 0

    assert result.inserted_count == 1
    assert result.updated_count == 0
    assert result.catalogued_count == 1

    assert len(
        catalog.calls
    ) == 1

    assert (
        catalog.calls[
            0
        ][
            "source"
        ].source_account
        == "company-a"
    )

    verification = (
        result.verifications[
            0
        ]
    )

    assert verification.verified is True
    assert verification.job_count == 3
    assert (
        verification.detected_at
        == DETECTED_AT
    )


def test_existing_verified_candidate_is_updated() -> None:
    provider = FakeProvider(
        [
            candidate(
                "company-a",
                "Company A",
            ),
        ]
    )

    catalog = FakeCatalog(
        existing_accounts={
            "company-a"
        }
    )

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                FakeFetcher()
            )
        ),
        catalog=catalog,
    )

    assert result.verified_count == 1
    assert result.failed_count == 0

    assert result.inserted_count == 0
    assert result.updated_count == 1

    assert result.catalogued_count == 1

    assert len(
        catalog.calls
    ) == 1


def test_duplicate_candidate_identity_is_verified_once() -> None:
    provider = FakeProvider(
        [
            candidate(
                "company-a",
                "Company A",
            ),
            candidate(
                "company-a",
                "Duplicate Company Name",
            ),
        ]
    )

    fetcher = FakeFetcher()

    catalog = FakeCatalog()

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                fetcher
            )
        ),
        catalog=catalog,
    )

    assert result.discovered_count == 2
    assert result.unique_count == 1

    assert result.verified_count == 1
    assert result.failed_count == 0

    assert fetcher.calls == [
        "company-a"
    ]

    assert len(
        catalog.calls
    ) == 1

    assert (
        catalog.calls[
            0
        ][
            "source"
        ].company_name
        == "Company A"
    )


def test_failed_verification_is_not_catalogued() -> None:
    provider = FakeProvider(
        [
            candidate(
                "broken-company",
                "Broken Company",
            ),
        ]
    )

    catalog = FakeCatalog()

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                FakeFetcher(
                    failing_accounts={
                        "broken-company"
                    }
                )
            )
        ),
        catalog=catalog,
    )

    assert result.discovered_count == 1
    assert result.unique_count == 1

    assert result.verified_count == 0
    assert result.failed_count == 1

    assert result.catalogued_count == 0

    assert catalog.calls == []

    verification = (
        result.verifications[
            0
        ]
    )

    assert (
        verification.verified
        is False
    )

    assert (
        verification.error_type
        == "RuntimeError"
    )

    assert (
        "Synthetic discovery"
        in (
            verification.error_message
            or ""
        )
    )


def test_failed_candidate_does_not_block_later_candidate() -> None:
    provider = FakeProvider(
        [
            candidate(
                "broken",
                "Broken Company",
            ),
            candidate(
                "working",
                "Working Company",
            ),
        ]
    )

    fetcher = FakeFetcher(
        failing_accounts={
            "broken"
        }
    )

    catalog = FakeCatalog()

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                fetcher
            )
        ),
        catalog=catalog,
    )

    assert result.discovered_count == 2
    assert result.unique_count == 2

    assert result.verified_count == 1
    assert result.failed_count == 1

    assert result.inserted_count == 1
    assert result.updated_count == 0

    assert fetcher.calls == [
        "broken",
        "working",
    ]

    assert len(
        catalog.calls
    ) == 1

    assert (
        catalog.calls[
            0
        ][
            "source"
        ].source_account
        == "working"
    )


def test_discovery_metadata_reaches_catalog() -> None:
    provider = FakeProvider(
        [
            candidate(
                "startup-x",
                "Startup X",
                discovery_source=(
                    "startup-directory"
                ),
            ),
        ]
    )

    catalog = FakeCatalog()

    result = run_source_discovery(
        provider=provider,
        verifier=(
            DispatcherSourceVerifier(
                FakeFetcher()
            )
        ),
        catalog=catalog,
    )

    assert result.verified_count == 1

    assert len(
        catalog.calls
    ) == 1

    call = catalog.calls[
        0
    ]

    assert (
        call[
            "discovery_source"
        ]
        == "startup-directory"
    )

    assert (
        call[
            "verified_at"
        ]
        == DETECTED_AT
    )


def test_candidate_conversion_preserves_scheduler_configuration() -> None:
    source_candidate = SourceCandidate(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account="startup-y",
        company_name="Startup Y",
        discovery_source="test",
        poll_interval_seconds=120,
    )

    source = (
        source_candidate
        .to_source_definition()
    )

    assert (
        source.source_type
        == SourceType.GREENHOUSE
    )

    assert (
        source.source_account
        == "startup-y"
    )

    assert (
        source.company_name
        == "Startup Y"
    )

    assert (
        source.poll_interval_seconds
        == 120
    )

    assert source.enabled is True