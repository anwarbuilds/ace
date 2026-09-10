"""Persistent SQLAlchemy models for ACE.

These classes represent durable database records rather than external
ATS payloads.

CanonicalJob is the normalized application-domain representation.
JobRecord is the durable PostgreSQL representation of a discovered job.
JobSourceRecord describes an external ATS account ACE should monitor.
JobEvaluationRecord materializes the deterministic eligibility decision
for one job so the web application can filter and sort in SQL instead of
re-running the gate over every stored job on every request.
"""

from datetime import (
    date,
    datetime,
)

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy.types import JSON

from backend.app.db.base import Base


# PostgreSQL should use BIGINT for durable identifiers.
#
# SQLite only provides implicit autoincrement semantics for a column whose
# declared type is exactly INTEGER PRIMARY KEY. The variant therefore keeps
# production PostgreSQL BIGINT behavior while allowing lightweight SQLite
# repository tests to exercise normal inserts without supplying fake IDs.
BIGINT_ID = BigInteger().with_variant(
    Integer(),
    "sqlite",
)


# PostgreSQL stores structured notification payloads as JSONB.
#
# SQLite has no JSONB type, so repository-level tests fall back to the
# generic JSON type while production keeps JSONB indexing behavior.
#
# none_as_null is required. Without it SQLAlchemy stores a Python None
# as the JSON value 'null' rather than SQL NULL, which would make
# "payload IS NULL" silently match nothing and hide rows that still need
# a structured payload.
JSON_PAYLOAD = JSONB(
    none_as_null=True
).with_variant(
    JSON(
        none_as_null=True
    ),
    "sqlite",
)


class JobRecord(Base):
    """Persistent representation of a job discovered by ACE."""

    __tablename__ = "jobs"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_account",
            "external_id",
            name="uq_jobs_source_identity",
        ),
        Index(
            "ix_jobs_first_seen_at",
            "first_seen_at",
        ),
        Index(
            "ix_jobs_company",
            "company",
        ),
        Index(
            "ix_jobs_is_active",
            "is_active",
        ),
        Index(
            "ix_jobs_first_seen_session",
            "first_seen_session_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Workday uses the posting URL path as its identity, and those embed
    # the location and full title. One Target path reached 256
    # characters and failed a whole poll at the old 255 limit.
    external_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    requisition_id: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    location: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    official_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Only a handful of providers expose this at all -- None means the
    # source never said, never "full-time assumed". Added after a real
    # Vestwell posting and a real T-Mobile posting both passed the
    # gate stating "contract" through Adzuna's own structured field,
    # which was being read and then dropped before it reached storage.
    employment_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # The discovery run that first saw this job, so the web application
    # can group new arrivals into readable batches instead of one long
    # undifferentiated list.
    first_seen_session_id: Mapped[int | None] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "poll_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


class SourceState(Base):
    """Persistent state for one external ATS source account."""

    __tablename__ = "source_states"

    source: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    initialized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_success_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_job_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # HTTP validators from the last successful fetch. Sending these back
    # lets an unchanged board answer 304 with no body, skipping the
    # download, the parse and the diff entirely.
    http_etag: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    http_last_modified: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_unchanged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # When this source was last fetched unconditionally. A provider
    # returning a stale validator could otherwise keep answering 304
    # forever, and ACE would go quietly out of date.
    last_full_fetch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class JobSourceRecord(Base):
    """Persistent external job source monitored by ACE.

    Company name is descriptive provenance metadata.

    Source identity is:

        source_type + source_account

    Company identity must never determine job eligibility.
    """

    __tablename__ = "job_sources"

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_account",
            name=(
                "uq_job_sources_"
                "source_identity"
            ),
        ),
        CheckConstraint(
            "poll_interval_seconds > 0",
            name=(
                "ck_job_sources_"
                "poll_interval_positive"
            ),
        ),
        Index(
            "ix_job_sources_enabled",
            "enabled",
            "source_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_account: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_host: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="300",
    )

    discovery_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobEvaluationRecord(Base):
    """Materialized eligibility decision for one persisted job.

    Eligibility is a pure function of a job's normalized content, so the
    decision is cached rather than recomputed per request.

    ``content_hash`` records exactly which version of the job was
    evaluated, and ``rule_version`` records which gate produced it.
    Together they make a stale evaluation detectable instead of silently
    wrong after the job changes or the rules do.

    This table is derived data. It can be dropped and rebuilt from the
    jobs table at any time, which is why eligibility deliberately does
    not live on JobRecord itself.
    """

    __tablename__ = "job_evaluations"

    __table_args__ = (
        Index(
            (
                "ix_job_evaluations_"
                "status"
            ),
            "eligibility_status",
        ),
        Index(
            (
                "ix_job_evaluations_"
                "family_priority"
            ),
            "role_family",
            "role_priority",
        ),
        Index(
            (
                "ix_job_evaluations_"
                "early_career"
            ),
            "is_early_career",
        ),
        Index(
            (
                "ix_job_evaluations_"
                "verified"
            ),
            "requirements_verified",
        ),
    )

    job_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "jobs.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
    )

    eligibility_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    role_family: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    role_priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    rule_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reason_codes: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    reasons: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    required_experience_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # True when the posting explicitly presents itself as a new-grad or
    # early-career role. Informational: it orders the queue, it never
    # excludes, because unlabelled roles are frequently open to grads.
    is_early_career: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # False when the posting text was unavailable, so the rules reading
    # requirement text never ran. Such jobs stay in the web application
    # but are not emailed as ready to apply.
    requirements_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ResumeRecord(Base):
    """One uploaded resume.

    Only one resume is active at a time. History is retained so a score
    change can be attributed to a resume edit rather than to a change in
    the job market.
    """

    __tablename__ = "resumes"

    __table_args__ = (
        Index(
            "ix_resumes_active",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    extracted_skills: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobResumeScoreRecord(Base):
    """One posting scored against one resume.

    Derived data: it can be rebuilt from the resume and the job corpus,
    which is what makes re-scoring after a resume edit cheap.
    """

    __tablename__ = "job_resume_scores"

    __table_args__ = (
        Index(
            "ix_job_resume_scores_resume",
            "resume_id",
            "score",
        ),
    )

    job_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "jobs.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
    )

    resume_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "resumes.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
    )

    # Null when the posting carried too little signal to rank. An
    # unscored posting is not a badly-matching one.
    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    matched_skills: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    missing_skills: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    # Requirements earned at the partial rate, by way of a related skill
    # on the resume rather than the skill itself.
    related_skills: Mapped[dict | None] = mapped_column(
        JSON_PAYLOAD,
        nullable=True,
    )

    # What this posting scored before the last re-score. Null means it
    # has never been scored before, which is not the same as unchanged.
    previous_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Which scoring algorithm produced this row. Scores are derived data
    # with no other staleness signal, so without this a stored number
    # could reflect rules that no longer exist.
    algorithm_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PollSessionRecord(Base):
    """One discovery run: a batch of newly found jobs.

    Not one row per scheduler cycle. Most cycles poll a single source
    and find nothing, so cycle-level rows would be noise. A session is
    opened when a cycle discovers new jobs and extended while further
    discoveries arrive close behind it, which produces the grouping a
    person means by "this morning's pull".
    """

    __tablename__ = "poll_sessions"

    __table_args__ = (
        Index(
            "ix_poll_sessions_started",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    jobs_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    qualifying_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )


class JobMarkRecord(Base):
    """One person's standing judgement about one job.

    Unlike evaluations and scores, these cannot be recomputed. They are
    entered by hand, so they are authoritative rather than derived and
    must never be rebuilt or discarded by a re-score.
    """

    __tablename__ = "job_marks"

    __table_args__ = (
        CheckConstraint(
            "review_state IS NULL OR "
            "review_state IN "
            "('reviewed', 'dismissed')",
            name=(
                "ck_job_marks_"
                "review_state_valid"
            ),
        ),
        Index(
            "ix_job_marks_saved",
            "is_saved",
        ),
        Index(
            "ix_job_marks_review_state",
            "review_state",
        ),
    )

    job_id: Mapped[int] = mapped_column(
        BIGINT_ID,
        ForeignKey(
            "jobs.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
    )

    is_saved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # "reviewed" or "dismissed". One column rather than two booleans
    # because both mean "handled" and a job cannot be each at once.
    review_state: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Where the application stands now. Separate from applied_at, which
    # records when it was sent and never moves, because a rejection
    # must not overwrite the date it was applied.
    application_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )

    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ExternalApplicationRecord(Base):
    """An application to a posting ACE never stored.

    ACE's corpus starts the day it began watching, so an application
    sent earlier, to a posting that has since closed, has nothing to
    attach to. These rows keep that history rather than discarding it,
    which is what stops the Applied page from being a record of what
    ACE happened to witness instead of where the user actually applied.

    They are never matched to a job. If ACE later discovers the same
    role reposted, that is a different opening.
    """

    __tablename__ = "external_applications"

    __table_args__ = (
        UniqueConstraint(
            "match_key",
            name=(
                "uq_external_applications_"
                "match_key"
            ),
        ),
        Index(
            "ix_external_applications_status",
            "application_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Normalised company and title. Stored so the unique constraint can
    # enforce that re-importing a sheet updates rather than duplicates.
    match_key: Mapped[str] = mapped_column(
        String(600),
        nullable=False,
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    application_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
    )

    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ApplicationAnswerRecord(Base):
    """One answer the user gives on most application forms.

    Label and value are free-form because no fixed schema survives
    contact with real forms: one asks for a portfolio, the next for a
    Dribbble, the next for "tell us something surprising".
    """

    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    label: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HistoryEntryRecord(Base):
    """One job or one degree, for the repeating blocks forms ask for.

    The answer bank cannot hold these. It is one value per question,
    and a work history is several of the same question over again:
    employer, title, dates and description, then a Remove link and
    another identical block underneath. Real Workday and Oracle forms
    ask for three or four.

    Work and study share a table because they share a shape. The
    columns are named for the job case and reused for the degree case
    (``employer`` holds the school, ``job_title`` the degree), which is
    a small dishonesty in the names bought in exchange for one set of
    date handling, one ordering rule and one extension code path. The
    alternative was two tables differing only in two column names.

    Dates are stored as a month and a year rather than a date. That is
    what the forms ask for -- two dropdowns, never a day -- and storing
    a real date would mean inventing a day that no form will ever show
    and no user ever typed.
    """

    __tablename__ = "history_entries"

    __table_args__ = (
        Index(
            "ix_history_entries_kind_order",
            "kind",
            "sort_order",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT_ID,
        primary_key=True,
        autoincrement=True,
    )

    # "work" or "education".
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Most recent first, which is the order every one of these forms
    # lists its blocks in.
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    employer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="",
    )

    job_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="",
    )

    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="",
    )

    # Whether this is the role or course the user is still in. Forms
    # ask it as a Yes/No beside the dates, and answering it wrong is
    # what makes an end date required or forbidden.
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    start_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    start_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

