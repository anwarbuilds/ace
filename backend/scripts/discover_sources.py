"""Live ACE public source-discovery command.

Examples:

Preview discovered ATS sources:

    python -m backend.scripts.discover_sources

Preview only the first 20:

    python -m backend.scripts.discover_sources --limit 20

Verify and persist the first 20:

    python -m backend.scripts.discover_sources --limit 20 --apply
"""

from __future__ import annotations

import argparse

from backend.app.db.session import (
    SessionLocal,
)
from backend.app.discovery import (
    DispatcherSourceVerifier,
    run_source_discovery,
)
from backend.app.discovery.providers import (
    PublicJobFeedProvider,
)
from backend.app.scheduling import (
    SqlAlchemySourceCatalogRepository,
    build_default_source_dispatcher,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover ATS job sources "
            "from public feeds."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum number of unique "
            "discovered source candidates."
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Verify discovered candidates "
            "and persist verified sources."
        ),
    )

    return parser.parse_args()


def _preview(
    provider: (
        PublicJobFeedProvider
    ),
) -> None:
    candidates = (
        provider.discover()
    )

    print()
    print(
        "ACE Public Source Discovery"
    )
    print(
        "=" * 72
    )

    print(
        "Candidates:",
        len(
            candidates
        ),
    )

    print()

    if not candidates:
        print(
            "No supported ATS candidates "
            "were discovered."
        )

        return

    for (
        index,
        candidate,
    ) in enumerate(
        candidates,
        start=1,
    ):
        print(
            (
                f"{index:>3}. "
                f"{candidate.company_name}"
            )
        )

        print(
            (
                "     Type:     "
                f"{candidate.source_type.value}"
            )
        )

        print(
            (
                "     Account:  "
                f"{candidate.source_account}"
            )
        )

        print(
            (
                "     Found via:"
                f" {candidate.discovery_source}"
            )
        )


def _apply(
    provider: (
        PublicJobFeedProvider
    ),
) -> None:
    dispatcher = (
        build_default_source_dispatcher()
    )

    verifier = (
        DispatcherSourceVerifier(
            dispatcher
        )
    )

    with SessionLocal.begin() as session:
        catalog = (
            SqlAlchemySourceCatalogRepository(
                session
            )
        )

        result = (
            run_source_discovery(
                provider=provider,
                verifier=verifier,
                catalog=catalog,
            )
        )

    print()
    print(
        "ACE Public Source Discovery"
    )
    print(
        "=" * 72
    )

    print(
        "Discovered:",
        result.discovered_count,
    )

    print(
        "Unique:",
        result.unique_count,
    )

    print(
        "Verified:",
        result.verified_count,
    )

    print(
        "Failed:",
        result.failed_count,
    )

    print(
        "Inserted:",
        result.inserted_count,
    )

    print(
        "Updated:",
        result.updated_count,
    )

    print(
        "Catalogued:",
        result.catalogued_count,
    )


def main() -> None:
    args = _parse_args()

    provider = (
        PublicJobFeedProvider(
            max_candidates=(
                args.limit
            )
        )
    )

    if args.apply:
        _apply(
            provider
        )

        return

    _preview(
        provider
    )


if __name__ == "__main__":
    main()