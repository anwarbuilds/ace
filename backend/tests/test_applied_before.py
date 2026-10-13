"""A posting the user applied to, listed again, must say so.

Microsoft closed "Software Engineer" in Redmond and listed it again under
new ids days after the user had applied. The mark sat on the closed rows,
so the new listings read as unapplied and arrived in the pull and the alert
as if nothing had happened. The notice is derived on read; the mark is
never copied, because only the user knows whether a second listing is the
same opening.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.alerts.service import (
    applied_before_notes,
    qualifying_jobs,
    render,
    render_html,
)
from backend.app.api.main import _serialize_job
from backend.app.api.marks import set_mark
from backend.app.api.queries import (
    JobFilters,
    list_jobs,
)
from backend.app.applications.prior import same_place
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobMarkRecord,
    JobRecord,
    PollSessionRecord,
)


NOW = datetime.now(
    timezone.utc
).replace(
    minute=0,
    second=0,
    microsecond=0,
) - timedelta(
    hours=1,
)


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with factory() as session:
        yield session


def add_job(
    session,
    *,
    external_id: str,
    company: str = "Northwind Labs",
    title: str = "Software Engineer",
    location: str = "Redmond, WA, United States",
    is_active: bool = True,
    pull_id: int | None = None,
    requisition_id: str | None = None,
) -> JobRecord:
    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=external_id,
        company=company,
        requisition_id=requisition_id,
        title=title,
        location=location,
        description="Build software.",
        official_url=f"https://careers.example/{external_id}",
        posted_at=NOW,
        content_hash=f"hash-{external_id}",
        first_seen_at=NOW,
        last_seen_at=NOW,
        is_active=is_active,
        first_seen_session_id=pull_id,
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
            content_hash=f"hash-{external_id}",
            requirements_verified=True,
            is_early_career=True,
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def applied(
    session,
    job,
    *,
    days_ago: int = 5,
) -> None:
    set_mark(
        session,
        job_id=job.id,
        applied=True,
        applied_at=NOW - timedelta(days=days_ago),
    )

    session.flush()


def listing(
    session,
    job,
):
    page = list_jobs(
        session,
        filters=JobFilters(
            job_ids=(
                job.id,
            ),
            statuses=(),
            active_only=False,
        ),
    )

    return page.items[0]


def test_a_relisting_of_an_applied_posting_says_so(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
        is_active=False,
    )

    applied(
        session,
        old,
        days_ago=8,
    )

    new = add_job(
        session,
        external_id="2",
    )

    marks_before = session.scalar(
        select(
            func.count()
        ).select_from(
            JobMarkRecord
        )
    )

    item = listing(
        session,
        new,
    )

    assert item.applied_before is not None
    assert item.applied_before.job_id == old.id
    assert item.applied_before.is_active is False
    assert item.applied_before.count == 1
    assert (
        NOW - item.applied_before.applied_at
        > timedelta(days=7)
    )

    # The mark is never copied across: only the user knows whether a
    # second listing is the same opening.
    assert item.applied_at is None
    assert item.application_status is None

    assert session.scalar(
        select(
            func.count()
        ).select_from(
            JobMarkRecord
        )
    ) == marks_before


def test_the_applied_posting_itself_is_not_flagged(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
    )

    applied(
        session,
        old,
    )

    add_job(
        session,
        external_id="2",
    )

    assert listing(
        session,
        old,
    ).applied_before is None


def test_company_and_title_match_ignoring_case_and_spacing(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
        company="Northwind Labs",
        title="Software Engineer",
    )

    applied(
        session,
        old,
    )

    same = add_job(
        session,
        external_id="2",
        company="NORTHWIND LABS",
        title="software   engineer",
    )

    other_title = add_job(
        session,
        external_id="3",
        title="Software Engineer II",
    )

    other_company = add_job(
        session,
        external_id="4",
        company="Contoso Systems",
    )

    assert listing(
        session,
        same,
    ).applied_before is not None

    assert listing(
        session,
        other_title,
    ).applied_before is None

    assert listing(
        session,
        other_company,
    ).applied_before is None


def test_the_same_title_in_another_place_is_not_flagged(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
        location="Redmond, WA, United States",
    )

    applied(
        session,
        old,
    )

    austin = add_job(
        session,
        external_id="2",
        location="Austin, TX, United States",
    )

    remote = add_job(
        session,
        external_id="3",
        location="Remote",
    )

    country = add_job(
        session,
        external_id="4",
        location="US",
    )

    assert listing(
        session,
        austin,
    ).applied_before is None

    assert listing(
        session,
        remote,
    ).applied_before is None

    # A listing that names only a country could be any city.
    assert listing(
        session,
        country,
    ).applied_before is not None


def test_several_earlier_applications_report_the_latest_and_a_count(
    session,
) -> None:
    first = add_job(
        session,
        external_id="1",
        is_active=False,
    )

    second = add_job(
        session,
        external_id="2",
        is_active=False,
    )

    applied(
        session,
        first,
        days_ago=9,
    )

    applied(
        session,
        second,
        days_ago=3,
    )

    item = listing(
        session,
        add_job(
            session,
            external_id="3",
        ),
    )

    assert item.applied_before.job_id == second.id
    assert item.applied_before.count == 2


def test_a_job_marked_applied_itself_carries_no_notice(
    session,
) -> None:
    one = add_job(
        session,
        external_id="1",
    )

    two = add_job(
        session,
        external_id="2",
    )

    applied(
        session,
        one,
    )

    applied(
        session,
        two,
    )

    assert listing(
        session,
        two,
    ).applied_before is None


def test_the_api_shape_carries_the_notice_or_null(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
        is_active=False,
    )

    applied(
        session,
        old,
    )

    flagged = _serialize_job(
        listing(
            session,
            add_job(
                session,
                external_id="2",
            ),
        )
    )

    assert flagged["applied_before"]["job_id"] == old.id
    assert flagged["applied_before"]["is_active"] is False
    assert flagged["applied_before"]["count"] == 1
    assert flagged["applied_before"]["applied_at"].startswith(
        str(
            (NOW - timedelta(days=5)).year
        )
    )

    plain = _serialize_job(
        listing(
            session,
            add_job(
                session,
                external_id="3",
                company="Contoso Systems",
            ),
        )
    )

    assert plain["applied_before"] is None


@pytest.mark.parametrize(
    "first, second, expected",
    [
        ("Redmond, WA", "Redmond, WA, United States", True),
        ("US", "Redmond, WA", True),
        ("United States", "Austin, TX", True),
        ("Redmond, WA", "Austin, TX", False),
        ("Remote", "Redmond, WA", False),
        ("Remote", "Remote, US", True),
        (None, "Redmond, WA", False),
        (
            "US - California - Thousand Oaks",
            "US - California - Westlake Village",
            False,
        ),
    ],
)
def test_same_place(
    first,
    second,
    expected,
) -> None:
    assert same_place(
        first,
        second,
    ) is expected


def _alert_with_a_relisting(
    session,
):
    old = add_job(
        session,
        external_id="1",
        is_active=False,
    )

    applied(
        session,
        old,
        days_ago=8,
    )

    pull = PollSessionRecord(
        started_at=NOW,
        last_activity_at=NOW,
        jobs_discovered=2,
        qualifying_discovered=2,
    )

    session.add(
        pull
    )

    session.flush()

    add_job(
        session,
        external_id="2",
        pull_id=pull.id,
    )

    add_job(
        session,
        external_id="3",
        company="Contoso Systems",
        pull_id=pull.id,
    )

    jobs = qualifying_jobs(
        session,
        pull,
    )

    return pull, jobs, applied_before_notes(
        session,
        jobs,
    )


def test_the_alert_says_a_role_was_applied_to_before(
    session,
) -> None:
    pull, jobs, notes = _alert_with_a_relisting(
        session,
    )

    assert len(
        notes
    ) == 1

    (note,) = notes.values()

    assert note.startswith(
        "Applied before, "
    )

    _subject, text = render(
        pull,
        jobs,
        notes,
    )

    assert text.count(
        "Applied before"
    ) == 1

    html = render_html(
        pull,
        jobs,
        notes,
    )

    assert html.count(
        "Applied before"
    ) == 1

    # Nothing changes for an alert with no such role.
    _subject, plain = render(
        pull,
        jobs,
    )

    assert "Applied before" not in plain

    assert "Applied before" not in render_html(
        pull,
        jobs,
    )


def test_no_dash_reaches_the_applied_before_email(
    session,
) -> None:
    pull, jobs, notes = _alert_with_a_relisting(
        session,
    )

    html = render_html(
        pull,
        jobs,
        notes,
    )

    _subject, text = render(
        pull,
        jobs,
        notes,
    )

    for body in (
        html,
        text,
    ):
        assert not any(
            ch in body
            for ch in "\u2012\u2013\u2014\u2015\u2212"
        )


def test_the_requisition_numbers_tell_two_openings_apart(
    session,
) -> None:
    old = add_job(
        session,
        external_id="1",
        requisition_id="R-108814",
    )

    applied(
        session,
        old,
    )

    other = _serialize_job(
        listing(
            session,
            add_job(
                session,
                external_id="2",
                requisition_id="R-110488",
            ),
        )
    )

    # Both are open and the numbers differ: a second opening that looks
    # the same, which is why the number is carried.
    assert other["applied_before"]["requisition_id"] == "R-108814"
    assert other["applied_before"]["is_active"] is True
    assert other["requisition_id"] == "R-110488"
