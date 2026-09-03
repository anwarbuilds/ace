"""Source discovery orchestration for ACE.

The discovery service deliberately separates:

1. finding possible ATS accounts;
2. verifying that those accounts are actually fetchable;
3. writing verified accounts into the persistent scheduler catalog.

A broken candidate must never prevent unrelated candidates from being
verified.
"""

from collections.abc import (
    Iterable,
)
from typing import (
    Protocol,
)

from backend.app.discovery.types import (
    SourceCandidate,
    SourceDiscoveryRunResult,
    SourceVerification,
)
from backend.app.scheduling.types import (
    FetchedSourceSnapshot,
    SourceDefinition,
)


class SourceDiscoveryProvider(
    Protocol
):
    """Provider capable of finding possible job sources."""

    def discover(
        self,
    ) -> Iterable[
        SourceCandidate
    ]:
        """Return potential ATS source candidates."""
        ...


class SourceCandidateFetcher(
    Protocol
):
    """Fetcher used to verify one ATS account."""

    def fetch(
        self,
        source: SourceDefinition,
    ) -> FetchedSourceSnapshot:
        """Fetch one candidate source."""
        ...


class SourceCatalogWriter(
    Protocol
):
    """Persistent catalog writer required by discovery."""

    def upsert(
        self,
        source: SourceDefinition,
        *,
        discovery_source: str | None = None,
        verified_at=None,
    ) -> bool:
        """Insert or update one verified source."""
        ...


class DispatcherSourceVerifier:
    """Verify candidates using ACE's normal source dispatcher.

    This is intentionally the same fetching machinery the production
    scheduler uses.

    A candidate is therefore not considered valid merely because its URL
    exists. It must successfully produce an ACE normalized source snapshot.
    """

    def __init__(
        self,
        fetcher: SourceCandidateFetcher,
    ) -> None:
        self._fetcher = fetcher

    def verify(
        self,
        candidate: SourceCandidate,
    ) -> SourceVerification:
        """Perform live validation of one candidate."""

        source = (
            candidate
            .to_source_definition()
        )

        try:
            snapshot = (
                self._fetcher.fetch(
                    source
                )
            )

        except Exception as exc:
            return SourceVerification(
                candidate=candidate,
                verified=False,
                error_type=(
                    type(exc).__name__
                ),
                error_message=str(
                    exc
                ),
            )

        return SourceVerification(
            candidate=candidate,
            verified=True,
            job_count=(
                snapshot.job_count
            ),
            detected_at=(
                snapshot.detected_at
            ),
        )


def _deduplicate_candidates(
    candidates: Iterable[
        SourceCandidate
    ],
) -> tuple[
    SourceCandidate,
    ...,
]:
    """Deduplicate ATS identities while preserving discovery order.

    The first discovery candidate wins.

    Multiple discovery providers may eventually find the same company.
    Source identity therefore remains:

        source_type + source_account

    rather than company name.
    """

    unique: list[
        SourceCandidate
    ] = []

    seen: set[
        tuple[
            object,
            str,
        ]
    ] = set()

    for candidate in candidates:
        identity = (
            candidate.identity
        )

        if identity in seen:
            continue

        seen.add(
            identity
        )

        unique.append(
            candidate
        )

    return tuple(
        unique
    )


def run_source_discovery(
    *,
    provider: SourceDiscoveryProvider,
    verifier: DispatcherSourceVerifier,
    catalog: SourceCatalogWriter,
) -> SourceDiscoveryRunResult:
    """Discover, verify, and catalog external job sources.

    Candidate verification failures are isolated.

    Database/catalog failures are intentionally *not* swallowed. A catalog
    write failure is infrastructure failure and should cause the surrounding
    transaction to fail rather than silently pretending discovery succeeded.
    """

    discovered = tuple(
        provider.discover()
    )

    unique_candidates = (
        _deduplicate_candidates(
            discovered
        )
    )

    verifications: list[
        SourceVerification
    ] = []

    inserted_count = 0

    updated_count = 0

    for candidate in unique_candidates:
        verification = (
            verifier.verify(
                candidate
            )
        )

        verifications.append(
            verification
        )

        if not verification.verified:
            continue

        source = (
            candidate
            .to_source_definition()
        )

        inserted = catalog.upsert(
            source,
            discovery_source=(
                candidate.discovery_source
            ),
            verified_at=(
                verification.detected_at
            ),
        )

        if inserted:
            inserted_count += 1
        else:
            updated_count += 1

    verified_count = sum(
        1
        for verification
        in verifications
        if verification.verified
    )

    failed_count = (
        len(verifications)
        - verified_count
    )

    return SourceDiscoveryRunResult(
        discovered_count=len(
            discovered
        ),
        unique_count=len(
            unique_candidates
        ),
        verified_count=(
            verified_count
        ),
        failed_count=(
            failed_count
        ),
        inserted_count=(
            inserted_count
        ),
        updated_count=(
            updated_count
        ),
        verifications=tuple(
            verifications
        ),
    )