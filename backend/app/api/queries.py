"""Read-model queries for the ACE web application.

The web application is a read surface over the same PostgreSQL data the
scheduler writes. It never fetches from an ATS, never evaluates
eligibility inline, and never sends email.

Eligibility is read from the materialized job_evaluations table, so
filtering and sorting happen in SQL rather than by loading the whole
corpus into Python.
"""

from collections.abc import Sequence
from dataclasses import dataclass
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
)


DEFAULT_PAGE_SIZE = 50

MAX_PAGE_SIZE = 200


ALERTABLE_STATUSES = (
    "PASS",
    "STRETCH",
)


SORT_OPTIONS = (
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
        ALERTABLE_STATUSES
    )

    families: tuple[str, ...] = ()

    priorities: tuple[str, ...] = ()

    companies: tuple[str, ...] = ()

    sources: tuple[str, ...] = ()

    search: str | None = None

    max_age_days: int | None = None

    active_only: bool = True

    sort: str = "newest"

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

    base = select(
        JobRecord,
        JobEvaluationRecord,
    ).join(
        JobEvaluationRecord,
        JobEvaluationRecord.job_id
        == JobRecord.id,
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
        )
        for job, evaluation in rows
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
        ALERTABLE_STATUSES
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
    now: datetime | None = None,
) -> dict:
    """Return headline counts for the dashboard."""

    reference_time = (
        _as_utc(
            now
        )
        or datetime.now(
            timezone.utc
        )
    )

    total_jobs = session.scalar(
        select(
            func.count()
        ).select_from(
            JobRecord
        )
    )

    active_jobs = session.scalar(
        select(
            func.count()
        )
        .select_from(
            JobRecord
        )
        .where(
            JobRecord.is_active.is_(
                True
            )
        )
    )

    evaluated_jobs = session.scalar(
        select(
            func.count()
        ).select_from(
            JobEvaluationRecord
        )
    )

    by_status = dict(
        count_by(
            session,
            JobEvaluationRecord
            .eligibility_status,
            statuses=(),
        )
    )

    qualifying = session.scalar(
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
            JobRecord.is_active.is_(
                True
            ),
            JobEvaluationRecord
            .eligibility_status.in_(
                ALERTABLE_STATUSES
            ),
        )
    )

    fresh_cutoff = (
        reference_time
        - timedelta(
            days=7
        )
    )

    fresh = session.scalar(
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
            JobRecord.is_active.is_(
                True
            ),
            JobEvaluationRecord
            .eligibility_status.in_(
                ALERTABLE_STATUSES
            ),
            JobRecord.posted_at.is_not(
                None
            ),
            JobRecord.posted_at
            >= fresh_cutoff,
        )
    )

    return {
        "total_jobs": int(
            total_jobs or 0
        ),
        "active_jobs": int(
            active_jobs or 0
        ),
        "evaluated_jobs": int(
            evaluated_jobs or 0
        ),
        "qualifying_active_jobs": int(
            qualifying or 0
        ),
        "posted_last_7_days": int(
            fresh or 0
        ),
        "by_eligibility": by_status,
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
        "statuses": list(
            ALERTABLE_STATUSES
        )
        + [
            "REJECT",
        ],
        "sorts": list(
            SORT_OPTIONS
        ),
    }
