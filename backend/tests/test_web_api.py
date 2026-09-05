"""Tests for the ACE web read model.

The web application must never disagree with what ACE decided, and must
never invent an apply link.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.api.queries import (
    JobFilters,
    build_facets,
    build_stats,
    list_jobs,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)


NOW = datetime(
    2026,
    9,
    5,
    16,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    """Provide an isolated in-memory database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def add_job(
    session: Session,
    *,
    external_id: str,
    title: str = "Software Engineer",
    company: str = "Example Co",
    location: str = "Seattle, WA",
    status: str = "PASS",
    family: str = "SOFTWARE_ENGINEERING",
    priority: str = "PRIMARY",
    age_days: int | None = 2,
    is_active: bool = True,
    source: str = "greenhouse",
) -> JobRecord:
    """Insert one job plus its materialized evaluation."""

    posted_at = (
        None
        if age_days is None
        else NOW
        - timedelta(
            days=age_days
        )
    )

    job = JobRecord(
        source=source,
        source_account="example",
        external_id=external_id,
        company=company,
        requisition_id=None,
        title=title,
        location=location,
        description="Build software.",
        official_url=(
            "https://boards.example.com"
            f"/jobs/{external_id}"
        ),
        posted_at=posted_at,
        source_updated_at=None,
        content_hash=(
            f"hash-{external_id}"
        ),
        first_seen_at=NOW
        - timedelta(
            hours=int(
                external_id
            )
            if external_id.isdigit()
            else 1
        ),
        last_seen_at=NOW,
        is_active=is_active,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status=status,
            role_family=family,
            role_priority=priority,
            rule_version="test-v1",
            reason_codes=[
                "NO_HARD_BLOCKER",
            ],
            reasons=[
                "No hard eligibility "
                "blocker detected.",
            ],
            required_experience_years=None,
            content_hash=(
                f"hash-{external_id}"
            ),
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def test_defaults_return_only_qualifying_active_jobs(
    session_factory,
) -> None:
    """The default view is what ACE would actually alert about."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            status="PASS",
        )

        add_job(
            session,
            external_id="2",
            status="STRETCH",
        )

        add_job(
            session,
            external_id="3",
            status="REJECT",
        )

        add_job(
            session,
            external_id="4",
            status="PASS",
            is_active=False,
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        )

    assert page.total == 2

    assert {
        item.external_id
        for item in page.items
    } == {
        "1",
        "2",
    }


def test_rejected_jobs_are_reachable_when_asked(
    session_factory,
) -> None:
    """Nothing is deleted; the gate's rejects stay inspectable."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            status="REJECT",
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                statuses=(
                    "REJECT",
                )
            ),
            now=NOW,
        )

    assert page.total == 1


def test_closed_jobs_are_reachable_when_asked(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            is_active=False,
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                active_only=False
            ),
            now=NOW,
        )

    assert page.total == 1


def test_age_filter_excludes_unknown_posting_dates(
    session_factory,
) -> None:
    """An unknown posting date is never claimed to be recent."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=2,
        )

        add_job(
            session,
            external_id="2",
            age_days=None,
        )

        add_job(
            session,
            external_id="3",
            age_days=90,
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                max_age_days=7
            ),
            now=NOW,
        )

    assert page.total == 1

    assert (
        page.items[0].external_id
        == "1"
    )


def test_search_matches_title_company_and_location(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            title="Backend Engineer",
        )

        add_job(
            session,
            external_id="2",
            company="Databricks",
        )

        add_job(
            session,
            external_id="3",
            location="Austin, TX",
        )

    for term, expected in (
        (
            "backend",
            "1",
        ),
        (
            "databr",
            "2",
        ),
        (
            "austin",
            "3",
        ),
    ):
        with session_factory() as session:
            page = list_jobs(
                session,
                filters=JobFilters(
                    search=term
                ),
                now=NOW,
            )

        assert page.total == 1

        assert (
            page.items[0].external_id
            == expected
        )


def test_family_and_priority_filters(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            family="AI_ML_ENGINEERING",
        )

        add_job(
            session,
            external_id="2",
            family=(
                "FORWARD_DEPLOYED_"
                "ENGINEERING"
            ),
            priority="SECONDARY",
        )

    with session_factory() as session:
        assert (
            list_jobs(
                session,
                filters=JobFilters(
                    families=(
                        "AI_ML_ENGINEERING",
                    )
                ),
                now=NOW,
            ).total
            == 1
        )

        assert (
            list_jobs(
                session,
                filters=JobFilters(
                    priorities=(
                        "SECONDARY",
                    )
                ),
                now=NOW,
            ).total
            == 1
        )


def test_pagination_is_stable_and_complete(
    session_factory,
) -> None:
    """Paging must show every job exactly once."""

    with session_factory.begin() as session:
        for index in range(
            1,
            8,
        ):
            add_job(
                session,
                external_id=str(
                    index
                ),
                title=f"Role {index}",
            )

    seen: list[str] = []

    offset = 0

    while True:
        with session_factory() as session:
            page = list_jobs(
                session,
                filters=JobFilters(
                    limit=3,
                    offset=offset,
                ),
                now=NOW,
            )

        seen.extend(
            item.external_id
            for item in page.items
        )

        if not page.has_more:
            break

        offset += 3

    assert sorted(
        seen
    ) == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
    ]

    assert len(
        seen
    ) == len(
        set(
            seen
        )
    )


def test_recently_posted_sort_puts_unknown_dates_last(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=None,
        )

        add_job(
            session,
            external_id="2",
            age_days=1,
        )

        add_job(
            session,
            external_id="3",
            age_days=20,
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                sort="recently_posted"
            ),
            now=NOW,
        )

    assert [
        item.external_id
        for item in page.items
    ] == [
        "2",
        "3",
        "1",
    ]


def test_listing_exposes_official_url_and_age(
    session_factory,
) -> None:
    """The apply link is the employer's own posting."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=3,
        )

    with session_factory() as session:
        item = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        ).items[0]

    assert item.official_url == (
        "https://boards.example.com"
        "/jobs/1"
    )

    assert item.posting_age_days == 3

    assert item.reasons


def test_limit_is_capped(
    session_factory,
) -> None:
    """A hostile limit cannot ask for the whole corpus."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
        )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                limit=100000
            ),
            now=NOW,
        )

    assert page.limit <= 200


def test_stats_report_qualifying_and_fresh_counts(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=2,
        )

        add_job(
            session,
            external_id="2",
            age_days=40,
        )

        add_job(
            session,
            external_id="3",
            status="REJECT",
        )

    with session_factory() as session:
        stats = build_stats(
            session,
            now=NOW,
        )

    assert stats["total_jobs"] == 3

    assert (
        stats["qualifying_active_jobs"]
        == 2
    )

    assert (
        stats["posted_last_7_days"] == 1
    )

    assert (
        stats["by_eligibility"]["PASS"]
        == 2
    )

    assert (
        stats["by_eligibility"]["REJECT"]
        == 1
    )


def test_facets_only_offer_qualifying_options(
    session_factory,
) -> None:
    """Filter options describe the qualifying corpus, not the rejects."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            company="Alpha",
        )

        add_job(
            session,
            external_id="2",
            company="Beta",
            status="REJECT",
        )

    with session_factory() as session:
        facets = build_facets(
            session
        )

    companies = {
        entry["value"]
        for entry in facets["companies"]
    }

    assert companies == {
        "Alpha",
    }

    assert facets["sorts"]

    assert facets["statuses"]


def test_empty_database_is_handled(
    session_factory,
) -> None:
    """A fresh install must not error before the first poll."""

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        )

        stats = build_stats(
            session,
            now=NOW,
        )

    assert page.total == 0

    assert page.items == ()

    assert stats["total_jobs"] == 0
