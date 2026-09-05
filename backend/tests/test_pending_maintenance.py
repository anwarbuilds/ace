"""Tests for safe retirement of the ACE pending notification backlog.

The backlog must be reclassified, never blindly drained and never
blindly deleted.
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
    JobRecord,
    NotificationOutboxRecord,
)
from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.scripts.manage_pending_notifications import (
    backfill_payloads,
    classify_pending_candidates,
    requeue_dead_candidates,
    suppress_candidates,
)


NOW = datetime(
    2026,
    9,
    5,
    16,
    0,
    tzinfo=timezone.utc,
)


POLICY = FreshnessPolicy(
    max_posting_age_days=30
)


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


def add_backlog_row(
    session: Session,
    *,
    external_id: str,
    age_days: float | None,
    status: str = "PENDING",
    observation_status: str = "NEW",
    with_job: bool = True,
    with_payload: bool = False,
) -> None:
    """Insert one outbox row and its corresponding job record."""

    posted_at = (
        None
        if age_days is None
        else NOW
        - timedelta(
            days=age_days
        )
    )

    if with_job:
        session.add(
            JobRecord(
                source="greenhouse",
                source_account="example",
                external_id=external_id,
                company="Example Co",
                requisition_id=None,
                title=(
                    "Software Engineer "
                    f"{external_id}"
                ),
                location="Seattle, WA",
                description=(
                    "Build reliable "
                    "software systems."
                ),
                official_url=(
                    "https://boards.example.com"
                    f"/jobs/{external_id}"
                ),
                posted_at=posted_at,
                source_updated_at=None,
                content_hash=(
                    f"hash-{external_id}"
                ),
                first_seen_at=NOW,
                last_seen_at=NOW,
                is_active=True,
            )
        )

    session.add(
        NotificationOutboxRecord(
            dedupe_key=(
                f"key-{external_id}"
            ),
            source="greenhouse",
            source_account="example",
            external_id=external_id,
            observation_status=(
                observation_status
            ),
            job_content_hash=(
                f"hash-{external_id}"
            ),
            source_updated_at=None,
            recipient="user@example.com",
            subject=(
                "[ACE] NEW | PRIMARY | "
                "Software Engineer "
                f"{external_id} | Example Co"
            ),
            text_body="legacy body",
            status=status,
            attempt_count=0,
            next_attempt_at=NOW,
            created_at=NOW,
            payload=(
                {
                    "version": 1,
                    "title": "Existing",
                }
                if with_payload
                else None
            ),
            digest_id=None,
        )
    )

    session.flush()


def test_classification_splits_fresh_from_historical(
    session_factory,
) -> None:
    """The 30-day policy separates real openings from the backlog."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="fresh",
            age_days=3,
        )

        add_backlog_row(
            session,
            external_id="boundary",
            age_days=30,
        )

        add_backlog_row(
            session,
            external_id="old",
            age_days=336,
        )

        add_backlog_row(
            session,
            external_id="ancient",
            age_days=478,
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    assert report.total == 4

    retained_ids = {
        entry.title
        for entry in report.retained
    }

    assert retained_ids == {
        "Software Engineer fresh",
        "Software Engineer boundary",
    }

    assert (
        len(report.suppressed) == 2
    )

    ages = sorted(
        entry.posting_age_days
        for entry in report.suppressed
    )

    assert ages == [
        336,
        478,
    ]


def test_unknown_posting_age_is_suppressed_by_default(
    session_factory,
) -> None:
    """Backlog rows of unknown age are treated conservatively."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="unknown",
            age_days=None,
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    assert len(report.suppressed) == 1

    assert (
        report.suppressed[0].reason
        == "UNKNOWN_POSTING_AGE"
    )


def test_classification_is_read_only(
    session_factory,
) -> None:
    """A dry run must never change outbox state."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="old",
            age_days=400,
        )

    with session_factory() as session:
        classify_pending_candidates(
            session,
            policy=POLICY,
            now=NOW,
        )

    with session_factory() as session:
        assert (
            session.scalars(
                select(
                    NotificationOutboxRecord.status
                )
            ).all()
            == [
                "PENDING",
            ]
        )


def test_sent_and_dead_rows_are_never_classified(
    session_factory,
) -> None:
    """Delivered history is out of scope for the cleanup."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="sent",
            age_days=400,
            status="SENT",
        )

        add_backlog_row(
            session,
            external_id="dead",
            age_days=400,
            status="DEAD",
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    assert report.total == 0


def test_suppression_preserves_rows_and_history(
    session_factory,
) -> None:
    """Stale candidates are retired, not deleted."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="fresh",
            age_days=2,
        )

        add_backlog_row(
            session,
            external_id="old",
            age_days=400,
        )

        add_backlog_row(
            session,
            external_id="sent",
            age_days=400,
            status="SENT",
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    with session_factory.begin() as session:
        suppressed = (
            suppress_candidates(
                session,
                outbox_ids=[
                    entry.outbox_id
                    for entry
                    in report.suppressed
                ],
                now=NOW,
                reason="stale backlog",
            )
        )

    assert suppressed == 1

    with session_factory() as session:
        rows = {
            row.external_id: row.status
            for row in session.scalars(
                select(
                    NotificationOutboxRecord
                )
            ).all()
        }

        # Nothing was deleted.
        assert len(rows) == 3

        assert (
            rows["old"] == "SUPPRESSED"
        )

        assert (
            rows["fresh"] == "PENDING"
        )

        assert rows["sent"] == "SENT"

        # Jobs are untouched.
        assert (
            len(
                session.scalars(
                    select(
                        JobRecord
                    )
                ).all()
            )
            == 3
        )


def test_suppression_only_affects_listed_rows(
    session_factory,
) -> None:
    """The apply step acts strictly on the reported set."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="a",
            age_days=400,
        )

        add_backlog_row(
            session,
            external_id="b",
            age_days=400,
        )

    with session_factory.begin() as session:
        target = session.scalars(
            select(
                NotificationOutboxRecord
            ).where(
                NotificationOutboxRecord.external_id
                == "a"
            )
        ).one()

        suppress_candidates(
            session,
            outbox_ids=[
                target.id,
            ],
            now=NOW,
            reason="stale",
        )

    with session_factory() as session:
        rows = {
            row.external_id: row.status
            for row in session.scalars(
                select(
                    NotificationOutboxRecord
                )
            ).all()
        }

    assert rows == {
        "a": "SUPPRESSED",
        "b": "PENDING",
    }


def test_empty_suppression_list_is_a_no_op(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        assert (
            suppress_candidates(
                session,
                outbox_ids=[],
                now=NOW,
                reason="none",
            )
            == 0
        )


def test_retained_legacy_rows_get_structured_payloads(
    session_factory,
) -> None:
    """Backfilling restores full digest detail for old rows."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="fresh",
            age_days=2,
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    with session_factory.begin() as session:
        updated = backfill_payloads(
            session,
            outbox_ids=[
                entry.outbox_id
                for entry
                in report.retained
            ],
        )

    assert updated == 1

    with session_factory() as session:
        row = session.scalars(
            select(
                NotificationOutboxRecord
            )
        ).one()

        assert row.payload is not None

        assert (
            row.payload["title"]
            == "Software Engineer fresh"
        )

        assert (
            row.payload["official_url"]
            == (
                "https://boards.example.com"
                "/jobs/fresh"
            )
        )

        assert (
            row.payload["location"]
            == "Seattle, WA"
        )


def test_backfill_does_not_overwrite_existing_payloads(
    session_factory,
) -> None:
    """Rows written by the current pipeline are left alone."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="fresh",
            age_days=2,
            with_payload=True,
        )

    with session_factory() as session:
        report = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

    with session_factory.begin() as session:
        updated = backfill_payloads(
            session,
            outbox_ids=[
                entry.outbox_id
                for entry
                in report.retained
            ],
        )

    assert updated == 0

    with session_factory() as session:
        row = session.scalars(
            select(
                NotificationOutboxRecord
            )
        ).one()

        assert (
            row.payload["title"]
            == "Existing"
        )


def test_requeue_dead_restores_candidates(
    session_factory,
) -> None:
    """A resolved outage can return abandoned candidates to the queue."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="dead",
            age_days=2,
            status="DEAD",
        )

        add_backlog_row(
            session,
            external_id="sent",
            age_days=2,
            status="SENT",
        )

    with session_factory.begin() as session:
        requeued = (
            requeue_dead_candidates(
                session,
                now=NOW,
            )
        )

    assert requeued == 1

    with session_factory() as session:
        rows = {
            row.external_id: row.status
            for row in session.scalars(
                select(
                    NotificationOutboxRecord
                )
            ).all()
        }

    assert rows == {
        "dead": "PENDING",
        "sent": "SENT",
    }


def test_threshold_override_changes_classification(
    session_factory,
) -> None:
    """A wider policy retains more of the backlog."""

    with session_factory.begin() as session:
        add_backlog_row(
            session,
            external_id="mid",
            age_days=45,
        )

    with session_factory() as session:
        strict = (
            classify_pending_candidates(
                session,
                policy=POLICY,
                now=NOW,
            )
        )

        relaxed = (
            classify_pending_candidates(
                session,
                policy=FreshnessPolicy(
                    max_posting_age_days=60
                ),
                now=NOW,
            )
        )

    assert len(strict.suppressed) == 1

    assert len(relaxed.retained) == 1
