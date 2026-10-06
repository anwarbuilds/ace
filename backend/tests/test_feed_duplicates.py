"""A feed's copy of a role ACE already reads from the employer.

Adding direct boards for companies a curated feed already listed --
Microsoft among them -- put the same role in the queue twice. The
feed's copy is the worse of the two: its description is a placeholder,
so the gate cannot read it, which is exactly how clearance roles were
getting through.

Only exact duplicates are hidden. Measured before applying, 14 feed
rows matched a direct posting on company and title, and 56 did not --
worded differently, or listed by the feed and not the board. Those 56
stay, because hiding them would hide roles the user may see nowhere
else.
"""

from __future__ import annotations

import ast
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.api.queries import (
    JobFilters,
    list_jobs,
    posting_link_key,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)


NOW = datetime(
    2026,
    10,
    4,
    12,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
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
    key: str,
    source: str,
    title: str,
    company: str = "Microsoft",
    active: bool = True,
    url: str | None = None,
) -> JobRecord:
    job = JobRecord(
        source=source,
        source_account="acct",
        external_id=key,
        company=company,
        requisition_id=None,
        title=title,
        location="Redmond, WA, US",
        description="Build software.",
        official_url=url or f"https://example.com/{key}",
        posted_at=NOW,
        content_hash=f"hash-{key}",
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=active,
    )

    session.add(
        job
    )

    session.flush()

    session.add(
        JobEvaluationRecord(
            job_id=job.id,
            eligibility_status="PASS",
            role_family="SOFTWARE_ENGINEERING",
            role_priority="PRIMARY",
            rule_version="test",
            content_hash=f"hash-{key}",
            requirements_verified=True,
            is_early_career=True,
            is_new_grad=False,
            required_experience_years=None,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def queue(
    session: Session,
) -> list[tuple[str, str]]:
    page = list_jobs(
        session,
        filters=JobFilters(),
        now=NOW,
    )

    return sorted(
        (
            item.source,
            item.title,
        )
        for item in page.items
    )


def test_a_feed_copy_of_a_direct_role_is_hidden(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer - Intune",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer - Intune",
        )

        assert queue(
            session
        ) == [
            (
                "eightfold_pcsx",
                "Software Engineer - Intune",
            ),
        ], "the same role appeared twice"


def test_a_feed_role_the_board_lacks_is_kept(
    session_factory,
) -> None:
    """The reason this is exact-match only. A feed role with no twin on
    the direct board may be the only place the user sees it."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer II",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer - Forward Deployed",
        )

        assert len(
            queue(
                session
            )
        ) == 2


def test_a_closed_direct_posting_does_not_hide_the_feed_copy(
    session_factory,
) -> None:
    """If the employer's own copy has gone, the feed's is all that is
    left; hiding it would hide the role entirely."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="eightfold_pcsx",
            title="Software Engineer",
            active=False,
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer",
        )

        assert queue(
            session
        ) == [
            (
                "simplify",
                "Software Engineer",
            ),
        ]


def test_the_same_title_at_another_company_is_not_a_duplicate(
    session_factory,
) -> None:
    """"Software Engineer" is the most common title there is."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="greenhouse",
            title="Software Engineer",
            company="Algolia",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            title="Software Engineer",
            company="Microsoft",
        )

        assert len(
            queue(
                session
            )
        ) == 2


def test_the_same_posting_under_a_reworded_title_is_hidden(
    session_factory,
) -> None:
    """183 feed rows pointed at the very posting a direct row held,
    under a title the feed had reworded -- every one shown twice."""

    link = "https://lifeattiktok.com/search/7685552743586826549"

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="bytedance",
            company="TikTok",
            title=(
                "Machine Learning Engineer Graduate "
                "(E-Commerce Content Recommendation) - 2027 Start"
            ),
            url=link,
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            company="TikTok",
            title="Machine Learning Engineer Graduate - E-Commerce Content",
            url=link,
        )

        assert [
            source
            for source, _title in queue(
                session
            )
        ] == ["bytedance"]


def test_a_link_differing_only_in_www_or_scheme_is_the_same_posting(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="amazon",
            company="Amazon",
            title="Software Development Engineer, Robotics, Early Career",
            url="https://www.amazon.jobs/en/jobs/10567489/sde-robotics",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            company="Amazon",
            title="Software Development Engineer - Robotics",
            url="http://amazon.jobs/en/jobs/10567489/sde-robotics",
        )

        assert [
            source
            for source, _title in queue(
                session
            )
        ] == ["amazon"]


def test_a_different_link_with_a_different_title_is_kept(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="bytedance",
            company="TikTok",
            title="Backend Software Engineer Graduate - 2027 Start",
            url="https://lifeattiktok.com/search/1",
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            company="TikTok",
            title="Frontend Software Engineer Graduate",
            url="https://lifeattiktok.com/search/2",
        )

        assert len(
            queue(
                session
            )
        ) == 2


def test_a_closed_direct_posting_does_not_hide_by_link_either(
    session_factory,
) -> None:
    link = "https://lifeattiktok.com/search/3"

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="bytedance",
            company="TikTok",
            title="Software Engineer Graduate (Backend)",
            url=link,
            active=False,
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            company="TikTok",
            title="Software Engineer Graduate",
            url=link,
        )

        assert [
            source
            for source, _title in queue(
                session
            )
        ] == ["simplify"]


def test_a_workday_link_with_a_locale_is_the_same_posting(
    session_factory,
) -> None:
    """The feed writes "/en-US/" into Workday links where the board does
    not: every RELX and LexisNexis role was shown twice."""

    with session_factory() as session:
        add_job(
            session,
            key="direct",
            source="workday",
            company="RELX",
            title="Software Engineer 1",
            url=(
                "https://relx.wd3.myworkdayjobs.com/relx/job/"
                "Alpharetta-GA/Software-Engineer-1_R117973-1"
            ),
        )

        add_job(
            session,
            key="feed",
            source="simplify",
            company="RELX",
            title="Software Engineer I - Risk Solutions",
            url=(
                "https://relx.wd3.myworkdayjobs.com/en-US/relx/job/"
                "Alpharetta-GA/Software-Engineer-1_R117973-1"
            ),
        )

        assert [
            source
            for source, _title in queue(
                session
            )
        ] == ["workday"]


def test_a_switched_off_agencys_feed_copies_are_hidden_too(
    session_factory,
) -> None:
    """The board is off; its reposts arriving through a feed are the
    same noise by another door."""

    from backend.app.db.models import JobSourceRecord

    with session_factory() as session:
        session.add(
            JobSourceRecord(
                source_type="smartrecruiters",
                source_account="9to9SoftwareSolutionsLLC",
                company_name="9to9 Software Solutions",
                enabled=False,
                poll_interval_seconds=900,
                discovery_source="manual rejected: staffing agency",
            )
        )

        add_job(
            session,
            key="agency",
            source="simplify",
            company="9to9 Software Solutions",
            title="Software Engineer",
        )

        add_job(
            session,
            key="employer",
            source="simplify",
            company="Garmin",
            title="Software Engineer",
        )

        assert queue(
            session
        ) == [
            ("simplify", "Software Engineer"),
        ]


def _indexed_link_expression() -> str:
    """The expression the newest migration indexes the posting link on."""

    versions = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
    )

    statements = [
        node.value
        for path in sorted(
            versions.glob("*.py")
        )
        for function in ast.parse(
            path.read_text()
        ).body
        if isinstance(function, ast.FunctionDef)
        and function.name == "upgrade"
        for node in ast.walk(function)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(
            "CREATE INDEX ix_jobs_posting_link_key"
        )
    ]

    return statements[-1].split(
        "ON jobs (",
        1,
    )[1][:-1]


def test_the_link_key_is_the_indexed_expression_with_no_parameters() -> None:
    """Sent as parameters, the strings stop matching the index once
    Postgres plans the prepared statement generically: every feed row
    then read the whole jobs table, and ACE's page sat loading."""

    compiled = posting_link_key(
        JobRecord.official_url
    ).compile(
        dialect=postgresql.psycopg.dialect(),
        compile_kwargs={
            "render_postcompile": True,
        },
    )

    assert compiled.params == {}

    assert str(compiled).replace(
        "jobs.official_url",
        "official_url",
    ) == _indexed_link_expression()
