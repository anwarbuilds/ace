"""Tests for retry-safe ACE outbox delivery."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.app.notifications.delivery import (
    DeliveryOutcome,
    PendingNotification,
    compute_retry_delay_seconds,
    deliver_one_due_notification,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


NOW = datetime(
    2026,
    9,
    2,
    20,
    30,
    tzinfo=timezone.utc,
)


class FakeStore:
    """In-memory delivery store for unit tests."""

    def __init__(
        self,
        pending: (
            PendingNotification | None
        ),
    ) -> None:
        self.pending = pending

        self.sent_calls: list[
            dict[str, object]
        ] = []

        self.failed_calls: list[
            dict[str, object]
        ] = []

    def claim_next_due(
        self,
        *,
        now: datetime,
    ) -> PendingNotification | None:
        return self.pending

    def mark_sent(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        self.sent_calls.append(
            {
                "outbox_id": outbox_id,
                "attempt_count": (
                    attempt_count
                ),
                "attempted_at": (
                    attempted_at
                ),
            }
        )

    def mark_failed(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        attempted_at: datetime,
        next_attempt_at: datetime,
        error: str,
        dead: bool,
    ) -> None:
        self.failed_calls.append(
            {
                "outbox_id": outbox_id,
                "attempt_count": (
                    attempt_count
                ),
                "attempted_at": (
                    attempted_at
                ),
                "next_attempt_at": (
                    next_attempt_at
                ),
                "error": error,
                "dead": dead,
            }
        )


class FakeTransport:
    """Controllable notification transport."""

    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error

        self.messages: list[
            tuple[
                NotificationMessage,
                str,
            ]
        ] = []

    def send(
        self,
        message: NotificationMessage,
        *,
        recipient: str,
    ) -> None:
        if self.error is not None:
            raise self.error

        self.messages.append(
            (
                message,
                recipient,
            )
        )


def make_pending(
    *,
    attempt_count: int = 0,
) -> PendingNotification:
    """Create one deterministic pending notification."""

    return PendingNotification(
        id=42,
        recipient="user@example.com",
        subject="[ACE] Test",
        text_body="ACE test notification.",
        attempt_count=attempt_count,
    )


def test_successful_delivery_marks_sent() -> None:
    store = FakeStore(
        make_pending()
    )

    transport = FakeTransport()

    result = (
        deliver_one_due_notification(
            store,
            transport,
            now=NOW,
        )
    )

    assert result is not None

    assert (
        result.outcome
        == DeliveryOutcome.SENT
    )

    assert (
        result.attempt_count
        == 1
    )

    assert len(
        transport.messages
    ) == 1

    assert len(
        store.sent_calls
    ) == 1

    assert (
        store.failed_calls
        == []
    )


def test_failed_delivery_schedules_retry() -> None:
    store = FakeStore(
        make_pending()
    )

    transport = FakeTransport(
        error=RuntimeError(
            "SMTP temporarily unavailable"
        )
    )

    result = (
        deliver_one_due_notification(
            store,
            transport,
            now=NOW,
        )
    )

    assert result is not None

    assert (
        result.outcome
        == DeliveryOutcome
        .RETRY_SCHEDULED
    )

    assert (
        result.attempt_count
        == 1
    )

    assert len(
        store.failed_calls
    ) == 1

    failure = (
        store.failed_calls[
            0
        ]
    )

    assert (
        failure["dead"]
        is False
    )

    assert (
        failure["next_attempt_at"]
        == NOW
        + timedelta(
            seconds=60
        )
    )


def test_final_failure_marks_dead() -> None:
    store = FakeStore(
        make_pending(
            attempt_count=4
        )
    )

    transport = FakeTransport(
        error=RuntimeError(
            "Permanent failure"
        )
    )

    result = (
        deliver_one_due_notification(
            store,
            transport,
            now=NOW,
            max_attempts=5,
        )
    )

    assert result is not None

    assert (
        result.outcome
        == DeliveryOutcome.DEAD
    )

    assert (
        result.attempt_count
        == 5
    )

    failure = (
        store.failed_calls[
            0
        ]
    )

    assert (
        failure["dead"]
        is True
    )


def test_no_due_notification_does_nothing() -> None:
    store = FakeStore(
        None
    )

    transport = FakeTransport()

    result = (
        deliver_one_due_notification(
            store,
            transport,
            now=NOW,
        )
    )

    assert result is None

    assert (
        transport.messages
        == []
    )

    assert (
        store.sent_calls
        == []
    )

    assert (
        store.failed_calls
        == []
    )


def test_retry_delay_is_exponential_and_capped() -> None:
    assert (
        compute_retry_delay_seconds(
            1
        )
        == 60
    )

    assert (
        compute_retry_delay_seconds(
            2
        )
        == 120
    )

    assert (
        compute_retry_delay_seconds(
            3
        )
        == 240
    )

    assert (
        compute_retry_delay_seconds(
            20
        )
        == 3600
    )