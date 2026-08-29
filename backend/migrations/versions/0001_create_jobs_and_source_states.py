"""Create jobs and source-state tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial ACE persistence schema."""

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
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
            "company",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "requisition_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "location",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "official_url",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_jobs",
        ),
        sa.UniqueConstraint(
            "source",
            "source_account",
            "external_id",
            name="uq_jobs_source_identity",
        ),
    )

    op.create_index(
        "ix_jobs_first_seen_at",
        "jobs",
        ["first_seen_at"],
        unique=False,
    )

    op.create_index(
        "ix_jobs_company",
        "jobs",
        ["company"],
        unique=False,
    )

    op.create_index(
        "ix_jobs_is_active",
        "jobs",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "source_states",
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
            "initialized_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_success_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_job_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "source",
            "source_account",
            name="pk_source_states",
        ),
    )


def downgrade() -> None:
    """Remove the initial ACE persistence schema."""

    op.drop_table(
        "source_states",
    )

    op.drop_index(
        "ix_jobs_is_active",
        table_name="jobs",
    )

    op.drop_index(
        "ix_jobs_company",
        table_name="jobs",
    )

    op.drop_index(
        "ix_jobs_first_seen_at",
        table_name="jobs",
    )

    op.drop_table(
        "jobs",
    )