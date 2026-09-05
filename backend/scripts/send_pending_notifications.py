"""Deliver ACE notification digests.

ACE groups every qualifying opportunity accumulated during a delivery
window into one email.

    zero qualifying jobs  -> zero emails
    many qualifying jobs  -> one digest

The number of digests per local calendar day is bounded by the
configured windows in NOTIFICATION_DIGEST_TIMES (at most two).

Examples:

    One attempt for the currently open window:

        python -m backend.scripts.send_pending_notifications

    Continuous worker:

        python -m backend.scripts.send_pending_notifications --loop

    Rehearse without sending anything:

        python -m backend.scripts.send_pending_notifications --dry-run
"""

import argparse
import logging
import signal
import sys
from collections.abc import Sequence
from datetime import (
    datetime,
    timezone,
)
from threading import Event

from backend.app.config import (
    get_settings,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.notifications.digest_delivery import (
    DigestOutcome,
    deliver_due_digest,
    preview_due_digest,
)
from backend.app.notifications.runtime import (
    build_smtp_transport_from_settings,
    require_notification_recipient,
)


LOGGER = logging.getLogger(
    "ace.notifications.worker"
)


# Outcomes that mean "there is nothing further to do until either new
# candidates arrive or the next window opens".
IDLE_OUTCOMES = frozenset(
    {
        DigestOutcome.NO_OPEN_WINDOW,
        DigestOutcome.NOTHING_TO_SEND,
        DigestOutcome.ALREADY_DELIVERED,
        DigestOutcome.WINDOW_ABANDONED,
        DigestOutcome.RETRY_NOT_DUE,
        DigestOutcome.CONCURRENT_WORKER,
    }
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


def _aware_datetime(
    value: str,
) -> datetime:
    """Parse an ISO-8601 reference instant for controlled testing."""

    try:
        parsed = datetime.fromisoformat(
            value
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            (
                "value must be an ISO-8601 "
                "timestamp"
            )
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise argparse.ArgumentTypeError(
            (
                "value must include a UTC "
                "offset"
            )
        )

    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build notification-worker CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Deliver the ACE notification "
            "digest for the currently open "
            "delivery window."
        )
    )

    parser.add_argument(
        "--max-jobs",
        "--max-messages",
        dest="max_jobs",
        type=_positive_integer,
        default=None,
        help=(
            "Maximum number of opportunities "
            "to include in one digest. "
            "Remaining candidates appear in "
            "the next digest. Defaults to "
            "NOTIFICATION_DIGEST_MAX_JOBS. "
            "--max-messages is accepted as a "
            "backward-compatible alias."
        ),
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help=(
            "Continuously deliver digests "
            "until stopped."
        ),
    )

    parser.add_argument(
        "--idle-sleep-seconds",
        type=_positive_float,
        default=30.0,
        help=(
            "Seconds to wait when no digest "
            "is currently deliverable."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Render the digest that would be "
            "sent without delivering it and "
            "without consuming the window."
        ),
    )

    parser.add_argument(
        "--now",
        type=_aware_datetime,
        default=None,
        help=(
            "Override the reference instant "
            "(ISO-8601 with offset). Intended "
            "for controlled smoke tests."
        ),
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=(
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ),
        help="Python logging level.",
    )

    return parser


def _run_preview(
    *,
    recipient: str,
    schedule,
    reference_time: datetime,
    max_jobs: int,
) -> int:
    """Print the digest the open window would deliver, changing nothing."""

    preview = preview_due_digest(
        SessionLocal,
        schedule=schedule,
        recipient=recipient,
        now=reference_time,
        max_jobs=max_jobs,
    )

    print(
        "ACE Digest Dry Run"
    )

    print(
        "=" * 80
    )

    print(
        f"Reference time:     "
        f"{reference_time.isoformat()}"
    )

    if preview.window_label is None:
        print(
            "Open window:        none"
        )

        print(
            (
                "Next window opens:  "
                f"{schedule.next_window_opens_at(
                    now=reference_time
                ).isoformat()}"
            )
        )

    else:
        print(
            f"Open window:        "
            f"{preview.window_label} "
            f"on {preview.local_date}"
        )

    print(
        f"Would include:      "
        f"{preview.item_count}"
    )

    print(
        f"Would defer:        "
        f"{preview.deferred_count}"
    )

    if preview.message is None:
        print()

        if preview.item_count == 0:
            print(
                (
                    "Nothing qualifies. ACE "
                    "would send no email."
                )
            )

        else:
            print(
                (
                    "Candidates are waiting, but "
                    "no delivery window is open. "
                    "ACE would send no email yet."
                )
            )

        return 0

    print(
        f"Subject:            "
        f"{preview.message.subject}"
    )

    print()

    print(
        "-" * 80
    )

    print(
        preview.message.text_body
    )

    print(
        "-" * 80
    )

    print()

    print(
        (
            "Nothing was sent and no database "
            "state changed."
        )
    )

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Deliver the currently deliverable ACE digest."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    logging.basicConfig(
        level=getattr(
            logging,
            args.log_level,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )

    settings = get_settings()

    try:
        recipient = (
            require_notification_recipient(
                settings
            )
        )

        schedule = (
            settings.digest_schedule
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

    max_jobs = (
        args.max_jobs
        if args.max_jobs is not None
        else (
            settings
            .notification_digest_max_jobs
        )
    )

    if args.dry_run:
        reference_time = (
            args.now
            if args.now is not None
            else datetime.now(
                timezone.utc
            )
        )

        return _run_preview(
            recipient=recipient,
            schedule=schedule,
            reference_time=reference_time,
            max_jobs=max_jobs,
        )

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
        result = deliver_due_digest(
            SessionLocal,
            transport,
            schedule=schedule,
            recipient=recipient,
            now=args.now,
            max_jobs=max_jobs,
        )

        print(
            "ACE Notification Digest Worker"
        )

        print(
            "=" * 80
        )

        print(
            f"Outcome:            "
            f"{result.outcome.value}"
        )

        print(
            f"Digest id:          "
            f"{result.digest_id}"
        )

        print(
            f"Included jobs:      "
            f"{result.item_count}"
        )

        print(
            f"Deferred jobs:      "
            f"{result.deferred_count}"
        )

        if result.subject:
            print(
                f"Subject:            "
                f"{result.subject}"
            )

        if result.error:
            print(
                f"Error:              "
                f"{result.error}"
            )

        if not args.loop:
            if (
                result.outcome
                is DigestOutcome.DEAD
            ):
                return 1

            return 0

        if stop_event.is_set():
            return 0

        if (
            result.outcome
            in IDLE_OUTCOMES
            or result.outcome
            is DigestOutcome
            .RETRY_SCHEDULED
        ):
            stop_event.wait(
                args.idle_sleep_seconds
            )

            if stop_event.is_set():
                return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
