"""Record applications to postings ACE never saw.

ACE's corpus begins on the day it started watching. An application sent
before that, to a posting that closed before ACE first polled, can never
be matched to a stored job because there is no stored job. The user
applied to roughly 74 roles; 27 were still open when ACE started and so
could be linked. The rest are real applications with nothing to attach
them to.

Leaving them out would make the Applied page a record of "what ACE
happened to witness" rather than "where you applied", which is the
wrong thing for it to be.

Identity is the normalised company and title, so re-importing an updated
sheet moves an existing row forward instead of duplicating it. That is
the same guarantee the job-linked path already gives.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018"

down_revision: str | None = "0017"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the standalone application table."""

    op.create_table(
        "external_applications",
        sa.Column(
            "id",
            sa.BigInteger()
            .with_variant(
                sa.Integer(),
                "sqlite",
            ),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "company",
            sa.String(
                length=255,
            ),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(
                length=500,
            ),
            nullable=False,
        ),
        # The identity used for de-duplication. Stored rather than
        # computed so the unique constraint can enforce it.
        sa.Column(
            "match_key",
            sa.String(
                length=600,
            ),
            nullable=False,
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "application_status",
            sa.String(
                length=24,
            ),
            nullable=True,
        ),
        sa.Column(
            "status_changed_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "url",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "match_key",
            name=(
                "uq_external_applications_"
                "match_key"
            ),
        ),
    )

    op.create_index(
        "ix_external_applications_status",
        "external_applications",
        [
            "application_status",
        ],
    )


def downgrade() -> None:
    """Drop the table.

    Destructive: these rows exist precisely because they cannot be
    rebuilt from anything ACE polls.
    """

    op.drop_index(
        "ix_external_applications_status",
        table_name="external_applications",
    )

    op.drop_table(
        "external_applications",
    )
