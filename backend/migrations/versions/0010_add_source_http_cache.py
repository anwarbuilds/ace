"""Remember HTTP validators per source so unchanged boards cost nothing.

Most boards are unchanged between polls. Sending back the validator a
board gave us last time lets it answer 304 Not Modified with no body at
all, which skips the download, the parse, and the whole diff.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010"

down_revision: str | None = "0009"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store the last ETag and Last-Modified seen for each source."""

    op.add_column(
        "source_states",
        sa.Column(
            "http_etag",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "source_states",
        sa.Column(
            "http_last_modified",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "source_states",
        sa.Column(
            "last_unchanged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the HTTP cache validators."""

    op.drop_column(
        "source_states",
        "last_unchanged_at",
    )

    op.drop_column(
        "source_states",
        "http_last_modified",
    )

    op.drop_column(
        "source_states",
        "http_etag",
    )
