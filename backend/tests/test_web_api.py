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
            status="PASS",
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


def test_stats_describe_only_the_apply_ready_queue(
    session_factory,
) -> None:
    """Every headline figure counts jobs worth applying to.

    Corpus size is deliberately absent: the page exists to show what to
    apply to, and a total that includes rejected postings only invites
    the question of why they are not on screen.
    """

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=0,
        )

        add_job(
            session,
            external_id="2",
            age_days=3,
        )

        add_job(
            session,
            external_id="3",
            age_days=40,
        )

        add_job(
            session,
            external_id="4",
            status="REJECT",
            age_days=0,
        )

    with session_factory() as session:
        stats = build_stats(
            session,
            now=NOW,
        )

    assert stats["posted_today"] == 1

    assert (
        stats["posted_last_7_days"] == 2
    )

    assert (
        stats["qualifying_active_jobs"]
        == 3
    )

    # Nothing leaks the size of the rejected corpus.
    assert "total_jobs" not in stats

    assert "active_jobs" not in stats

    assert (
        "by_eligibility" not in stats
    )


def test_stats_count_labelled_new_grad_roles(
    session_factory,
) -> None:
    """The labelled-new-grad tile counts only flagged postings."""

    with session_factory.begin() as session:
        job = add_job(
            session,
            external_id="1",
            age_days=1,
        )

        session.query(
            JobEvaluationRecord
        ).filter(
            JobEvaluationRecord.job_id
            == job.id
        ).update(
            {
                "is_early_career": True,
            }
        )

        add_job(
            session,
            external_id="2",
            age_days=1,
        )

    with session_factory() as session:
        stats = build_stats(
            session,
            now=NOW,
        )

    assert (
        stats["labelled_new_grad"] == 1
    )

    assert (
        stats["qualifying_active_jobs"]
        == 2
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

    assert (
        stats["qualifying_active_jobs"]
        == 0
    )

    assert stats["posted_today"] == 0


def test_stats_honour_the_same_filters_as_the_listing(
    session_factory,
) -> None:
    """The headline total must equal the rows on screen.

    A tile answering a different question than the list reads as a
    promise that jobs are being withheld.
    """

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=2,
        )

        add_job(
            session,
            external_id="2",
            age_days=200,
        )

        add_job(
            session,
            external_id="3",
            age_days=200,
        )

    filters = JobFilters(
        max_age_days=14
    )

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=filters,
            now=NOW,
        )

        stats = build_stats(
            session,
            filters=filters,
            now=NOW,
        )

    assert page.total == 1

    assert (
        stats["qualifying_active_jobs"]
        == page.total
    )


def test_stats_honour_company_filter(
    session_factory,
) -> None:
    """Narrowing to one company narrows the headline figure too."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            company="Alpha",
            age_days=1,
        )

        add_job(
            session,
            external_id="2",
            company="Beta",
            age_days=1,
        )

    filters = JobFilters(
        companies=(
            "Alpha",
        )
    )

    with session_factory() as session:
        stats = build_stats(
            session,
            filters=filters,
            now=NOW,
        )

    assert (
        stats["qualifying_active_jobs"]
        == 1
    )


def test_unfiltered_stats_count_everything_qualifying(
    session_factory,
) -> None:
    """With no filters the total is the whole apply-ready queue."""

    with session_factory.begin() as session:
        add_job(
            session,
            external_id="1",
            age_days=2,
        )

        add_job(
            session,
            external_id="2",
            age_days=200,
        )

    with session_factory() as session:
        stats = build_stats(
            session,
            now=NOW,
        )

    assert (
        stats["qualifying_active_jobs"]
        == 2
    )


# ----------------------------------------------------------------------
# Discovery runs
# ----------------------------------------------------------------------


def test_jobs_can_be_filtered_to_one_discovery_run(
    session_factory,
) -> None:
    """The UI groups arrivals by the run that found them."""

    from backend.app.db.models import (
        PollSessionRecord,
    )

    with session_factory.begin() as session:
        run = PollSessionRecord(
            started_at=NOW,
            last_activity_at=NOW,
            jobs_discovered=1,
            qualifying_discovered=1,
        )

        session.add(
            run
        )

        session.flush()

        mine = add_job(
            session,
            external_id="1",
        )

        mine.first_seen_session_id = (
            run.id
        )

        add_job(
            session,
            external_id="2",
        )

        session.flush()

        run_id = run.id

    with session_factory() as session:
        page = list_jobs(
            session,
            filters=JobFilters(
                session_id=run_id
            ),
            now=NOW,
        )

    assert page.total == 1

    assert (
        page.items[0].external_id == "1"
    )

    assert (
        page.items[0]
        .first_seen_session_id
        == run_id
    )


def test_last_poll_time_reflects_checking_not_finding(
    session_factory,
) -> None:
    """A poll that found nothing is still a poll.

    Answering "when did you last look" with the last time something
    turned up would imply ACE had stopped running.
    """

    from backend.app.api.queries import (
        last_poll_completed_at,
    )
    from backend.app.db.models import (
        SourceState,
    )

    with session_factory.begin() as session:
        session.add(
            SourceState(
                source="greenhouse",
                source_account="example",
                initialized_at=NOW,
                last_success_at=NOW,
                last_job_count=0,
            )
        )

    with session_factory() as session:
        assert (
            last_poll_completed_at(
                session
            )
            is not None
        )


def test_no_polls_yet_reports_no_last_poll_time(
    session_factory,
) -> None:
    from backend.app.api.queries import (
        last_poll_completed_at,
    )

    with session_factory() as session:
        assert (
            last_poll_completed_at(
                session
            )
            is None
        )


def test_match_filter_does_not_multiply_the_total(
    session_factory,
) -> None:
    """A match filter must count jobs, not job-score pairs.

    The page query joined the score table but its count query did not,
    so a min_match filter left the count referencing a table absent
    from its FROM clause and the database answered with a cartesian
    product. With a second resume in the table, 3 jobs reported as 6.
    This is user-visible: the number sits on the "Highly matched"
    control.
    """

    from backend.app.db.models import (
        JobResumeScoreRecord,
        ResumeRecord,
    )

    with session_factory() as session:
        resumes = []

        for label in (
            "active",
            "older",
        ):
            record = ResumeRecord(
                label=label,
                filename=f"{label}.pdf",
                content_hash=label * 8,
                raw_text="Python.",
                extracted_skills=[
                    "python",
                ],
                is_active=(
                    label == "active"
                ),
                uploaded_at=NOW,
            )

            session.add(
                record
            )

            resumes.append(
                record
            )

        session.flush()

        for index in (
            "1",
            "2",
            "3",
        ):
            job = add_job(
                session,
                external_id=index,
            )

            # Every job carries a score for BOTH resumes, which is what
            # the unconstrained join multiplied by.
            for resume in resumes:
                session.add(
                    JobResumeScoreRecord(
                        job_id=job.id,
                        resume_id=resume.id,
                        score=90,
                        matched_skills=[
                            "python",
                        ],
                        missing_skills=[],
                        related_skills=[],
                        algorithm_version="test",
                        scored_at=NOW,
                    )
                )

        session.flush()

        page = list_jobs(
            session,
            filters=JobFilters(
                resume_id=resumes[0].id,
                min_match=70,
            ),
            now=NOW,
        )

        assert page.total == 3

        assert len(
            page.items
        ) == 3


def test_since_filter_is_minute_accurate(
    session_factory,
) -> None:
    """"New since last visit" must resolve finer than a day.

    max_age_days cannot express "since 2:14 PM", and rounding it up to
    a day would mark a whole day of jobs as new every time.
    """

    with session_factory() as session:
        add_job(
            session,
            external_id="1",
        )

        add_job(
            session,
            external_id="5",
        )

        cutoff = NOW - timedelta(
            hours=3
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                since=cutoff,
            ),
            now=NOW,
        )

        # Job "1" was first seen 1 hour ago, job "5" five hours ago.
        assert page.total == 1

        assert (
            page.items[0].external_id
            == "1"
        )


def test_session_jobs_are_attached_in_one_pass(
    session_factory,
) -> None:
    """The feed shows a few arrivals per run without a request each.

    Twenty-five runs rendering three rows apiece would otherwise be
    twenty-five round trips.
    """

    from backend.app.api.main import (
        _with_session_jobs,
    )
    from backend.app.db.models import (
        PollSessionRecord,
    )

    with session_factory() as session:
        run = PollSessionRecord(
            started_at=NOW,
            last_activity_at=NOW,
            jobs_discovered=40,
            qualifying_discovered=5,
        )

        session.add(
            run
        )

        session.flush()

        for index in range(
            5
        ):
            job = add_job(
                session,
                external_id=str(
                    index
                ),
            )

            job.first_seen_session_id = (
                run.id
            )

        session.flush()

        enriched = _with_session_jobs(
            session,
            runs=[
                {
                    "id": run.id,
                    "qualifying_discovered": 5,
                },
            ],
            per_session=3,
        )

        assert len(
            enriched[0]["jobs"]
        ) == 3


def test_a_run_that_found_nothing_keeps_an_empty_list(
    session_factory,
) -> None:
    """Empty runs stay in the feed: they are the proof of work."""

    from backend.app.api.main import (
        _with_session_jobs,
    )

    with session_factory() as session:
        enriched = _with_session_jobs(
            session,
            runs=[
                {
                    "id": 1,
                    "qualifying_discovered": 0,
                },
            ],
            per_session=3,
        )

        assert enriched[0]["jobs"] == []
