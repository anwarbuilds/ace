"""Add accounts, sessions, and an owner for hand-entered data.

ACE ran as a single-user system on one laptop, where "who does this
belong to" had one possible answer and no column was needed. Deploying
it changes that, and not because other people are expected to sign in:
a public URL means an unauthenticated request can reach the same rows,
and the answer bank alone holds a home address, phone number, and
gender, race, veteran and disability answers.

The knowledge base recorded this before the work started -- auth is
required from day one of deployment rather than bolted on afterwards --
so ownership lands with the accounts rather than in a later migration.

owner_id is nullable here only because the column is being added to
tables that already hold rows. The bootstrap script claims every
existing row for the first account created, and nothing writes a NULL
afterwards.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OWNED_TABLES = (
    "resumes",
    "job_marks",
    "external_applications",
    "application_answers",
    "history_entries",
)


def upgrade() -> None:
    """Create the account tables and add ownership."""

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
    )

    op.create_table(
        "auth_sessions",
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
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_auth_sessions_user",
        "auth_sessions",
        ["user_id"],
    )

    op.create_index(
        "ix_auth_sessions_expires",
        "auth_sessions",
        ["expires_at"],
    )

    for table in OWNED_TABLES:
        op.add_column(
            table,
            sa.Column(
                "owner_id",
                sa.BigInteger(),
                sa.ForeignKey(
                    "users.id",
                    ondelete="CASCADE",
                ),
                nullable=True,
            ),
        )

        op.create_index(
            f"ix_{table}_owner",
            table,
            ["owner_id"],
        )


def downgrade() -> None:
    """Remove ownership and the account tables."""

    for table in OWNED_TABLES:
        op.drop_index(
            f"ix_{table}_owner",
            table_name=table,
        )

        op.drop_column(
            table,
            "owner_id",
        )

    op.drop_index(
        "ix_auth_sessions_expires",
        table_name="auth_sessions",
    )

    op.drop_index(
        "ix_auth_sessions_user",
        table_name="auth_sessions",
    )

    op.drop_table(
        "auth_sessions",
    )

    op.drop_table(
        "users",
    )
