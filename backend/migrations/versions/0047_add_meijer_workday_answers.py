"""Add blank answers for distinct Meijer Workday questions.

Revision ID: 0047
Revises: 0046

Values are supplied by the owner in Answers, never inferred from screenshots.
Existing answers are preserved.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADDED_LABELS = (
    "Currently on OPT student visa",
    "Current visa or sponsorship description",
    "Previously contracted with Meijer group",
    "Previously worked for Meijer or Fresh Thyme",
    "Discussed Meijer opportunities with recruiters",
    "Current contractor at Meijer or another client",
    "Consent to recruiting text messages",
    "AI-assisted engineering tools experience",
    "Years building AI features on Azure",
    "AI coding assistance tools used",
    "Live in Meijer six-state footprint",
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
