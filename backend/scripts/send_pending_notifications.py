"""Deliver due ACE notification-outbox messages."""

import argparse
import signal
import sys
from collections.abc import Sequence
from threading import Event

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


def _positive_float(
    value: str,
) -> float:
    """Parse one strictly positive command-line float."""

    try:
        parsed = float(
            value
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be a number"
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
            "notifications to attempt "
            "per drain cycle."
        ),
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help=(
            "Continuously drain due "
            "notifications until stopped."
        ),
    )

    parser.add_argument(
        "--idle-sleep-seconds",
        type=_positive_float,
        default=30.0,
        help=(
            "Seconds to wait when no "
            "due notification exists."
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

    stop_event = Event()

    if args.loop:
        def request_stop(
            signum,
            frame,
        ) -> None:
            del signum
            del frame

            stop_event.set()

        signal.signal(
            signal.SIGTERM,
            request_stop,
        )

        signal.signal(
            signal.SIGINT,
            request_stop,
        )

    while True:
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

        if not args.loop:
            if result.dead_count:
                return 1

            return 0

        if stop_event.is_set():
            return 0

        if result.attempted_count == 0:
            stop_event.wait(
                args.idle_sleep_seconds
            )

            if stop_event.is_set():
                return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )