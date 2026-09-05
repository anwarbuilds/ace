"""Persistent SQLAlchemy models for ACE.

These classes represent durable database records rather than external
ATS payloads.

CanonicalJob is the normalized application-domain representation.
JobRecord is the durable PostgreSQL representation of a discovered job.
JobSourceRecord describes an external ATS account ACE should monitor.
NotificationOutboxRecord stores delivery work until external transports
successfully complete.

NotificationDigestRecord groups many outbox rows into one delivered
email so ACE reports opportunities as a digest rather than a firehose.

JobEvaluationRecord materializes the deterministic eligibility decision
for one job so the web application can filter and sort in SQL instead of
re-running the gate over every stored job on every request.
"""

from datetime import (
    date,
    datetime,
)
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy.types import JSON

from backend.app.db.base import Base


# PostgreSQL should use BIGINT for durable identifiers.
#
# SQLite only provides implicit autoincrement semantics for a column whose
# declared type is exactly INTEGER PRIMARY KEY. The variant therefore keeps
# production PostgreSQL BIGINT behavior while allowing lightweight SQLite
# repository tests to exercise normal inserts without supplying fake IDs.
BIGINT_ID = BigInteger().with_variant(
    Integer(),
    "sqlite",
)


# PostgreSQL stores structured notification payloads as JSONB.
#
# SQLite has no JSONB type, so repository-level tests fall back to the
# generic JSON type while production keeps JSONB indexing behavior.
#
# none_as_null is required. Without it SQLAlchemy stores a Python None
# as the JSON value 'null' rather than SQL NULL, which would make
# "payload IS NULL" silently match nothing and hide rows that still need
# a structured payload.
JSON_PAYLOAD = JSONB(
    none_as_null=True
).with_variant(
    JSON(
        none_as_null=True
    ),
    "sqlite",
)


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
        BIGINT_ID,
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


class JobSourceRecord(Base):
    """Persistent external job source monitored by ACE.

    Company name is descriptive provenance metadata.

    Source identity is:

        source_type + source_account

    Company identity must never determine job eligibility.
    """

    __tablename__ = "job_sources"

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_account",
            name=(
                "uq_job_sources_"
                "source_identity"
            ),
        ),
        CheckConstraint(
            "poll_interval_seconds > 0",
            name=(
                "ck_job_sources_"
                "poll_interval_positive"
            ),
        ),
        Index(
            "ix_job_sources_enabled",
            "enabled",
            "source_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_host: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="300",
    )

    discovery_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
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
                "('PENDING', 'SENT', "
                "'DEAD', 'SUPPRESSED')"
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
        Index(
            (
                "ix_notification_outbox_"
                "digest"
            ),
            "digest_id",
        ),
        Index(
            (
                "ix_notification_outbox_"
                "claimable"
            ),
            "recipient",
            "status",
            "digest_id",
            "next_attempt_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
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

    # Structured alert content captured at enqueue time.
    #
    # The digest renderer reads this instead of re-reading the jobs
    # table, so a delivered digest always reflects exactly what ACE
    # evaluated, even if the posting is edited afterwards.
    #
    # Rows created before digest delivery existed have no payload and
    # are rendered from their legacy columns instead.
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    # Set when this candidate has been assigned to a digest.
    #
    # Assignment is what prevents the same opportunity appearing in two
    # successfully delivered digests.
    digest_id: Mapped[int | None] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "notification_digests.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


class NotificationDigestRecord(Base):
    """One digest email grouping many alert candidates.

    A digest is uniquely identified by its window:

        local date + window index + recipient

    That UNIQUE constraint is what makes digest delivery restart-safe.
    A worker that restarts mid-day cannot resend a digest whose window
    has already been delivered, because inserting the same digest_key a
    second time is rejected by PostgreSQL.
    """

    __tablename__ = "notification_digests"

    __table_args__ = (
        UniqueConstraint(
            "digest_key",
            name=(
                "uq_notification_digests_"
                "digest_key"
            ),
        ),
        CheckConstraint(
            (
                "status IN "
                "('PENDING', 'SENT', 'DEAD')"
            ),
            name=(
                "ck_notification_digests_"
                "status"
            ),
        ),
        CheckConstraint(
            "item_count >= 0",
            name=(
                "ck_notification_digests_"
                "item_count_non_negative"
            ),
        ),
        Index(
            (
                "ix_notification_digests_"
                "status_next_attempt"
            ),
            "status",
            "next_attempt_at",
        ),
        Index(
            (
                "ix_notification_digests_"
                "recipient_window"
            ),
            "recipient",
            "window_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    digest_key: Mapped[str] = mapped_column(
        String(400),
        nullable=False,
    )

    recipient: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    window_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    window_label: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    window_opens_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
    )

    item_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    subject: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

class JobEvaluationRecord(Base):
    """Materialized eligibility decision for one persisted job.

    Eligibility is a pure function of a job's normalized content, so the
    decision is cached rather than recomputed per request.

    ``content_hash`` records exactly which version of the job was
    evaluated, and ``rule_version`` records which gate produced it.
    Together they make a stale evaluation detectable instead of silently
    wrong after the job changes or the rules do.

    This table is derived data. It can be dropped and rebuilt from the
    jobs table at any time, which is why eligibility deliberately does
    not live on JobRecord itself.
    """

    __tablename__ = "job_evaluations"

    __table_args__ = (
        Index(
            (
                "ix_job_evaluations_"
                "status"
            ),
            "eligibility_status",
        ),
        Index(
            (
                "ix_job_evaluations_"
                "family_priority"
            ),
            "role_family",
            "role_priority",
        ),
    )

    job_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "jobs.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
    )

    eligibility_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    role_family: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    role_priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    rule_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reason_codes: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    reasons: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    required_experience_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
