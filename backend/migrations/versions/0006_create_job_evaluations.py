"""Materialize job eligibility decisions for the ACE web application.

Eligibility is a pure function of a job's normalized content. Caching it
lets the web application filter and sort in SQL rather than re-running
the gate across every stored job on each request.

This table is derived data and can be rebuilt at any time with:

    python -m backend.scripts.backfill_job_evaluations --apply

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006"

down_revision: str | None = "0005"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the materialized job-evaluation table."""

    op.create_table(
        "job_evaluations",
        sa.Column(
            "job_id",
            sa.BigInteger(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "eligibility_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "role_family",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "role_priority",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "rule_version",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "reason_codes",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "reasons",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "required_experience_years",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "job_id",
            name="pk_job_evaluations",
        ),
        sa.ForeignKeyConstraint(
            [
                "job_id",
            ],
            [
                "jobs.id",
            ],
            name="fk_job_evaluations_job_id",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_job_evaluations_status",
        "job_evaluations",
        [
            "eligibility_status",
        ],
    )

    op.create_index(
        (
            "ix_job_evaluations_"
            "family_priority"
        ),
        "job_evaluations",
        [
            "role_family",
            "role_priority",
        ],
    )


def downgrade() -> None:
    """Drop the materialized job-evaluation table."""

    op.drop_index(
        (
            "ix_job_evaluations_"
            "family_priority"
        ),
        table_name="job_evaluations",
    )

    op.drop_index(
        "ix_job_evaluations_status",
        table_name="job_evaluations",
    )

    op.drop_table(
        "job_evaluations"
    )
