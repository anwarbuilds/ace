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
from datetime import datetime

from sqlalchemy import select

from backend.app.config import (
    get_settings,
)
from backend.app.coverage.cadence import (
    promote_productive_sources,
)
from backend.app.coverage.recovery import (
    recover_dark_sources,
)
from backend.app.db.models import (
    SourceState,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.app.alerts.service import (
    send_pending,
)
from backend.app.persistence.sessions import (
    record_check,
    record_discoveries,
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
            freshness_policy=(
                freshness_policy
            ),
        )

    def send_alerts() -> None:
        """Email any pull that has finished and not been alerted yet.

        Runs every cycle, which is cheap: the query asks for pulls with
        no notified_at, which is almost always empty.
        """

        with SessionLocal.begin() as session:
            sent = send_pending(
                session,
            )

        if sent:
            LOGGER.info(
                "alerts_sent count=%d",
                sent,
            )

    def record_cycle(
        *,
        started_at,
        checks_since,
    ) -> None:
        """Group anything this cycle discovered into a run, and record
        how much the run has checked so far."""

        with SessionLocal.begin() as session:
            run = record_discoveries(
                session,
                since=started_at,
            )

            # Nothing found, but ACE looked, and the log is read to find
            # out whether it did.
            checked = run or record_check(
                session
            )

            boards, postings = checks_since(
                checked.started_at
            )

            # Never lowered: after a restart the scheduler remembers
            # nothing read before it, and the pull already counted it.
            checked.boards_checked = max(
                checked.boards_checked or 0,
                boards,
            )

            checked.postings_checked = max(
                checked.postings_checked or 0,
                postings,
            )

        if run is not None:
            LOGGER.info(
                (
                    "discovery_run_updated "
                    "session_id=%s "
                    "jobs_discovered=%d "
                    "qualifying=%d"
                ),
                run.id,
                run.jobs_discovered,
                run.qualifying_discovered,
            )

    def reload_registry() -> SourceRegistry:
        """Read the source list again, in its own short session.

        Called between cycles so a company registered from the
        interface starts being polled without a restart. Kept subject
        to the same --source-type/--source-account selection as the
        first load, or a diagnostic run narrowed to one source would
        quietly widen to all of them.
        """

        with SessionLocal() as session:
            return select_source_registry(
                load_source_registry(
                    session
                ),
                source_type=(
                    args.source_type
                ),
                source_account=(
                    args.source_account
                ),
                limit=args.limit,
            )

    def last_polled() -> dict[
        tuple[str, str],
        datetime,
    ]:
        """When each source last polled successfully, from source_states."""

        with SessionLocal() as session:
            return {
                (
                    source,
                    source_account,
                ): last_success_at
                for (
                    source,
                    source_account,
                    last_success_at,
                ) in session.execute(
                    select(
                        SourceState.source,
                        SourceState.source_account,
                        SourceState.last_success_at,
                    )
                ).all()
            }

    def maintain() -> None:
        """Speed up productive boards; follow ones that stopped answering.

        Dark boards are logged at warning either way: a board found
        dark is exactly the thing that went unnoticed for seventeen
        days.
        """

        with SessionLocal.begin() as session:
            promotions = promote_productive_sources(
                session
            )

        for promotion in promotions:
            LOGGER.info(
                (
                    "source_promoted "
                    "company=%r source=%s/%s "
                    "passing_roles=%d "
                    "interval_seconds=%d->%d"
                ),
                promotion.company_name,
                promotion.source_type,
                promotion.source_account,
                promotion.passing_roles,
                promotion.old_interval,
                promotion.new_interval,
            )

        with SessionLocal.begin() as session:
            recoveries = recover_dark_sources(
                session
            )

        for recovery in recoveries:
            dark = recovery.dark

            if recovery.replaced_by is not None:
                LOGGER.warning(
                    (
                        "source_replaced "
                        "company=%r old=%s/%s new=%s/%s "
                        "closed_jobs=%d"
                    ),
                    dark.company_name,
                    dark.source_type,
                    dark.source_account,
                    *recovery.replaced_by,
                    recovery.closed_jobs,
                )

                continue

            LOGGER.warning(
                (
                    "source_dark "
                    "company=%r source=%s/%s "
                    "dark_since=%s outcome=%s"
                ),
                dark.company_name,
                dark.source_type,
                dark.source_account,
                dark.dark_since.isoformat(),
                recovery.diagnosis.outcome,
            )

    runtime = SchedulerRuntime(
        registry=registry,
        poller=poll_source,
        cycle_recorder=record_cycle,
        alert_sender=send_alerts,
        reload_registry=reload_registry,
        maintenance=maintain,
        # --once is how a person asks for everything now, so it does
        # not wait out anyone's interval.
        last_polled=(
            None
            if args.once
            else last_polled
        ),
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