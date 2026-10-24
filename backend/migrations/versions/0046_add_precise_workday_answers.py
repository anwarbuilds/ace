"""Add blank answers for Workday screening questions.

Revision ID: 0046
Revises: 0045

The owner supplies values in Answers. Existing answers and history are kept.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADDED_LABELS = (
    "Work authorization through spouse visa",
    "Eligible for bilateral visa classification",
    "Currently on F-1 student visa",
    "Maximum OPT or CPT authorization end date",
    "Big Four employment in prior 18 months",
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
    # Keep any value the owner entered, even in a local rollback.
    bind = op.get_bind()
    for label in ADDED_LABELS:
        bind.execute(
            sa.text("DELETE FROM application_answers WHERE label = :label AND value = ''"),
            {"label": label},
        )
