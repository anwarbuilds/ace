"""Persistent SQLAlchemy models for ACE.

These classes represent durable database records rather than external
ATS payloads.

CanonicalJob is the normalized application-domain representation.
JobRecord is the durable PostgreSQL representation of a discovered job.
NotificationOutboxRecord stores delivery work until external transports
successfully complete.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.app.db.base import Base


class JobRecord(Base):
    """Persistent representation of a job discovered by ACE."""

    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_account",
            "external_id",
            name="uq_jobs_source_identity",
        ),
        Index(
            "ix_jobs_first_seen_at",
            "first_seen_at",
        ),
        Index(
            "ix_jobs_company",
            "company",
        ),
        Index(
            "ix_jobs_is_active",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    requisition_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    location: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    official_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class SourceState(Base):
    """Persistent state for one external ATS source account."""

    __tablename__ = "source_states"

    source: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    initialized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_success_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_job_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )


class NotificationOutboxRecord(Base):
    """Durable notification awaiting external delivery.

    The outbox separates committed ACE state from unreliable external
    systems such as SMTP.

    Delivery failures therefore cannot cause ACE to permanently lose a
    qualifying job alert.
    """

    __tablename__ = "notification_outbox"

    __table_args__ = (
        UniqueConstraint(
            "dedupe_key",
            name=(
                "uq_notification_outbox_"
                "dedupe_key"
            ),
        ),
        CheckConstraint(
            (
                "status IN "
                "('PENDING', 'SENT', 'DEAD')"
            ),
            name=(
                "ck_notification_outbox_"
                "status"
            ),
        ),
        Index(
            (
                "ix_notification_outbox_"
                "status_next_attempt"
            ),
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    dedupe_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    observation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    job_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recipient: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    text_body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )