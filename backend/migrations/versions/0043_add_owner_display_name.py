"""Store the owner's workspace display name.

The field is additive and starts blank for an existing owner. The account
settings page or a later verified Google sign-in can populate it without
changing authentication credentials or product data.

Revision ID: 0043
Revises: 0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0043"

down_revision: str | None = "0042"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "display_name",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
