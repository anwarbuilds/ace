"""Career Dashboard skill demand: the newest passing postings in the window."""

from datetime import timedelta

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
from backend.app.db.models import JobRecord
from backend.tests.test_web_api import add_job


@pytest.fixture(name="client")
def fixture_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    with factory.begin() as session:
        def posting(external_id, description, *, status="PASS", family="SOFTWARE_ENGINEERING", days_ago=1):
            job = add_job(session, external_id=external_id, status=status, family=family)
            job.description = description
            job.first_seen_at = job.first_seen_at - timedelta(days=days_ago)

        posting("1", "Python and Kafka services")
        posting("2", "Python with Kubernetes")
        posting("3", "Go and Rust", family="MACHINE_LEARNING")
        # Rejected, or older than the window: never counted.
        posting("4", "Python and Terraform", status="REJECT")
        posting("5", "Python and Snowflake", days_ago=40)
        session.flush()
        assert session.query(JobRecord).count() == 5

    get_settings.cache_clear()

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    get_settings.cache_clear()


def demand(client, **params) -> dict[str, int]:
    body = client.get("/api/intelligence", params=params).json()
    return {item["skill"]: item["count"] for item in body["observed_skill_demand"]["items"]}


def test_counts_skills_of_passing_postings_inside_the_window(client) -> None:
    found = demand(client, days=30)

    assert found["python"] == 2
    assert found["kafka"] == 1
    assert found["kubernetes"] == 1
    assert "terraform" not in found
    assert "snowflake" not in found


def test_family_narrows_the_postings_read(client) -> None:
    found = demand(client, days=30, family="MACHINE_LEARNING")

    assert "python" not in found
    assert set(found) <= {"go", "rust"}
