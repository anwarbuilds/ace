"""The system endpoint tells the truth about delivery and freshness."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import (
    PollSessionRecord,
    SourceState,
)


NOW = datetime.now(
    timezone.utc
)


@pytest.fixture(name="client")
def fixture_client(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override

    with factory.begin() as session:
        session.add_all(
            [
                PollSessionRecord(
                    started_at=NOW - timedelta(hours=2),
                    last_activity_at=NOW - timedelta(hours=2),
                    notified_at=NOW - timedelta(hours=1),
                    alert_status="unconfigured",
                ),
                SourceState(
                    source="greenhouse",
                    source_account="example",
                    initialized_at=NOW - timedelta(days=1),
                    last_success_at=NOW - timedelta(hours=3),
                    last_job_count=1,
                ),
            ]
        )

    yield TestClient(app)

    get_settings.cache_clear()


def test_an_unconfigured_provider_is_reported_as_such(client) -> None:
    body = client.get("/api/system").json()

    assert body["alerts"]["provider_configured"] is False
    assert body["alerts"]["last_sent_at"] is None
    assert body["alerts"]["last_7_days"] == {"unconfigured": 1}


def test_a_scheduler_silent_for_hours_is_stale(client) -> None:
    body = client.get("/api/system").json()

    assert body["scheduler"]["stale"] is True
    assert body["scheduler"]["last_poll_at"] is not None


def test_versions_are_reported(client) -> None:
    body = client.get("/api/system").json()

    assert body["versions"]["gate"]
    assert body["versions"]["matching"]
    assert body["scoring"] == {"resume_active": False, "queue_jobs": 0, "queue_unscored": 0}


def test_the_export_holds_everything_entered_by_hand(client) -> None:
    from backend.app.api.deps import get_session as dep

    override = client.app.dependency_overrides[dep]
    session = next(override())

    from backend.app.db.models import (
        ApplicationAnswerRecord,
        JobMarkRecord,
        JobRecord,
    )

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id="1",
        company="Example Co",
        title="Software Engineer",
        location="Seattle, WA",
        description="",
        official_url="https://boards.example.com/1",
        content_hash="h",
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=True,
    )
    session.add(job)
    session.flush()
    session.add(JobMarkRecord(job_id=job.id, is_saved=False, applied_at=NOW, application_status="screening", status_note="call booked", updated_at=NOW))
    session.add(ApplicationAnswerRecord(label="First name", value="Alex", sort_order=0, updated_at=NOW))
    session.commit()

    response = client.get("/api/export.json")
    body = response.json()

    assert "attachment" in response.headers["content-disposition"]
    assert body["format"] == "ace-owner-export/1"
    assert body["marks"][0]["application_status"] == "screening"
    assert body["marks"][0]["status_note"] == "call booked"
    assert body["marks"][0]["job"]["official_url"] == "https://boards.example.com/1"
    assert body["answers"] == [{"label": "First name", "value": "Alex"}]
