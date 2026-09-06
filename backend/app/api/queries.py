"""Read-model queries for the ACE web application.

The web application is a read surface over the same PostgreSQL data the
scheduler writes. It never fetches from an ATS, never evaluates
eligibility inline, and never sends email.

Eligibility is read from the materialized job_evaluations table, so
filtering and sorting happen in SQL rather than by loading the whole
corpus into Python.
"""

from collections.abc import Sequence
from dataclasses import (
    dataclass,
    replace,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import (
    Select,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
    PollSessionRecord,
    SourceState,
)


DEFAULT_PAGE_SIZE = 50

MAX_PAGE_SIZE = 200


# A surfaced job means "apply to this". The gate is binary, so the
# qualifying set is exactly PASS. STRETCH remains readable for rows
# evaluated under an older rule version.
ALERTABLE_STATUSES = (
    "PASS",
    "STRETCH",
)

QUALIFYING_STATUSES = (
    "PASS",
)


SORT_OPTIONS = (
    "best_match",
    "new_grad_first",
    "newest",
    "oldest",
    "recently_posted",
    "company",
    "title",
)


@dataclass(
    frozen=True,
    slots=True,
)
class JobFilters:
    """User-selected constraints for a job listing."""

    statuses: tuple[str, ...] = (
        QUALIFYING_STATUSES
    )

    families: tuple[str, ...] = ()

    priorities: tuple[str, ...] = ()

    companies: tuple[str, ...] = ()

    sources: tuple[str, ...] = ()

    search: str | None = None

    max_age_days: int | None = None

    active_only: bool = True

    early_career_only: bool = False

    verified_only: bool = False

    resume_id: int | None = None

    session_id: int | None = None

    min_match: int | None = None

    sort: str = "new_grad_first"

    limit: int = DEFAULT_PAGE_SIZE

    offset: int = 0


@dataclass(
    frozen=True,
    slots=True,
)
class JobListing:
    """One job as presented by the web application."""

    id: int

    company: str

    title: str

    location: str

    official_url: str

    source: str

    source_account: str

    external_id: str

    requisition_id: str | None

    eligibility_status: str

    role_family: str

    role_priority: str

    reasons: tuple[str, ...]

    required_experience_years: int | None

    posted_at: datetime | None

    first_seen_at: datetime

    last_seen_at: datetime

    is_active: bool

    closed_at: datetime | None

    posting_age_days: int | None

    first_seen_session_id: int | None = None

    is_early_career: bool = False

    requirements_verified: bool = True

    match_score: int | None = None

    matched_skills: tuple[str, ...] = ()

    missing_skills: tuple[str, ...] = ()

    # Requirements the resume covers by a related skill rather than by
    # name. Kept apart from matched so the UI can show partial credit
    # as partial rather than overstating the fit.
    related_skills: tuple[str, ...] = ()


@dataclass(
    frozen=True,
    slots=True,
)
class JobPage:
    """One page of job listings."""

    items: tuple[JobListing, ...]

    total: int

    limit: int

    offset: int

    @property
    def has_more(self) -> bool:
        """Return whether further pages exist."""

        return (
            self.offset
            + len(self.items)
        ) < self.total


def _as_utc(
    value: datetime | None,
) -> datetime | None:
    """Normalize a stored timestamp to aware UTC."""

    if value is None:
        return None

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _posting_age_days(
    posted_at: datetime | None,
    *,
    now: datetime,
) -> int | None:
    """Return whole days since a posting was published."""

    normalized = _as_utc(
        posted_at
    )

    if normalized is None:
        return None

    return max(
        0,
        (
            now - normalized
        ).days,
    )


def _string_list(
    value,
) -> tuple[str, ...]:
    """Coerce stored JSON list data into a tuple of strings."""

    if not isinstance(
        value,
        list,
    ):
        return ()

    return tuple(
        str(item)
        for item in value
        if str(item).strip()
    )


def _apply_filters(
    statement: Select,
    filters: JobFilters,
    *,
    now: datetime,
) -> Select:
    """Apply user filters to a job query."""

    if filters.active_only:
        statement = statement.where(
            JobRecord.is_active.is_(
                True
            )
        )

    if filters.statuses:
        statement = statement.where(
            JobEvaluationRecord
            .eligibility_status.in_(
                filters.statuses
            )
        )

    if filters.families:
        statement = statement.where(
            JobEvaluationRecord
            .role_family.in_(
                filters.families
            )
        )

    if filters.priorities:
        statement = statement.where(
            JobEvaluationRecord
            .role_priority.in_(
                filters.priorities
            )
        )

    if filters.companies:
        statement = statement.where(
            JobRecord.company.in_(
                filters.companies
            )
        )

    if filters.sources:
        statement = statement.where(
            JobRecord.source.in_(
                filters.sources
            )
        )

    if filters.session_id is not None:
        statement = statement.where(
            JobRecord.first_seen_session_id
            == filters.session_id
        )

    if filters.min_match is not None:
        statement = statement.where(
            JobResumeScoreRecord.score
            >= filters.min_match
        )

    if filters.verified_only:
        statement = statement.where(
            JobEvaluationRecord
            .requirements_verified.is_(
                True
            )
        )

    if filters.early_career_only:
        statement = statement.where(
            JobEvaluationRecord
            .is_early_career.is_(True)
        )

    if filters.max_age_days is not None:
        cutoff = now - timedelta(
            days=filters.max_age_days
        )

        # An unknown posting date is never claimed to be recent.
        statement = statement.where(
            JobRecord.posted_at.is_not(
                None
            ),
            JobRecord.posted_at >= cutoff,
        )

    search = (
        filters.search or ""
    ).strip()

    if search:
        pattern = f"%{search}%"

        statement = statement.where(
            or_(
                JobRecord.title.ilike(
                    pattern
                ),
                JobRecord.company.ilike(
                    pattern
                ),
                JobRecord.location.ilike(
                    pattern
                ),
            )
        )

    return statement


def _apply_sort(
    statement: Select,
    sort: str,
) -> Select:
    """Apply a deterministic ordering to a job query."""

    if sort == "best_match":
        # Highest match first. Unscored postings sort last rather than
        # as zero: ACE could not read them, which is not the same as a
        # poor fit.
        return statement.order_by(
            JobResumeScoreRecord.score.desc()
            .nullslast(),
            JobRecord.posted_at.desc()
            .nullslast(),
            JobRecord.id.desc(),
        )

    if sort == "new_grad_first":
        # Verified postings lead, then labelled new-grad, then freshest.
        # An unverified posting is a lead to check, not a result.
        return statement.order_by(
            JobEvaluationRecord
            .requirements_verified.desc(),
            JobEvaluationRecord
            .is_early_career.desc(),
            JobRecord.posted_at.desc()
            .nullslast(),
            JobRecord.id.desc(),
        )

    if sort == "oldest":
        return statement.order_by(
            JobRecord.first_seen_at.asc(),
            JobRecord.id.asc(),
        )

    if sort == "recently_posted":
        return statement.order_by(
            JobRecord.posted_at.desc()
            .nullslast(),
            JobRecord.id.desc(),
        )

    if sort == "company":
        return statement.order_by(
            JobRecord.company.asc(),
            JobRecord.title.asc(),
            JobRecord.id.asc(),
        )

    if sort == "title":
        return statement.order_by(
            JobRecord.title.asc(),
            JobRecord.company.asc(),
            JobRecord.id.asc(),
        )

    return statement.order_by(
        JobRecord.first_seen_at.desc(),
        JobRecord.id.desc(),
    )


def list_jobs(
    session: Session,
    *,
    filters: JobFilters,
    now: datetime | None = None,
) -> JobPage:
    """Return one filtered, ordered page of jobs."""

    reference_time = (
        _as_utc(
            now
        )
        or datetime.now(
            timezone.utc
        )
    )

    limit = max(
        1,
        min(
            filters.limit,
            MAX_PAGE_SIZE,
        ),
    )

    offset = max(
        0,
        filters.offset,
    )

    base = (
        select(
            JobRecord,
            JobEvaluationRecord,
            JobResumeScoreRecord,
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .outerjoin(
            JobResumeScoreRecord,
            (
                JobResumeScoreRecord.job_id
                == JobRecord.id
            )
            & (
                JobResumeScoreRecord
                .resume_id
                == filters.resume_id
            ),
        )
    )

    filtered = _apply_filters(
        base,
        filters,
        now=reference_time,
    )

    total = session.scalar(
        select(
            func.count()
        ).select_from(
            _apply_filters(
                select(
                    JobRecord.id
                ).join(
                    JobEvaluationRecord,
                    JobEvaluationRecord.job_id
                    == JobRecord.id,
                ),
                filters,
                now=reference_time,
            ).subquery()
        )
    )

    rows = session.execute(
        _apply_sort(
            filtered,
            filters.sort,
        )
        .limit(
            limit
        )
        .offset(
            offset
        )
    ).all()

    items = tuple(
        JobListing(
            id=job.id,
            company=job.company,
            title=job.title,
            location=job.location,
            official_url=(
                job.official_url
            ),
            source=job.source,
            source_account=(
                job.source_account
            ),
            external_id=(
                job.external_id
            ),
            requisition_id=(
                job.requisition_id
            ),
            eligibility_status=(
                evaluation
                .eligibility_status
            ),
            role_family=(
                evaluation.role_family
            ),
            role_priority=(
                evaluation.role_priority
            ),
            reasons=_string_list(
                evaluation.reasons
            ),
            required_experience_years=(
                evaluation
                .required_experience_years
            ),
            posted_at=_as_utc(
                job.posted_at
            ),
            first_seen_at=_as_utc(
                job.first_seen_at
            ),
            last_seen_at=_as_utc(
                job.last_seen_at
            ),
            is_active=job.is_active,
            closed_at=_as_utc(
                job.closed_at
            ),
            posting_age_days=(
                _posting_age_days(
                    job.posted_at,
                    now=reference_time,
                )
            ),
            first_seen_session_id=(
                job.first_seen_session_id
            ),
            is_early_career=bool(
                evaluation.is_early_career
            ),
            requirements_verified=bool(
                evaluation
                .requirements_verified
            ),
            match_score=(
                None
                if match is None
                else match.score
            ),
            matched_skills=(
                ()
                if match is None
                else tuple(
                    match.matched_skills
                    or ()
                )
            ),
            missing_skills=(
                ()
                if match is None
                else tuple(
                    match.missing_skills
                    or ()
                )
            ),
            related_skills=(
                ()
                if match is None
                else tuple(
                    match.related_skills
                    or ()
                )
            ),
        )
        for job, evaluation, match in rows
    )

    return JobPage(
        items=items,
        total=int(
            total or 0
        ),
        limit=limit,
        offset=offset,
    )


def count_by(
    session: Session,
    column,
    *,
    active_only: bool = True,
    statuses: Sequence[str] = (
        QUALIFYING_STATUSES
    ),
) -> list[tuple[str, int]]:
    """Return counts grouped by one column, largest first."""

    statement = (
        select(
            column,
            func.count(),
        )
        .select_from(
            JobRecord
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id
            == JobRecord.id,
        )
        .group_by(
            column
        )
        .order_by(
            func.count().desc(),
            column.asc(),
        )
    )

    if active_only:
        statement = statement.where(
            JobRecord.is_active.is_(
                True
            )
        )

    if statuses:
        statement = statement.where(
            JobEvaluationRecord
            .eligibility_status.in_(
                tuple(
                    statuses
                )
            )
        )

    return [
        (
            str(
                value
            ),
            int(
                count
            ),
        )
        for value, count
        in session.execute(
            statement
        ).all()
    ]


def build_stats(
    session: Session,
    *,
    filters: JobFilters | None = None,
    now: datetime | None = None,
) -> dict:
    """Return headline counts for the dashboard.

    Every figure honours the caller's filters, so the headline total
    always equals the number of rows on screen. Tiles that answer a
    different question than the list are worse than no tiles: they read
    as a promise that jobs are being withheld.
    """

    reference_time = (
        _as_utc(
            now
        )
        or datetime.now(
            timezone.utc
        )
    )

    active_filters = (
        filters
        if filters is not None
        else JobFilters()
    )

    def _qualifying_count(
        *,
        max_age_days: int | None = None,
        early_career_only: bool = False,
        verified_only: bool = False,
    ) -> int:
        """Count gate-passing jobs under the caller's filters."""

        # Start from the user's own selection, then narrow further for
        # the specific tile being computed.
        tile_filters = replace(
            active_filters,
            max_age_days=(
                max_age_days
                if max_age_days is not None
                else (
                    active_filters
                    .max_age_days
                )
            ),
            early_career_only=(
                early_career_only
                or active_filters
                .early_career_only
            ),
            verified_only=(
                verified_only
                or active_filters
                .verified_only
            ),
        )

        statement = _apply_filters(
            select(
                JobRecord.id
            ).join(
                JobEvaluationRecord,
                JobEvaluationRecord.job_id
                == JobRecord.id,
            ),
            tile_filters,
            now=reference_time,
        )

        return int(
            session.scalar(
                select(
                    func.count()
                ).select_from(
                    statement.subquery()
                )
            )
            or 0
        )

    qualifying = _qualifying_count()

    posted_today = _qualifying_count(
        max_age_days=1
    )

    fresh = _qualifying_count(
        max_age_days=7
    )

    labelled_new_grad = (
        _qualifying_count(
            early_career_only=True
        )
    )

    verified = _qualifying_count(
        verified_only=True
    )

    return {
        # Every figure here describes the apply-ready queue. Corpus
        # size is deliberately absent: this page exists to show what to
        # apply to, and a 15,000-row total only invites the question of
        # why those rows are not on screen.
        "posted_today": posted_today,
        "posted_last_7_days": fresh,
        "labelled_new_grad": (
            labelled_new_grad
        ),
        "verified_jobs": verified,
        "qualifying_active_jobs": (
            qualifying
        ),
        "generated_at": (
            reference_time.isoformat()
        ),
    }


def build_facets(
    session: Session,
) -> dict:
    """Return the filter options the UI should offer."""

    return {
        "families": [
            {
                "value": value,
                "count": count,
            }
            for value, count in count_by(
                session,
                JobEvaluationRecord
                .role_family,
            )
        ],
        "priorities": [
            {
                "value": value,
                "count": count,
            }
            for value, count in count_by(
                session,
                JobEvaluationRecord
                .role_priority,
            )
        ],
        "companies": [
            {
                "value": value,
                "count": count,
            }
            for value, count in count_by(
                session,
                JobRecord.company,
            )
        ],
        "sources": [
            {
                "value": value,
                "count": count,
            }
            for value, count in count_by(
                session,
                JobRecord.source,
            )
        ],
        "statuses": [
            "PASS",
            "REJECT",
        ],
        "sorts": list(
            SORT_OPTIONS
        ),
    }


def last_poll_completed_at(
    session: Session,
) -> datetime | None:
    """Return when ACE last successfully checked any source.

    Read from source state rather than from discovery runs: a poll that
    found nothing is still a poll, and answering "when did you last
    look" with the last time something turned up would be misleading.
    """

    latest = session.scalar(
        select(
            func.max(
                SourceState.last_success_at
            )
        )
    )

    return _as_utc(
        latest
    )


def list_discovery_runs(
    session: Session,
    *,
    limit: int = 20,
    now: datetime | None = None,
) -> list[dict]:
    """Return recent discovery runs, newest first.

    Only runs that actually found something exist, so this is a history
    of arrivals rather than a log of scheduler activity.
    """

    reference = (
        _as_utc(
            now
        )
        or datetime.now(
            timezone.utc
        )
    )

    rows = session.scalars(
        select(
            PollSessionRecord
        )
        .order_by(
            PollSessionRecord
            .last_activity_at.desc()
        )
        .limit(
            max(
                1,
                min(
                    limit,
                    100,
                ),
            )
        )
    ).all()

    runs: list[dict] = []

    for row in rows:
        started = _as_utc(
            row.started_at
        )

        finished = _as_utc(
            row.last_activity_at
        )

        # Count what is still open and qualifying now, which is what the
        # user can actually act on -- the stored count is a record of
        # what arrived, including jobs since closed.
        open_qualifying = session.scalar(
            select(
                func.count()
            )
            .select_from(
                JobRecord
            )
            .join(
                JobEvaluationRecord,
                JobEvaluationRecord.job_id
                == JobRecord.id,
            )
            .where(
                JobRecord
                .first_seen_session_id
                == row.id,
                JobRecord.is_active.is_(
                    True
                ),
                JobEvaluationRecord
                .eligibility_status.in_(
                    QUALIFYING_STATUSES
                ),
            )
        )

        runs.append(
            {
                "id": row.id,
                "started_at": (
                    None
                    if started is None
                    else started.isoformat()
                ),
                "finished_at": (
                    None
                    if finished is None
                    else finished.isoformat()
                ),
                "jobs_discovered": (
                    row.jobs_discovered
                ),
                "qualifying_discovered": (
                    row.qualifying_discovered
                ),
                "qualifying_open_now": int(
                    open_qualifying or 0
                ),
                "age_seconds": (
                    None
                    if finished is None
                    else int(
                        (
                            reference
                            - finished
                        ).total_seconds()
                    )
                ),
            }
        )

    return runs
