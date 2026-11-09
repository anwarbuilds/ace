"""The stale-evaluation refresh keeps the stored job's own hash.

Before 2026-09-09 the job content hash had no employment type, and
before 2026-10-04 it hashed a posting time as text with its offset. A
job closed before those changes still carries its original hash. The
backfill CLI rebuilds the job and hashes it again with today's formula,
so it writes a correct decision under a hash the job row never had, and
that evaluation reads as stale forever. ``refresh_stale_evaluations``
labels the decision with the hash stored on the job, which is the
identity polling compares, so the same row stops being stale.

Every job here is fictional.
"""

import hashlib
import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.db.base import Base
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
)
from backend.app.intelligence.eligibility import (
    ELIGIBILITY_RULE_VERSION,
    EligibilityReasonCode,
    evaluate_job,
)
from backend.app.persistence.evaluations import (
    iter_stale_job_ids,
    record_job_evaluations,
    refresh_stale_evaluations,
)
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)
from backend.scripts.backfill_job_evaluations import (
    _to_canonical,
)


NOW = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)

POSTED = datetime(2026, 8, 20, 13, 30, tzinfo=timezone.utc)

PAD = (
    " We are a team building reliable distributed systems at scale. You"
    " will collaborate across product and platform groups, write and"
    " review code, and help operate what you ship. We value clear written"
    " communication and steady engineering judgement over heroics."
    " Benefits include health cover, paid leave and a learning budget."
) * 2

NEW_GRAD = "New grad role. Build reliable software systems in Python." + PAD

NO_SPONSOR = (
    "New grad role. Build reliable software systems in Python."
    " Candidates must be authorized to work without current or future"
    " sponsorship." + PAD
)

DERIVED_FIELDS = (
    "eligibility_status",
    "role_family",
    "role_priority",
    "rule_version",
    "reason_codes",
    "reasons",
    "required_experience_years",
    "is_early_career",
    "is_new_grad",
    "requirements_verified",
)

JOB_FIELDS = (
    "id",
    "source",
    "source_account",
    "external_id",
    "company",
    "title",
    "location",
    "description",
    "official_url",
    "posted_at",
    "employment_type",
    "content_hash",
    "first_seen_at",
    "last_seen_at",
    "is_active",
    "closed_at",
)


@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session_factory")
def fixture_session_factory(engine):
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def old_formula_hash(
    record: JobRecord,
    *,
    offset_hours: float,
    with_employment_type: bool,
) -> str:
    """Hash a job the way ACE did before 2026-10-04 (or 2026-09-09)."""

    payload = {
        "company": record.company,
        "requisition_id": record.requisition_id,
        "title": record.title,
        "location": record.location,
        "description": record.description,
        "official_url": record.official_url,
        "posted_at": POSTED.astimezone(
            timezone(timedelta(hours=offset_hours))
        ).isoformat(),
    }
    if with_employment_type:
        payload["employment_type"] = record.employment_type
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def add_job(
    session: Session,
    external_id: str,
    *,
    title: str = "Software Engineer",
    description: str = NEW_GRAD,
    active: bool = True,
    offset_hours: float | None = None,
    with_employment_type: bool = True,
) -> JobRecord:
    """Store one fictional job, optionally under an older hash formula."""

    record = JobRecord(
        source="greenhouse",
        source_account="northwind",
        external_id=external_id,
        company="Northwind Robotics",
        requisition_id=None,
        title=title,
        location="Seattle, WA",
        description=description,
        official_url=f"https://example.com/jobs/{external_id}",
        posted_at=POSTED,
        source_updated_at=None,
        employment_type=None,
        content_hash="pending",
        first_seen_at=NOW - timedelta(days=80),
        last_seen_at=NOW - timedelta(days=70),
        is_active=active,
        closed_at=None if active else NOW - timedelta(days=70),
    )
    session.add(record)
    session.flush()
    if offset_hours is None:
        record.content_hash = compute_job_content_hash(
            _to_canonical(record)
        )
    else:
        record.content_hash = old_formula_hash(
            record,
            offset_hours=offset_hours,
            with_employment_type=with_employment_type,
        )
    session.flush()
    return record


def cli_backfill(session: Session, records: list[JobRecord]) -> int:
    """Write evaluations exactly as backfill_job_evaluations --apply does."""

    candidates = []
    for record in records:
        canonical = _to_canonical(record)
        candidates.append(
            EvaluatedJob(
                job=canonical,
                observation_status=JobObservationStatus.UNCHANGED,
                eligibility=evaluate_job(canonical),
                alert_disposition=AlertDisposition.SUPPRESS,
            )
        )
    return record_job_evaluations(
        session,
        source="greenhouse",
        source_account="northwind",
        evaluated_jobs=candidates,
        evaluated_at=NOW - timedelta(hours=10),
    )


def stale_ids(session: Session) -> list[int]:
    return list(
        iter_stale_job_ids(
            session,
            rule_version=ELIGIBILITY_RULE_VERSION,
        )
    )


def as_utc(value):
    """SQLite drops the zone on reload; compare instants, not spellings."""

    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def job_rows(session: Session) -> list[tuple]:
    return [
        tuple(as_utc(getattr(record, field)) for field in JOB_FIELDS)
        for record in session.scalars(
            select(JobRecord).order_by(JobRecord.id)
        )
    ]


def stored(session: Session, job_id: int) -> JobEvaluationRecord:
    return session.get(JobEvaluationRecord, job_id)


@pytest.mark.parametrize(
    ("offset_hours", "with_employment_type"),
    [(-4, True), (-5, True), (0, False), (-4, False)],
)
def test_a_job_hashed_under_an_older_formula_stays_stale_after_the_cli_but_not_after_refresh(
    session_factory,
    offset_hours,
    with_employment_type,
) -> None:
    with session_factory.begin() as session:
        record = add_job(
            session,
            "old-hash",
            active=False,
            offset_hours=offset_hours,
            with_employment_type=with_employment_type,
        )
        assert record.content_hash != compute_job_content_hash(
            _to_canonical(record)
        )

        assert cli_backfill(session, [record]) == 1
        cached = stored(session, record.id)
        assert cached.rule_version == ELIGIBILITY_RULE_VERSION
        # The CLI decision is right but carries a hash the row never had.
        assert stale_ids(session) == [record.id]
        decision_before = {
            field: getattr(cached, field) for field in DERIVED_FIELDS
        }
        jobs_before = job_rows(session)

        assert refresh_stale_evaluations(session, evaluated_at=NOW) == 1

        assert stale_ids(session) == []
        cached = stored(session, record.id)
        assert cached.content_hash == record.content_hash
        assert as_utc(cached.evaluated_at) == NOW
        assert {
            field: getattr(cached, field) for field in DERIVED_FIELDS
        } == decision_before
        assert job_rows(session) == jobs_before


def test_missing_and_old_version_evaluations_are_rebuilt_under_the_stored_hash(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        missing = add_job(session, "missing", offset_hours=-4)
        old_version = add_job(session, "old-version")
        cli_backfill(session, [old_version])
        stored(session, old_version.id).rule_version = "2026-10-01-v50"
        stored(session, old_version.id).eligibility_status = "REJECT"
        session.flush()

        assert stale_ids(session) == [missing.id, old_version.id]
        assert refresh_stale_evaluations(session, evaluated_at=NOW) == 2
        assert stale_ids(session) == []

        for record in (missing, old_version):
            cached = stored(session, record.id)
            fresh = evaluate_job(_to_canonical(record))
            assert cached.content_hash == record.content_hash
            assert cached.rule_version == ELIGIBILITY_RULE_VERSION
            assert cached.eligibility_status == fresh.status.value == "PASS"


def test_real_blockers_still_reject_and_good_roles_still_pass(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        sponsor = add_job(
            session,
            "sponsor",
            description=NO_SPONSOR,
            offset_hours=-4,
        )
        senior = add_job(
            session,
            "senior",
            title="Senior Staff Software Engineer",
            offset_hours=-5,
        )
        good = add_job(session, "good", offset_hours=-4)
        cli_backfill(session, [sponsor, senior, good])
        assert refresh_stale_evaluations(session, evaluated_at=NOW) == 3

        sponsor_row = stored(session, sponsor.id)
        assert sponsor_row.eligibility_status == "REJECT"
        assert (
            EligibilityReasonCode.SPONSORSHIP_BLOCKER.value
            in sponsor_row.reason_codes
        )
        senior_row = stored(session, senior.id)
        assert senior_row.eligibility_status == "REJECT"
        assert (
            EligibilityReasonCode.SENIOR_TITLE.value
            in senior_row.reason_codes
        )
        assert stored(session, good.id).eligibility_status == "PASS"
        assert stale_ids(session) == []


def test_inactive_jobs_are_refreshed_without_being_reopened(
    session_factory,
) -> None:
    with session_factory.begin() as session:
        closed = add_job(session, "closed", active=False, offset_hours=-4)
        closed_at = closed.closed_at
        cli_backfill(session, [closed])

        refresh_stale_evaluations(session, evaluated_at=NOW)

        session.refresh(closed)
        assert closed.is_active is False
        assert as_utc(closed.closed_at) == closed_at
        assert stale_ids(session) == []


def test_a_current_evaluation_is_left_alone(session_factory) -> None:
    with session_factory.begin() as session:
        current = add_job(session, "current")
        cli_backfill(session, [current])
        evaluated_at = stored(session, current.id).evaluated_at

        assert stale_ids(session) == []
        assert refresh_stale_evaluations(session, evaluated_at=NOW) == 0
        assert stored(session, current.id).evaluated_at == evaluated_at


def test_limit_and_batch_size_bound_each_call(session_factory) -> None:
    with session_factory.begin() as session:
        records = [
            add_job(session, f"bounded-{index}", offset_hours=-4)
            for index in range(5)
        ]
        cli_backfill(session, records)

        assert (
            refresh_stale_evaluations(
                session,
                evaluated_at=NOW,
                batch_size=2,
                limit=3,
            )
            == 3
        )
        # Lowest ids go first, so a bounded call is predictable.
        assert stale_ids(session) == [records[3].id, records[4].id]
        assert (
            refresh_stale_evaluations(
                session,
                evaluated_at=NOW,
                batch_size=2,
                limit=3,
            )
            == 2
        )
        assert stale_ids(session) == []


def test_refresh_writes_only_job_evaluations(engine, session_factory) -> None:
    with session_factory.begin() as session:
        records = [
            add_job(session, "write-a", active=False, offset_hours=-4),
            add_job(session, "write-b", offset_hours=0, with_employment_type=False),
        ]
        cli_backfill(session, records)
        missing = add_job(session, "write-c", offset_hours=-5)
        jobs_before = job_rows(session)

    writes: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"}:
            writes.append(" ".join(statement.split()[:3]).lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with session_factory.begin() as session:
            assert refresh_stale_evaluations(session, evaluated_at=NOW) == 3
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert writes
    assert all(
        statement in {"update job_evaluations set", "insert into job_evaluations"}
        for statement in writes
    ), writes
    with session_factory() as session:
        assert job_rows(session) == jobs_before
        assert stale_ids(session) == []
        assert stored(session, missing.id) is not None
