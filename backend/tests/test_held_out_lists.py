"""Test lists stay unread (REC-03).

ACE is scored against two job lists it never reads. If anything that finds
jobs ever reads one, the score measures ACE against its own inputs, so these
tests fail. Every company, board and job here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.adapters.simplify import FEED_URLS
from backend.app.coverage.benchmark import HELD_OUT_LISTS as BENCHMARK_LISTS
from backend.app.coverage.held_out import (
    HELD_OUT_HOSTS,
    HELD_OUT_LISTS,
    HELD_OUT_OWNERS,
    READING_LISTS,
    HeldOutListRead,
    held_out_rows,
    is_held_out,
)
from backend.app.coverage.host_policy import PoliteReader, read_targets
from backend.app.coverage.service import add_source
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobRecord, JobSourceRecord
from backend.app.discovery import providers
from backend.app.discovery.providers import DEFAULT_PUBLIC_DISCOVERY_FEEDS, DiscoveryFeed


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)

TEST_LIST_ADDRESSES = (
    "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md",
    "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md",
    "https://github.com/speedyapply/2028-SWE-College-Jobs",
    "https://raw.githubusercontent.com/vanshb03/New-Grad-2027/main/README.md",
    "https://github.com/VANSHB03/New-Grad-2026/blob/main/README.md",
    "https://api.github.com/repos/vanshb03/New-Grad-2027/contents/README.md",
    "https://go.vansh.nyc/1Ak?s=A",
    "go.vansh.nyc/1A4",
    "https://speedyapply.github.io/",
)

READING_ADDRESSES = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
    "https://github.com/speedyapplyx/lists",
    "https://job-boards.greenhouse.io/northwind/jobs/123",
    "https://vansh.nyc.example.com/jobs",
    "https://jobs.ashbyhq.com/lumora-pay",
    "",
    None,
)


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, class_=Session, expire_on_commit=False)() as session:
        yield session


@pytest.mark.parametrize("url", TEST_LIST_ADDRESSES)
def test_every_form_of_a_test_list_address_is_known(url) -> None:
    assert is_held_out(url)


@pytest.mark.parametrize("url", READING_ADDRESSES)
def test_other_addresses_are_not_test_lists(url) -> None:
    assert not is_held_out(url)


def test_the_two_sets_never_overlap() -> None:
    assert not READING_LISTS & HELD_OUT_OWNERS
    assert {item.key for item in HELD_OUT_LISTS} == {"speedyapply", "vanshb03"}
    for item in HELD_OUT_LISTS:
        assert is_held_out(item.url)
    assert [url for _, url in BENCHMARK_LISTS] == [item.url for item in HELD_OUT_LISTS]


def test_speedyapply_is_scored_on_its_new_grad_usa_file() -> None:
    """Its README now lists internships only."""

    speedy = next(item for item in HELD_OUT_LISTS if item.key == "speedyapply")
    assert speedy.url.endswith("/NEW_GRAD_USA.md")


def test_no_list_ace_reads_is_a_test_list() -> None:
    for url in FEED_URLS.values():
        assert not is_held_out(url), url
    for feed in DEFAULT_PUBLIC_DISCOVERY_FEEDS:
        assert not is_held_out(feed.url), feed.url
    for account in FEED_URLS:
        for target in read_targets("simplify", account):
            for path in target.paths:
                assert not is_held_out(f"https://{target.host}{path}")


def test_a_test_list_cannot_be_made_a_discovery_feed() -> None:
    with pytest.raises(ValueError, match="test list"):
        DiscoveryFeed(name="borrowed", url=TEST_LIST_ADDRESSES[0])


def test_the_feed_reader_refuses_a_test_list_before_any_request(monkeypatch) -> None:
    def no_request(*args, **kwargs):
        raise AssertionError("a request was sent")

    monkeypatch.setattr(providers.httpx, "get", no_request)
    with pytest.raises(HeldOutListRead):
        providers._fetch_public_text(TEST_LIST_ADDRESSES[3])


def test_the_polite_reader_never_reads_a_test_list() -> None:
    calls: list[str] = []

    reader = PoliteReader(
        fetch=lambda url, **kwargs: calls.append(url) or {"jobs": []},
        fetch_text=lambda url, **kwargs: calls.append(url) or "text",
        post=lambda url, payload, **kwargs: calls.append(url) or {},
        robots=lambda host: calls.append(host) or "",
        refuses=lambda url: calls.append(url) or True,
    )

    for url in TEST_LIST_ADDRESSES:
        assert reader.fetch(url) is None
        assert reader.fetch_text(url) == ""
        assert reader.post(url, {}) is None
        assert reader.refuses(url) is False
    assert calls == []

    assert reader.fetch_text("https://careers.northwind.example/jobs") == "text"
    assert calls


def test_a_pasted_short_link_is_never_followed(session) -> None:
    calls: list[str] = []

    def record(url, *args, **kwargs):
        calls.append(url)
        return None

    result = add_source(
        session,
        text="https://go.vansh.nyc/1Ak?s=A",
        fetch=record,
        fetch_text=lambda url, **kwargs: record(url) or "",
        post=lambda url, payload, **kwargs: record(url),
        robots=lambda host: record(host) or "",
        refuses=lambda url: bool(record(url)),
        fetch_robots=lambda host: record(host) or (404, ""),
        now=NOW,
    )

    assert not [url for url in calls if "vansh" in str(url)]
    assert result.status != "added"


def test_no_code_or_data_names_a_test_list() -> None:
    """Only ``held_out.py`` may name them, so nothing else can read them."""

    allowed = {ROOT / "backend/app/coverage/held_out.py"}
    markers = tuple(HELD_OUT_OWNERS | HELD_OUT_HOSTS)
    roots = ("backend/app", "backend/scripts", "extension", "web/src", "deploy", "scripts")
    suffixes = {".py", ".json", ".js", ".ts", ".tsx", ".yaml", ".yml", ".toml", ".sh", ".md", ".txt", ".csv"}

    found = []
    for name in roots:
        for path in (ROOT / name).rglob("*"):
            if not path.is_file() or path.suffix not in suffixes or path in allowed:
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            found.extend(f"{path.relative_to(ROOT)}: {marker}" for marker in markers if marker in text)

    assert found == []


def test_stored_rows_from_a_test_list_are_found(session) -> None:
    assert held_out_rows(session) == {"boards": 0, "jobs": 0, "leads": 0}

    session.add_all(
        [
            JobSourceRecord(
                source_type="greenhouse",
                source_account="northwind",
                company_name="Northwind Robotics",
                poll_interval_seconds=900,
            ),
            JobRecord(
                source="greenhouse",
                source_account="northwind",
                external_id="1",
                company="Northwind Robotics",
                title="Software Engineer, New Grad",
                location="Denver, CO",
                description="",
                official_url="https://job-boards.greenhouse.io/northwind/jobs/1",
                content_hash="a",
                first_seen_at=NOW,
                last_seen_at=NOW,
            ),
        ]
    )
    session.commit()
    assert held_out_rows(session) == {"boards": 0, "jobs": 0, "leads": 0}

    session.add_all(
        [
            JobRecord(
                source="simplify",
                source_account="new-grad",
                external_id="2",
                company="Lumora Pay",
                title="Software Engineer I",
                location="Austin, TX",
                description="",
                official_url="https://go.vansh.nyc/1Zz?s=A",
                content_hash="b",
                first_seen_at=NOW,
                last_seen_at=NOW,
            ),
            EmployerLead(
                company_key="lumora pay",
                company_name="Lumora Pay",
                origin="feed",
                origin_details=[{"list": "speedyapply/2027-SWE-College-Jobs"}],
                state="checking",
                reason="fictional",
                boards=[],
                first_seen_at=NOW,
                next_check_at=NOW,
            ),
        ]
    )
    session.commit()
    assert held_out_rows(session) == {"boards": 0, "jobs": 1, "leads": 1}
