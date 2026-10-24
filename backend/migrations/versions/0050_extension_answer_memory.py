"""Add isolated, owner-approved extension answer memory.

Revision ID: 0050
Revises: 0049
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extension_answer_memory",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("concept", sa.String(180), nullable=False, unique=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(24), nullable=False),
        sa.Column("reuse_policy", sa.String(24), nullable=False, server_default="reusable"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_host", sa.String(255), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Export this table before downgrade. No legacy rows are touched.
    op.drop_table("extension_answer_memory")
