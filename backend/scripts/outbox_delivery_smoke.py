"""Real PostgreSQL + Gmail smoke test for durable ACE delivery."""

import hashlib

from sqlalchemy import (
    delete,
    select,
)

from backend.app.config import (
    get_settings,
)
from backend.app.db.models import (
    NotificationOutboxRecord,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.notifications.delivery import (
    deliver_due_notifications,
)
from backend.app.notifications.outbox import (
    SqlAlchemyNotificationOutboxRepository,
)
from backend.app.notifications.runtime import (
    build_smtp_transport_from_settings,
    require_notification_recipient,
)


SOURCE = "test"

SOURCE_ACCOUNT = (
    "ace-module5-delivery-smoke"
)

DEDUPE_KEY = hashlib.sha256(
    b"ace-module5-delivery-smoke"
).hexdigest()


def cleanup() -> None:
    """Remove only this smoke test's outbox rows."""

    with SessionLocal.begin() as session:
        session.execute(
            delete(
                NotificationOutboxRecord
            ).where(
                NotificationOutboxRecord
                .source
                == SOURCE,
                NotificationOutboxRecord
                .source_account
                == SOURCE_ACCOUNT,
            )
        )


def main() -> None:
    """Verify PENDING -> SMTP -> SENT using real infrastructure."""

    settings = get_settings()

    recipient = (
        require_notification_recipient(
            settings
        )
    )

    transport = (
        build_smtp_transport_from_settings(
            settings
        )
    )

    cleanup()

    try:
        with SessionLocal.begin() as session:
            repository = (
                SqlAlchemyNotificationOutboxRepository(
                    session
                )
            )

            inserted = (
                repository.enqueue_if_absent(
                    dedupe_key=DEDUPE_KEY,
                    source=SOURCE,
                    source_account=(
                        SOURCE_ACCOUNT
                    ),
                    external_id=(
                        "delivery-smoke-1"
                    ),
                    observation_status=(
                        "NEW"
                    ),
                    job_content_hash=(
                        hashlib.sha256(
                            b"delivery-smoke-job"
                        ).hexdigest()
                    ),
                    source_updated_at=None,
                    recipient=recipient,
                    subject=(
                        "[ACE] Durable outbox "
                        "delivery smoke test"
                    ),
                    text_body=(
                        "ACE DURABLE DELIVERY TEST\n"
                        "\n"
                        "This email was first "
                        "persisted to PostgreSQL "
                        "as PENDING and was then "
                        "delivered by the ACE "
                        "outbox worker.\n"
                    ),
                )
            )

        if not inserted:
            raise RuntimeError(
                (
                    "Smoke notification was "
                    "not inserted."
                )
            )

        delivery = (
            deliver_due_notifications(
                SessionLocal,
                transport,
                max_messages=1,
            )
        )

        with SessionLocal() as session:
            record = session.scalar(
                select(
                    NotificationOutboxRecord
                ).where(
                    NotificationOutboxRecord
                    .dedupe_key
                    == DEDUPE_KEY
                )
            )

        if record is None:
            raise RuntimeError(
                (
                    "Outbox smoke record "
                    "disappeared."
                )
            )

        if record.status != "SENT":
            raise RuntimeError(
                (
                    "Expected SENT status, "
                    f"got {record.status}."
                )
            )

        if record.attempt_count != 1:
            raise RuntimeError(
                (
                    "Expected exactly one "
                    "delivery attempt."
                )
            )

        if record.sent_at is None:
            raise RuntimeError(
                (
                    "Successful delivery has "
                    "no sent_at timestamp."
                )
            )

        print(
            "ACE Durable Outbox Delivery Smoke Test"
        )

        print(
            "=" * 80
        )

        print(
            f"Queued:             "
            f"{inserted}"
        )

        print(
            f"Attempted:          "
            f"{delivery.attempted_count}"
        )

        print(
            f"Sent:               "
            f"{delivery.sent_count}"
        )

        print(
            f"Retry scheduled:    "
            f"{delivery.retry_scheduled_count}"
        )

        print(
            f"Database status:    "
            f"{record.status}"
        )

        print(
            f"Attempt count:      "
            f"{record.attempt_count}"
        )

        print(
            f"Sent at:            "
            f"{record.sent_at}"
        )

        print()

        print(
            (
                "Durable outbox delivery "
                "smoke test passed."
            )
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()