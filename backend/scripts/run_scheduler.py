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
from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.app.notifications.runtime import (
    require_notification_recipient,
)
from backend.app.scheduling import (
    SchedulerRuntime,
    SourceDefinition,
    SourceRegistry,
    SourceType,
    build_default_source_dispatcher,
    load_source_registry,
    poll_source_once,
)


LOGGER = logging.getLogger(
    "ace.scheduler.cli"
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


def select_source_registry(
    registry: SourceRegistry,
    *,
    source_type: str | None,
    source_account: str | None,
    limit: int | None,
) -> SourceRegistry:
    """Select a deterministic scheduler subset for diagnostics."""

    if (
        source_account is not None
        and source_type is None
    ):
        raise ValueError(
            "--source-account requires --source-type."
        )

    selected = (
        registry.enabled_sources
    )

    if source_type is not None:
        normalized_source_type = (
            SourceType(
                source_type
            )
        )

        selected = tuple(
            source
            for source in selected
            if (
                source.source_type
                == normalized_source_type
            )
        )

    if source_account is not None:
        normalized_source_account = (
            source_account.strip()
        )

        if not normalized_source_account:
            raise ValueError(
                "--source-account must not be blank."
            )

        selected = tuple(
            source
            for source in selected
            if (
                source.source_account
                == normalized_source_account
            )
        )

    if limit is not None:
        selected = (
            selected[
                :limit
            ]
        )

    return SourceRegistry(
        selected
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
        "--limit",
        type=_positive_integer,
        default=None,
        help=(
            "Maximum number of enabled "
            "sources to run."
        ),
    )

    parser.add_argument(
        "--source-type",
        choices=tuple(
            source_type.value
            for source_type in SourceType
        ),
        default=None,
        help=(
            "Restrict polling to one ATS "
            "provider family."
        ),
    )

    parser.add_argument(
        "--source-account",
        default=None,
        help=(
            "Restrict polling to one source "
            "account. Requires --source-type."
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

    try:
        registry = (
            select_source_registry(
                registry,
                source_type=(
                    args.source_type
                ),
                source_account=(
                    args.source_account
                ),
                limit=args.limit,
            )
        )

    except ValueError as exc:
        parser.error(
            str(
                exc
            )
        )

    dispatcher = (
        build_default_source_dispatcher()
    )

    freshness_policy = FreshnessPolicy(
        max_posting_age_days=(
            settings
            .max_alert_posting_age_days
        ),
        alert_on_unknown_posting_age=(
            settings
            .alert_on_unknown_posting_age
        ),
    )

    LOGGER.info(
        (
            "ace_freshness_policy "
            "max_posting_age_days=%d "
            "alert_on_unknown_posting_age=%s"
        ),
        freshness_policy
        .max_posting_age_days,
        freshness_policy
        .alert_on_unknown_posting_age,
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
            freshness_policy=(
                freshness_policy
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