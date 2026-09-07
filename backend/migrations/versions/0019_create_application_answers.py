"""Store the answers every application form asks for.

Applying is not slow because the postings are hard to find. It is slow
because every form asks the same fifteen questions: work authorisation,
sponsorship, earliest start, links, school, salary expectation. Typing
those out four times a day is the actual cost.

Free-form label and value rather than fixed columns, because no schema
survives contact with real application forms. The user adds whatever
they are actually asked for.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0019"

down_revision: str | None = "0018"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


SEED_LABELS = (
    "Full name",
    "Email",
    "Phone",
    "Location",
    "LinkedIn",
    "GitHub",
    "Portfolio",
    "Work authorisation",
    "Need sponsorship now",
    "Need sponsorship in future",
    "Earliest start date",
    "University",
    "Degree",
    "Graduation date",
    "Salary expectation",
    "Why this company",
)


def upgrade() -> None:
    """Create the answer bank and seed the usual questions."""

    table = op.create_table(
        "application_answers",
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
            "label",
            sa.String(
                length=120,
            ),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seeded with labels and no values. The questions are predictable;
    # the answers are the user's and must never be invented for them.
    op.bulk_insert(
        table,
        [
            {
                "label": label,
                "value": "",
                "sort_order": index,
            }
            for index, label in enumerate(
                SEED_LABELS
            )
        ],
    )


def downgrade() -> None:
    """Drop the answer bank. Hand-entered and not recoverable."""

    op.drop_table(
        "application_answers",
    )
