"""Add the employer lead ledger and host verdicts.

Revision ID: 0051
Revises: 0050

Additive only: two new tables, and no existing row or column is touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employer_leads",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("company_key", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("origin_details", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("boards", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_key", name="uq_employer_leads_company_key"),
        sa.CheckConstraint(
            "state IN ('polling', 'waiting', 'checking', 'dormant', 'noreader', 'refused', 'agency')",
            name="ck_employer_leads_state",
        ),
    )
    op.create_index("ix_employer_leads_state", "employer_leads", ["state"])
    op.create_index("ix_employer_leads_next_check_at", "employer_leads", ["next_check_at"])

    op.create_table(
        "host_policies",
        sa.Column("host", sa.String(255), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("robots_verdict", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("robots_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("robots_status", sa.Integer(), nullable=True),
        sa.Column("paths", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "robots_verdict IN ('unknown', 'allowed', 'refused')",
            name="ck_host_policies_robots_verdict",
        ),
    )
    op.create_index("ix_host_policies_next_check_at", "host_policies", ["next_check_at"])


def downgrade() -> None:
    # Both tables are rebuilt by the next maintenance run; nothing else
    # reads them, and no other table is touched.
    op.drop_index("ix_host_policies_next_check_at", table_name="host_policies")
    op.drop_table("host_policies")
    op.drop_index("ix_employer_leads_next_check_at", table_name="employer_leads")
    op.drop_index("ix_employer_leads_state", table_name="employer_leads")
    op.drop_table("employer_leads")
