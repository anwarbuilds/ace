"""Run one live Greenhouse source check through the ACE pipeline."""

import argparse
import sys

import httpx
from sqlalchemy.exc import (
    SQLAlchemyError,
)

from backend.app.config import (
    get_settings,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.evaluation.types import (
    EvaluationBatchResult,
)
from backend.app.notifications.delivery import (
    DeliveryBatchResult,
    deliver_due_notifications,
)
from backend.app.notifications.outbox import (
    OutboxEnqueueResult,
    SqlAlchemyNotificationOutboxRepository,
    enqueue_alert_candidates,
)
from backend.app.notifications.renderer import (
    format_timestamp,
    render_alert_notification,
)
from backend.app.notifications.runtime import (
    build_smtp_transport_from_settings,
    require_notification_recipient,
)
from backend.app.persistence.repository import (
    JobRepository,
)
from backend.app.runners.greenhouse import (
    GreenhouseLiveSnapshot,
    fetch_live_greenhouse_snapshot,
    process_live_greenhouse_snapshot,
)
from backend.app.workflows.source_snapshot import (
    SourceSnapshotWorkflowResult,
)


DEFAULT_BOARD_TOKEN = "databricks"
DEFAULT_COMPANY_NAME = "Databricks"

DELIVERY_BATCH_SIZE = 50


def print_run_summary(
    live_snapshot: GreenhouseLiveSnapshot,
    result: SourceSnapshotWorkflowResult,
) -> None:
    """Print source, persistence, and evaluation summaries."""

    snapshot = result.snapshot
    evaluation = result.evaluation

    print()

    print(
        "ACE Live Greenhouse Run"
    )

    print(
        "=" * 80
    )

    print(
        f"Company:                "
        f"{live_snapshot.company_name}"
    )

    print(
        f"Board token:            "
        f"{live_snapshot.board_token}"
    )

    print(
        f"ACE detected at:        "
        f"{format_timestamp(
            live_snapshot.detected_at
        )}"
    )

    print()

    print(
        "Persistence"
    )

    print(
        "-" * 80
    )

    print(
        f"Baseline:               "
        f"{snapshot.is_baseline}"
    )

    print(
        f"Fetched:                "
        f"{snapshot.fetched_count}"
    )

    print(
        f"Unique:                 "
        f"{snapshot.unique_count}"
    )

    print(
        f"Duplicates:             "
        f"{snapshot.duplicate_count}"
    )

    print(
        f"NEW:                    "
        f"{snapshot.new_count}"
    )

    print(
        f"UPDATED:                "
        f"{snapshot.updated_count}"
    )

    print(
        f"REOPENED:               "
        f"{snapshot.reopened_count}"
    )

    print(
        f"UNCHANGED:              "
        f"{snapshot.unchanged_count}"
    )

    print(
        f"CLOSED:                 "
        f"{snapshot.closed_count}"
    )

    print(
        f"Evaluation candidates:  "
        f"{snapshot.evaluation_candidate_count}"
    )

    print()

    print(
        "Evaluation"
    )

    print(
        "-" * 80
    )

    print(
        f"Evaluated:              "
        f"{evaluation.evaluated_count}"
    )

    print(
        f"PASS:                   "
        f"{evaluation.pass_count}"
    )

    print(
        f"STRETCH:                "
        f"{evaluation.stretch_count}"
    )

    print(
        f"REJECT:                 "
        f"{evaluation.reject_count}"
    )

    print(
        f"Alert candidates:       "
        f"{evaluation.alert_candidate_count}"
    )

    print(
        f"Suppressed:             "
        f"{evaluation.suppressed_count}"
    )


def print_alert_candidates(
    *,
    evaluation: EvaluationBatchResult,
    detected_at,
) -> None:
    """Render and print notification-ready candidates."""

    print()

    print(
        "Notification-Ready Alerts"
    )

    print(
        "=" * 80
    )

    if not evaluation.alert_candidates:
        print(
            (
                "No new alert candidates "
                "were detected in this run."
            )
        )

        return

    for candidate in (
        evaluation.alert_candidates
    ):
        message = (
            render_alert_notification(
                candidate,
                detected_at=detected_at,
            )
        )

        print(
            "-" * 80
        )

        print(
            f"Subject: {message.subject}"
        )

        print()

        print(
            message.text_body
        )


def print_suppressed_changes(
    evaluation: EvaluationBatchResult,
) -> None:
    """Print changed jobs rejected by deterministic eligibility."""

    if not evaluation.suppressed_jobs:
        return

    print()

    print(
        "Suppressed Changed Jobs"
    )

    print(
        "=" * 80
    )

    for item in (
        evaluation.suppressed_jobs
    ):
        print(
            "-" * 80
        )

        print(
            f"Change:      "
            f"{item.observation_status.value}"
        )

        print(
            f"Title:       "
            f"{item.job.title}"
        )

        print(
            f"Eligibility: "
            f"{item.eligibility.status.value}"
        )

        print(
            "Reasons:"
        )

        for reason in (
            item.eligibility.reasons
        ):
            print(
                f"  - {reason}"
            )


def print_outbox_summary(
    result: OutboxEnqueueResult,
) -> None:
    """Print durable notification enqueue results."""

    print()

    print(
        "Notification Outbox"
    )

    print(
        "-" * 80
    )

    print(
        f"Candidates:            "
        f"{result.candidate_count}"
    )

    print(
        f"Queued:                "
        f"{result.queued_count}"
    )

    print(
        f"Already queued:        "
        f"{result.duplicate_count}"
    )


def print_delivery_summary(
    result: DeliveryBatchResult,
) -> None:
    """Print external delivery-worker results."""

    print()

    print(
        "Notification Delivery"
    )

    print(
        "-" * 80
    )

    print(
        f"Attempted:             "
        f"{result.attempted_count}"
    )

    print(
        f"Sent:                  "
        f"{result.sent_count}"
    )

    print(
        f"Retry scheduled:       "
        f"{result.retry_scheduled_count}"
    )

    print(
        f"Dead:                  "
        f"{result.dead_count}"
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the ACE live Greenhouse CLI parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Fetch one live Greenhouse board "
            "and run it through ACE."
        )
    )

    parser.add_argument(
        "--board",
        default=DEFAULT_BOARD_TOKEN,
        help=(
            "Greenhouse board token "
            "(default: databricks)."
        ),
    )

    parser.add_argument(
        "--company",
        default=DEFAULT_COMPANY_NAME,
        help=(
            "Human-readable company name "
            "(default: Databricks)."
        ),
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    """Run one live Greenhouse poll."""

    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    settings = get_settings()

    outbox_result = (
        OutboxEnqueueResult(
            candidate_count=0,
            queued_count=0,
            duplicate_count=0,
        )
    )

    try:
        print(
            (
                "Fetching live Greenhouse jobs "
                f"for {args.company}..."
            )
        )

        live_snapshot = (
            fetch_live_greenhouse_snapshot(
                board_token=args.board,
                company_name=args.company,
            )
        )

        print(
            (
                "Fetched "
                f"{live_snapshot.job_count} "
                "live jobs."
            )
        )

        # This transaction intentionally contains BOTH:
        #
        # 1. source/job reconciliation
        # 2. durable notification enqueue
        #
        # If either operation fails, neither is committed.
        with SessionLocal.begin() as session:
            job_repository = (
                JobRepository(
                    session
                )
            )

            result = (
                process_live_greenhouse_snapshot(
                    job_repository,
                    snapshot=live_snapshot,
                )
            )

            if (
                result.evaluation
                .alert_candidates
            ):
                recipient = (
                    require_notification_recipient(
                        settings
                    )
                )

                outbox_repository = (
                    SqlAlchemyNotificationOutboxRepository(
                        session
                    )
                )

                outbox_result = (
                    enqueue_alert_candidates(
                        outbox_repository,
                        candidates=(
                            result.evaluation
                            .alert_candidates
                        ),
                        source_account=(
                            args.board
                        ),
                        recipient=recipient,
                        detected_at=(
                            live_snapshot
                            .detected_at
                        ),
                    )
                )

    except (
        httpx.HTTPError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        print(
            (
                "ACE live Greenhouse run "
                f"failed: {exc}"
            ),
            file=sys.stderr,
        )

        return 1

    print_run_summary(
        live_snapshot,
        result,
    )

    print_alert_candidates(
        evaluation=result.evaluation,
        detected_at=(
            live_snapshot.detected_at
        ),
    )

    print_suppressed_changes(
        result.evaluation
    )

    print_outbox_summary(
        outbox_result
    )

    # Delivery begins only AFTER the source + outbox transaction above
    # has successfully committed.
    try:
        transport = (
            build_smtp_transport_from_settings(
                settings
            )
        )

    except ValueError as exc:
        print()

        print(
            (
                "Notification delivery "
                "skipped: "
                f"{exc}"
            ),
            file=sys.stderr,
        )

        print(
            (
                "Any queued notifications "
                "remain safely PENDING."
            ),
            file=sys.stderr,
        )

        return 0

    delivery_result = (
        deliver_due_notifications(
            SessionLocal,
            transport,
            max_messages=(
                DELIVERY_BATCH_SIZE
            ),
        )
    )

    print_delivery_summary(
        delivery_result
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )