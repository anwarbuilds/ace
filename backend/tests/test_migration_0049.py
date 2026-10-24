"""The owner profile migration must leave the existing login intact."""

from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_owner_profile_upgrade_preserves_existing_identity(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0049_add_owner_profile")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(320), "
            "display_name VARCHAR(120), password_hash TEXT)"
        ))
        connection.execute(sa.text(
            "CREATE TABLE auth_codes (id INTEGER PRIMARY KEY, purpose VARCHAR(20))"
        ))
        connection.execute(sa.text(
            "INSERT INTO users VALUES (1, 'owner@example.com', 'Alex Rivera', 'hashed-password')"
        ))
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()
        row = connection.execute(sa.text(
            "SELECT email, display_name, password_hash, first_name, last_name, phone_number "
            "FROM users WHERE id = 1"
        )).one()
        assert row == ("owner@example.com", "Alex Rivera", "hashed-password", "", "", "")
        assert {
            column["name"] for column in sa.inspect(connection).get_columns("users")
        } >= {"avatar_data", "avatar_content_type", "avatar_updated_at"}
        assert "target_email" in {
            column["name"] for column in sa.inspect(connection).get_columns("auth_codes")
        }
