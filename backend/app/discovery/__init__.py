"""ACE external source discovery."""

from backend.app.discovery.service import (
    DispatcherSourceVerifier,
    SourceCandidateFetcher,
    SourceCatalogWriter,
    SourceDiscoveryProvider,
    run_source_discovery,
)
from backend.app.discovery.types import (
    SourceCandidate,
    SourceDiscoveryRunResult,
    SourceVerification,
)


__all__ = [
    "DispatcherSourceVerifier",
    "SourceCandidate",
    "SourceCandidateFetcher",
    "SourceCatalogWriter",
    "SourceDiscoveryProvider",
    "SourceDiscoveryRunResult",
    "SourceVerification",
    "run_source_discovery",
]