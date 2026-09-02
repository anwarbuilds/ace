"""Create durable notification outbox.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"

down_revision: str | None = "0001"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable ACE notification outbox."""

    op.create_table(
        "notification_outbox",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "dedupe_key",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "source_account",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "external_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "observation_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "job_content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "recipient",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "text_body",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text(
                "'PENDING'"
            ),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('PENDING', 'SENT', 'DEAD')"
            ),
            name=(
                "ck_notification_outbox_"
                "status"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=(
                "pk_notification_outbox"
            ),
        ),
        sa.UniqueConstraint(
            "dedupe_key",
            name=(
                "uq_notification_outbox_"
                "dedupe_key"
            ),
        ),
    )

    op.create_index(
        (
            "ix_notification_outbox_"
            "status_next_attempt"
        ),
        "notification_outbox",
        [
            "status",
            "next_attempt_at",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove the durable notification outbox."""

    op.drop_index(
        (
            "ix_notification_outbox_"
            "status_next_attempt"
        ),
        table_name=(
            "notification_outbox"
        ),
    )

    op.drop_table(
        "notification_outbox"
    )