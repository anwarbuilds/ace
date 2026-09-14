"""Store outstanding password-reset links.

Single use and short lived, and the token is never stored: only its
SHA-256, so a stolen database cannot be turned into account takeovers.

Rows survive being used rather than being deleted, so a link clicked
twice can say "already used" instead of "invalid". Mail clients
prefetch links, so the second click is a normal thing to happen.

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the table and its indexes."""

    op.create_table(
        "password_resets",
        sa.Column(
            "token_fingerprint",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_password_resets_user",
        "password_resets",
        ["user_id"],
    )

    op.create_index(
        "ix_password_resets_expires",
        "password_resets",
        ["expires_at"],
    )


def downgrade() -> None:
    """Drop it."""

    op.drop_index(
        "ix_password_resets_expires",
        table_name="password_resets",
    )

    op.drop_index(
        "ix_password_resets_user",
        table_name="password_resets",
    )

    op.drop_table(
        "password_resets",
    )
