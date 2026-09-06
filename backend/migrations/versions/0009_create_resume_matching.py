"""Store an uploaded resume and its per-job match scores.

Scores are derived data: they can be rebuilt from the resume and the job
corpus, which is what makes re-scoring after a resume edit cheap.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009"

down_revision: str | None = "0008"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create resume storage and per-job scores."""

    op.create_table(
        "resumes",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "label",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "filename",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "raw_text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "extracted_skills",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_resumes",
        ),
    )

    op.create_index(
        "ix_resumes_active",
        "resumes",
        [
            "is_active",
        ],
    )

    op.create_table(
        "job_resume_scores",
        sa.Column(
            "job_id",
            sa.BigInteger(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "resume_id",
            sa.BigInteger(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "matched_skills",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "missing_skills",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=True,
        ),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "job_id",
            "resume_id",
            name="pk_job_resume_scores",
        ),
        sa.ForeignKeyConstraint(
            [
                "job_id",
            ],
            [
                "jobs.id",
            ],
            name="fk_job_resume_scores_job",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "resume_id",
            ],
            [
                "resumes.id",
            ],
            name=(
                "fk_job_resume_scores_resume"
            ),
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_job_resume_scores_resume",
        "job_resume_scores",
        [
            "resume_id",
            "score",
        ],
    )


def downgrade() -> None:
    """Remove resume storage and scores."""

    op.drop_index(
        "ix_job_resume_scores_resume",
        table_name="job_resume_scores",
    )

    op.drop_table(
        "job_resume_scores"
    )

    op.drop_index(
        "ix_resumes_active",
        table_name="resumes",
    )

    op.drop_table(
        "resumes"
    )
