"""FastAPI read application for ACE.

This service is deliberately read-only over the database the scheduler
writes.

It does not fetch from any ATS, does not evaluate eligibility inline,
and does not send email. Those responsibilities stay with the scheduler
and the notification worker, so the web application cannot become a
second, divergent source of truth.
"""

from collections.abc import Iterator
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    Query,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.queries import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SORT_OPTIONS,
    JobFilters,
    build_facets,
    build_stats,
    list_jobs,
)
from backend.app.db.session import SessionLocal


STATIC_DIRECTORY = (
    Path(
        __file__
    ).parent
    / "static"
)


def get_session() -> Iterator[Session]:
    """Provide one request-scoped read session."""

    with SessionLocal() as session:
        yield session


def _split_csv(
    value: str | None,
) -> tuple[str, ...]:
    """Parse a comma-separated query parameter."""

    if not value:
        return ()

    return tuple(
        item.strip()
        for item in value.split(
            ","
        )
        if item.strip()
    )


def _serialize_job(
    job,
) -> dict:
    """Render one job listing as JSON."""

    return {
        "id": job.id,
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "official_url": (
            job.official_url
        ),
        "source": job.source,
        "source_account": (
            job.source_account
        ),
        "external_id": (
            job.external_id
        ),
        "requisition_id": (
            job.requisition_id
        ),
        "eligibility_status": (
            job.eligibility_status
        ),
        "role_family": (
            job.role_family
        ),
        "role_priority": (
            job.role_priority
        ),
        "reasons": list(
            job.reasons
        ),
        "required_experience_years": (
            job.required_experience_years
        ),
        "posted_at": (
            None
            if job.posted_at is None
            else job.posted_at.isoformat()
        ),
        "first_seen_at": (
            job.first_seen_at.isoformat()
        ),
        "last_seen_at": (
            job.last_seen_at.isoformat()
        ),
        "is_active": job.is_active,
        "closed_at": (
            None
            if job.closed_at is None
            else job.closed_at.isoformat()
        ),
        "posting_age_days": (
            job.posting_age_days
        ),
    }


def create_app() -> FastAPI:
    """Build the ACE web application."""

    app = FastAPI(
        title="ACE",
        description=(
            "Personal career-intelligence "
            "read model."
        ),
        version="1.0.0",
    )

    @app.get(
        "/healthz"
    )
    def healthz(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Report service and database health."""

        session.execute(
            text(
                "SELECT 1"
            )
        )

        return {
            "status": "ok",
            "checked_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    @app.get(
        "/api/jobs"
    )
    def get_jobs(
        session: Session = Depends(
            get_session
        ),
        status: str | None = Query(
            default="PASS,STRETCH",
            description=(
                "Comma-separated "
                "eligibility statuses."
            ),
        ),
        family: str | None = Query(
            default=None,
            description=(
                "Comma-separated role "
                "families."
            ),
        ),
        priority: str | None = Query(
            default=None,
            description=(
                "Comma-separated role "
                "priorities."
            ),
        ),
        company: str | None = Query(
            default=None,
            description=(
                "Comma-separated company "
                "names."
            ),
        ),
        source: str | None = Query(
            default=None,
            description=(
                "Comma-separated ATS "
                "providers."
            ),
        ),
        q: str | None = Query(
            default=None,
            description=(
                "Free-text search over "
                "title, company, location."
            ),
        ),
        max_age_days: int | None = Query(
            default=None,
            ge=1,
            le=3650,
            description=(
                "Only jobs posted within "
                "this many days."
            ),
        ),
        active_only: bool = Query(
            default=True,
        ),
        sort: str = Query(
            default="newest",
        ),
        limit: int = Query(
            default=DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
        ),
        offset: int = Query(
            default=0,
            ge=0,
        ),
    ) -> dict:
        """Return one filtered page of jobs."""

        normalized_sort = (
            sort
            if sort in SORT_OPTIONS
            else "newest"
        )

        page = list_jobs(
            session,
            filters=JobFilters(
                statuses=_split_csv(
                    status
                ),
                families=_split_csv(
                    family
                ),
                priorities=_split_csv(
                    priority
                ),
                companies=_split_csv(
                    company
                ),
                sources=_split_csv(
                    source
                ),
                search=q,
                max_age_days=(
                    max_age_days
                ),
                active_only=active_only,
                sort=normalized_sort,
                limit=limit,
                offset=offset,
            ),
        )

        return {
            "items": [
                _serialize_job(
                    job
                )
                for job in page.items
            ],
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.has_more,
            "sort": normalized_sort,
        }

    @app.get(
        "/api/stats"
    )
    def get_stats(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Return headline dashboard counts."""

        return build_stats(
            session
        )

    @app.get(
        "/api/facets"
    )
    def get_facets(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Return available filter options."""

        return build_facets(
            session
        )

    if STATIC_DIRECTORY.is_dir():
        @app.get(
            "/"
        )
        def index() -> FileResponse:
            """Serve the single-page application."""

            return FileResponse(
                STATIC_DIRECTORY
                / "index.html"
            )

        app.mount(
            "/static",
            StaticFiles(
                directory=(
                    STATIC_DIRECTORY
                )
            ),
            name="static",
        )

    return app


app = create_app()
