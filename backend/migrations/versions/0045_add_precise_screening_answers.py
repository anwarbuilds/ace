"""Add blank answers for distinct screening questions.

Revision ID: 0045
Revises: 0044

Existing answers are never changed. The owner supplies each value in the
Answers editor. Named employers and narrower government questions must not
inherit a similar answer from another row.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADDED_LABELS = (
    "Citizen or permanent resident of restricted regions",
    "Federal government employment in last 5 years",
    "Federal government conflict with employer",
    "Government employment in last 5 years",
    "Immediate family government employment in last 5 years",
    "Government contract suspension or debarment",
    "Previously employed by ServiceNow",
    "Previously employed by PwC",
    "ServiceNow RiseUp graduate",
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
    # Keep any answer the owner has filled, even if this migration is
    # reversed in a local rehearsal. Production rollback retains schema.
    bind = op.get_bind()
    for label in ADDED_LABELS:
        bind.execute(
            sa.text("DELETE FROM application_answers WHERE label = :label AND value = ''"),
            {"label": label},
        )
