"""Report how much of the market ACE reaches: python -m backend.scripts.coverage_benchmark

Measured against job lists ACE does not seed from, so the number is
recall it earned rather than its own inputs read back. Run it before
and after any change to discovery. A coverage claim that is not this
number is an opinion.

    --json    machine-readable, for recording a baseline
    --misses  print the companies ACE cannot reach
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from sqlalchemy import select

from backend.app.coverage.benchmark import (
    HELD_OUT_LISTS,
    ListResult,
    measure_list,
    normalise_company,
    overall_recall,
)
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
)
from backend.app.db.session import SessionLocal


def fetch(
    url: str,
) -> str:
    """Return a held-out list, or an empty string when unreachable."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "ACE-coverage-benchmark/1.0"
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
    except Exception as error:
        print(
            f"  could not fetch {url}: {error}",
            file=sys.stderr,
        )

        return ""


def main() -> int:
    """Print recall per list and overall."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--json",
        action="store_true",
    )

    parser.add_argument(
        "--misses",
        action="store_true",
    )

    args = parser.parse_args()

    with SessionLocal() as session:
        corpus = {
            normalise_company(
                name
            )
            for name in session.scalars(
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
        }

        watched = {
            normalise_company(
                name
            )
            for name in session.scalars(
                select(
                    JobSourceRecord
                    .company_name
                ).distinct()
            )
        }

    results: list[ListResult] = []

    for name, url in HELD_OUT_LISTS:
        markdown = fetch(
            url
        )

        if not markdown:
            continue

        results.append(
            measure_list(
                name=name,
                markdown=markdown,
                corpus=corpus,
                watched=watched,
            )
        )

    if not results:
        print(
            "no held-out list could be fetched",
            file=sys.stderr,
        )

        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "boards_watched": len(
                        watched
                    ),
                    "companies_in_corpus": len(
                        corpus
                    ),
                    "overall_recall": round(
                        overall_recall(
                            results
                        ),
                        4,
                    ),
                    "lists": [
                        {
                            "name": result.name,
                            "listed": result.listed,
                            "reached": result.reached,
                            "recall": round(
                                result.recall,
                                4,
                            ),
                        }
                        for result in results
                    ],
                },
                indent=2,
            )
        )

        return 0

    print(
        f"ACE polls {len(watched)} boards "
        f"and holds jobs from "
        f"{len(corpus)} companies\n"
    )

    for result in results:
        print(
            f"{result.name}"
        )

        print(
            f"  {result.listed:4d} companies listed"
        )

        print(
            f"  {result.reached:4d} reached "
            f"({result.recall:.0%})   "
            f"[{result.watched} polled, "
            f"{result.in_corpus} already in corpus]"
        )

        print(
            f"  {len(result.missing):4d} missed"
        )

        if args.misses:
            print(
                "       "
                + ", ".join(
                    result.missing[:40]
                )
            )

        print()

    print(
        f"OVERALL RECALL: "
        f"{overall_recall(results):.0%}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
