"""Database-backed tests for ACE digest delivery.

These exercise the real SQLAlchemy store rather than a fake, so the
durability claims (restart safety, exactly-once inclusion, recipient
isolation) are verified against actual SQL.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    NotificationDigestRecord,
    NotificationOutboxRecord,
)
from backend.app.notifications.digest_delivery import (
    DigestOutcome,
    SqlAlchemyDigestDeliveryStore,
    deliver_digest_once,
    preview_due_digest,
)
from backend.app.notifications.schedule import (
    DigestWindowSchedule,
    parse_digest_times,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


RECIPIENT = "user@example.com"

OTHER_RECIPIENT = "other@example.com"


SCHEDULE = DigestWindowSchedule(
    timezone_name="UTC",
    times=parse_digest_times(
        "08:00,18:00"
    ),
)


MORNING = datetime(
    2026,
    9,
    5,
    9,
    0,
    tzinfo=timezone.utc,
)


EVENING = datetime(
    2026,
    9,
    5,
    19,
    0,
    tzinfo=timezone.utc,
)


class RecordingTransport:
    """Transport that records digests and can be made to fail."""

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
        self.messages.append(
            (
                message,
                recipient,
            )
        )

        if self.error is not None:
            raise self.error


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    """Provide an isolated in-memory database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def add_candidate(
    session: Session,
    *,
    external_id: str,
    title: str = "Software Engineer",
    company: str = "Example Co",
    recipient: str = RECIPIENT,
    created_at: datetime | None = None,
) -> NotificationOutboxRecord:
    """Insert one PENDING outbox candidate."""

    timestamp = (
        created_at
        if created_at is not None
        else MORNING
        - timedelta(
            hours=1
        )
    )

    record = NotificationOutboxRecord(
        dedupe_key=(
            f"{recipient}-{external_id}"
        ),
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        observation_status="NEW",
        job_content_hash=(
            f"hash-{external_id}"
        ),
        source_updated_at=None,
        recipient=recipient,
        subject=(
            f"[ACE] NEW | PRIMARY | "
            f"{title} | {company}"
        ),
        text_body="legacy body",
        status="PENDING",
        attempt_count=0,
        next_attempt_at=timestamp,
        created_at=timestamp,
        payload={
            "version": 1,
            "title": title,
            "company": company,
            "location": "Remote (US)",
            "official_url": (
                "https://boards.example.com"
                f"/jobs/{external_id}"
            ),
            "observation_status": "NEW",
            "eligibility_status": "PASS",
            "role_family": (
                "SOFTWARE_ENGINEERING"
            ),
            "role_priority": "PRIMARY",
            "reasons": [
                "No hard eligibility "
                "blocker detected.",
            ],
            "posted_at": (
                "2026-09-04T12:00:00+00:00"
            ),
            "posting_age_days": 1,
        },
        digest_id=None,
    )

    session.add(
        record
    )

    session.flush()

    return record


def attempt(
    session_factory,
    transport,
    *,
    now: datetime = MORNING,
    recipient: str = RECIPIENT,
    max_jobs: int = 100,
    max_attempts: int = 5,
):
    """Run one digest attempt in its own transaction."""

    with session_factory.begin() as session:
        return deliver_digest_once(
            SqlAlchemyDigestDeliveryStore(
                session
            ),
            transport,
            now=now,
            schedule=SCHEDULE,
            recipient=recipient,
            max_jobs=max_jobs,
            max_attempts=max_attempts,
        )


def statuses(
    session_factory,
    *,
    recipient: str = RECIPIENT,
) -> list[str]:
    """Return outbox statuses for one recipient."""

    with session_factory() as session:
        return list(
            session.scalars(
                select(
                    NotificationOutboxRecord.status
                )
                .where(
                    NotificationOutboxRecord.recipient
                    == recipient
                )
                .order_by(
                    NotificationOutboxRecord.id
                )
            ).all()
        )


def test_successful_digest_marks_included_rows_sent(
    session_factory,
) -> None:
    """Delivery marks exactly the candidates it reported."""

    with session_factory.begin() as session:
        for index in range(
            1,
            4,
        ):
            add_candidate(
                session,
                external_id=str(
                    index
                ),
                title=f"Role {index}",
            )

    transport = RecordingTransport()

    result = attempt(
        session_factory,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.SENT
    )

    assert len(
        transport.messages
    ) == 1

    assert statuses(
        session_factory
    ) == [
        "SENT",
        "SENT",
        "SENT",
    ]

    with session_factory() as session:
        digest = session.scalars(
            select(
                NotificationDigestRecord
            )
        ).one()

        assert digest.status == "SENT"

        assert digest.item_count == 3

        assert digest.sent_at is not None


def test_worker_restart_does_not_resend_digest(
    session_factory,
) -> None:
    """The digest_key UNIQUE constraint survives a process restart."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
        )

    transport = RecordingTransport()

    assert (
        attempt(
            session_factory,
            transport,
        ).outcome
        is DigestOutcome.SENT
    )

    # Three further "restarts" inside the same window.
    for offset in (
        1,
        2,
        3,
    ):
        assert (
            attempt(
                session_factory,
                transport,
                now=MORNING
                + timedelta(
                    hours=offset
                ),
            ).outcome
            is DigestOutcome
            .ALREADY_DELIVERED
        )

    assert len(
        transport.messages
    ) == 1

    with session_factory() as session:
        assert (
            len(
                session.scalars(
                    select(
                        NotificationDigestRecord
                    )
                ).all()
            )
            == 1
        )


def test_two_windows_send_at_most_twice_per_day(
    session_factory,
) -> None:
    """A full simulated day yields exactly two emails."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
            title="Morning Role",
        )

    transport = RecordingTransport()

    # Poll every hour across the whole day.
    for hour in range(
        0,
        24,
    ):
        now = datetime(
            2026,
            9,
            5,
            hour,
            0,
            tzinfo=timezone.utc,
        )

        if hour == 12:
            with (
                session_factory.begin()
                as session
            ):
                add_candidate(
                    session,
                    external_id="2",
                    title="Afternoon Role",
                    created_at=now,
                )

        attempt(
            session_factory,
            transport,
            now=now,
        )

    assert len(
        transport.messages
    ) == 2

    morning_body = (
        transport.messages[0][
            0
        ].text_body
    )

    evening_body = (
        transport.messages[1][
            0
        ].text_body
    )

    assert (
        "Morning Role"
        in morning_body
    )

    assert (
        "Afternoon Role"
        not in morning_body
    )

    assert (
        "Afternoon Role"
        in evening_body
    )

    # No duplicate inclusion across successful digests.
    assert (
        "Morning Role"
        not in evening_body
    )


def test_empty_window_sends_nothing_and_stays_open(
    session_factory,
) -> None:
    """Zero qualifying jobs means zero email, without burning a window."""

    transport = RecordingTransport()

    result = attempt(
        session_factory,
        transport,
    )

    assert (
        result.outcome
        is DigestOutcome.NOTHING_TO_SEND
    )

    assert transport.messages == []

    with session_factory() as session:
        assert (
            session.scalars(
                select(
                    NotificationDigestRecord
                )
            ).all()
            == []
        )

    # A job arriving later in the same window can still be delivered.
    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
            created_at=MORNING
            + timedelta(
                minutes=30
            ),
        )

    assert (
        attempt(
            session_factory,
            transport,
            now=MORNING
            + timedelta(
                hours=1
            ),
        ).outcome
        is DigestOutcome.SENT
    )


def test_recipients_are_never_mixed(
    session_factory,
) -> None:
    """Each recipient gets their own digest containing only their jobs."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
            title="Mine",
            recipient=RECIPIENT,
        )

        add_candidate(
            session,
            external_id="2",
            title="Theirs",
            recipient=OTHER_RECIPIENT,
        )

    transport = RecordingTransport()

    attempt(
        session_factory,
        transport,
        recipient=RECIPIENT,
    )

    attempt(
        session_factory,
        transport,
        recipient=OTHER_RECIPIENT,
    )

    assert len(
        transport.messages
    ) == 2

    first_message, first_to = (
        transport.messages[0]
    )

    second_message, second_to = (
        transport.messages[1]
    )

    assert first_to == RECIPIENT

    assert (
        "Mine"
        in first_message.text_body
    )

    assert (
        "Theirs"
        not in first_message.text_body
    )

    assert (
        second_to == OTHER_RECIPIENT
    )

    assert (
        "Theirs"
        in second_message.text_body
    )

    assert (
        "Mine"
        not in second_message.text_body
    )


def test_failed_digest_keeps_rows_pending_then_recovers(
    session_factory,
) -> None:
    """An SMTP outage defers rather than loses opportunities."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
        )

    failing = RecordingTransport(
        error=RuntimeError(
            "smtp unavailable"
        )
    )

    result = attempt(
        session_factory,
        failing,
    )

    assert (
        result.outcome
        is DigestOutcome.RETRY_SCHEDULED
    )

    assert statuses(
        session_factory
    ) == [
        "PENDING",
    ]

    with session_factory() as session:
        digest = session.scalars(
            select(
                NotificationDigestRecord
            )
        ).one()

        assert digest.status == "PENDING"

        assert digest.attempt_count == 1

        assert (
            digest.last_error
            is not None
        )

    working = RecordingTransport()

    recovered = attempt(
        session_factory,
        working,
        now=MORNING
        + timedelta(
            hours=1
        ),
    )

    assert (
        recovered.outcome
        is DigestOutcome.SENT
    )

    assert statuses(
        session_factory
    ) == [
        "SENT",
    ]


def test_exhausted_digest_marks_rows_dead(
    session_factory,
) -> None:
    """A permanently broken transport ends in a visible state."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
        )

    failing = RecordingTransport(
        error=RuntimeError(
            "smtp broken"
        )
    )

    result = attempt(
        session_factory,
        failing,
        max_attempts=1,
    )

    assert (
        result.outcome
        is DigestOutcome.DEAD
    )

    assert statuses(
        session_factory
    ) == [
        "DEAD",
    ]

    with session_factory() as session:
        digest = session.scalars(
            select(
                NotificationDigestRecord
            )
        ).one()

        assert digest.status == "DEAD"


def test_size_limit_defers_remainder_to_next_window(
    session_factory,
) -> None:
    """An oversized backlog splits across windows instead of clipping."""

    with session_factory.begin() as session:
        for index in range(
            1,
            6,
        ):
            add_candidate(
                session,
                external_id=str(
                    index
                ),
                title=f"Role {index}",
            )

    transport = RecordingTransport()

    morning = attempt(
        session_factory,
        transport,
        max_jobs=2,
    )

    assert morning.item_count == 2

    assert morning.deferred_count == 3

    assert statuses(
        session_factory
    ) == [
        "SENT",
        "SENT",
        "PENDING",
        "PENDING",
        "PENDING",
    ]

    evening = attempt(
        session_factory,
        transport,
        now=EVENING,
        max_jobs=2,
    )

    assert evening.item_count == 2

    assert statuses(
        session_factory
    ) == [
        "SENT",
        "SENT",
        "SENT",
        "SENT",
        "PENDING",
    ]


def test_preview_changes_no_state(
    session_factory,
) -> None:
    """A dry run must be repeatable and side-effect free."""

    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
        )

    for _ in range(
        3,
    ):
        preview = preview_due_digest(
            session_factory,
            schedule=SCHEDULE,
            recipient=RECIPIENT,
            now=MORNING,
        )

        assert preview.item_count == 1

        assert (
            preview.message is not None
        )

    assert statuses(
        session_factory
    ) == [
        "PENDING",
    ]

    with session_factory() as session:
        assert (
            session.scalars(
                select(
                    NotificationDigestRecord
                )
            ).all()
            == []
        )

    # The real send still works afterwards.
    transport = RecordingTransport()

    assert (
        attempt(
            session_factory,
            transport,
        ).outcome
        is DigestOutcome.SENT
    )


def test_preview_outside_window_reports_no_message(
    session_factory,
) -> None:
    """Candidates waiting outside a window produce no rendered digest."""

    # Due well before 03:00, so the only thing holding it back is that
    # no delivery window is open.
    with session_factory.begin() as session:
        add_candidate(
            session,
            external_id="1",
            created_at=datetime(
                2026,
                9,
                5,
                1,
                0,
                tzinfo=timezone.utc,
            ),
        )

    preview = preview_due_digest(
        session_factory,
        schedule=SCHEDULE,
        recipient=RECIPIENT,
        now=datetime(
            2026,
            9,
            5,
            3,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert preview.message is None

    assert preview.window_label is None

    assert preview.item_count == 1
