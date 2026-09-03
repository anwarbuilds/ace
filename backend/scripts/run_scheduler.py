"""Run the ACE automatic source scheduler.

Examples:

    One scheduler cycle:

        python -m backend.scripts.run_scheduler --once

    Continuous scheduler:

        python -m backend.scripts.run_scheduler

Production scheduler sources are loaded from the persistent PostgreSQL
source catalog rather than being hard-coded into Python.
"""

import argparse
import logging
from collections.abc import (
    Sequence,
)

from backend.app.config import (
    get_settings,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.notifications.runtime import (
    require_notification_recipient,
)
from backend.app.scheduling import (
    SchedulerRuntime,
    SourceDefinition,
    build_default_source_dispatcher,
    load_source_registry,
    poll_source_once,
)


LOGGER = logging.getLogger(
    "ace.scheduler.cli"
)


def build_parser() -> (
    argparse.ArgumentParser
):
    """Build the scheduler command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the ACE automatic "
            "job-source scheduler."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Run currently due sources "
            "once and exit."
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


def configure_logging(
    *,
    level: str,
) -> None:
    """Configure scheduler console logging."""

    logging.basicConfig(
        level=getattr(
            logging,
            level,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    """Run the ACE scheduler."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    configure_logging(
        level=args.log_level
    )

    settings = get_settings()

    recipient = (
        require_notification_recipient(
            settings
        )
    )

    with SessionLocal() as session:
        registry = (
            load_source_registry(
                session
            )
        )

    dispatcher = (
        build_default_source_dispatcher()
    )

    def poll_source(
        source: SourceDefinition,
    ):
        return poll_source_once(
            source=source,
            fetcher=dispatcher,
            transaction_factory=(
                SessionLocal
            ),
            notification_recipient=(
                recipient
            ),
        )

    runtime = SchedulerRuntime(
        registry=registry,
        poller=poll_source,
    )

    if runtime.source_count == 0:
        LOGGER.error(
            "ace_scheduler_no_enabled_sources"
        )

        return 1

    LOGGER.info(
        (
            "ace_scheduler_ready "
            "enabled_sources=%d"
        ),
        runtime.source_count,
    )

    try:
        if args.once:
            result = (
                runtime.run_due_sources()
            )

            LOGGER.info(
                (
                    "ace_scheduler_once_completed "
                    "attempted=%d "
                    "succeeded=%d "
                    "failed=%d"
                ),
                result.attempted_count,
                result.succeeded_count,
                result.failed_count,
            )

            return (
                0
                if result.failed_count == 0
                else 1
            )

        runtime.run_forever()

    except KeyboardInterrupt:
        LOGGER.info(
            (
                "ace_scheduler_interrupted "
                "reason=keyboard_interrupt"
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )