"""Add application evidence, opt-in Gmail state and official company reports.

Revision ID: 0044
Revises: 0043

All tables are additive. No existing application or discovery row is rewritten.
Downgrade drops only the new tables and is intentionally a data-loss operation;
production rollback should restore the prior image and retain this migration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
payload_type = sa.JSON(none_as_null=True).with_variant(postgresql.JSONB(none_as_null=True), "postgresql")

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_connections",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.LargeBinary(), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="paused"),
        sa.Column("history_id", sa.String(80)),
        sa.Column("preview_baseline_history_id", sa.String(80)),
        sa.Column("preview_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(120)),
        sa.Column("auto_outcomes_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", name="uq_gmail_connections_owner"),
    )
    op.create_table(
        "gmail_messages",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("connection_id", id_type, sa.ForeignKey("gmail_connections.id"), nullable=False),
        sa.Column("gmail_id", sa.String(128), nullable=False),
        sa.Column("thread_id", sa.String(128)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sender", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("snippet", sa.String(500), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("requisition_id", sa.String(120)),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("candidate_keys", payload_type),
        sa.Column("decision_reason", sa.String(300), nullable=False),
        sa.Column("selected_application_key", sa.String(80)),
        sa.Column("parser_version", sa.String(24), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("connection_id", "gmail_id", name="uq_gmail_messages_identity"),
    )
    op.create_index("ix_gmail_messages_review", "gmail_messages", ["connection_id", "decision"])
    op.create_table(
        "application_events",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("application_key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("previous_status", sa.String(24)),
        sa.Column("new_status", sa.String(24)),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("gmail_message_id", id_type, sa.ForeignKey("gmail_messages.id")),
        sa.Column("undo_of_id", id_type, sa.ForeignKey("application_events.id")),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_application_events_dedupe"),
    )
    op.create_index("ix_application_events_target", "application_events", ["application_key", "recorded_at"])
    op.create_table(
        "company_petition_reports",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("ace_company", sa.String(255), nullable=False),
        sa.Column("legal_entity", sa.String(255), nullable=False),
        sa.Column("source_name", sa.String(120), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("metric_definition", sa.String(200), nullable=False),
        sa.Column("period", sa.String(60), nullable=False),
        sa.Column("report_version", sa.String(80), nullable=False),
        sa.Column("petition_approvals", sa.Integer()),
        sa.Column("petition_denials", sa.Integer()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("source_uri", "legal_entity", "period", "report_version", name="uq_company_petition_report"),
    )
    op.create_index("ix_company_petition_alias", "company_petition_reports", ["ace_company"])


def downgrade() -> None:
    op.drop_index("ix_company_petition_alias", table_name="company_petition_reports")
    op.drop_table("company_petition_reports")
    op.drop_index("ix_application_events_target", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_gmail_messages_review", table_name="gmail_messages")
    op.drop_table("gmail_messages")
    op.drop_table("gmail_connections")
