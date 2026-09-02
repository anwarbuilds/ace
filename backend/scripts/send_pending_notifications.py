"""Deliver due ACE notification-outbox messages."""

import sys

from backend.app.config import (
    get_settings,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.notifications.delivery import (
    deliver_due_notifications,
)
from backend.app.notifications.runtime import (
    build_smtp_transport_from_settings,
)


def main() -> int:
    """Drain the currently due notification queue."""

    settings = get_settings()

    try:
        transport = (
            build_smtp_transport_from_settings(
                settings
            )
        )

    except ValueError as exc:
        print(
            (
                "ACE notification worker "
                f"configuration error: {exc}"
            ),
            file=sys.stderr,
        )

        return 2

    result = deliver_due_notifications(
        SessionLocal,
        transport,
    )

    print(
        "ACE Notification Delivery Worker"
    )

    print(
        "=" * 80
    )

    print(
        f"Attempted:          "
        f"{result.attempted_count}"
    )

    print(
        f"Sent:               "
        f"{result.sent_count}"
    )

    print(
        f"Retry scheduled:    "
        f"{result.retry_scheduled_count}"
    )

    print(
        f"Dead:               "
        f"{result.dead_count}"
    )

    if result.dead_count:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )