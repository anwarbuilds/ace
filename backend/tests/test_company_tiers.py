"""Tests for employer tiers and the sorts built on them.

The one property that matters most here is that Python and SQL agree.
Display reads :func:`classify_company`; ordering reads a SQL CASE built
from the same name sets. If those ever diverge, a posting sorts into one
tier while its badge claims another, which is worse than having no tiers
at all because it quietly teaches the user the labels are unreliable.
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
    parse_sort,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.intelligence.companies import (
    ALIASES,
    BIG_TECH_NAMES,
    ESTABLISHED_NAMES,
    TOP_TIER_NAMES,
    CompanyTier,
    classify_company,
    names_for_tier,
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
    index: int,
    company: str,
    early_career: bool = False,
) -> JobRecord:
    """Insert one qualifying job at a given company."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index
        ),
        company=company,
        requisition_id=None,
        title="Software Engineer",
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            f"https://example.com/{index}"
        ),
        posted_at=NOW,
        content_hash=f"hash-{index}",
        first_seen_at=NOW
        - timedelta(
            minutes=index
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
            content_hash=f"hash-{index}",
            requirements_verified=True,
            is_early_career=early_career,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


# --- classification --------------------------------------------------


@pytest.mark.parametrize(
    "company,expected",
    [
        ("Amazon", CompanyTier.BIG_TECH),
        ("NVIDIA", CompanyTier.BIG_TECH),
        ("TikTok", CompanyTier.BIG_TECH),
        ("Stripe", CompanyTier.TOP_TIER),
        ("Anthropic", CompanyTier.TOP_TIER),
        ("Jane Street", CompanyTier.TOP_TIER),
        (
            "American Express",
            CompanyTier.ESTABLISHED,
        ),
        (
            "Some Unknown Startup",
            CompanyTier.OTHER,
        ),
        ("", CompanyTier.OTHER),
        (None, CompanyTier.OTHER),
    ],
)
def test_companies_land_in_the_right_tier(
    company,
    expected,
) -> None:
    assert classify_company(
        company
    ) is expected


def test_classification_ignores_case_and_padding() -> None:
    assert classify_company(
        "  aMaZoN  "
    ) is CompanyTier.BIG_TECH


def test_aliases_resolve_to_their_canonical_tier() -> None:
    assert classify_company(
        "Meta Platforms"
    ) is CompanyTier.BIG_TECH


def test_a_company_belongs_to_exactly_one_tier() -> None:
    """Overlapping sets would make the SQL CASE order-dependent.

    The CASE checks big tech first, so a name in two sets would sort as
    the earlier tier while a reader of the lists would expect the other.
    """

    assert not (
        BIG_TECH_NAMES & TOP_TIER_NAMES
    )

    assert not (
        BIG_TECH_NAMES
        & ESTABLISHED_NAMES
    )

    assert not (
        TOP_TIER_NAMES
        & ESTABLISHED_NAMES
    )


def test_every_alias_points_at_a_real_name() -> None:
    """An alias to nothing is a silent no-op."""

    known = (
        BIG_TECH_NAMES
        | TOP_TIER_NAMES
        | ESTABLISHED_NAMES
    )

    for spelling, canonical in (
        ALIASES.items()
    ):
        assert canonical in known, (
            f"{spelling!r} points at "
            f"unknown {canonical!r}"
        )


def test_names_are_stored_already_normalized() -> None:
    """SQL matches on lower(trim(company)) and cannot normalise more.

    A set entry with a capital or stray space would never match
    anything, and would fail silently.
    """

    for name in (
        BIG_TECH_NAMES
        | TOP_TIER_NAMES
        | ESTABLISHED_NAMES
        | set(ALIASES)
    ):
        assert name == name.strip().lower(), name


def test_sql_ordering_agrees_with_python_classification(
    session_factory,
) -> None:
    """The guarantee the whole feature rests on.

    Ordering is done in SQL for pagination; the badge is computed in
    Python. Both must reach the same answer for the same posting.
    """

    with session_factory() as session:
        for index, company in enumerate(
            (
                "Some Unknown Startup",
                "American Express",
                "Stripe",
                "Amazon",
            ),
            start=1,
        ):
            add_job(
                session,
                index=index,
                company=company,
            )

        page = list_jobs(
            session,
            filters=JobFilters(
                sort="big_tech_first",
            ),
            now=NOW,
        )

        ordered = [
            item.company
            for item in page.items
        ]

        assert ordered == [
            "Amazon",
            "Stripe",
            "American Express",
            "Some Unknown Startup",
        ]

        # And each row's own badge matches where it sorted.
        for item in page.items:
            assert (
                item.company_tier
                == classify_company(
                    item.company
                ).value
            )


# --- filtering -------------------------------------------------------


def test_tier_filter_keeps_only_the_requested_tiers(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
        )

        add_job(
            session,
            index=2,
            company="Stripe",
        )

        add_job(
            session,
            index=3,
            company="Unknown Co",
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                tiers=(
                    "BIG_TECH",
                    "TOP_TIER",
                ),
            ),
            now=NOW,
        )

        assert page.total == 2

        assert {
            item.company
            for item in page.items
        } == {
            "Amazon",
            "Stripe",
        }


def test_filtering_to_other_is_the_complement_not_a_list(
    session_factory,
) -> None:
    """"Everything unlisted" cannot be enumerated, only excluded."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
        )

        add_job(
            session,
            index=2,
            company="Unknown Co",
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                tiers=(
                    "OTHER",
                ),
            ),
            now=NOW,
        )

        assert page.total == 1

        assert (
            page.items[0].company
            == "Unknown Co"
        )


# --- multi-key sorting -----------------------------------------------


def test_sorts_combine_in_the_order_given() -> None:
    assert parse_sort(
        "new_grad_first,best_match"
    ) == (
        "new_grad_first",
        "best_match",
    )


def test_unknown_sort_keys_are_dropped_not_rejected() -> None:
    """A stale bookmark should still return jobs."""

    assert parse_sort(
        "nonsense,best_match"
    ) == (
        "best_match",
    )


def test_an_entirely_unknown_sort_falls_back() -> None:
    assert parse_sort(
        "nonsense"
    ) == (
        "new_grad_first",
    )

    assert parse_sort(
        None
    ) == (
        "new_grad_first",
    )


def test_duplicate_sort_keys_are_collapsed() -> None:
    assert parse_sort(
        "best_match,best_match"
    ) == (
        "best_match",
    )


def test_combining_sorts_groups_then_orders_within_the_group(
    session_factory,
) -> None:
    """The point of item one: both things at once, not a choice.

    Early-career postings lead, and inside that group the strongest
    matches come first.
    """

    with session_factory() as session:
        # An unlabelled job at a household name, and two early-career
        # jobs. Early career must win the outer ordering.
        add_job(
            session,
            index=1,
            company="Amazon",
            early_career=False,
        )

        add_job(
            session,
            index=2,
            company="Unknown Co",
            early_career=True,
        )

        add_job(
            session,
            index=3,
            company="Stripe",
            early_career=True,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                sort=(
                    "new_grad_first,"
                    "big_tech_first"
                ),
            ),
            now=NOW,
        )

        ordered = [
            (
                item.company,
                item.is_early_career,
            )
            for item in page.items
        ]

        # Both early-career jobs first; Stripe ahead of Unknown Co
        # inside that group because of the second key.
        assert ordered == [
            ("Stripe", True),
            ("Unknown Co", True),
            ("Amazon", False),
        ]


def test_a_company_can_be_excluded(
    session_factory,
) -> None:
    """"Everything except Amazon" is a different question from
    "only Amazon", and both are worth wanting."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
        )

        add_job(
            session,
            index=2,
            company="Stripe",
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                exclude_companies=(
                    "Amazon",
                ),
            ),
            now=NOW,
        )

        assert page.total == 1

        assert (
            page.items[0].company
            == "Stripe"
        )


def test_exclusion_ignores_case(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                exclude_companies=(
                    "amazon",
                ),
            ),
            now=NOW,
        )

        assert page.total == 0


def test_exclusion_stacks_with_every_other_filter(
    session_factory,
) -> None:
    """The whole point: narrow to big tech, then drop one name."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
            early_career=True,
        )

        add_job(
            session,
            index=2,
            company="NVIDIA",
            early_career=True,
        )

        add_job(
            session,
            index=3,
            company="Unknown Co",
            early_career=True,
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                tiers=(
                    "BIG_TECH",
                ),
                early_career_only=True,
                exclude_companies=(
                    "Amazon",
                ),
                sort=(
                    "new_grad_first,"
                    "best_match"
                ),
            ),
            now=NOW,
        )

        assert page.total == 1

        assert (
            page.items[0].company
            == "NVIDIA"
        )


def test_stats_honour_tier_and_exclusion(
    session_factory,
) -> None:
    """The headline total must equal the rows on screen.

    A count that disagrees with the list reads as jobs being withheld.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
        )

        add_job(
            session,
            index=2,
            company="NVIDIA",
        )

        add_job(
            session,
            index=3,
            company="Unknown Co",
        )

        filters = JobFilters(
            tiers=(
                "BIG_TECH",
            ),
            exclude_companies=(
                "Amazon",
            ),
        )

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
