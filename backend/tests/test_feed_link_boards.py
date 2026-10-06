"""Feed links are a list of boards to read directly.

Two Chewy postings had passed through the feed, both linking to its
Workday board. The probe, working from the name alone, found nothing,
and nobody had re-run discovery since early September: a Chewy
"Software Engineer I" was seen by the user before ACE ever looked.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
)
from backend.app.discovery.feed_links import (
    DISCOVERY_SOURCE,
    boards_named_in,
    find_unregistered_boards,
    read_boards,
    register_confirmed_boards,
    stored_feed_links,
)


CHEWY = (
    "https://wd5.myworkdaysite.com/recruiting/chewy/External/job/"
    "Bellevue-WA/Software-Engineer-I_R30985",
    "Chewy",
)

NOW = datetime(
    2026,
    10,
    6,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )

    Base.metadata.create_all(
        engine
    )

    with sessionmaker(
        bind=engine,
        class_=Session,
    )() as session:
        yield session


def add_source(
    session: Session,
    source_type: str,
    account: str,
    *,
    enabled: bool = True,
) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=account,
            enabled=enabled,
            poll_interval_seconds=900,
        )
    )

    session.flush()


def postings(
    count: int,
    *,
    description: str = "",
    title: str = "Software Engineer I",
) -> list:
    from types import SimpleNamespace

    return [
        SimpleNamespace(
            title=title,
            description=description,
        )
        for _ in range(count)
    ]


def test_a_feed_link_names_a_board_to_read() -> None:
    [board] = boards_named_in(
        [
            CHEWY,
            # The same board again, and a link to nothing ACE reads.
            (
                "https://wd5.myworkdaysite.com/recruiting/chewy/External/"
                "job/Plantation-FL/Category-Analyst_R1",
                "Chewy, Inc.",
            ),
            ("https://www.tesla.com/careers/search/job/123", "Tesla"),
        ]
    )

    assert board.key == ("workday", "chewy/external")

    assert board.company_name == "Chewy"

    assert board.detected.source_host == "chewy.wd5.myworkdayjobs.com"


def test_a_board_already_known_is_never_touched(
    session: Session,
) -> None:
    """Enabled or not: one switched off by hand stays off."""

    add_source(session, "workday", "Chewy/External")

    add_source(
        session,
        "smartrecruiters",
        "Jobsbridge1",
        enabled=False,
    )

    assert find_unregistered_boards(
        session,
        [
            CHEWY,
            (
                "https://jobs.smartrecruiters.com/Jobsbridge1/123-java",
                "Jobsbridge",
            ),
        ],
    ) == []


def test_only_a_board_that_reads_and_holds_postings_is_confirmed() -> None:
    boards = boards_named_in(
        [
            CHEWY,
            ("https://boards.greenhouse.io/emptyco/jobs/1", "EmptyCo"),
            ("https://jobs.lever.co/brokenco/abc", "BrokenCo"),
        ]
    )

    def read_board(definition):
        if definition.source_account == "brokenco":
            raise RuntimeError("404")

        return postings(268) if definition.company_name == "Chewy" else []

    outcomes = {
        outcome.board.company_name: outcome
        for outcome in read_boards(
            boards,
            read_board,
        )
    }

    assert outcomes["Chewy"].registered

    assert outcomes["Chewy"].job_count == 268

    assert not outcomes["EmptyCo"].registered

    assert "nothing" in outcomes["EmptyCo"].error

    assert not outcomes["BrokenCo"].registered

    assert "404" in outcomes["BrokenCo"].error


def test_a_confirmed_board_is_registered_to_be_polled(
    session: Session,
) -> None:
    outcomes = read_boards(
        boards_named_in(
            [CHEWY]
        ),
        lambda _definition: postings(268),
    )

    [added] = register_confirmed_boards(
        session,
        outcomes,
        now=NOW,
    )

    row = session.scalar(
        sa.select(
            JobSourceRecord,
        )
    )

    assert (
        row.source_type,
        row.source_account,
        row.source_host,
        row.company_name,
        row.enabled,
        row.poll_interval_seconds,
        row.discovery_source,
    ) == (
        "workday",
        "chewy/External",
        "chewy.wd5.myworkdayjobs.com",
        "Chewy",
        True,
        # Workday starts hourly; a passing role promotes it.
        3600,
        DISCOVERY_SOURCE,
    )


def test_a_board_registered_meanwhile_is_not_added_twice(
    session: Session,
) -> None:
    """The boards are read outside any transaction."""

    outcomes = read_boards(
        boards_named_in(
            [CHEWY]
        ),
        lambda _definition: postings(268),
    )

    add_source(session, "workday", "chewy/External")

    assert register_confirmed_boards(
        session,
        outcomes,
    ) == []

    assert session.scalar(
        sa.select(
            sa.func.count(),
        ).select_from(
            JobSourceRecord,
        )
    ) == 1


def test_every_feed_posting_ever_stored_is_a_link(
    session: Session,
) -> None:
    for index, (source, url) in enumerate(
        [
            ("simplify", CHEWY[0]),
            ("greenhouse", "https://boards.greenhouse.io/acme/jobs/1"),
        ]
    ):
        session.add(
            JobRecord(
                source=source,
                source_account="acct",
                external_id=str(index),
                company="Chewy" if source == "simplify" else "Acme",
                title="Software Engineer I",
                location="Bellevue, WA",
                description="",
                official_url=url,
                content_hash=f"hash-{index}",
                first_seen_at=NOW,
                last_seen_at=NOW,
                # Closed long ago: the board is still Chewy's.
                is_active=False,
            )
        )

    session.flush()

    assert stored_feed_links(
        session
    ) == [
        (CHEWY[0], "Chewy"),
    ]


# --- recognising the links ----------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://wd5.myworkdaysite.com/recruiting/chewy/External/job/x",
            ("workday", "chewy/External", "chewy.wd5.myworkdayjobs.com"),
        ),
        (
            "https://wd1.myworkdaysite.com/en-US/recruiting/caris/"
            "CarisLifeSciences/job/x",
            ("workday", "caris/CarisLifeSciences", "caris.wd1.myworkdayjobs.com"),
        ),
        (
            "https://egug.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/"
            "en/sites/CX_1/job/26013256",
            (
                "oracle_recruiting",
                "egug.fa.us2.oraclecloud.com/CX_1",
                "egug.fa.us2.oraclecloud.com",
            ),
        ),
        ("https://wd5.myworkdaysite.com/recruiting/chewy", None),
        ("https://example.oraclecloud.com/fscmUI/faces/x", None),
    ],
)
def test_both_workday_addresses_and_oracle_sites_are_recognised(
    url,
    expected,
) -> None:
    from backend.app.discovery.detector import (
        detect_source_from_url,
    )

    detected = detect_source_from_url(
        url
    )

    assert (
        None
        if detected is None
        else (
            detected.source_type.value,
            detected.source_account,
            detected.source_host,
        )
    ) == expected


def test_a_feed_posting_stays_until_its_board_is_actually_read() -> None:
    """Dropped because ACE *could* read the board, a posting on a board
    ACE did not poll was read nowhere at all."""

    from backend.app.adapters.simplify import (
        is_included,
    )

    entry = {
        "active": True,
        "is_visible": True,
        "category": "Software",
        "url": CHEWY[0],
    }

    # Registered and polled: the feed's copy is not needed.
    assert not is_included(
        entry,
        read_directly=lambda _url: True,
    )

    # Readable but not registered: kept, so it is seen meanwhile.
    assert is_included(
        entry,
        read_directly=lambda _url: False,
    )



# --- agencies are not employers ---------------------------------------


AGENCY_TEMPLATE = (
    "Job Title: Software Developer Location: Pittsburgh, PA Duration: "
    "6-9 Months Interview: Phone & In-Person Client: Direct Client. "
) * 4


@pytest.mark.parametrize(
    "link, company, jobs, reason",
    [
        (
            "https://jobs.smartrecruiters.com/AtriaGroupLLC/1-java",
            "Atria Group",
            postings(966),
            "SmartRecruiters board",
        ),
        (
            "https://jobs.smartrecruiters.com/DellforTechnologies/1-java",
            "DellFor Technologies",
            postings(40),
            "agency-style name",
        ),
        (
            "https://jobs.smartrecruiters.com/TestingXperts/1-qa",
            "Testing Xperts",
            postings(20),
            "agency name",
        ),
        (
            "https://boards.greenhouse.io/someagency/jobs/1",
            "Northwind",
            postings(10, description=AGENCY_TEMPLATE),
            "contract templates",
        ),
    ],
)
def test_a_staffing_agency_board_is_not_registered(
    link,
    company,
    jobs,
    reason,
) -> None:
    """The first automatic run registered nine of them."""

    [outcome] = read_boards(
        boards_named_in(
            [(link, company)]
        ),
        lambda _definition: jobs,
    )

    assert not outcome.registered

    assert reason in outcome.error


def test_an_employer_on_smartrecruiters_is_registered() -> None:
    [outcome] = read_boards(
        boards_named_in(
            [
                (
                    "https://jobs.smartrecruiters.com/NorthwesternMutual/1",
                    "Northwestern Mutual",
                ),
            ]
        ),
        lambda _definition: postings(
            69,
            description=(
                "At Northwestern Mutual, we believe relationships are "
                "built on trust. " * 10
            ),
        ),
    )

    assert outcome.registered


def test_a_rejected_board_is_recorded_switched_off_with_its_reason(
    session: Session,
) -> None:
    """So it is not read again every half hour, cannot crowd new boards
    out of a run, and a person can see why."""

    outcomes = read_boards(
        boards_named_in(
            [
                (
                    "https://jobs.smartrecruiters.com/TestingXperts/1-qa",
                    "Testing Xperts",
                ),
                ("https://jobs.lever.co/brokenco/abc", "BrokenCo"),
            ]
        ),
        lambda definition: (
            postings(20)
            if definition.source_account == "TestingXperts"
            else (_ for _ in ()).throw(RuntimeError("404"))
        ),
    )

    assert register_confirmed_boards(
        session,
        outcomes,
    ) == []

    rows = {
        row.source_account: row
        for row in session.scalars(
            sa.select(JobSourceRecord)
        ).all()
    }

    assert not rows["TestingXperts"].enabled

    assert rows["TestingXperts"].discovery_source.startswith(
        "feed_link rejected: staffing"
    )

    assert len(rows["TestingXperts"].discovery_source) <= 100

    assert not rows["brokenco"].enabled

    # And neither is a candidate again.
    assert find_unregistered_boards(
        session,
        [
            ("https://jobs.smartrecruiters.com/TestingXperts/1-qa", "x"),
            ("https://jobs.lever.co/brokenco/abc", "y"),
        ],
    ) == []



def test_links_whose_posting_could_pass_are_kept_apart() -> None:
    """Chewy's board was 168th of 1,197: the boards that matter are all
    read every run, the rest a few at a time."""

    from backend.app.discovery.feed_links import (
        split_links,
    )

    wanted, rest = split_links(
        [
            ("https://jobs.lever.co/a/1", "A", "Warehouse Associate"),
            (CHEWY[0], "Chewy", "Software Engineer I"),
            ("https://jobs.lever.co/b/1", "B", "Sales Lead"),
        ],
        could_pass=lambda _company, title: "Engineer" in title,
    )

    assert wanted == [
        (CHEWY[0], "Chewy"),
    ]

    assert rest == [
        ("https://jobs.lever.co/a/1", "A"),
        ("https://jobs.lever.co/b/1", "B"),
    ]


def test_a_large_employer_on_smartrecruiters_is_not_taken_for_an_agency() -> None:
    """Bosch has 4,851 postings there; size alone turned it away."""

    [outcome] = read_boards(
        boards_named_in(
            [
                (
                    "https://jobs.smartrecruiters.com/BoschGroup/1-sw",
                    "Bosch",
                ),
            ]
        ),
        lambda _definition: postings(
            4800,
        ) + postings(
            51,
            description=(
                "At Bosch, we shape the future by inventing high-quality "
                "technologies and services that spark enthusiasm. " * 5
            ),
        ),
    )

    assert outcome.registered
