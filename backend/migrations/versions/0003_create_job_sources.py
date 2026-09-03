"""Create persistent ACE job-source catalog.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"

down_revision: str | None = "0002"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the persistent external job-source catalog."""

    op.create_table(
        "job_sources",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "source_account",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "company_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "poll_interval_seconds",
            sa.Integer(),
            server_default=sa.text("300"),
            nullable=False,
        ),
        sa.Column(
            "discovery_source",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "first_discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "poll_interval_seconds > 0",
            name=(
                "ck_job_sources_"
                "poll_interval_positive"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_job_sources",
        ),
        sa.UniqueConstraint(
            "source_type",
            "source_account",
            name=(
                "uq_job_sources_"
                "source_identity"
            ),
        ),
    )

    op.create_index(
        "ix_job_sources_enabled",
        "job_sources",
        [
            "enabled",
            "source_type",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Remove the persistent source catalog."""

    op.drop_index(
        "ix_job_sources_enabled",
        table_name="job_sources",
    )

    op.drop_table(
        "job_sources"
    )