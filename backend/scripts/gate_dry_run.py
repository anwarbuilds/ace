"""Show what a gate change would do, without changing anything.

Re-runs the eligibility gate over stored jobs under a chosen candidate
profile and lists every job whose decision would differ from the one
stored today. Read-only: on PostgreSQL the transaction is declared READ
ONLY, and nothing is ever written or committed.

Run it on the real database before switching ACE_TARGET_PROFILE, and
judge the change by the jobs it actually moves:

    .venv/bin/python -m backend.scripts.gate_dry_run --profile sde2
    .venv/bin/python -m backend.scripts.gate_dry_run --profile sde2 --csv flips.csv

Active jobs only by default, because those are the ones the queue would
change; --all includes closed postings too.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import (
    select,
    text,
)
from sqlalchemy.orm import Session

from backend.app.intelligence.eligibility import (
    PROFILES,
    EligibilityReasonCode,
    evaluate_job,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.models.job import CanonicalJob


BATCH = 500


@dataclass(frozen=True)
class Flip:
    """One job whose decision the profile would change."""

    job_id: int
    company: str
    title: str
    location: str
    url: str
    before: str
    after: str
    reasons_before: str
    reasons_after: str


def _canonical(
    job: JobRecord,
) -> CanonicalJob:
    return CanonicalJob(
        source=job.source,
        company=job.company,
        external_id=job.external_id,
        requisition_id=job.requisition_id,
        title=job.title,
        location=job.location,
        description=job.description,
        official_url=job.official_url,
        posted_at=job.posted_at,
        updated_at=job.source_updated_at,
        employment_type=job.employment_type,
    )


def dry_run(
    session: Session,
    *,
    profile_key: str,
    include_inactive: bool = False,
) -> tuple[list[Flip], Counter]:
    """Return the jobs whose stored decision the profile would change,
    and a tally of every outcome pair."""

    profile = PROFILES[profile_key]

    statement = (
        select(
            JobRecord,
            JobEvaluationRecord,
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        )
        .order_by(
            JobRecord.id
        )
    )

    if not include_inactive:
        statement = statement.where(
            JobRecord.is_active.is_(
                True
            )
        )

    flips: list[Flip] = []

    tally: Counter = Counter()

    for job, stored in session.execute(
        statement.execution_options(
            yield_per=BATCH
        )
    ):
        decision = evaluate_job(
            _canonical(
                job
            ),
            profile,
        )

        after = decision.status.value

        before = stored.eligibility_status

        tally[(before, after)] += 1

        if before == after:
            continue

        flips.append(
            Flip(
                job_id=job.id,
                company=job.company,
                title=job.title,
                location=job.location,
                url=job.official_url,
                before=before,
                after=after,
                reasons_before="; ".join(
                    str(code)
                    for code in (stored.reason_codes or [])
                ),
                reasons_after="; ".join(
                    code.value
                    for code in decision.reason_codes
                    if code is not EligibilityReasonCode.NO_HARD_BLOCKER
                ),
            )
        )

    return flips, tally


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "List the jobs a candidate profile would admit or drop, "
            "compared with the decisions stored now. Changes nothing."
        ),
    )

    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        required=True,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="include closed postings",
    )

    parser.add_argument(
        "--csv",
        metavar="PATH",
        help="also write every changed job to this CSV file",
    )

    args = parser.parse_args(
        argv
    )

    from backend.app.db.session import SessionLocal

    with SessionLocal() as session:
        if session.bind.dialect.name == "postgresql":
            session.execute(
                text(
                    "SET TRANSACTION READ ONLY"
                )
            )

        flips, tally = dry_run(
            session,
            profile_key=args.profile,
            include_inactive=args.all,
        )

        session.rollback()

    gained = [f for f in flips if f.after == "PASS"]
    lost = [f for f in flips if f.before == "PASS"]

    print(
        f"Profile {args.profile}: {sum(tally.values())} "
        f"{'jobs' if args.all else 'active jobs'} re-evaluated, nothing written."
    )
    print(f"  would newly appear: {len(gained)}")
    print(f"  would disappear:    {len(lost)}")

    for heading, rows in (
        ("Would newly appear", gained),
        ("Would disappear", lost),
    ):
        if not rows:
            continue

        print(f"\n{heading}:")

        for flip in rows:
            print(
                f"  [{flip.job_id}] {flip.company}, {flip.title} "
                f"({flip.location})\n"
                f"      was: {flip.reasons_before or flip.before}\n"
                f"      now: {flip.reasons_after or flip.after}\n"
                f"      {flip.url}"
            )

    if args.csv:
        with open(
            args.csv,
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.writer(
                handle
            )

            writer.writerow(
                [
                    "job_id",
                    "company",
                    "title",
                    "location",
                    "before",
                    "after",
                    "reasons_before",
                    "reasons_after",
                    "url",
                ]
            )

            for flip in flips:
                writer.writerow(
                    [
                        flip.job_id,
                        flip.company,
                        flip.title,
                        flip.location,
                        flip.before,
                        flip.after,
                        flip.reasons_before,
                        flip.reasons_after,
                        flip.url,
                    ]
                )

        print(f"\nWrote {len(flips)} rows to {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
