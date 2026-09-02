"""Retry-safe delivery worker for the ACE notification outbox."""

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import Enum
from typing import Protocol

from sqlalchemy import (
    select,
    update,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.models import (
    NotificationOutboxRecord,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_RETRY_BASE_SECONDS = 60
DEFAULT_RETRY_MAX_SECONDS = 3600


class DeliveryOutcome(str, Enum):
    """Possible outcomes for one delivery attempt."""

    SENT = "SENT"

    RETRY_SCHEDULED = "RETRY_SCHEDULED"

    DEAD = "DEAD"


@dataclass(
    frozen=True,
    slots=True,
)
class PendingNotification:
    """Transport-neutral outbox item ready for delivery."""

    id: int

    recipient: str

    subject: str

    text_body: str

    attempt_count: int


@dataclass(
    frozen=True,
    slots=True,
)
class DeliveryAttemptResult:
    """Result of attempting one outbox notification."""

    outbox_id: int

    outcome: DeliveryOutcome

    attempt_count: int

    error: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class DeliveryBatchResult:
    """Summary of one worker drain operation."""

    attempted_count: int

    sent_count: int

    retry_scheduled_count: int

    dead_count: int


class NotificationTransport(Protocol):
    """External transport contract used by ACE."""

    def send(
        self,
        message: NotificationMessage,
        *,
        recipient: str,
    ) -> None:
        """Deliver one notification."""


class NotificationDeliveryStore(Protocol):
    """Persistence operations required by the delivery worker."""

    def claim_next_due(
        self,
        *,
        now: datetime,
    ) -> PendingNotification | None:
        """Lock and return the next due PENDING notification."""

    def mark_sent(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        """Mark a successfully delivered notification."""

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
        """Persist a failed delivery attempt."""


class SqlAlchemyNotificationDeliveryStore:
    """PostgreSQL implementation of delivery-worker persistence.

    FOR UPDATE SKIP LOCKED allows multiple future workers to safely
    consume different outbox rows without delivering the same row
    concurrently.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def claim_next_due(
        self,
        *,
        now: datetime,
    ) -> PendingNotification | None:
        """Lock the oldest due PENDING notification."""

        statement = (
            select(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.status
                == "PENDING",
                NotificationOutboxRecord.next_attempt_at
                <= now,
            )
            .order_by(
                NotificationOutboxRecord.next_attempt_at,
                NotificationOutboxRecord.created_at,
                NotificationOutboxRecord.id,
            )
            .with_for_update(
                skip_locked=True
            )
            .limit(1)
        )

        record = self._session.scalar(
            statement
        )

        if record is None:
            return None

        return PendingNotification(
            id=record.id,
            recipient=record.recipient,
            subject=record.subject,
            text_body=record.text_body,
            attempt_count=record.attempt_count,
        )

    def mark_sent(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        """Persist successful delivery."""

        self._session.execute(
            update(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.id
                == outbox_id
            )
            .values(
                status="SENT",
                attempt_count=attempt_count,
                last_attempt_at=attempted_at,
                sent_at=attempted_at,
                last_error=None,
            )
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
        """Persist failed delivery and retry state."""

        self._session.execute(
            update(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.id
                == outbox_id
            )
            .values(
                status=(
                    "DEAD"
                    if dead
                    else "PENDING"
                ),
                attempt_count=attempt_count,
                last_attempt_at=attempted_at,
                next_attempt_at=next_attempt_at,
                last_error=error,
            )
        )


def _require_aware_datetime(
    value: datetime,
) -> datetime:
    """Require an aware datetime and normalize it to UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "now must be timezone-aware."
        )

    return value.astimezone(
        timezone.utc
    )


def compute_retry_delay_seconds(
    attempt_count: int,
    *,
    base_seconds: int = (
        DEFAULT_RETRY_BASE_SECONDS
    ),
    max_seconds: int = (
        DEFAULT_RETRY_MAX_SECONDS
    ),
) -> int:
    """Return exponential retry delay for a failed attempt.

    Attempt 1 -> 60 seconds
    Attempt 2 -> 120 seconds
    Attempt 3 -> 240 seconds

    Delay is capped to prevent unbounded exponential growth.
    """

    if attempt_count < 1:
        raise ValueError(
            (
                "attempt_count must be "
                "at least 1."
            )
        )

    if base_seconds < 1:
        raise ValueError(
            (
                "base_seconds must be "
                "at least 1."
            )
        )

    if max_seconds < base_seconds:
        raise ValueError(
            (
                "max_seconds must be greater "
                "than or equal to base_seconds."
            )
        )

    delay = (
        base_seconds
        * (2 ** (attempt_count - 1))
    )

    return min(
        delay,
        max_seconds,
    )


def deliver_one_due_notification(
    store: NotificationDeliveryStore,
    transport: NotificationTransport,
    *,
    now: datetime,
    max_attempts: int = (
        DEFAULT_MAX_ATTEMPTS
    ),
    retry_base_seconds: int = (
        DEFAULT_RETRY_BASE_SECONDS
    ),
    retry_max_seconds: int = (
        DEFAULT_RETRY_MAX_SECONDS
    ),
) -> DeliveryAttemptResult | None:
    """Attempt delivery of one due outbox notification."""

    normalized_now = (
        _require_aware_datetime(
            now
        )
    )

    if max_attempts < 1:
        raise ValueError(
            (
                "max_attempts must be "
                "at least 1."
            )
        )

    pending = store.claim_next_due(
        now=normalized_now
    )

    if pending is None:
        return None

    attempt_count = (
        pending.attempt_count
        + 1
    )

    message = NotificationMessage(
        subject=pending.subject,
        text_body=pending.text_body,
    )

    try:
        transport.send(
            message,
            recipient=pending.recipient,
        )

    except Exception as exc:
        error = (
            f"{type(exc).__name__}: {exc}"
        )

        # Prevent an unexpectedly large provider error from bloating
        # PostgreSQL indefinitely.
        error = error[:4000]

        is_dead = (
            attempt_count
            >= max_attempts
        )

        if is_dead:
            next_attempt_at = (
                normalized_now
            )

        else:
            retry_delay = (
                compute_retry_delay_seconds(
                    attempt_count,
                    base_seconds=(
                        retry_base_seconds
                    ),
                    max_seconds=(
                        retry_max_seconds
                    ),
                )
            )

            next_attempt_at = (
                normalized_now
                + timedelta(
                    seconds=retry_delay
                )
            )

        store.mark_failed(
            outbox_id=pending.id,
            attempt_count=attempt_count,
            attempted_at=normalized_now,
            next_attempt_at=next_attempt_at,
            error=error,
            dead=is_dead,
        )

        return DeliveryAttemptResult(
            outbox_id=pending.id,
            outcome=(
                DeliveryOutcome.DEAD
                if is_dead
                else DeliveryOutcome
                .RETRY_SCHEDULED
            ),
            attempt_count=attempt_count,
            error=error,
        )

    store.mark_sent(
        outbox_id=pending.id,
        attempt_count=attempt_count,
        attempted_at=normalized_now,
    )

    return DeliveryAttemptResult(
        outbox_id=pending.id,
        outcome=DeliveryOutcome.SENT,
        attempt_count=attempt_count,
    )


def deliver_due_notifications(
    session_factory: sessionmaker,
    transport: NotificationTransport,
    *,
    max_messages: int = 50,
    max_attempts: int = (
        DEFAULT_MAX_ATTEMPTS
    ),
    retry_base_seconds: int = (
        DEFAULT_RETRY_BASE_SECONDS
    ),
    retry_max_seconds: int = (
        DEFAULT_RETRY_MAX_SECONDS
    ),
) -> DeliveryBatchResult:
    """Drain due notifications using one DB transaction per message.

    One notification per transaction keeps SMTP failures isolated and
    minimizes the amount of committed work that could be repeated after
    a process crash.
    """

    if max_messages < 1:
        raise ValueError(
            (
                "max_messages must be "
                "at least 1."
            )
        )

    attempted_count = 0
    sent_count = 0
    retry_scheduled_count = 0
    dead_count = 0

    for _ in range(
        max_messages
    ):
        now = datetime.now(
            timezone.utc
        )

        with (
            session_factory.begin()
            as session
        ):
            store = (
                SqlAlchemyNotificationDeliveryStore(
                    session
                )
            )

            result = (
                deliver_one_due_notification(
                    store,
                    transport,
                    now=now,
                    max_attempts=(
                        max_attempts
                    ),
                    retry_base_seconds=(
                        retry_base_seconds
                    ),
                    retry_max_seconds=(
                        retry_max_seconds
                    ),
                )
            )

        if result is None:
            break

        attempted_count += 1

        if (
            result.outcome
            == DeliveryOutcome.SENT
        ):
            sent_count += 1

        elif (
            result.outcome
            == DeliveryOutcome
            .RETRY_SCHEDULED
        ):
            retry_scheduled_count += 1

        elif (
            result.outcome
            == DeliveryOutcome.DEAD
        ):
            dead_count += 1

    return DeliveryBatchResult(
        attempted_count=(
            attempted_count
        ),
        sent_count=sent_count,
        retry_scheduled_count=(
            retry_scheduled_count
        ),
        dead_count=dead_count,
    )