"""Applications sent before ACE started watching, and when that was.

The Applications page reads the start date from this route so it needs
no queue statistics, which took longer than everything else on the page.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.auth.guard import require_auth
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import ExternalApplicationRecord, JobRecord


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@pytest.fixture(name="client")
def fixture_client(factory):
    get_settings.cache_clear()

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    get_settings.cache_clear()


def _job(external_id: str, first_seen: datetime) -> JobRecord:
    return JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example Co",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build software.",
        official_url=f"https://boards.example.com/jobs/{external_id}",
        posted_at=first_seen,
        source_updated_at=None,
        content_hash=f"hash-{external_id}",
        first_seen_at=first_seen,
        last_seen_at=first_seen,
        is_active=True,
    )


def test_no_postings_means_no_start_date(client) -> None:
    body = client.get("/api/applications/external").json()

    assert body == {"corpus_started_at": None, "items": [], "total": 0}


def test_start_date_is_the_first_posting_ace_saw(client, factory) -> None:
    with factory.begin() as session:
        session.add(_job("2", datetime(2026, 9, 5, 12, tzinfo=timezone.utc)))
        session.add(_job("1", datetime(2026, 9, 1, 12, tzinfo=timezone.utc)))
        session.add(
            ExternalApplicationRecord(
                company="Fictional Labs",
                title="Software Engineer",
                match_key="fictional labs|software engineer",
                applied_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
                application_status="applied",
            )
        )

    body = client.get("/api/applications/external").json()

    assert body["corpus_started_at"] == "2026-09-01T12:00:00+00:00"
    assert body["total"] == 1
    assert body["items"][0]["company"] == "Fictional Labs"
