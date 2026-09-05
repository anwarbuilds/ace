"""Deliver due ACE notification-outbox messages."""

import argparse
import sys
from collections.abc import Sequence

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


def _positive_integer(
    value: str,
) -> int:
    """Parse one strictly positive command-line integer."""

    try:
        parsed = int(
            value
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be an integer"
        ) from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            "value must be greater than zero"
        )

    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build notification-worker CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Deliver due ACE notification "
            "outbox messages."
        )
    )

    parser.add_argument(
        "--max-messages",
        type=_positive_integer,
        default=50,
        help=(
            "Maximum number of due "
            "notifications to attempt."
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Drain currently due notification messages."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

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
        max_messages=(
            args.max_messages
        ),
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