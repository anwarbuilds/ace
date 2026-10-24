"""Add blank answers for distinct Verizon Workday questions.

Revision ID: 0048
Revises: 0047

The owner saves values in Answers. Existing values are preserved.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADDED_LABELS = (
    "Currently require employer visa sponsorship",
    "Authorized to work for any US employer",
    "Federal state or local government employment",
    "Agreement restricting work for employer",
    "Family or close personal relationship with employee here",
    "Family member on employer board",
    "Personally served in US military",
    "Spouse served in US military",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(bind.execute(sa.text("SELECT label FROM application_answers")).scalars())
    next_order = bind.execute(
        sa.text("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM application_answers")
    ).scalar_one()

    for label in ADDED_LABELS:
        if label in existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO application_answers (label, value, sort_order, updated_at) "
                "VALUES (:label, '', :sort_order, CURRENT_TIMESTAMP)"
            ),
            {"label": label, "sort_order": next_order},
        )
        next_order += 1


def downgrade() -> None:
    bind = op.get_bind()
    for label in ADDED_LABELS:
        bind.execute(
            sa.text("DELETE FROM application_answers WHERE label = :label AND value = ''"),
            {"label": label},
        )
