"""Index the posting link the queue matches feed copies on.

The queue hides a feed's copy of a role ACE reads from the employer
directly. It matched on company and title only, and once TikTok,
ByteDance and fifteen Oracle employers were read directly, 183 feed
rows pointed at the very posting a direct row held, under a title the
feed had reworded -- every one shown twice. It now also matches on the
posting link, compared without case, scheme or "www.".

That is a correlated lookup on every queue load, like the one 0031
indexed. This indexes the exact expression the query compares, so the
planner can use it.

Revision ID: 0034
Revises: 0033
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0034"

down_revision: str | None = "0033"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_posting_link_key "
        "ON jobs (replace(replace(lower(official_url), "
        "'://www.', '://'), 'http://', 'https://'))"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_jobs_posting_link_key"
    )
