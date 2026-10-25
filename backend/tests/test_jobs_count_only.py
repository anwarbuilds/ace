"""The "new since your last visit" badge reads a count, never a page."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.api.queries import JobFilters, count_jobs, list_jobs
from backend.app.auth.guard import require_auth
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.tests.test_web_api import NOW, add_job


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory.begin() as session:
        add_job(session, external_id="1")
        add_job(session, external_id="5")
        add_job(session, external_id="30")
        add_job(session, external_id="2", status="REJECT")
    return factory


@pytest.mark.parametrize("hours", [2, 10, 48])
def test_count_equals_the_listed_total(factory, hours) -> None:
    filters = JobFilters(since=NOW - timedelta(hours=hours))
    with factory() as session:
        assert count_jobs(session, filters=filters, now=NOW) == list_jobs(session, filters=filters, now=NOW).total


def test_route_returns_the_total_without_rows(factory) -> None:
    get_settings.cache_clear()

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[require_auth] = lambda: None
    client = TestClient(app)
    since = (NOW - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    counted = client.get("/api/jobs", params={"since": since, "count_only": "true"}).json()
    listed = client.get("/api/jobs", params={"since": since}).json()

    assert counted["items"] == []
    assert counted["total"] == listed["total"] == 2
    get_settings.cache_clear()
