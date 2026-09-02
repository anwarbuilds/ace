"""Real PostgreSQL smoke test for the ACE notification outbox."""

import hashlib

from sqlalchemy import (
    delete,
    select,
)

from backend.app.db.models import (
    NotificationOutboxRecord,
)
from backend.app.db.session import (
    SessionLocal,
)
from backend.app.notifications.outbox import (
    SqlAlchemyNotificationOutboxRepository,
)


SOURCE = "test"

SOURCE_ACCOUNT = (
    "ace-module5-outbox-smoke"
)

DEDUPE_KEY = hashlib.sha256(
    b"ace-module5-outbox-smoke-event"
).hexdigest()


def cleanup() -> None:
    """Remove only records belonging to this smoke test."""

    with SessionLocal.begin() as session:
        session.execute(
            delete(
                NotificationOutboxRecord
            ).where(
                (
                    NotificationOutboxRecord
                    .source
                    == SOURCE
                ),
                (
                    NotificationOutboxRecord
                    .source_account
                    == SOURCE_ACCOUNT
                ),
            )
        )


def main() -> None:
    """Validate real PostgreSQL enqueue and deduplication behavior."""

    cleanup()

    try:
        with SessionLocal.begin() as session:
            repository = (
                SqlAlchemyNotificationOutboxRepository(
                    session
                )
            )

            first_inserted = (
                repository.enqueue_if_absent(
                    dedupe_key=(
                        DEDUPE_KEY
                    ),
                    source=SOURCE,
                    source_account=(
                        SOURCE_ACCOUNT
                    ),
                    external_id=(
                        "smoke-job-1"
                    ),
                    observation_status=(
                        "NEW"
                    ),
                    job_content_hash=(
                        hashlib.sha256(
                            b"job-content"
                        ).hexdigest()
                    ),
                    source_updated_at=None,
                    recipient=(
                        "smoke@example.com"
                    ),
                    subject=(
                        "[ACE] Outbox smoke test"
                    ),
                    text_body=(
                        "ACE outbox smoke test."
                    ),
                )
            )

            duplicate_inserted = (
                repository.enqueue_if_absent(
                    dedupe_key=(
                        DEDUPE_KEY
                    ),
                    source=SOURCE,
                    source_account=(
                        SOURCE_ACCOUNT
                    ),
                    external_id=(
                        "smoke-job-1"
                    ),
                    observation_status=(
                        "NEW"
                    ),
                    job_content_hash=(
                        hashlib.sha256(
                            b"job-content"
                        ).hexdigest()
                    ),
                    source_updated_at=None,
                    recipient=(
                        "smoke@example.com"
                    ),
                    subject=(
                        "[ACE] Outbox smoke test"
                    ),
                    text_body=(
                        "ACE outbox smoke test."
                    ),
                )
            )

        with SessionLocal() as session:
            records = (
                session.scalars(
                    select(
                        NotificationOutboxRecord
                    ).where(
                        (
                            NotificationOutboxRecord
                            .source_account
                            == SOURCE_ACCOUNT
                        )
                    )
                )
                .all()
            )

        if first_inserted is not True:
            raise RuntimeError(
                (
                    "First outbox insert "
                    "was not created."
                )
            )

        if duplicate_inserted is not False:
            raise RuntimeError(
                (
                    "Duplicate outbox event "
                    "was not suppressed."
                )
            )

        if len(records) != 1:
            raise RuntimeError(
                (
                    "Expected exactly one "
                    "persistent outbox row."
                )
            )

        record = records[
            0
        ]

        if record.status != "PENDING":
            raise RuntimeError(
                (
                    "New outbox record was "
                    "not PENDING."
                )
            )

        print(
            "ACE notification outbox smoke test"
        )

        print(
            "=" * 80
        )

        print(
            f"First insert:      "
            f"{first_inserted}"
        )

        print(
            f"Duplicate insert:  "
            f"{duplicate_inserted}"
        )

        print(
            f"Persistent rows:   "
            f"{len(records)}"
        )

        print(
            f"Status:            "
            f"{record.status}"
        )

        print(
            f"Attempts:          "
            f"{record.attempt_count}"
        )

        print()

        print(
            (
                "Notification outbox "
                "smoke test passed."
            )
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()