"""Resume Studio: documents, the career knowledge base and its audit
trail, resume versions and checker assessments.

Purely additive. The existing resumes table keeps feeding the job list's
match scores; a primary version is copied into it when the owner makes
one primary.

Revision ID: 0039
Revises: 0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0039"

down_revision: str | None = "0038"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return postgresql.JSONB(none_as_null=True).with_variant(sa.JSON(none_as_null=True), "sqlite")


def _when(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _id() -> sa.Column:
    return sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True)


def _job() -> sa.Column:
    return sa.Column(
        "job_id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        sa.ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        "resume_documents",
        _id(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("parser", sa.String(24), nullable=False),
        sa.Column("report", _json(), nullable=True),
        _when("created_at"),
    )
    op.create_index("ix_resume_documents_sha256", "resume_documents", ["sha256"])

    op.create_table(
        "career_facts",
        _id(),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("bullets", _json(), nullable=True),
        sa.Column("skills", _json(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("resume_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        _when("created_at"),
        _when("updated_at"),
        sa.CheckConstraint(
            "status IN ('verified', 'suggested', 'deprecated', 'needs_clarification')",
            name="ck_career_facts_status",
        ),
    )
    op.create_index("ix_career_facts_kind_status", "career_facts", ["kind", "status"])

    op.create_table(
        "career_fact_events",
        _id(),
        sa.Column(
            "fact_id",
            sa.Integer(),
            sa.ForeignKey("career_facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=False),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("before", _json(), nullable=True),
        _when("at"),
    )
    op.create_index("ix_career_fact_events_fact_id", "career_fact_events", ["fact_id"])

    op.create_table(
        "resume_versions",
        _id(),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("resume_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("resume_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("resume_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        _job(),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        _when("created_at"),
        _when("approved_at", nullable=True),
    )

    op.create_table(
        "resume_assessments",
        _id(),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("resume_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _job(),
        sa.Column("job_source", sa.String(16), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("job_company", sa.String(255), nullable=False),
        sa.Column("job_text_hash", sa.String(64), nullable=False),
        sa.Column("job_text", sa.Text(), nullable=False),
        sa.Column("algorithm_version", sa.String(40), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("aggregate", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("result", _json(), nullable=False),
        _when("created_at"),
    )
    op.create_index("ix_resume_assessments_version", "resume_assessments", ["version_id", "created_at"])
    op.create_index("ix_resume_assessments_job", "resume_assessments", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_resume_assessments_job", table_name="resume_assessments")
    op.drop_index("ix_resume_assessments_version", table_name="resume_assessments")
    op.drop_table("resume_assessments")
    op.drop_table("resume_versions")
    op.drop_index("ix_career_fact_events_fact_id", table_name="career_fact_events")
    op.drop_table("career_fact_events")
    op.drop_index("ix_career_facts_kind_status", table_name="career_facts")
    op.drop_table("career_facts")
    op.drop_index("ix_resume_documents_sha256", table_name="resume_documents")
    op.drop_table("resume_documents")
