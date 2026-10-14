"""Owner sign-in: users, browser sessions, extension tokens, one-time
codes and a record of attempts for throttling.

Purely additive. No existing table changes, so the old UI and the
scheduler are unaffected by the upgrade itself; what changes behaviour
is ACE_AUTH (see backend/app/config.py).

Revision ID: 0038
Revises: 0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0038"

down_revision: str | None = "0037"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def _when(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
    )


def _user() -> sa.Column:
    return sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _when("created_at"),
        _when("password_changed_at"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        _user(),
        _when("created_at"),
        _when("last_seen_at"),
        _when("expires_at"),
        _when("revoked_at", nullable=True),
        sa.Column("user_agent", sa.String(length=200), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        _user(),
        _when("created_at"),
        _when("last_used_at", nullable=True),
        _when("revoked_at", nullable=True),
    )
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])

    op.create_table(
        "auth_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        _user(),
        _when("created_at"),
        _when("expires_at"),
        _when("used_at", nullable=True),
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=400), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        _when("attempted_at"),
    )
    op.create_index(
        "ix_login_attempts_key_at",
        "login_attempts",
        ["key", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_key_at", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_table("auth_codes")
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
