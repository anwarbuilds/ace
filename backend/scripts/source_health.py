"""Which sources are actually working: python -m backend.scripts.source_health

A board can be enabled, registered, and completely dead. Eleven Lever
boards sat in the catalog failing on every cycle with "Lever
source_host is required", and nothing surfaced it: the scheduler was
healthy, the queue looked normal, and the only symptom was jobs that
never arrived from companies ACE believed it was watching.

Silence is the failure mode this exists to break.

    --json    machine-readable
"""

from __future__ import annotations

import argparse
import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select

from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
    SourceState,
)
from backend.app.db.session import SessionLocal


# A board polled less often than this has either broken or been
# forgotten. Generous, because the discovered tail polls daily.
STALE_AFTER = timedelta(
    days=2,
)


def collect() -> dict:
    """Return the health of every enabled source."""

    now = datetime.now(
        timezone.utc
    )

    with SessionLocal() as session:
        sources = list(
            session.scalars(
                select(
                    JobSourceRecord
                ).where(
                    JobSourceRecord
                    .enabled.is_(
                        True
                    )
                )
            )
        )

        states = {
            (
                state.source,
                state.source_account,
            ): state
            for state in session.scalars(
                select(
                    SourceState
                )
            )
        }

        counts: dict[
            tuple[str, str],
            int,
        ] = {}

        for (
            source,
            account,
            total,
        ) in session.execute(
            select(
                JobRecord.source,
                JobRecord.source_account,
                # count() over the grouped rows
                JobRecord.id,
            ).where(
                JobRecord.is_active.is_(
                    True
                )
            )
        ):
            key = (
                source,
                account,
            )

            counts[key] = (
                counts.get(
                    key,
                    0,
                )
                + 1
            )

    never: list[dict] = []

    stale: list[dict] = []

    empty: list[dict] = []

    healthy = 0

    for source in sources:
        key = (
            source.source_type,
            source.source_account,
        )

        state = states.get(
            key
        )

        entry = {
            "source_type": (
                source.source_type
            ),
            "source_account": (
                source.source_account
            ),
            "company": (
                source.company_name
            ),
            "discovery_source": (
                source.discovery_source
            ),
            "jobs": counts.get(
                key,
                0,
            ),
        }

        if state is None:
            never.append(
                entry
            )

            continue

        entry["last_success"] = (
            state.last_success_at.isoformat()
            if state.last_success_at
            else None
        )

        if (
            state.last_success_at
            is None
            or state.last_success_at
            < now - STALE_AFTER
        ):
            stale.append(
                entry
            )

            continue

        if not entry["jobs"]:
            empty.append(
                entry
            )

            continue

        healthy += 1

    return {
        "enabled": len(
            sources
        ),
        "healthy": healthy,
        "never_polled": never,
        "stale": stale,
        "polled_but_empty": empty,
    }


def main() -> int:
    """Print a source health report."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    report = collect()

    if args.json:
        print(
            json.dumps(
                report,
                indent=2,
            )
        )

        return 0

    print(
        f"{report['healthy']} of "
        f"{report['enabled']} sources "
        "healthy\n"
    )

    for label, key in (
        (
            "NEVER POLLED",
            "never_polled",
        ),
        (
            "STALE",
            "stale",
        ),
        (
            "POLLED BUT HOLDING NO JOBS",
            "polled_but_empty",
        ),
    ):
        rows = report[key]

        if not rows:
            continue

        print(
            f"{label} ({len(rows)})"
        )

        for row in rows[:20]:
            print(
                f"  {row['source_type']:16} "
                f"{row['source_account'][:28]:28} "
                f"{(row['company'] or '')[:24]:24} "
                f"{row['discovery_source'] or ''}"
            )

        if len(rows) > 20:
            print(
                f"  ... and {len(rows) - 20} more"
            )

        print()

    problems = (
        len(
            report["never_polled"]
        )
        + len(
            report["stale"]
        )
    )

    if not problems:
        print(
            "every source is polling."
        )

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
