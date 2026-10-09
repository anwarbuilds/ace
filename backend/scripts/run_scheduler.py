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
import time
from collections.abc import (
    Sequence,
)
from datetime import datetime

import httpx
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
from backend.app.adapters.simplify import (
    FEED_URLS,
    is_in_scope,
)
from backend.app.discovery.feed_links import (
    BOARDS_PER_RUN,
    find_unregistered_boards,
    read_boards,
    register_confirmed_boards,
    split_links,
    stored_feed_postings,
)
from backend.app.runners.prefilter import (
    build_detail_predicate,
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


# Feed links are checked for new boards, and productive boards promoted,
# every half hour; dark boards are diagnosed every six.
MAINTENANCE_SECONDS = 30 * 60

DARK_CHECK_SECONDS = 6 * 60 * 60

# Boards whose feed postings could pass for the user, read in one run.
# A ceiling against a runaway, not an expected number: the first run
# found about 170.
URGENT_BOARDS_PER_RUN = 500


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

    def register_feed_boards() -> None:
        """Read and register the boards feed links name that ACE has
        never known -- the step that, run by hand, had not run since
        early September, which is how Chewy's board went unread."""

        postings: list[tuple[str, str, str]] = []

        current_wanted: list[tuple[str, str, str]] = []

        try:
            with httpx.Client(
                timeout=60,
                headers={
                    "User-Agent": (
                        "ACE/0.1 "
                        "(personal career-intelligence project)"
                    ),
                },
            ) as client:
                for feed_url in FEED_URLS.values():
                    for entry in client.get(
                        feed_url
                    ).json():
                        if not (
                            isinstance(entry, dict)
                            and entry.get("active")
                        ):
                            continue

                        posting = (
                            str(entry.get("url") or ""),
                            str(entry.get("company_name") or ""),
                            str(entry.get("title") or ""),
                        )

                        # Today's in-scope postings lead the queue.
                        (
                            current_wanted
                            if is_in_scope(entry)
                            else postings
                        ).append(
                            posting
                        )

        except (httpx.HTTPError, ValueError):
            # Stored links still count; today's listing is tried again
            # next time.
            LOGGER.warning(
                "feed_listing_unavailable",
                exc_info=True,
            )

        with SessionLocal() as session:
            postings.extend(
                stored_feed_postings(
                    session
                )
            )

            wanted, rest = split_links(
                current_wanted + postings,
                could_pass=lambda company, title: (
                    build_detail_predicate(
                        source="simplify",
                        company_name=company,
                    )(
                        title
                    )
                ),
            )

            urgent = find_unregistered_boards(
                session,
                wanted,
                limit=URGENT_BOARDS_PER_RUN,
            )

            urgent_keys = {
                board.key
                for board in urgent
            }

            boards = urgent + [
                board
                for board in find_unregistered_boards(
                    session,
                    rest,
                    limit=(
                        BOARDS_PER_RUN
                        + len(urgent)
                    ),
                )
                if board.key not in urgent_keys
            ][
                :BOARDS_PER_RUN
            ]

        if not boards:
            return

        # A provider that answered "too many requests" is left alone for
        # the rest of the run; its boards are read on a later one.
        throttled: set[str] = set()

        # One board at a time, each saved as soon as it is read: a run
        # through a backlog of 170 boards takes the better part of an
        # hour, and a restart must not throw away what it had done.
        for board in boards:
            provider = board.detected.source_type.value

            if provider in throttled:
                continue

            [outcome] = read_boards(
                [board],
                lambda definition: dispatcher.fetch(
                    definition
                ).jobs,
            )

            with SessionLocal.begin() as session:
                added = register_confirmed_boards(
                    session,
                    [outcome],
                )

            if outcome.transient:
                throttled.add(
                    provider
                )

                LOGGER.info(
                    (
                        "feed_board_deferred "
                        "company=%r source=%s/%s reason=%r"
                    ),
                    outcome.board.company_name,
                    provider,
                    outcome.board.detected.source_account,
                    outcome.error,
                )

            elif added:
                LOGGER.warning(
                    (
                        "source_registered_from_feed "
                        "company=%r source=%s/%s postings=%d"
                    ),
                    outcome.board.company_name,
                    outcome.board.detected.source_type.value,
                    outcome.board.detected.source_account,
                    outcome.job_count,
                )

            else:
                LOGGER.info(
                    (
                        "feed_board_not_registered "
                        "company=%r source=%s/%s reason=%r"
                    ),
                    outcome.board.company_name,
                    outcome.board.detected.source_type.value,
                    outcome.board.detected.source_account,
                    outcome.error,
                )

    # When dark boards were last diagnosed. That reads companies'
    # websites, so it keeps its six-hour rhythm while the rest of the
    # maintenance runs every half hour.
    dark_checked = [
        0.0,
    ]

    def maintain() -> None:
        """Register boards feed links name, speed up productive boards,
        and -- every six hours -- follow ones that stopped answering.

        Dark boards are logged at warning either way: a board found
        dark is exactly the thing that went unnoticed for seventeen
        days.
        """

        register_feed_boards()

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

        if time.monotonic() - dark_checked[0] < DARK_CHECK_SECONDS:
            return

        dark_checked[0] = time.monotonic()

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
        maintenance_interval_seconds=(
            MAINTENANCE_SECONDS
        ),
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