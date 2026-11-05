"""The Coverage page reads the ledger and the host verdicts through these routes."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.auth.guard import EXTENSION_PATHS, require_auth
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, HostPolicyRecord


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


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
        session.add(
            EmployerLead(
                company_key="fictional works",
                company_name="Fictional Works",
                origin="network",
                origin_details=["network"],
                state="waiting",
                reason="Ashby board reads. Waiting for your approval.",
                boards=[],
                first_seen_at=NOW,
                next_check_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            HostPolicyRecord(
                host="closed.wd5.myworkdayjobs.example",
                platform="workday",
                paths=["/wday/cxs/closed/External/jobs"],
                robots_verdict="refused",
                robots_detail="Robots file disallows /wday/.",
                next_check_at=NOW,
                first_seen_at=NOW,
                updated_at=NOW,
            )
        )

    get_settings.cache_clear()

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    get_settings.cache_clear()


def test_the_ledger_route_lists_filters_and_limits(client) -> None:
    body = client.get("/api/coverage/leads").json()
    assert body["total"] == 1
    assert body["rows"][0]["company"] == "Fictional Works"
    assert body["rows"][0]["state_label"] == "Waiting for you"

    assert client.get("/api/coverage/leads", params={"state": "polling"}).json()["rows"] == []
    assert client.get("/api/coverage/leads", params={"q": "works"}).json()["matched"] == 1
    assert client.get("/api/coverage/leads", params={"limit": 0}).status_code == 422
    assert client.get("/api/coverage/leads", params={"limit": 500}).status_code == 422


def test_an_unknown_state_filter_is_ignored_not_an_error(client) -> None:
    assert client.get("/api/coverage/leads", params={"state": "nonsense"}).json()["matched"] == 1


def test_the_hosts_route_reports_verdicts_and_says_it_is_not_enforcing(client) -> None:
    body = client.get("/api/coverage/hosts").json()
    assert body["enforcing"] is False
    assert body["refused"] == 1
    assert body["refused_hosts"][0]["host"] == "closed.wd5.myworkdayjobs.example"
    assert body["groups"][0]["label"] == "Workday"
    assert body["groups"][0]["terms"]["verdict"] == "restricted"


def test_a_stolen_extension_token_cannot_read_either_route() -> None:
    assert "/api/coverage/leads" not in EXTENSION_PATHS
    assert "/api/coverage/hosts" not in EXTENSION_PATHS
