"""Undo dates pushed a day forward by rendering the sheet in UTC.

python -m backend.scripts.repair_applied_date_drift --apply

Instants are stored in UTC, which is right. The CSV export used to
format them in UTC too, which was not: an application marked at 19:43
in Seattle exported as the following day, because UTC had already
rolled over. ACE's own screen, which formats in the browser's zone,
showed the correct day, so the two disagreed about the same
application.

That alone would have been a display bug. Re-importing the exported
sheet made it a data one: the wrong date was read back as a real date
and stored, replacing the precise instant of the click with noon UTC on
the following day. The export is fixed, so this cannot recur, but rows
that already went round the loop carry the wrong day.

Only the rows carrying that exact signature are touched:

    - ``applied_at`` sits at exactly noon UTC, the marker of a date that
      came back through an import rather than from a click
    - ``status_changed_at``, which records when the mark was actually
      made, falls at or after 17:00 local, the window where UTC has
      already rolled over
    - the stored date is exactly one day after that local date

A row failing any of those is left alone. A job genuinely applied to
weeks before it was imported also has two different dates, and that
difference is correct: the sheet's date is the truth and the import
time is not. Widening the rule to catch those would rewrite real
history, so it stays narrow, and reports what it skipped.

Repaired rows are set back to the instant of the click itself, which
``status_changed_at`` still holds, rather than to noon on the corrected
day. That is the real answer rather than a reconstruction of it.

The script is read-only by default. Nothing is written without
--apply.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.models import JobMarkRecord, JobRecord
from backend.app.db.session import SessionLocal


# Local hour from which UTC is already on the next calendar day for any
# zone behind it. Below this, the drift this script repairs cannot have
# happened.
ROLLOVER_HOUR = 17


def _as_utc(
    moment: datetime,
) -> datetime:
    """Read a stored instant as UTC when it carries no zone.

    Postgres hands these back with an offset, but a naive value read as
    system-local would silently shift every comparison below by the
    running machine's offset -- which is the exact class of bug this
    script exists to repair.
    """

    if (
        moment.tzinfo is None
        or moment.utcoffset() is None
    ):
        return moment.replace(
            tzinfo=timezone.utc
        )

    return moment


def find_drifted(
    session,
    *,
    zone: ZoneInfo,
) -> list[tuple[JobMarkRecord, JobRecord]]:
    """Return the marks whose stored date is a day ahead of the click."""

    rows = session.execute(
        select(
            JobMarkRecord,
            JobRecord,
        )
        .join(
            JobRecord,
            JobRecord.id
            == JobMarkRecord.job_id,
        )
        .where(
            JobMarkRecord.applied_at
            .is_not(
                None
            ),
            JobMarkRecord
            .status_changed_at
            .is_not(
                None
            ),
        )
    ).all()

    drifted = []

    for mark, job in rows:
        stored = _as_utc(
            mark.applied_at
        )

        # Noon UTC exactly is what _applied_instant writes for a date
        # read out of a sheet. A click carries its real time instead.
        if (
            stored.hour != 12
            or stored.minute != 0
            or stored.second != 0
        ):
            continue

        clicked = _as_utc(
            mark.status_changed_at
        ).astimezone(
            zone
        )

        if clicked.hour < ROLLOVER_HOUR:
            continue

        if (
            stored.astimezone(
                zone
            ).date()
            != clicked.date()
            + timedelta(
                days=1,
            )
        ):
            continue

        drifted.append(
            (
                mark,
                job,
            )
        )

    return drifted


def build_parser() -> argparse.ArgumentParser:
    """Build the repair CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Undo applied dates pushed a "
            "day forward by UTC rendering."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write the corrected dates. "
            "Without this flag the script "
            "only reports."
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Report, and optionally repair, drifted applied dates."""

    args = build_parser().parse_args(
        argv
    )

    zone = ZoneInfo(
        get_settings()
        .display_timezone
    )

    print(
        "ACE Applied-Date Drift Repair"
    )

    print(
        "=" * 78
    )

    print(
        f"Mode:     "
        f"{'APPLY' if args.apply else 'DRY RUN (read-only)'}"
    )

    print(
        f"Timezone: {zone.key}"
    )

    print()

    with SessionLocal() as session:
        drifted = find_drifted(
            session,
            zone=zone,
        )

        if not drifted:
            print(
                "Nothing to repair."
            )

            return 0

        for mark, job in drifted:
            clicked = _as_utc(
                mark.status_changed_at
            ).astimezone(
                zone
            )

            print(
                f"  {job.company[:26]:26} "
                f"{_as_utc(mark.applied_at).astimezone(zone).strftime('%-d %b'):7}"
                f" -> "
                f"{clicked.strftime('%-d %b')}"
                f"  (marked at "
                f"{clicked.strftime('%H:%M')})"
            )

            if args.apply:
                mark.applied_at = (
                    mark.status_changed_at
                )

        print()

        print(
            f"Rows affected: "
            f"{len(drifted)}"
        )

        if not args.apply:
            print()

            print(
                (
                    "DRY RUN. No changes were "
                    "made. Re-run with --apply."
                )
            )

            return 0

        session.commit()

    print()

    print(
        "Repaired."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
