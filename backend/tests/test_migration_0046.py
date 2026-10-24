from importlib import import_module

import sqlalchemy as sa

from backend.app.answers.catalogue import BOOLEAN, TEXT, question_for


def test_workday_answers_are_blank_and_existing_answers_survive(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0046_add_precise_workday_answers")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE application_answers ("
            "id INTEGER PRIMARY KEY, label VARCHAR(120), value TEXT, "
            "sort_order INTEGER, updated_at DATETIME)"
        ))
        conn.execute(sa.text(
            "INSERT INTO application_answers (label, value, sort_order, updated_at) "
            "VALUES ('Work authorisation', 'Yes', 2, CURRENT_TIMESTAMP), "
            "('Currently on F-1 student visa', 'Saved answer', 3, CURRENT_TIMESTAMP)"
        ))
        monkeypatch.setattr(migration.op, "get_bind", lambda: conn)

        migration.upgrade()
        migration.upgrade()
        rows = conn.execute(sa.text(
            "SELECT label, value FROM application_answers ORDER BY sort_order"
        )).all()

        assert len(rows) == len(migration.ADDED_LABELS) + 1
        assert ("Work authorisation", "Yes") in rows
        assert ("Currently on F-1 student visa", "Saved answer") in rows
        assert all(value == "" for label, value in rows if label not in {
            "Work authorisation", "Currently on F-1 student visa"
        })
        for label in migration.ADDED_LABELS:
            expected = TEXT if label == "Maximum OPT or CPT authorization end date" else BOOLEAN
            assert question_for(label).kind == expected

        migration.downgrade()
        kept = conn.execute(sa.text("SELECT label, value FROM application_answers")).all()
        assert set(kept) == {
            ("Work authorisation", "Yes"),
            ("Currently on F-1 student visa", "Saved answer"),
        }
