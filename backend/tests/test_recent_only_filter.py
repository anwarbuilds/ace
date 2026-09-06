"""Tests for the default Queue housekeeping filter.

The feature is a hide, not a delete: a posting past the window still
exists, still counts in statistics, and stays reachable once the filter
is lifted. Every test here is really checking one of those three
guarantees, because the risk with a feature named after "removing" old
jobs is that it quietly becomes destructive.
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
    7,
    12,
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
    detected_days_ago: int,
    posted_at=None,
) -> JobRecord:
    """Insert one qualifying job detected a given number of days ago.

    ``posted_at`` defaults to unset, on purpose: the filter must key on
    detection time, which every posting has, not the publish date many
    sources omit or misreport.
    """

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company="Example Co",
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            "https://example.com/"
            f"{external_id}"
        ),
        posted_at=posted_at,
        content_hash=f"hash-{external_id}",
        first_seen_at=NOW
        - timedelta(
            days=detected_days_ago
        ),
        last_seen_at=NOW,
        is_active=True,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family=(
                "SOFTWARE_ENGINEERING"
            ),
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{external_id}",
            requirements_verified=True,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def test_recent_postings_pass_the_filter(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=3,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert page.total == 1


def test_older_postings_are_hidden_not_visible_by_default(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=20,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert page.total == 0


def test_a_posting_exactly_at_the_boundary_is_kept(
    session_factory,
) -> None:
    """15 days ago is still within the last 15 days, not past them.

    An off-by-one here would hide a job the same morning it should have
    been the last one still visible, which is the kind of thing a user
    notices and a test does not catch unless it sits exactly on the
    line.
    """

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=15,
        )

        add_job(
            session,
            external_id="2",
            detected_days_ago=16,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert page.total == 1

        assert (
            page.items[0].external_id
            == "1"
        )


def test_the_filter_never_deletes_anything(
    session_factory,
) -> None:
    """The row must still exist and still be findable once the filter lifts.

    This is the property that separates "hide" from "delete", and it is
    the one the user explicitly chose over the destructive reading.
    """

    with session_factory() as session:
        job = add_job(
            session,
            external_id="1",
            detected_days_ago=40,
        )

        hidden = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert hidden.total == 0

        # The row is untouched: no filter, and it is there.
        everything = list_jobs(
            session,
            filters=JobFilters(),
            now=NOW,
        )

        assert everything.total == 1

        assert (
            everything.items[0].id
            == job.id
        )


def test_stats_reflect_the_same_cutoff_as_the_list(
    session_factory,
) -> None:
    """The headline total must equal the number of rows on screen."""

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=3,
        )

        add_job(
            session,
            external_id="2",
            detected_days_ago=40,
        )

        stats = build_stats(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert (
            stats["qualifying_active_jobs"]
            == 1
        )


def test_a_stale_posted_date_does_not_hide_a_freshly_detected_job(
    session_factory,
) -> None:
    """A source can misreport posted_at; ACE's own clock must win.

    If the filter were keyed on posted_at, a source claiming a posting
    went live two months ago would hide something ACE only just found,
    which is the opposite of what this feature is for.
    """

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=1,
            posted_at=NOW
            - timedelta(
                days=60
            ),
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert page.total == 1


def test_a_posting_with_no_posted_at_is_still_correctly_filtered(
    session_factory,
) -> None:
    """Most postings have no trustworthy posted_at at all.

    A filter that silently required posted_at would hide almost the
    whole corpus rather than the intended 15-day-old slice.
    """

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
            detected_days_ago=2,
            posted_at=None,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                max_detected_age_days=15,
            ),
            now=NOW,
        )

        assert page.total == 1
