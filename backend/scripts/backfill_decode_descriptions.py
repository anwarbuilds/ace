"""Fix double-encoded HTML entities in already-stored descriptions.

python -m backend.scripts.backfill_decode_descriptions --apply

Five adapters each called ``html.unescape`` exactly once. Greenhouse's
own source content is itself already HTML-encoded once, so that single
pass only ever resolved the outer layer and left entities like
``&nbsp;``, ``&amp;`` and ``&mdash;`` sitting in stored descriptions as
literal text rather than the characters they name. 15,008 stored jobs
carry this -- 14,485 of them still active, 138 of those currently
marked eligible (PASS).

This is not cosmetic. Every eligibility rule that matches a multi-word
phrase depends on real whitespace between the words:
``security\\s+clearance`` does not match
``security&nbsp;clearance``, because those six literal characters are
not whitespace to a regex engine. A posting stating a clearance,
citizenship or experience requirement using exactly that phrasing read
as silent and passed the gate.

The adapters themselves are already fixed (``html_text.unescape_fully``
loops the decode to a fixed point instead of stopping after one pass),
so every future poll stores clean text. This script repairs what is
already sitting in the table: raw HTML is not stored, only the
once-decoded text, so the fix is a second ``unescape_fully`` pass over
the stored ``description`` column, applied in place.

Fixing the text changes ``content_hash`` for every row it touches,
which is deliberate: it is what makes
``python -m backend.scripts.backfill_job_evaluations`` recognise the
row as stale and re-evaluate it against the corrected content. Run
that script after this one.

The script is read-only by default. Nothing is written without
--apply.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.html_text import unescape_fully
from backend.app.db.models import JobRecord
from backend.app.db.session import SessionLocal
from backend.app.models.job import CanonicalJob
from backend.app.persistence.hashing import compute_job_content_hash


DEFAULT_BATCH_SIZE = 500


def _to_canonical(record: JobRecord, *, description: str) -> CanonicalJob:
    """Rebuild the canonical job used to recompute content_hash.

    Every field the hash payload reads must be mirrored here, exactly
    as it must be at every other CanonicalJob reconstruction boundary
    in ACE -- a field left out here would make the recomputed hash
    wrong rather than merely stale.
    """

    return CanonicalJob(
        source=record.source,
        company=record.company,
        external_id=record.external_id,
        requisition_id=record.requisition_id,
        title=record.title,
        location=record.location,
        description=description,
        official_url=record.official_url,
        posted_at=record.posted_at,
        updated_at=record.source_updated_at,
        employment_type=record.employment_type,
    )


def load_batch(
    session: Session,
    *,
    after_id: int,
    batch_size: int,
) -> list[JobRecord]:
    """Load the next id-ordered slice of jobs."""

    statement = (
        select(JobRecord)
        .where(JobRecord.id > after_id)
        .order_by(JobRecord.id)
        .limit(batch_size)
    )

    return list(session.scalars(statement).all())


def build_parser() -> argparse.ArgumentParser:
    """Build the backfill CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Fix double-encoded HTML entities "
            "in stored job descriptions."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write corrected descriptions. "
            "Without this flag the script "
            "only reports."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Jobs to scan per transaction.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Decode any still-encoded description in place."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        print("--batch-size must be at least 1.", file=sys.stderr)
        return 2

    print("ACE Description Decode Backfill")
    print("=" * 80)
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN (read-only)'}")

    changed_by_source: Counter[str] = Counter()
    scanned = 0
    changed = 0
    after_id = 0

    while True:
        if args.apply:
            session_ctx = SessionLocal.begin()
        else:
            session_ctx = SessionLocal()

        with session_ctx as session:
            records = load_batch(
                session,
                after_id=after_id,
                batch_size=args.batch_size,
            )

            if not records:
                break

            after_id = records[-1].id

            for record in records:
                scanned += 1

                decoded = unescape_fully(record.description)

                if decoded == record.description:
                    continue

                changed += 1
                changed_by_source[record.source] += 1

                if not args.apply:
                    continue

                canonical = _to_canonical(
                    record, description=decoded
                )

                record.description = decoded
                record.content_hash = compute_job_content_hash(
                    canonical
                )

        if scanned % (args.batch_size * 10) == 0:
            print(f"  scanned {scanned}, changed {changed}")

    print()
    print("=" * 80)
    print(f"Jobs scanned: {scanned}")
    print(f"Jobs changed: {changed}")

    for source, count in changed_by_source.most_common():
        print(f"  {source}: {count}")

    if not args.apply:
        print()
        print("DRY RUN. No changes were made. Re-run with --apply.")
        print(
            "After --apply, run "
            "'python -m backend.scripts.backfill_job_evaluations "
            "--apply' to re-evaluate the corrected jobs."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
