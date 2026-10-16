"""Bind an optional Google OpenID Connect identity to the owner.

The column is nullable, so email and password sign-in remains unchanged
until Google is configured and the owner completes the first successful
Google sign-in.

Revision ID: 0041
Revises: 0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0041"

down_revision: str | None = "0040"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("google_subject", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_google_subject",
        "users",
        ["google_subject"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_google_subject", "users", type_="unique")
    op.drop_column("users", "google_subject")
