"""Boards found through startup talent networks earn a place by hiring.

The owner asked on 2026-10-29 for every startup in networks like a16z's
speedrun. Every name here is fictional.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import json

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import JobSourceRecord
from backend.app.models.job import CanonicalJob
from backend.scripts.register_network_boards import (
    DISCOVERY_SOURCE,
    Candidate,
    assess,
    known_boards,
    load_candidates,
    register,
    settle_name,
)


NOW = datetime(
    2026,
    10,
    29,
    tzinfo=timezone.utc,
)

DESCRIPTION = (
    "This is a new grad role. Build and ship reliable services with a "
    "small team. You will write and review code, own features end to "
    "end and help operate what you ship. We value clear writing and "
    "steady engineering judgement. Benefits include health cover, paid "
    "leave and a learning budget. "
) * 3


def job(
    title: str,
    location: str = "New York, NY",
) -> CanonicalJob:
    return CanonicalJob(
        source="ashby",
        company="Fictional AI",
        external_id=title,
        title=title,
        location=location,
        description=DESCRIPTION,
        official_url="https://jobs.ashbyhq.com/fictional-ai/1",
    )


FICTIONAL = Candidate(
    source_type="ashby",
    source_account="fictional-ai",
    company="Fictional AI",
)


@pytest.fixture(name="session_factory")
def fixture_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(
        engine
    )

    return sessionmaker(
        bind=engine,
    )


def test_a_board_hiring_us_engineers_is_registered(
    session_factory,
) -> None:
    outcome = assess(
        FICTIONAL,
        lambda definition: [
            job("Software Engineer, New Grad"),
            job("Account Executive"),
        ],
    )

    assert outcome.added
    assert outcome.us_engineering == 1
    assert outcome.passing == 1

    with session_factory.begin() as session:
        assert register(
            session,
            outcome,
            now=NOW,
        )

    with session_factory() as session:
        row = session.scalars(
            sa.select(
                JobSourceRecord
            )
        ).one()

    assert (
        row.source_type,
        row.source_account,
        row.company_name,
        row.enabled,
        row.discovery_source,
        row.poll_interval_seconds,
        row.source_host,
    ) == (
        "ashby",
        "fictional-ai",
        "Fictional AI",
        True,
        DISCOVERY_SOURCE,
        900,
        "jobs.ashbyhq.com",
    )


def test_a_senior_only_board_still_counts_as_hiring_us_engineers() -> None:
    """A startup hiring senior engineers today posts the junior role
    tomorrow; the gate decides the role, not whether to read the board."""

    outcome = assess(
        FICTIONAL,
        lambda definition: [
            job("Senior Software Engineer"),
        ],
    )

    assert outcome.added
    assert outcome.passing == 0


def test_a_board_without_a_passing_role_starts_hourly(
    session_factory,
) -> None:
    outcome = assess(
        FICTIONAL,
        lambda definition: [
            job("Senior Software Engineer"),
        ],
    )

    with session_factory.begin() as session:
        assert register(
            session,
            outcome,
            now=NOW,
        )

    with session_factory() as session:
        row = session.scalars(
            sa.select(
                JobSourceRecord
            )
        ).one()

    assert row.poll_interval_seconds == 3600


def test_a_board_the_catalog_holds_is_never_touched(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        session.add(
            JobSourceRecord(
                source_type="ashby",
                source_account="Fictional-AI",
                company_name="Fictional AI",
                enabled=False,
                poll_interval_seconds=86400,
                discovery_source="manual",
            )
        )

    outcome = assess(
        FICTIONAL,
        lambda definition: [
            job("Software Engineer"),
        ],
    )

    with session_factory.begin() as session:
        assert FICTIONAL.key in known_boards(
            session
        )

        assert not register(
            session,
            outcome,
            now=NOW,
        )

    with session_factory() as session:
        row = session.scalars(
            sa.select(
                JobSourceRecord
            )
        ).one()

    assert (
        row.enabled,
        row.poll_interval_seconds,
        row.discovery_source,
    ) == (
        False,
        86400,
        "manual",
    )


@pytest.mark.parametrize(
    "jobs",
    [
        [job("Account Executive"), job("Recruiter")],
        [job("Software Engineer", "London, United Kingdom")],
        [job("Software Engineer Intern")],
        [job("Site Reliability Engineer"), job("iOS Engineer")],
    ],
    ids=["no engineers", "abroad", "internship", "unwanted trades"],
)
def test_a_board_without_us_software_roles_is_left_out(
    jobs,
) -> None:
    outcome = assess(
        FICTIONAL,
        lambda definition: jobs,
    )

    assert not outcome.added
    assert outcome.reason == "no US software or ML roles today"


def _http_error(
    status: int,
) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "GET",
        "https://api.ashbyhq.com/posting-api/job-board/fictional-ai",
    )

    return httpx.HTTPStatusError(
        str(status),
        request=request,
        response=httpx.Response(
            status,
            request=request,
        ),
    )


def test_unreadable_empty_and_agency_boards_are_left_out() -> None:
    def gone(definition):
        raise _http_error(404)

    def busy(definition):
        raise _http_error(429)

    missing = assess(
        FICTIONAL,
        gone,
    )

    assert not missing.added
    assert not missing.transient
    assert missing.reason.startswith("unreadable")

    throttled = assess(
        FICTIONAL,
        busy,
    )

    assert not throttled.added
    assert throttled.transient

    empty = assess(
        FICTIONAL,
        lambda definition: [],
    )

    assert not empty.added
    assert empty.reason.startswith("empty")

    agency = assess(
        Candidate(
            source_type="ashby",
            source_account="fictional-staffing",
            company="Fictional Staffing Partners",
        ),
        lambda definition: [
            job("Software Engineer"),
        ],
    )

    assert not agency.added
    assert agency.reason.startswith("staffing")


def test_collected_boards_are_one_board_under_any_case(
    tmp_path,
) -> None:
    path = tmp_path / "boards.json"

    path.write_text(
        json.dumps(
            {
                "boards": [
                    {
                        "source_type": "ashby",
                        "source_account": "fictional-ai",
                        "company": "Fictional AI",
                    },
                    {
                        "source_type": "ashby",
                        "source_account": "Fictional-AI",
                        "company": "Another Name",
                    },
                    {
                        "source_type": "gem",
                        "source_account": "fictional-robotics",
                        "company": None,
                        "source_host": "api.gem.com",
                    },
                ]
            }
        )
    )

    candidates = load_candidates(
        path
    )

    assert [
        (candidate.source_type, candidate.company)
        for candidate in candidates
    ] == [
        ("ashby", "Fictional AI"),
        ("gem", "fictional-robotics"),
    ]

    assert candidates[1].definition().source_host == "api.gem.com"


def test_a_board_is_registered_under_the_name_it_declares() -> None:
    """A network can list a company by its old name: the roles are on
    the board of the company that bought it."""

    assert settle_name(
        "Fictional Data",
        "Fictional Tower",
    ) == ("Fictional Tower", None)

    # Initials are the same employer; the longer name says more.
    assert settle_name(
        "Fictional Space Intelligence",
        "FSI",
    ) == ("Fictional Space Intelligence", None)

    assert settle_name(
        "FSI",
        "Fictional Space Intelligence",
    ) == ("Fictional Space Intelligence", None)

    # Agreeing names, a domain suffix and silence keep the listed name.
    for declared in ("Fictional AI", "Fictional.ai", "Fictional", None, ""):
        assert settle_name(
            "Fictional AI",
            declared,
        ) == ("Fictional AI", None), declared


def test_a_firms_shared_portfolio_board_is_left_out() -> None:
    """A venture firm's own board lists its whole portfolio; the network
    that linked one posting named it after that one company."""

    outcome = assess(
        Candidate(
            source_type="ashby",
            source_account="Fictional-VC",
            company="Fictional Robotics",
        ),
        lambda definition: [
            job("Software Engineer, New Grad"),
        ],
        lambda candidate: "Fictional VC",
    )

    assert not outcome.added
    assert outcome.reason.startswith("shared")

    # A company whose own name says capital is still a company.
    assert settle_name(
        "Fictional Capital",
        "Fictional Capital Inc",
    ) == ("Fictional Capital", None)


def test_a_renamed_board_registers_under_its_own_name(
    session_factory,
) -> None:
    outcome = assess(
        FICTIONAL,
        lambda definition: [
            job("Software Engineer"),
        ],
        lambda candidate: "Fictional Tower",
    )

    with session_factory.begin() as session:
        assert register(
            session,
            outcome,
            now=NOW,
        )

    with session_factory() as session:
        assert session.scalars(
            sa.select(
                JobSourceRecord.company_name
            )
        ).one() == "Fictional Tower"


def test_the_collected_list_can_be_read_as_it_stands() -> None:
    """Every Workday board needs its tenant host to be read at all: the
    first round-two run read 90 Workday boards without one, and every one
    failed before a request was made."""

    from backend.scripts.register_network_boards import DEFAULT_INPUT

    candidates = load_candidates(
        DEFAULT_INPUT
    )

    assert candidates

    assert len(
        {candidate.key for candidate in candidates}
    ) == len(candidates)

    for candidate in candidates:
        host = candidate.definition().source_host

        if candidate.source_type == "workday":
            assert host and host.endswith(
                ("myworkdayjobs.com", "myworkdaysite.com")
            ), candidate

        if candidate.source_type == "gem":
            assert host == "api.gem.com", candidate
