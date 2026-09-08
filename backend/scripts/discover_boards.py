"""Propose job boards for companies ACE cannot currently reach.

    python -m backend.scripts.discover_boards --limit 100
    python -m backend.scripts.discover_boards --limit 100 --apply

Reads the coverage benchmark's own miss list, so it works on the exact
companies the benchmark counts against ACE, and the two numbers move
together.

Nothing is registered without ``--apply``. Discovery proposes and a
human confirms, because a wrong subscription fills the queue with
another employer's jobs under a name the user recognises, which is
harder to notice than a gap. Two real companies can share a name:
Greenhouse boards ``current`` and ``current81`` both declare
themselves "Current", and no automated check separates them.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import urllib.request

from sqlalchemy import select

from backend.app.coverage.benchmark import (
    HELD_OUT_LISTS,
    companies_in_markdown,
    normalise_company,
)
from backend.app.coverage.probing import (
    BoardCandidate,
    find_board,
)
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
)
from backend.app.db.session import SessionLocal


def fetch_text(
    url: str,
) -> str:
    """Return a held-out list, or empty when unreachable."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "ACE-source-discovery/1.0"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            return response.read().decode(
                "utf-8",
                "replace",
            )
    except Exception:
        return ""


def unreached_companies() -> list[str]:
    """Return companies the benchmark counts as missed, largest first.

    Ordered by how many lists name a company, so the ones several
    trackers agree are worth watching are probed first.
    """

    counts: dict[str, int] = {}

    for _, url in HELD_OUT_LISTS:
        for name in companies_in_markdown(
            fetch_text(
                url
            )
        ):
            counts[name] = (
                counts.get(
                    name,
                    0,
                )
                + 1
            )

    with SessionLocal() as session:
        reachable = {
            normalise_company(
                value
            )
            for value in session.scalars(
                select(
                    JobRecord.company
                )
                .where(
                    JobRecord.is_active.is_(
                        True
                    )
                )
                .distinct()
            )
        } | {
            normalise_company(
                value
            )
            for value in session.scalars(
                select(
                    JobSourceRecord
                    .company_name
                ).distinct()
            )
        }

    missing = [
        name
        for name in counts
        if name not in reachable
    ]

    return sorted(
        missing,
        key=lambda name: (
            -counts[name],
            name,
        ),
    )


# The host a source is fetched from. Greenhouse and Ashby default it
# themselves, but Lever refuses without one and every board the prober
# registered failed with "Lever source_host is required" before this
# was set. Found by auditing which sources had never polled.
SOURCE_HOSTS = {
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "greenhouse": (
        "job-boards.greenhouse.io"
    ),
}


def register(
    candidates: list[BoardCandidate],
) -> int:
    """Register confirmed boards, skipping any already known."""

    added = 0

    with SessionLocal() as session:
        for candidate in candidates:
            exists = session.scalar(
                select(
                    JobSourceRecord
                ).where(
                    JobSourceRecord
                    .source_type
                    == candidate.source_type,
                    JobSourceRecord
                    .source_account
                    == candidate.source_account,
                )
            )

            if exists is not None:
                continue

            session.add(
                JobSourceRecord(
                    source_type=(
                        candidate.source_type
                    ),
                    source_account=(
                        candidate.source_account
                    ),
                    company_name=(
                        candidate.company
                    ),
                    source_host=SOURCE_HOSTS.get(
                        candidate.source_type
                    ),
                    enabled=True,
                    # The tail is polled daily. Every board on a
                    # five-minute cycle is neither possible nor polite
                    # once there are thousands of them.
                    poll_interval_seconds=86400,
                    discovery_source=(
                        "board_probe"
                    ),
                )
            )

            added += 1

        session.commit()

    return added


def main() -> int:
    """Probe unreached companies and report what was found."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "register the boards found. "
            "Without it nothing is written."
        ),
    )

    args = parser.parse_args()

    companies = unreached_companies()[
        : args.limit
    ]

    if not companies:
        print(
            "nothing unreached to probe"
        )

        return 0

    print(
        f"probing {len(companies)} "
        "companies ACE cannot reach\n"
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers,
    ) as pool:
        found = [
            result
            for result in pool.map(
                find_board,
                companies,
            )
            if result is not None
        ]

    for candidate in sorted(
        found,
        key=lambda item: -item.job_count,
    ):
        print(
            f"  {candidate.company[:26]:26} "
            f"{candidate.source_type:11} "
            f"{candidate.source_account:20} "
            f"{candidate.job_count:5} jobs   "
            f"{candidate.evidence}"
        )

    print(
        f"\n{len(found)} of {len(companies)} "
        f"verified "
        f"({len(found) / len(companies):.0%})"
    )

    if not args.apply:
        print(
            "\nnothing written. Re-run with "
            "--apply to register these."
        )

        return 0

    added = register(
        found
    )

    print(
        f"\nregistered {added} new boards"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
