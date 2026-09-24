"""Probe every curated company and record what stood in the way.

    python -m backend.scripts.probe_coverage
    python -m backend.scripts.probe_coverage --apply

The companion to discover_boards. That script asks "which boards can
be found"; this one asks "why not", for every company on the user's own
list, and keeps the answer.

The difference paid for itself immediately. Coverage reported 154
companies as unreachable, and auditing them by hand found that most
were nothing of the kind: a dozen sat on Workday and SmartRecruiters,
which ACE has been able to read for months and never thought to probe;
Calm was refused because its board declares itself "Calm.com"; Zendesk
was missed because its careers page is larger than the buffer that
read it. None of that was visible from a list of names, and all of it
was ACE's own doing.

Nothing is written without --apply, including the probe results.
Discovery proposes and a human confirms.
"""

from __future__ import annotations

import argparse
import concurrent.futures
from collections import Counter

import sqlalchemy as sa

from backend.app.coverage.benchmark import (
    company_keys,
    normalise_company,
)
from backend.app.coverage.companies import (
    CURATED_POLL_INTERVAL_SECONDS,
    MULTI_EMPLOYER_SOURCES,
    TARGET_COMPANIES,
)
from backend.app.coverage.diagnosis import (
    Diagnosis,
    REACHED,
    diagnose,
)
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
    SourceProbeRecord,
)
from backend.app.db.session import SessionLocal
from backend.app.discovery.watchlist import (
    fetch_watchlist,
)


SOURCE_HOSTS = {
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "greenhouse": (
        "job-boards.greenhouse.io"
    ),
    "smartrecruiters": (
        "jobs.smartrecruiters.com"
    ),
}


def reachable_keys(
    session,
) -> set[str]:
    """Return every company whose own board ACE can already read.

    "Reachable" used to mean "polls **or holds jobs from**", and that
    second half was wrong in a way that silently capped coverage. A job
    arriving through a multi-employer feed proves only that the feed
    listed it; it says nothing about whether ACE can read the employer.
    Counting it made the company look covered, so it was dropped from
    the probe list and its own board was never looked for.

    Two Sigma is what that cost. Five of its roles came through the
    curated feed, so it never appeared in a single probe -- while its
    own board carried 55, including the campus software engineering
    posts the user found by hand. Every company in this position is in
    it permanently: reaching them once through a feed is exactly what
    stops ACE ever reaching them properly.
    """

    keys: set[str] = set()

    for name in session.scalars(
        sa.select(
            JobSourceRecord.company_name
        )
    ):
        keys |= company_keys(
            name
        )

    for name in session.scalars(
        sa.select(
            JobRecord.company
        )
        .where(
            JobRecord.is_active.is_(
                True
            ),
            JobRecord.source.not_in(
                MULTI_EMPLOYER_SOURCES
            ),
        )
        .distinct()
    ):
        keys |= company_keys(
            name
        )

    return keys


def corpus_companies(
    session,
) -> list[str]:
    """Employers ACE already holds live postings from.

    The curated list is the user's own picks, and it is 412 names long.
    The corpus is far wider: every employer any feed has ever listed a
    job for, which is a name ACE learned for free and mostly never
    looked at again. 574 of them have no board being polled, and 563
    had never been probed once.

    Two of those turned out to be plain Greenhouse boards with 33 and
    93 postings on them, found only because the user was sent a link
    and asked why ACE had not been. That is the whole argument for
    this: the names were already here.

    Drawn from ACE's own corpus and never from the held-out lists,
    which would make the recall benchmark measure ACE against its own
    inputs.
    """

    rows = session.scalars(
        sa.select(
            JobRecord.company
        )
        .where(
            JobRecord.is_active.is_(
                True
            )
        )
        .distinct()
    ).all()

    seen: set[str] = set()

    names: list[str] = []

    for name in rows:
        cleaned = (name or "").strip()

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        names.append(
            cleaned
        )

    return sorted(
        names
    )


def targets(
    *,
    everything: bool,
    corpus: bool = False,
    watchlist: bool = False,
) -> list[str]:
    """Return the companies worth probing."""

    if everything:
        return list(
            TARGET_COMPANIES
        )

    with SessionLocal() as session:
        reachable = reachable_keys(
            session
        )

        pool = list(
            TARGET_COMPANIES
        )

        if corpus:
            # The curated names first: they are the user's own picks
            # and deserve the earlier attempt when a run is limited.
            curated = {
                name.casefold()
                for name in TARGET_COMPANIES
            }

            pool += [
                name
                for name in corpus_companies(
                    session
                )
                if name.casefold()
                not in curated
            ]

        if watchlist:
            # Names only, from an aggregator. Each is still verified
            # against the employer's own board before it becomes a
            # source, exactly like every other candidate here.
            seen = {
                name.casefold()
                for name in pool
            }

            for name in fetch_watchlist():
                if name.casefold() in seen:
                    continue

                seen.add(
                    name.casefold(),
                )

                pool.append(
                    name,
                )

    return [
        name
        for name in pool
        if not (
            company_keys(
                name
            )
            & reachable
        )
    ]


def record(
    results: list[Diagnosis],
) -> tuple[int, int, int]:
    """Persist the probe results and register the boards found.

    Returns how many boards were registered, how many were renamed to
    the curated name, and how many probe rows were written.
    """

    added = 0

    renamed = 0

    with SessionLocal() as session:
        for result in results:
            key = normalise_company(
                result.company
            )

            row = session.scalar(
                sa.select(
                    SourceProbeRecord
                ).where(
                    SourceProbeRecord
                    .company_key
                    == key
                )
            )

            if row is None:
                row = SourceProbeRecord(
                    company_key=key,
                )

                session.add(
                    row
                )

            row.company_name = (
                result.company
            )

            row.outcome = result.outcome

            row.detail = result.detail

            row.source_type = (
                result.candidate.source_type
                if result.candidate
                else None
            )

            row.source_account = (
                result.candidate.source_account
                if result.candidate
                else None
            )

            row.checked_at = sa.func.now()

            candidate = result.candidate

            if candidate is None:
                continue

            exists = session.scalar(
                sa.select(
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
                # Already polled, under a name that does not match the
                # list. ACE was reading Color Health's board and
                # calling it "Color", so coverage reported the company
                # as unreachable while its jobs were arriving -- the
                # number understating ACE rather than overstating it,
                # which is the better direction to be wrong in and
                # still wrong.
                #
                # Safe to correct only because the probe just verified
                # this board against this company. The name is
                # provenance, never job identity.
                if exists.company_name != candidate.company:
                    exists.company_name = (
                        candidate.company
                    )

                    renamed += 1

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
                    # Workday's host is per tenant and per data
                    # centre, so discovery carries it. Registering one
                    # without it produces a source that never polls.
                    source_host=(
                        candidate.source_host
                        or SOURCE_HOSTS.get(
                            candidate.source_type
                        )
                    ),
                    enabled=True,
                    poll_interval_seconds=(
                        CURATED_POLL_INTERVAL_SECONDS
                    ),
                    discovery_source=(
                        "curated_list"
                    ),
                )
            )

            added += 1

        session.commit()

    return added, renamed, len(
        results
    )


def main() -> int:
    """Probe the curated list and report what is in the way."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "probe at most this many. "
            "0 means all of them."
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "probe every curated company, "
            "not only the unreached ones."
        ),
    )

    parser.add_argument(
        "--corpus",
        action="store_true",
        help=(
            "also probe every employer ACE "
            "already holds a live posting "
            "from, not only the curated list."
        ),
    )

    parser.add_argument(
        "--watchlist",
        action="store_true",
        help=(
            "also probe the employers an "
            "aggregator currently lists as "
            "hiring. Names only; the board "
            "found is always the employer's "
            "own."
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "register the boards found and "
            "record the results. Without it "
            "nothing is written."
        ),
    )

    args = parser.parse_args()

    companies = targets(
        everything=args.all,
        corpus=args.corpus,
        watchlist=args.watchlist,
    )

    if args.limit:
        companies = companies[
            : args.limit
        ]

    if not companies:
        print(
            "every curated company is "
            "already reachable"
        )

        return 0

    print(
        f"probing {len(companies)} "
        "companies\n"
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers,
    ) as pool:
        results = list(
            pool.map(
                diagnose,
                companies,
            )
        )

    counts = Counter(
        result.outcome
        for result in results
    )

    for result in sorted(
        results,
        key=lambda item: (
            item.outcome != REACHED,
            item.company,
        ),
    ):
        print(
            f"  {result.company[:24]:24} "
            f"{result.outcome:17} "
            f"{result.detail[:88]}"
        )

    print()

    for outcome, count in counts.most_common():
        print(
            f"  {count:4}  {outcome}"
        )

    if not args.apply:
        print(
            "\nnothing written. Re-run with "
            "--apply to register the boards "
            "found and record the rest."
        )

        return 0

    added, renamed, recorded = record(
        results
    )

    print(
        f"\nregistered {added} new boards, "
        f"renamed {renamed} to the curated "
        f"name, recorded {recorded} probe "
        "results"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
