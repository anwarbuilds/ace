from importlib import import_module


def test_repair_adds_only_missing_pull_telemetry(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0042_repair_pull_check_telemetry")
    added: list[tuple[str, str, bool]] = []

    class Inspector:
        def get_columns(self, table: str) -> list[dict[str, str]]:
            assert table == "poll_sessions"
            return [{"name": "id"}, {"name": "sources_attempted"}]

    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column.name, column.nullable)),
    )

    migration.upgrade()

    assert added == [
        ("poll_sessions", "poll_attempts", True),
        ("poll_sessions", "failed_checks", True),
    ]


def test_repair_is_a_noop_when_telemetry_is_present(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0042_repair_pull_check_telemetry")

    class Inspector:
        def get_columns(self, table: str) -> list[dict[str, str]]:
            assert table == "poll_sessions"
            return [{"name": name} for name in ("id", *migration.COLUMNS)]

    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda _table, _column: (_ for _ in ()).throw(AssertionError("unexpected column")),
    )

    migration.upgrade()
