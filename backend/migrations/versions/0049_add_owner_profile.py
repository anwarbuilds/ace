"""Add owner profile fields and a verified email change target.

Revision ID: 0049
Revises: 0048

Existing owner data and sign-in credentials are preserved. Profile fields
start empty and can be completed from My Account.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(80), nullable=False, server_default=""))
    op.add_column("users", sa.Column("last_name", sa.String(80), nullable=False, server_default=""))
    op.add_column("users", sa.Column("phone_number", sa.String(32), nullable=False, server_default=""))
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_content_type", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_codes", sa.Column("target_email", sa.String(320), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_codes", "target_email")
    op.drop_column("users", "avatar_updated_at")
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_data")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
