from importlib import import_module


def test_display_name_migration_adds_a_safe_existing_owner_default(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0043_add_owner_display_name")
    added: list[tuple[str, str, bool, str | None]] = []

    def capture(table, column) -> None:
        added.append((table, column.name, column.nullable, column.server_default.arg))

    monkeypatch.setattr(migration.op, "add_column", capture)
    migration.upgrade()

    assert added == [("users", "display_name", False, "")]
