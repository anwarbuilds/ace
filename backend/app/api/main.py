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
    File,
    HTTPException,
    Query,
    UploadFile,
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
    last_poll_completed_at,
    list_discovery_runs,
    list_jobs,
)
from backend.app.db.session import SessionLocal
from backend.app.matching.parsing import (
    ResumeParseError,
    extract_resume_text,
)
from backend.app.matching.service import (
    get_active_resume,
    rescore_corpus,
    skills_gap,
    store_resume,
)


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
        "first_seen_session_id": (
            job.first_seen_session_id
        ),
        "is_early_career": (
            job.is_early_career
        ),
        "requirements_verified": (
            job.requirements_verified
        ),
        "match_score": job.match_score,
        "matched_skills": list(
            job.matched_skills
        ),
        "missing_skills": list(
            job.missing_skills
        ),
        "related_skills": list(
            job.related_skills
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
            default="PASS",
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
        early_career_only: bool = Query(
            default=False,
            description=(
                "Only postings that "
                "explicitly present as "
                "new-grad roles."
            ),
        ),
        verified_only: bool = Query(
            default=False,
            description=(
                "Only postings whose "
                "requirements ACE could "
                "actually read."
            ),
        ),
        session_id: int | None = Query(
            default=None,
            description=(
                "Only jobs first found in "
                "this discovery run."
            ),
        ),
        since: datetime | None = Query(
            default=None,
            description=(
                "Only jobs first seen after this "
                "instant, for new since last visit."
            ),
        ),
        min_match: int | None = Query(
            default=None,
            ge=0,
            le=100,
            description=(
                "Hide postings scoring "
                "below this against the "
                "active resume."
            ),
        ),
        sort: str = Query(
            default="new_grad_first",
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
            else "new_grad_first"
        )

        resume = get_active_resume(
            session
        )

        resume_id = (
            None
            if resume is None
            else resume.id
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
                early_career_only=(
                    early_career_only
                ),
                verified_only=verified_only,
                resume_id=resume_id,
                session_id=session_id,
                min_match=min_match,
                since=since,
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
            "resume_id": resume_id,
        }

    @app.get(
        "/api/stats"
    )
    def get_stats(
        session: Session = Depends(
            get_session
        ),
        family: str | None = Query(
            default=None,
        ),
        company: str | None = Query(
            default=None,
        ),
        source: str | None = Query(
            default=None,
        ),
        q: str | None = Query(
            default=None,
        ),
        max_age_days: int | None = Query(
            default=None,
            ge=1,
            le=3650,
        ),
        active_only: bool = Query(
            default=True,
        ),
        early_career_only: bool = Query(
            default=False,
        ),
        verified_only: bool = Query(
            default=False,
        ),
    ) -> dict:
        """Return headline counts for the current filter selection.

        The same filters as /api/jobs are accepted so the headline total
        always equals the number of rows the user is looking at.
        """

        active_resume = (
            get_active_resume(
                session
            )
        )

        stats = build_stats(
            session,
            filters=JobFilters(
                resume_id=(
                    None
                    if active_resume is None
                    else active_resume.id
                ),
                families=_split_csv(
                    family
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
                early_career_only=(
                    early_career_only
                ),
                verified_only=verified_only,
            ),
        )

        last_poll = (
            last_poll_completed_at(
                session
            )
        )

        stats["last_poll_at"] = (
            None
            if last_poll is None
            else last_poll.isoformat()
        )

        return stats

    @app.get(
        "/api/sessions"
    )
    def get_sessions(
        session: Session = Depends(
            get_session
        ),
        limit: int = Query(
            default=20,
            ge=1,
            le=100,
        ),
    ) -> dict:
        """Return recent discovery runs and when ACE last checked.

        Runs exist only where something was actually found, so this is a
        history of arrivals rather than a log of scheduler activity.
        The last-checked time is separate, because a poll that found
        nothing is still a poll.
        """

        last_poll = (
            last_poll_completed_at(
                session
            )
        )

        return {
            "last_poll_at": (
                None
                if last_poll is None
                else last_poll.isoformat()
            ),
            "sessions": (
                list_discovery_runs(
                    session,
                    limit=limit,
                )
            ),
        }

    @app.get(
        "/api/resume"
    )
    def get_resume(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Return the active resume and its skills gap."""

        resume = get_active_resume(
            session
        )

        if resume is None:
            return {
                "resume": None,
                "skills_gap": [],
            }

        return {
            "resume": {
                "id": resume.id,
                "label": resume.label,
                "filename": (
                    resume.filename
                ),
                "skills": list(
                    resume.extracted_skills
                    or []
                ),
                "uploaded_at": (
                    resume.uploaded_at
                    .isoformat()
                ),
            },
            "skills_gap": skills_gap(
                session,
                resume=resume,
            ),
        }

    @app.post(
        "/api/resume"
    )
    def upload_resume(
        file: UploadFile = File(
            ...
        ),
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Upload a resume and re-score the whole corpus.

        Scoring is keyword overlap over already-stored text rather than
        a model call, so the corpus is re-ranked in this request instead
        of in a background job the user waits on.
        """

        payload = file.file.read()

        try:
            text = extract_resume_text(
                payload=payload,
                filename=(
                    file.filename or ""
                ),
            )

        except ResumeParseError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(
                    exc
                ),
            ) from exc

        resume = store_resume(
            session,
            label=(
                file.filename or "resume"
            ),
            filename=(
                file.filename or "resume"
            ),
            raw_text=text,
        )

        scored = rescore_corpus(
            session,
            resume=resume,
        )

        session.commit()

        return {
            "resume_id": resume.id,
            "filename": resume.filename,
            "skills": list(
                resume.extracted_skills
                or []
            ),
            "jobs_scored": scored,
        }

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
