"""Tests for importing an existing application history.

The asymmetry drives what is tested. A missed match costs one row the
user re-checks by hand. A wrong match silently tells them they already
applied somewhere they did not, and they never apply. So most of these
pin the refusal to guess.
"""

from datetime import (
    date,
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

from backend.app.applications.matching import (
    AMBIGUOUS,
    MATCHED,
    UNMATCHED,
    UNUSABLE,
    normalize_company,
    normalize_url,
    title_overlap,
)
from backend.app.applications.parsing import (
    ApplicationParseError,
    map_columns,
    parse_applications,
    parse_date,
)
from backend.app.applications.service import (
    apply_import,
    preview_import,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobMarkRecord,
    JobRecord,
)


NOW = datetime(
    2026,
    9,
    6,
    18,
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
    company: str = "Stripe",
    title: str = "Backend Engineer",
    url: str | None = None,
) -> JobRecord:
    """Insert one stored job."""

    job = JobRecord(
        source="greenhouse",
        source_account="example",
        external_id=str(
            index
        ),
        company=company,
        requisition_id=None,
        title=title,
        location="Seattle, WA",
        description="Build software.",
        official_url=(
            url
            or "https://boards.example.com"
            f"/jobs/{index}"
        ),
        posted_at=NOW,
        content_hash=f"hash-{index}",
        first_seen_at=NOW
        - timedelta(
            hours=index
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
            evaluated_at=NOW,
        )
    )

    session.flush()

    return job


def csv_bytes(
    text: str,
) -> bytes:
    """Encode a small CSV fixture."""

    return text.strip().encode(
        "utf-8"
    )


# --- parsing ---------------------------------------------------------


def test_columns_are_found_by_meaning_not_position() -> None:
    """Trackers invent their own shapes, so order must not matter."""

    mapping = map_columns(
        [
            "Notes",
            "Date Applied",
            "Employer",
            "Job Title",
            "Link",
        ]
    )

    assert mapping["applied_on"] == 1

    assert mapping["company"] == 2

    assert mapping["title"] == 3

    assert mapping["url"] == 4


def test_job_title_is_not_claimed_by_the_word_job() -> None:
    """Longest synonym wins, or "Job Title" binds to the wrong field."""

    mapping = map_columns(
        [
            "Company",
            "Job Title",
        ]
    )

    assert mapping["title"] == 1


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-03-04", date(2026, 3, 4)),
        ("3/4/2026", date(2026, 3, 4)),
        ("Mar 4, 2026", date(2026, 3, 4)),
        ("4 Mar 2026", date(2026, 3, 4)),
        ("", None),
        ("sometime last week", None),
    ],
)
def test_dates_are_read_in_the_shapes_people_write(
    raw,
    expected,
) -> None:
    assert parse_date(
        raw
    ) == expected


def test_a_file_with_no_recognisable_columns_is_refused() -> None:
    """Silently returning zero rows would look like "you applied to nothing"."""

    with pytest.raises(
        ApplicationParseError,
        match="No column",
    ):
        parse_applications(
            payload=csv_bytes(
                "alpha,beta\n1,2"
            ),
            filename="history.csv",
        )


def test_unsupported_extension_is_refused() -> None:
    with pytest.raises(
        ApplicationParseError,
        match="CSV or an Excel",
    ):
        parse_applications(
            payload=b"anything",
            filename="history.pdf",
        )


def test_rows_are_parsed_with_blank_lines_skipped() -> None:
    rows = parse_applications(
        payload=csv_bytes(
            "Company,Job Title,Date Applied\n"
            "Stripe,Backend Engineer,2026-03-04\n"
            "\n"
            "Amazon,SDE I,3/9/2026\n"
        ),
        filename="history.csv",
    )

    assert len(
        rows
    ) == 2

    assert rows[0].company == "Stripe"

    assert rows[0].applied_on == date(
        2026,
        3,
        4,
    )

    assert rows[1].applied_on == date(
        2026,
        3,
        9,
    )


# --- normalizing -----------------------------------------------------


def test_company_suffixes_do_not_prevent_a_match() -> None:
    assert normalize_company(
        "Stripe, Inc."
    ) == normalize_company(
        "Stripe"
    )


def test_url_identity_ignores_tracking_parameters() -> None:
    """The copy a person saved carries parameters ACE's copy does not."""

    assert normalize_url(
        "https://WWW.Example.com/jobs/12/"
        "?utm_source=linkedin"
    ) == normalize_url(
        "https://example.com/jobs/12"
    )


def test_title_overlap_ignores_seniority_filler() -> None:
    assert title_overlap(
        "Software Engineer, New Grad",
        "Software Engineer",
    ) == 1.0


# --- matching --------------------------------------------------------


def test_url_match_wins_over_everything(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Stripe",
            title="Backend Engineer",
            url="https://stripe.com/jobs/9",
        )

        rows = parse_applications(
            payload=csv_bytes(
                "Company,Job Title,Link\n"
                "Totally Wrong Name,Nonsense,"
                "https://stripe.com/jobs/9?x=1\n"
            ),
            filename="h.csv",
        )

        preview = preview_import(
            session,
            rows=rows,
        )

        assert (
            preview.matches[0].status
            == MATCHED
        )

        assert (
            preview.matches[0].method
            == "url"
        )


def test_two_equally_good_candidates_are_ambiguous_not_guessed(
    session_factory,
) -> None:
    """The central safety property of the whole import.

    Amazon posts the same title in several locations. Picking one would
    tell the user they had applied to a posting they had not.
    """

    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Amazon",
            title="Software Development Engineer",
        )

        add_job(
            session,
            index=2,
            company="Amazon",
            title="Software Development Engineer",
        )

        rows = parse_applications(
            payload=csv_bytes(
                "Company,Job Title\n"
                "Amazon,Software Development "
                "Engineer\n"
            ),
            filename="h.csv",
        )

        preview = preview_import(
            session,
            rows=rows,
        )

        match = preview.matches[0]

        assert match.status == AMBIGUOUS

        assert match.job_id is None

        assert len(
            match.candidates
        ) == 2


def test_a_row_naming_only_a_company_is_unusable(
    session_factory,
) -> None:
    """A company alone would match every posting it has open."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
        )

        rows = parse_applications(
            payload=csv_bytes(
                "Company,Job Title\n"
                "Stripe,\n"
            ),
            filename="h.csv",
        )

        assert (
            preview_import(
                session,
                rows=rows,
            )
            .matches[0]
            .status
            == UNUSABLE
        )


def test_unrelated_title_at_the_same_company_does_not_match(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            index=1,
            company="Stripe",
            title="Backend Engineer",
        )

        rows = parse_applications(
            payload=csv_bytes(
                "Company,Job Title\n"
                "Stripe,Technical Recruiter\n"
            ),
            filename="h.csv",
        )

        assert (
            preview_import(
                session,
                rows=rows,
            )
            .matches[0]
            .status
            == UNMATCHED
        )


def test_preview_writes_nothing(
    session_factory,
) -> None:
    """Seeing what an import would do must not do it."""

    with session_factory() as session:
        add_job(
            session,
            index=1,
        )

        rows = parse_applications(
            payload=csv_bytes(
                "Company,Job Title\n"
                "Stripe,Backend Engineer\n"
            ),
            filename="h.csv",
        )

        preview_import(
            session,
            rows=rows,
        )

        assert session.scalars(
            JobMarkRecord.__table__
            .select()
        ).first() is None


# --- applying --------------------------------------------------------


def test_import_records_the_date_from_the_file(
    session_factory,
) -> None:
    """An application happened when it happened, not at import time."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": (
                        "2026-03-04"
                    ),
                },
            ],
            now=NOW,
        )

        mark = session.get(
            JobMarkRecord,
            job.id,
        )

        assert (
            mark.applied_at.date()
            == date(
                2026,
                3,
                4,
            )
        )

        # The row was written today even though the application was not.
        assert (
            mark.updated_at.date()
            == NOW.date()
        )


def test_a_row_without_a_date_is_still_recorded(
    session_factory,
) -> None:
    """Dropping it would lose a real application over a blank cell."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": None,
                },
            ],
            now=NOW,
        )

        assert session.get(
            JobMarkRecord,
            job.id,
        ).applied_at is not None


def test_import_is_repeatable(
    session_factory,
) -> None:
    """Re-importing the same file must not double count."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        decisions = [
            {
                "job_id": job.id,
                "applied_on": "2026-03-04",
            },
        ]

        apply_import(
            session,
            decisions=decisions,
            now=NOW,
        )

        apply_import(
            session,
            decisions=decisions,
            now=NOW,
        )

        rows = session.scalars(
            JobMarkRecord.__table__
            .select()
        ).all()

        assert len(
            rows
        ) == 1


def test_import_does_not_disturb_other_marks(
    session_factory,
) -> None:
    """Importing applications must not clear saved or reviewed."""

    from backend.app.api.marks import (
        set_mark,
    )

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        set_mark(
            session,
            job_id=job.id,
            saved=True,
            review_state="reviewed",
            now=NOW,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": None,
                },
            ],
            now=NOW,
        )

        mark = session.get(
            JobMarkRecord,
            job.id,
        )

        assert mark.is_saved

        assert (
            mark.review_state
            == "reviewed"
        )

        assert mark.applied_at is not None


def test_unknown_job_ids_are_skipped(
    session_factory,
) -> None:
    with session_factory() as session:
        add_job(
            session,
            index=1,
        )

        marked = apply_import(
            session,
            decisions=[
                {
                    "job_id": 999999,
                    "applied_on": None,
                },
            ],
            now=NOW,
        )

        assert marked == 0


# --- status column ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Applied", "applied"),
        ("REJECTED", "rejected"),
        ("Rejected 3/4", "rejected"),
        ("Interview scheduled", "interviewing"),
        ("OA", "screening"),
        ("Declined", "rejected"),
        ("no", "rejected"),
        ("Offer", "offer"),
        ("", None),
        ("something nobody writes", None),
    ],
)
def test_status_cells_map_onto_ace_vocabulary(
    raw,
    expected,
) -> None:
    """Re-importing an updated sheet is the point, so spellings vary.

    Anything unrecognised returns None rather than a guess: a wrong
    status would tell the user a live application was rejected.
    """

    from backend.app.applications.parsing import (
        parse_status,
    )

    assert parse_status(
        raw
    ) == expected


def test_a_status_column_is_read_when_present() -> None:
    rows = parse_applications(
        payload=csv_bytes(
            "Company,Job Title,Status\n"
            "Stripe,Backend Engineer,Rejected\n"
        ),
        filename="h.csv",
    )

    assert rows[0].status == "rejected"


def test_a_sheet_without_a_status_column_still_parses() -> None:
    """Status is optional; most people's first sheet will not have one."""

    rows = parse_applications(
        payload=csv_bytes(
            "Company,Job Title\n"
            "Stripe,Backend Engineer\n"
        ),
        filename="h.csv",
    )

    assert rows[0].status is None


def test_importing_a_status_records_it(
    session_factory,
) -> None:
    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": "2026-03-04",
                    "status": "rejected",
                },
            ],
            now=NOW,
        )

        mark = session.get(
            JobMarkRecord,
            job.id,
        )

        assert (
            mark.application_status
            == "rejected"
        )

        # The application date still comes from the sheet, not today.
        assert (
            mark.applied_at.date()
            == date(
                2026,
                3,
                4,
            )
        )


def test_re_importing_moves_a_status_forward(
    session_factory,
) -> None:
    """The whole reason to re-upload: outcomes change over time."""

    with session_factory() as session:
        job = add_job(
            session,
            index=1,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": "2026-03-04",
                    "status": "applied",
                },
            ],
            now=NOW,
        )

        apply_import(
            session,
            decisions=[
                {
                    "job_id": job.id,
                    "applied_on": "2026-03-04",
                    "status": "rejected",
                },
            ],
            now=NOW,
        )

        mark = session.get(
            JobMarkRecord,
            job.id,
        )

        assert (
            mark.application_status
            == "rejected"
        )
