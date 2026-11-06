"""The ledger migration only adds, and can be taken back without touching anything else."""

from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_upgrade_adds_two_tables_and_downgrade_removes_only_them(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0051_lead_ledger_and_host_policies")
    assert migration.down_revision == "0050"

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE job_sources (id INTEGER PRIMARY KEY, company_name VARCHAR(255))"))
        connection.execute(sa.text("INSERT INTO job_sources VALUES (1, 'Fictional Works')"))

        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())
        assert {"employer_leads", "host_policies", "job_sources"} <= tables
        assert {index["name"] for index in inspector.get_indexes("employer_leads")} == {
            "ix_employer_leads_state",
            "ix_employer_leads_next_check_at",
        }

        # The state check refuses anything outside the ledger's vocabulary.
        connection.execute(
            sa.text(
                "INSERT INTO employer_leads (company_key, company_name, origin, origin_details, state, boards, next_check_at) "
                "VALUES ('fictional', 'Fictional', 'search', '[]', 'polling', '[]', '2026-11-05')"
            )
        )
        try:
            with connection.begin_nested():
                connection.execute(
                    sa.text(
                        "INSERT INTO employer_leads (company_key, company_name, origin, origin_details, state, boards, next_check_at) "
                        "VALUES ('other', 'Other', 'search', '[]', 'nonsense', '[]', '2026-11-05')"
                    )
                )
        except sa.exc.IntegrityError:
            pass
        else:
            raise AssertionError("the state check let an unknown state through")

        migration.downgrade()

        tables = set(sa.inspect(connection).get_table_names())
        assert "employer_leads" not in tables and "host_policies" not in tables
        assert connection.execute(sa.text("SELECT company_name FROM job_sources")).scalar_one() == "Fictional Works"
