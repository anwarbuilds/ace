from importlib import import_module

import sqlalchemy as sa

from backend.app.answers.catalogue import BOOLEAN, TEXT, question_for


def test_meijer_answers_are_blank_and_saved_values_survive(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0047_add_meijer_workday_answers")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE application_answers ("
            "id INTEGER PRIMARY KEY, label VARCHAR(120), value TEXT, "
            "sort_order INTEGER, updated_at DATETIME)"
        ))
        conn.execute(sa.text(
            "INSERT INTO application_answers (label, value, sort_order, updated_at) "
            "VALUES ('Need sponsorship in future', 'Yes', 2, CURRENT_TIMESTAMP), "
            "('Consent to recruiting text messages', 'Saved answer', 3, CURRENT_TIMESTAMP)"
        ))
        monkeypatch.setattr(migration.op, "get_bind", lambda: conn)

        migration.upgrade()
        migration.upgrade()
        rows = conn.execute(sa.text(
            "SELECT label, value FROM application_answers ORDER BY sort_order"
        )).all()

        assert len(rows) == len(migration.ADDED_LABELS) + 1
        assert ("Need sponsorship in future", "Yes") in rows
        assert ("Consent to recruiting text messages", "Saved answer") in rows
        assert all(value == "" for label, value in rows if label not in {
            "Need sponsorship in future", "Consent to recruiting text messages"
        })
        text_labels = {
            "Current visa or sponsorship description",
            "Years building AI features on Azure",
            "AI coding assistance tools used",
        }
        for label in migration.ADDED_LABELS:
            assert question_for(label).kind == (TEXT if label in text_labels else BOOLEAN)

        migration.downgrade()
        kept = conn.execute(sa.text("SELECT label, value FROM application_answers")).all()
        assert set(kept) == {
            ("Need sponsorship in future", "Yes"),
            ("Consent to recruiting text messages", "Saved answer"),
        }
