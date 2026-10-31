"""Real PostgreSQL isolation proof in an explicitly fictional CI database only."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import analytics_read, analytics_session
from backend.app.db.base import Base
from backend.app.db.models import (
    ApplicationEventRecord, GmailConnectionRecord, GmailMessageRecord, JobMarkRecord,
    UserRecord,
)
from backend.tests.test_analytics_read import app

NOW = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)


@pytest.fixture
def isolated_postgres():
    database_url = os.environ.get("ANALYTICS_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Fictional PostgreSQL CI service is not configured")
    url = make_url(database_url)
    # This test creates a private throwaway schema. It must never accept an
    # owner, legacy or production database supplied accidentally.
    if (url.host not in {"127.0.0.1", "localhost"} or url.database != "ace_analytics_test"
            or url.username != "fictional_ci"):
        pytest.fail("Snapshot test requires the dedicated localhost fictional CI database")
    engine = create_engine(database_url)
    schema = "analytics_test_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        yield isolated
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_committed_inbox_transaction_is_atomic_and_next_snapshot_is_current(isolated_postgres):
    with Session(isolated_postgres) as setup:
        setup.add(UserRecord(id=1, email="owner@example.test", password_hash="fictional",
                             created_at=NOW, password_changed_at=NOW))
        setup.flush()
        connection = GmailConnectionRecord(owner_id=1, email="mail@example.test",
            encrypted_refresh_token=b"fictional", scope="gmail.readonly", state="paused")
        setup.add(connection)
        setup.flush()
        connection_id = connection.id
        key = app(setup, 1)
        setup.commit()

    def read(session):
        return analytics_read(session, days="all", tz="America/Los_Angeles", now=NOW)

    with Session(isolated_postgres) as reader, Session(isolated_postgres) as writer:
        snapshot = analytics_session(reader)
        assert next(snapshot) is reader
        assert reader.execute(text("SHOW transaction_isolation")).scalar() == "repeatable read"
        assert reader.execute(text("SHOW transaction_read_only")).scalar() == "on"
        assert read(reader)["interviews"] == 0
        stamp = NOW - timedelta(hours=2)
        message = GmailMessageRecord(connection_id=connection_id, gmail_id="fictional-interview",
            received_at=stamp, sender="hiring@example.test", subject="Fictional interview",
            snippet="Fictional evidence", classification="interview", decision="automatic",
            decision_reason="Verified fictional interview", selected_application_key=key,
            candidate_keys=[key], parser_version="15")
        writer.add(message)
        writer.flush()
        writer.add(ApplicationEventRecord(application_key=key, kind="interview", actor="verified_automation",
            previous_status="applied", new_status="interviewing", occurred_at=stamp,
            gmail_message_id=message.id, reason="Fictional verified evidence", dedupe_key="fictional-atomic"))
        mark = writer.get(JobMarkRecord, int(key.split(":")[1]))
        mark.application_status = "interviewing"
        mark.status_changed_at = stamp
        writer.flush()
        assert read(reader)["classified_email_evidence"]["total"] == 0
        writer.commit()
        # The in-flight report retains its one snapshot even after commit.
        before = read(reader)
        assert before["classified_email_evidence"]["total"] == before["interviews"] == 0
        assert before["statuses"] == {"applied": 1}
        snapshot.close()
        reader.rollback()

    with Session(isolated_postgres) as next_request:
        snapshot = analytics_session(next_request)
        next(snapshot)
        current = read(next_request)
        assert current["classified_email_evidence"]["categories"]["interview"] == current["interviews"] == 1
        assert current["statuses"] == {"interviewing": 1}
        snapshot.close()
        next_request.rollback()


def test_analytics_snapshot_rejects_database_writes(isolated_postgres):
    with Session(isolated_postgres) as session:
        snapshot = analytics_session(session)
        next(snapshot)
        with pytest.raises(DBAPIError) as failure:
            session.execute(text("CREATE TABLE analytics_write_must_fail (id integer)"))
        assert getattr(failure.value.orig, "sqlstate", None) == "25006"
        snapshot.close()
        session.rollback()
