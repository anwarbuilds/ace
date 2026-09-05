"""Create digest delivery for ACE notifications.

Adds the notification_digests table, links outbox rows to a digest, and
stores structured alert payloads so a digest can be rendered without
re-reading the jobs table.

Also extends the outbox status domain with SUPPRESSED, a terminal,
auditable state used when a pending candidate is retired by policy
rather than delivered.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005"

down_revision: str | None = "0004"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create digest grouping for durable notification delivery."""

    op.create_table(
        "notification_digests",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "digest_key",
            sa.String(length=400),
            nullable=False,
        ),
        sa.Column(
            "recipient",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "window_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "window_label",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "window_opens_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "item_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_notification_digests",
        ),
        sa.UniqueConstraint(
            "digest_key",
            name=(
                "uq_notification_digests_"
                "digest_key"
            ),
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('PENDING', 'SENT', 'DEAD')"
            ),
            name=(
                "ck_notification_digests_"
                "status"
            ),
        ),
        sa.CheckConstraint(
            "item_count >= 0",
            name=(
                "ck_notification_digests_"
                "item_count_non_negative"
            ),
        ),
    )

    op.create_index(
        (
            "ix_notification_digests_"
            "status_next_attempt"
        ),
        "notification_digests",
        [
            "status",
            "next_attempt_at",
        ],
    )

    op.create_index(
        (
            "ix_notification_digests_"
            "recipient_window"
        ),
        "notification_digests",
        [
            "recipient",
            "window_date",
        ],
    )

    op.add_column(
        "notification_outbox",
        sa.Column(
            "payload",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "notification_outbox",
        sa.Column(
            "digest_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        (
            "fk_notification_outbox_"
            "digest_id"
        ),
        "notification_outbox",
        "notification_digests",
        [
            "digest_id",
        ],
        [
            "id",
        ],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_notification_outbox_digest",
        "notification_outbox",
        [
            "digest_id",
        ],
    )

    op.create_index(
        "ix_notification_outbox_claimable",
        "notification_outbox",
        [
            "recipient",
            "status",
            "digest_id",
            "next_attempt_at",
        ],
    )

    # Widen the outbox status domain so policy retirement is auditable
    # instead of destructive.
    op.drop_constraint(
        "ck_notification_outbox_status",
        "notification_outbox",
        type_="check",
    )

    op.create_check_constraint(
        "ck_notification_outbox_status",
        "notification_outbox",
        (
            "status IN "
            "('PENDING', 'SENT', "
            "'DEAD', 'SUPPRESSED')"
        ),
    )


def downgrade() -> None:
    """Remove digest delivery structures."""

    op.execute(
        (
            "UPDATE notification_outbox "
            "SET status = 'DEAD' "
            "WHERE status = 'SUPPRESSED'"
        )
    )

    op.drop_constraint(
        "ck_notification_outbox_status",
        "notification_outbox",
        type_="check",
    )

    op.create_check_constraint(
        "ck_notification_outbox_status",
        "notification_outbox",
        (
            "status IN "
            "('PENDING', 'SENT', 'DEAD')"
        ),
    )

    op.drop_index(
        "ix_notification_outbox_claimable",
        table_name="notification_outbox",
    )

    op.drop_index(
        "ix_notification_outbox_digest",
        table_name="notification_outbox",
    )

    op.drop_constraint(
        (
            "fk_notification_outbox_"
            "digest_id"
        ),
        "notification_outbox",
        type_="foreignkey",
    )

    op.drop_column(
        "notification_outbox",
        "digest_id",
    )

    op.drop_column(
        "notification_outbox",
        "payload",
    )

    op.drop_index(
        (
            "ix_notification_digests_"
            "recipient_window"
        ),
        table_name="notification_digests",
    )

    op.drop_index(
        (
            "ix_notification_digests_"
            "status_next_attempt"
        ),
        table_name="notification_digests",
    )

    op.drop_table(
        "notification_digests"
    )
