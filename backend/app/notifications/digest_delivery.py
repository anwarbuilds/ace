"""Durable, restart-safe digest delivery for ACE.

The outbox remains one row per opportunity. Delivery groups many rows
into one email.

Durability model
----------------

Two durable facts cooperate:

    notification_digests.digest_key   UNIQUE
        identifies one delivery window for one recipient

    notification_outbox.digest_id
        records which candidates a digest owns

Because the window identity is a database constraint rather than
in-process state, a worker restart cannot resend a window that has
already been delivered, and cannot deliver the same candidate inside two
successful digests.

Candidate freezing
------------------

Candidates are assigned to a digest exactly once, on its first delivery
attempt. Retries re-send the same frozen set rather than absorbing rows
that arrived in the meantime. This keeps an SMTP outage from producing
an ever-growing digest, and keeps "the digest that was sent" equal to
"the candidates that were marked delivered".

Rows arriving after assignment are picked up by the next window.

Delivery guarantee
------------------

Delivery is **at-least-once**, not exactly-once.

SMTP is attempted inside the database transaction that records the
result. If the process dies after the SMTP server accepts the message
but before the transaction commits, the digest is retried and the email
may arrive twice. SMTP itself offers no way to close that gap, so ACE
prefers a possible duplicate over a silently lost opportunity.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import Enum
import logging
from typing import (
    Any,
    Protocol,
)

from sqlalchemy import (
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import (
    insert as postgresql_insert,
)
from sqlalchemy.dialects.sqlite import (
    insert as sqlite_insert,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.models import (
    NotificationDigestRecord,
    NotificationOutboxRecord,
)
from backend.app.notifications.delivery import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_BASE_SECONDS,
    DEFAULT_RETRY_MAX_SECONDS,
    NotificationTransport,
    compute_retry_delay_seconds,
)
from backend.app.notifications.digest import (
    render_digest,
)
from backend.app.notifications.payload import (
    DigestItem,
    digest_item_from_legacy_row,
    digest_item_from_payload,
)
from backend.app.notifications.schedule import (
    DigestWindow,
    DigestWindowSchedule,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


LOGGER = logging.getLogger(
    "ace.notifications.digest"
)


DEFAULT_MAX_DIGEST_JOBS = 100


class DigestOutcome(str, Enum):
    """Result of one digest delivery attempt."""

    SENT = "SENT"

    RETRY_SCHEDULED = "RETRY_SCHEDULED"

    DEAD = "DEAD"

    NO_OPEN_WINDOW = "NO_OPEN_WINDOW"

    NOTHING_TO_SEND = "NOTHING_TO_SEND"

    ALREADY_DELIVERED = (
        "ALREADY_DELIVERED"
    )

    WINDOW_ABANDONED = (
        "WINDOW_ABANDONED"
    )

    RETRY_NOT_DUE = "RETRY_NOT_DUE"

    CONCURRENT_WORKER = (
        "CONCURRENT_WORKER"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class DigestAttemptResult:
    """Outcome of attempting one digest window."""

    outcome: DigestOutcome

    digest_id: int | None = None

    item_count: int = 0

    deferred_count: int = 0

    attempt_count: int = 0

    subject: str | None = None

    error: str | None = None

    @property
    def delivered(
        self,
    ) -> bool:
        """Return whether this attempt sent an email."""

        return (
            self.outcome
            is DigestOutcome.SENT
        )


@dataclass(
    frozen=True,
    slots=True,
)
class LockedDigest:
    """A digest row held under an exclusive lock."""

    id: int

    status: str

    item_count: int

    attempt_count: int

    next_attempt_at: datetime


@dataclass(
    frozen=True,
    slots=True,
)
class DigestCandidateRow:
    """One outbox row assigned to a digest."""

    id: int

    subject: str

    observation_status: str

    source_account: str

    external_id: str

    payload: dict[str, Any] | None


class DigestDeliveryStore(Protocol):
    """Persistence operations required by the digest worker."""

    def get_or_create_digest(
        self,
        *,
        window: DigestWindow,
        recipient: str,
    ) -> int:
        """Return the durable digest id for one window."""

    def lock_digest(
        self,
        *,
        digest_id: int,
    ) -> LockedDigest | None:
        """Exclusively lock a digest, or None if another worker holds it."""

    def assign_pending_candidates(
        self,
        *,
        digest_id: int,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> int:
        """Assign unassigned due candidates to a digest."""

    def count_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
    ) -> int:
        """Count due candidates not yet assigned to any digest."""

    def load_digest_candidates(
        self,
        *,
        digest_id: int,
    ) -> list[DigestCandidateRow]:
        """Load the candidates a digest owns."""

    def load_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> list[DigestCandidateRow]:
        """Load due candidates without assigning them to a digest."""

    def discard_empty_digest(
        self,
        *,
        digest_id: int,
    ) -> None:
        """Remove a digest window that had nothing to deliver."""

    def mark_digest_sent(
        self,
        *,
        digest_id: int,
        subject: str,
        item_count: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        """Record a delivered digest and its included candidates."""

    def mark_digest_failed(
        self,
        *,
        digest_id: int,
        attempt_count: int,
        attempted_at: datetime,
        next_attempt_at: datetime,
        error: str,
        dead: bool,
    ) -> None:
        """Record a failed digest delivery attempt."""


class SqlAlchemyDigestDeliveryStore:
    """PostgreSQL implementation of digest-delivery persistence."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def _upsert_statement(
        self,
        model,
    ):
        """Return a dialect-appropriate INSERT ... ON CONFLICT.

        PostgreSQL is production. SQLite backs the integration tests and
        supports the same ON CONFLICT DO NOTHING semantics, so digest
        creation can be exercised for real rather than through a mock.
        """

        if (
            self._session.get_bind()
            .dialect.name
            == "sqlite"
        ):
            return sqlite_insert(
                model
            )

        return postgresql_insert(
            model
        )

    @property
    def _supports_row_locking(
        self,
    ) -> bool:
        """Return whether the bound dialect supports SKIP LOCKED.

        SQLite is used for lightweight integration tests and has no row
        locking. It is also single-writer, so omitting the clause there
        is safe rather than a correctness compromise.
        """

        bind = self._session.get_bind()

        return (
            bind.dialect.name
            == "postgresql"
        )

    def get_or_create_digest(
        self,
        *,
        window: DigestWindow,
        recipient: str,
    ) -> int:
        """Return the durable digest id for one delivery window.

        The UNIQUE digest_key makes this safe under concurrency: two
        workers racing to open the same window converge on one row.
        """

        digest_key = window.digest_key(
            recipient=recipient
        )

        values = {
            "digest_key": digest_key,
            "recipient": recipient,
            "window_date": (
                window.local_date
            ),
            "window_label": (
                window.window_label
            ),
            "window_opens_at": (
                window.opens_at
            ),
            "status": "PENDING",
            "item_count": 0,
            "attempt_count": 0,
            "next_attempt_at": (
                window.opens_at
            ),
        }

        statement = (
            self._upsert_statement(
                NotificationDigestRecord
            )
            .values(
                **values
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "digest_key",
                ]
            )
            .returning(
                NotificationDigestRecord.id
            )
        )

        inserted_id = self._session.scalar(
            statement
        )

        if inserted_id is not None:
            return int(
                inserted_id
            )

        existing_id = self._session.scalar(
            select(
                NotificationDigestRecord.id
            ).where(
                NotificationDigestRecord.digest_key
                == digest_key
            )
        )

        if existing_id is None:
            raise RuntimeError(
                (
                    "Digest row disappeared "
                    "immediately after an "
                    "insert conflict: "
                    f"{digest_key!r}."
                )
            )

        return int(
            existing_id
        )

    def lock_digest(
        self,
        *,
        digest_id: int,
    ) -> LockedDigest | None:
        """Exclusively lock one digest row."""

        statement = select(
            NotificationDigestRecord
        ).where(
            NotificationDigestRecord.id
            == digest_id
        )

        if self._supports_row_locking:
            statement = (
                statement.with_for_update(
                    skip_locked=True
                )
            )

        record = self._session.scalar(
            statement
        )

        if record is None:
            return None

        return LockedDigest(
            id=record.id,
            status=record.status,
            item_count=(
                record.item_count
            ),
            attempt_count=(
                record.attempt_count
            ),
            next_attempt_at=(
                _as_utc(
                    record.next_attempt_at
                )
            ),
        )

    def _due_candidate_filter(
        self,
        *,
        recipient: str,
        now: datetime,
    ):
        """Return the predicate identifying assignable candidates."""

        return (
            NotificationOutboxRecord.recipient
            == recipient,
            NotificationOutboxRecord.status
            == "PENDING",
            NotificationOutboxRecord.digest_id
            .is_(None),
            NotificationOutboxRecord.next_attempt_at
            <= now,
        )

    def assign_pending_candidates(
        self,
        *,
        digest_id: int,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> int:
        """Durably assign due candidates to one digest."""

        if limit < 1:
            raise ValueError(
                (
                    "limit must be at least 1."
                )
            )

        selection = (
            select(
                NotificationOutboxRecord.id
            )
            .where(
                *self._due_candidate_filter(
                    recipient=recipient,
                    now=now,
                )
            )
            .order_by(
                NotificationOutboxRecord.created_at,
                NotificationOutboxRecord.id,
            )
            .limit(
                limit
            )
        )

        if self._supports_row_locking:
            selection = (
                selection.with_for_update(
                    skip_locked=True
                )
            )

        candidate_ids = list(
            self._session.scalars(
                selection
            ).all()
        )

        if not candidate_ids:
            return 0

        self._session.execute(
            update(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.id
                .in_(
                    candidate_ids
                )
            )
            .values(
                digest_id=digest_id
            )
        )

        self._session.execute(
            update(
                NotificationDigestRecord
            )
            .where(
                NotificationDigestRecord.id
                == digest_id
            )
            .values(
                item_count=len(
                    candidate_ids
                )
            )
        )

        self._session.flush()

        return len(
            candidate_ids
        )

    def count_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
    ) -> int:
        """Count due candidates still awaiting a digest."""

        total = self._session.scalar(
            select(
                func.count()
            )
            .select_from(
                NotificationOutboxRecord
            )
            .where(
                *self._due_candidate_filter(
                    recipient=recipient,
                    now=now,
                )
            )
        )

        return int(
            total or 0
        )

    def load_digest_candidates(
        self,
        *,
        digest_id: int,
    ) -> list[DigestCandidateRow]:
        """Load every outbox row assigned to a digest."""

        records = self._session.scalars(
            select(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.digest_id
                == digest_id
            )
            .order_by(
                NotificationOutboxRecord.created_at,
                NotificationOutboxRecord.id,
            )
        ).all()

        return [
            DigestCandidateRow(
                id=record.id,
                subject=record.subject,
                observation_status=(
                    record.observation_status
                ),
                source_account=(
                    record.source_account
                ),
                external_id=(
                    record.external_id
                ),
                payload=record.payload,
            )
            for record in records
        ]

    def load_unassigned_candidates(
        self,
        *,
        recipient: str,
        now: datetime,
        limit: int,
    ) -> list[DigestCandidateRow]:
        """Load due candidates without claiming them.

        This exists for read-only preview. It must never mutate outbox
        state, so a rehearsal cannot consume a delivery window or burn a
        retry attempt.
        """

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        records = self._session.scalars(
            select(
                NotificationOutboxRecord
            )
            .where(
                *self._due_candidate_filter(
                    recipient=recipient,
                    now=now,
                )
            )
            .order_by(
                NotificationOutboxRecord.created_at,
                NotificationOutboxRecord.id,
            )
            .limit(
                limit
            )
        ).all()

        return [
            DigestCandidateRow(
                id=record.id,
                subject=record.subject,
                observation_status=(
                    record.observation_status
                ),
                source_account=(
                    record.source_account
                ),
                external_id=(
                    record.external_id
                ),
                payload=record.payload,
            )
            for record in records
        ]

    def discard_empty_digest(
        self,
        *,
        digest_id: int,
    ) -> None:
        """Delete a digest window that owns no candidates.

        Removing the row rather than marking it sent keeps the window
        available: if a qualifying job arrives later in the same window,
        ACE can still deliver it instead of waiting for tomorrow.
        """

        self._session.execute(
            NotificationDigestRecord
            .__table__
            .delete()
            .where(
                NotificationDigestRecord.id
                == digest_id,
                NotificationDigestRecord.item_count
                == 0,
                NotificationDigestRecord.status
                == "PENDING",
            )
        )

        self._session.flush()

    def mark_digest_sent(
        self,
        *,
        digest_id: int,
        subject: str,
        item_count: int,
        attempt_count: int,
        attempted_at: datetime,
    ) -> None:
        """Record a delivered digest and mark its candidates SENT."""

        self._session.execute(
            update(
                NotificationDigestRecord
            )
            .where(
                NotificationDigestRecord.id
                == digest_id
            )
            .values(
                status="SENT",
                subject=subject,
                item_count=item_count,
                attempt_count=(
                    attempt_count
                ),
                last_attempt_at=(
                    attempted_at
                ),
                sent_at=attempted_at,
                last_error=None,
            )
        )

        self._session.execute(
            update(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.digest_id
                == digest_id,
                NotificationOutboxRecord.status
                == "PENDING",
            )
            .values(
                status="SENT",
                sent_at=attempted_at,
                last_attempt_at=(
                    attempted_at
                ),
                attempt_count=(
                    NotificationOutboxRecord
                    .attempt_count
                    + 1
                ),
                last_error=None,
            )
        )

        self._session.flush()

    def mark_digest_failed(
        self,
        *,
        digest_id: int,
        attempt_count: int,
        attempted_at: datetime,
        next_attempt_at: datetime,
        error: str,
        dead: bool,
    ) -> None:
        """Record a failed digest attempt.

        When a digest exhausts its attempts, its candidates become DEAD
        alongside it. They are never deleted, so the maintenance script
        can requeue them once the transport is healthy again.
        """

        self._session.execute(
            update(
                NotificationDigestRecord
            )
            .where(
                NotificationDigestRecord.id
                == digest_id
            )
            .values(
                status=(
                    "DEAD"
                    if dead
                    else "PENDING"
                ),
                attempt_count=(
                    attempt_count
                ),
                last_attempt_at=(
                    attempted_at
                ),
                next_attempt_at=(
                    next_attempt_at
                ),
                last_error=error,
            )
        )

        self._session.execute(
            update(
                NotificationOutboxRecord
            )
            .where(
                NotificationOutboxRecord.digest_id
                == digest_id,
                NotificationOutboxRecord.status
                == "PENDING",
            )
            .values(
                status=(
                    "DEAD"
                    if dead
                    else "PENDING"
                ),
                attempt_count=(
                    attempt_count
                ),
                last_attempt_at=(
                    attempted_at
                ),
                last_error=error,
            )
        )

        self._session.flush()


def _as_utc(
    value: datetime,
) -> datetime:
    """Normalize a stored timestamp to an aware UTC datetime."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
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


def build_digest_items(
    rows: Sequence[DigestCandidateRow],
) -> tuple[DigestItem, ...]:
    """Convert assigned outbox rows into renderable digest items.

    Rows written before structured payloads existed fall back to a
    best-effort item so historical candidates stay deliverable.
    """

    items: list[DigestItem] = []

    for row in rows:
        if isinstance(
            row.payload,
            dict,
        ):
            items.append(
                digest_item_from_payload(
                    row.payload
                )
            )

            continue

        items.append(
            digest_item_from_legacy_row(
                subject=row.subject,
                observation_status=(
                    row.observation_status
                ),
                source_account=(
                    row.source_account
                ),
                external_id=(
                    row.external_id
                ),
            )
        )

    return tuple(
        items
    )


def deliver_digest_once(
    store: DigestDeliveryStore,
    transport: NotificationTransport,
    *,
    now: datetime,
    schedule: DigestWindowSchedule,
    recipient: str,
    max_jobs: int = DEFAULT_MAX_DIGEST_JOBS,
    max_attempts: int = (
        DEFAULT_MAX_ATTEMPTS
    ),
    retry_base_seconds: int = (
        DEFAULT_RETRY_BASE_SECONDS
    ),
    retry_max_seconds: int = (
        DEFAULT_RETRY_MAX_SECONDS
    ),
) -> DigestAttemptResult:
    """Attempt delivery of the digest window open at ``now``.

    Returns without sending when there is no open window, when the
    window was already delivered, or when the window has nothing worth
    reporting. Zero qualifying jobs always means zero email.
    """

    normalized_now = (
        _require_aware_datetime(
            now
        )
    )

    normalized_recipient = (
        recipient.strip()
    )

    if not normalized_recipient:
        raise ValueError(
            (
                "recipient must not be "
                "empty."
            )
        )

    if max_jobs < 1:
        raise ValueError(
            (
                "max_jobs must be at "
                "least 1."
            )
        )

    if max_attempts < 1:
        raise ValueError(
            (
                "max_attempts must be at "
                "least 1."
            )
        )

    window = (
        schedule.resolve_active_window(
            now=normalized_now
        )
    )

    if window is None:
        return DigestAttemptResult(
            outcome=(
                DigestOutcome.NO_OPEN_WINDOW
            )
        )

    digest_id = (
        store.get_or_create_digest(
            window=window,
            recipient=(
                normalized_recipient
            ),
        )
    )

    locked = store.lock_digest(
        digest_id=digest_id
    )

    if locked is None:
        return DigestAttemptResult(
            outcome=(
                DigestOutcome
                .CONCURRENT_WORKER
            ),
            digest_id=digest_id,
        )

    if locked.status == "SENT":
        return DigestAttemptResult(
            outcome=(
                DigestOutcome
                .ALREADY_DELIVERED
            ),
            digest_id=digest_id,
            item_count=locked.item_count,
        )

    if locked.status == "DEAD":
        return DigestAttemptResult(
            outcome=(
                DigestOutcome
                .WINDOW_ABANDONED
            ),
            digest_id=digest_id,
            item_count=locked.item_count,
            attempt_count=(
                locked.attempt_count
            ),
        )

    if (
        locked.attempt_count > 0
        and locked.next_attempt_at
        > normalized_now
    ):
        return DigestAttemptResult(
            outcome=(
                DigestOutcome.RETRY_NOT_DUE
            ),
            digest_id=digest_id,
            item_count=locked.item_count,
            attempt_count=(
                locked.attempt_count
            ),
        )

    if locked.item_count == 0:
        assigned_count = (
            store.assign_pending_candidates(
                digest_id=digest_id,
                recipient=(
                    normalized_recipient
                ),
                now=normalized_now,
                limit=max_jobs,
            )
        )

        if assigned_count == 0:
            store.discard_empty_digest(
                digest_id=digest_id
            )

            return DigestAttemptResult(
                outcome=(
                    DigestOutcome
                    .NOTHING_TO_SEND
                ),
                digest_id=digest_id,
            )

    rows = store.load_digest_candidates(
        digest_id=digest_id
    )

    if not rows:
        store.discard_empty_digest(
            digest_id=digest_id
        )

        return DigestAttemptResult(
            outcome=(
                DigestOutcome
                .NOTHING_TO_SEND
            ),
            digest_id=digest_id,
        )

    deferred_count = (
        store.count_unassigned_candidates(
            recipient=(
                normalized_recipient
            ),
            now=normalized_now,
        )
    )

    items = build_digest_items(
        rows
    )

    message = render_digest(
        items,
        window_label=(
            window.display_label
        ),
        reference_time=normalized_now,
        timezone_name=(
            schedule.timezone_name
        ),
        deferred_count=deferred_count,
    )

    attempt_count = (
        locked.attempt_count
        + 1
    )

    try:
        transport.send(
            message,
            recipient=(
                normalized_recipient
            ),
        )

    except Exception as exc:
        error = (
            f"{type(exc).__name__}: {exc}"
        )[:4000]

        is_dead = (
            attempt_count
            >= max_attempts
        )

        if is_dead:
            next_attempt_at = (
                normalized_now
            )

        else:
            next_attempt_at = (
                normalized_now
                + timedelta(
                    seconds=(
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
                )
            )

        store.mark_digest_failed(
            digest_id=digest_id,
            attempt_count=attempt_count,
            attempted_at=normalized_now,
            next_attempt_at=(
                next_attempt_at
            ),
            error=error,
            dead=is_dead,
        )

        return DigestAttemptResult(
            outcome=(
                DigestOutcome.DEAD
                if is_dead
                else DigestOutcome
                .RETRY_SCHEDULED
            ),
            digest_id=digest_id,
            item_count=len(
                rows
            ),
            deferred_count=(
                deferred_count
            ),
            attempt_count=attempt_count,
            subject=message.subject,
            error=error,
        )

    store.mark_digest_sent(
        digest_id=digest_id,
        subject=message.subject,
        item_count=len(
            rows
        ),
        attempt_count=attempt_count,
        attempted_at=normalized_now,
    )

    return DigestAttemptResult(
        outcome=DigestOutcome.SENT,
        digest_id=digest_id,
        item_count=len(
            rows
        ),
        deferred_count=deferred_count,
        attempt_count=attempt_count,
        subject=message.subject,
    )


def deliver_due_digest(
    session_factory: sessionmaker,
    transport: NotificationTransport,
    *,
    schedule: DigestWindowSchedule,
    recipient: str,
    now: datetime | None = None,
    max_jobs: int = DEFAULT_MAX_DIGEST_JOBS,
    max_attempts: int = (
        DEFAULT_MAX_ATTEMPTS
    ),
    retry_base_seconds: int = (
        DEFAULT_RETRY_BASE_SECONDS
    ),
    retry_max_seconds: int = (
        DEFAULT_RETRY_MAX_SECONDS
    ),
    logger: logging.Logger = LOGGER,
) -> DigestAttemptResult:
    """Run one digest delivery attempt inside one transaction."""

    reference_time = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    with session_factory.begin() as session:
        store = (
            SqlAlchemyDigestDeliveryStore(
                session
            )
        )

        result = deliver_digest_once(
            store,
            transport,
            now=reference_time,
            schedule=schedule,
            recipient=recipient,
            max_jobs=max_jobs,
            max_attempts=max_attempts,
            retry_base_seconds=(
                retry_base_seconds
            ),
            retry_max_seconds=(
                retry_max_seconds
            ),
        )

    logger.info(
        (
            "digest_attempt "
            "outcome=%s "
            "digest_id=%s "
            "items=%d "
            "deferred=%d "
            "attempt=%d"
        ),
        result.outcome.value,
        result.digest_id,
        result.item_count,
        result.deferred_count,
        result.attempt_count,
    )

    return result


@dataclass(
    frozen=True,
    slots=True,
)
class DigestPreview:
    """Read-only rehearsal of the digest a window would deliver."""

    window_label: str | None

    local_date: Any | None

    message: "NotificationMessage | None"

    item_count: int

    deferred_count: int


def preview_due_digest(
    session_factory: sessionmaker,
    *,
    schedule: DigestWindowSchedule,
    recipient: str,
    now: datetime | None = None,
    max_jobs: int = DEFAULT_MAX_DIGEST_JOBS,
) -> DigestPreview:
    """Render what the open window would deliver, changing nothing.

    No digest row is created, no candidate is assigned, and no retry
    attempt is consumed. Running a preview repeatedly is safe.
    """

    reference_time = (
        _require_aware_datetime(
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )
    )

    normalized_recipient = (
        recipient.strip()
    )

    if not normalized_recipient:
        raise ValueError(
            "recipient must not be empty."
        )

    if max_jobs < 1:
        raise ValueError(
            "max_jobs must be at least 1."
        )

    window = (
        schedule.resolve_active_window(
            now=reference_time
        )
    )

    with session_factory() as session:
        store = (
            SqlAlchemyDigestDeliveryStore(
                session
            )
        )

        rows = (
            store
            .load_unassigned_candidates(
                recipient=(
                    normalized_recipient
                ),
                now=reference_time,
                limit=max_jobs,
            )
        )

        total_available = (
            store
            .count_unassigned_candidates(
                recipient=(
                    normalized_recipient
                ),
                now=reference_time,
            )
        )

    deferred_count = max(
        0,
        total_available
        - len(rows),
    )

    if window is None or not rows:
        return DigestPreview(
            window_label=(
                None
                if window is None
                else window.display_label
            ),
            local_date=(
                None
                if window is None
                else window.local_date
            ),
            message=None,
            item_count=len(
                rows
            ),
            deferred_count=(
                deferred_count
            ),
        )

    message = render_digest(
        build_digest_items(
            rows
        ),
        window_label=(
            window.display_label
        ),
        reference_time=reference_time,
        timezone_name=(
            schedule.timezone_name
        ),
        deferred_count=deferred_count,
    )

    return DigestPreview(
        window_label=(
            window.display_label
        ),
        local_date=window.local_date,
        message=message,
        item_count=len(
            rows
        ),
        deferred_count=deferred_count,
    )
