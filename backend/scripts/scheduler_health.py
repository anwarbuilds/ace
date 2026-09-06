"""Liveness probe for the ACE scheduler.

The scheduler is a polling loop, not a server, so "the process exists"
is a weak signal: it can be running and yet doing nothing useful, and a
crash loop looks like "restarting" rather than "broken". What actually
matters is whether any source has been polled successfully lately.

Exits 0 when a poll has succeeded inside the window, 1 otherwise, so
Docker reports the container unhealthy instead of merely up.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import os
import sys

from sqlalchemy import func, select

from backend.app.db.models import SourceState
from backend.app.db.session import SessionLocal


# Generous next to the shortest poll interval in the catalog. A probe
# tighter than the slowest legitimate cycle would report a healthy
# scheduler as broken, and an alert that cries wolf gets ignored.
DEFAULT_MAX_AGE_MINUTES = 45


def main() -> int:
    """Report whether the scheduler has polled anything recently."""

    max_age = timedelta(
        minutes=int(
            os.environ.get(
                "ACE_HEALTH_MAX_AGE_MINUTES",
                DEFAULT_MAX_AGE_MINUTES,
            )
        )
    )

    try:
        with SessionLocal() as session:
            latest = session.scalar(
                select(
                    func.max(
                        SourceState
                        .last_success_at
                    )
                )
            )
    except Exception as error:
        print(
            f"unhealthy: cannot reach the database: {error}",
            file=sys.stderr,
        )

        return 1

    if latest is None:
        # Nothing has ever succeeded. On a cold start that is normal
        # for a short while, so it is reported rather than judged.
        print(
            "starting: no successful poll recorded yet"
        )

        return 0

    if latest.tzinfo is None:
        latest = latest.replace(
            tzinfo=timezone.utc
        )

    age = (
        datetime.now(
            timezone.utc
        )
        - latest
    )

    if age > max_age:
        print(
            "unhealthy: last successful poll was "
            f"{age.total_seconds() / 60:.0f} minutes ago",
            file=sys.stderr,
        )

        return 1

    print(
        "healthy: last successful poll was "
        f"{age.total_seconds() / 60:.1f} minutes ago"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
