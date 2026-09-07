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

from pydantic import BaseModel

from backend.app.api.marks import (
    APPLICATION_STATUSES,
    REVIEW_STATES,
    mark_counts,
    set_mark,
)
from backend.app.applications.parsing import (
    ApplicationParseError,
    parse_applications,
)
from backend.app.applications.service import (
    apply_import,
    list_external_applications,
    preview_import,
    record_external_applications,
)
from backend.app.api.queries import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SORT_OPTIONS,
    SORT_SEPARATOR,
    parse_sort,
    JobFilters,
    build_facets,
    build_stats,
    last_poll_completed_at,
    list_discovery_runs,
    list_jobs,
)
from backend.app.db.models import JobRecord
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


# Accepted values for the mark filter on /api/jobs.
MARK_FILTERS = frozenset(
    {
        "saved",
        "archived",
        "applied",
    }
)


class ApplicationDecision(BaseModel):
    """One confirmed row of an application import."""

    job_id: int

    applied_on: str | None = None

    status: str | None = None


class ExternalApplicationEntry(BaseModel):
    """One application with no stored posting to attach it to."""

    company: str

    title: str

    applied_on: str | None = None

    status: str | None = None

    url: str | None = None


class ApplicationImport(BaseModel):
    """The rows a user confirmed after reviewing the preview."""

    decisions: list[
        ApplicationDecision
    ] = []

    # Rows ACE could not place against a stored posting, kept as
    # standalone history rather than dropped.
    external: list[
        ExternalApplicationEntry
    ] = []


class MarkUpdate(BaseModel):
    """A partial update to one job's marks.

    Every field is optional so a caller can toggle one mark without
    restating the others, which is what stops a save from wiping a
    review state.
    """

    saved: bool | None = None

    review_state: str | None = None

    clear_review: bool = False

    applied: bool | None = None

    application_status: str | None = None

    status_note: str | None = None


def _with_session_jobs(
    session: Session,
    *,
    runs: list[dict],
    per_session: int,
) -> list[dict]:
    """Attach each run's best few arrivals, for the feed.

    Done in one pass rather than a request per run: a feed showing
    twenty-five runs would otherwise cost twenty-five round trips to
    render three rows each.

    A run that found nothing keeps an empty list. That is deliberate:
    "21 found, none passed your filters" is the proof the system is
    working, and hiding those runs would make ACE look asleep during
    the many hours when it is running correctly and finding nothing.
    """

    if per_session <= 0:
        return runs

    resume = get_active_resume(
        session
    )

    enriched: list[dict] = []

    for run in runs:
        jobs: list[dict] = []

        if run.get(
            "qualifying_discovered"
        ):
            page = list_jobs(
                session,
                filters=JobFilters(
                    session_id=run["id"],
                    resume_id=(
                        None
                        if resume is None
                        else resume.id
                    ),
                    sort="best_match",
                    limit=per_session,
                ),
            )

            jobs = [
                _serialize_job(
                    job
                )
                for job in page.items
            ]

        enriched.append(
            {
                **run,
                "jobs": jobs,
            }
        )

    return enriched


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
        "related_evidence": [
            {
                "skill": skill,
                "via": via,
            }
            for skill, via in (
                job.related_evidence
            )
        ],
        "previous_match_score": (
            job.previous_match_score
        ),
        "score_changed_at": (
            None
            if job.score_changed_at is None
            else job.score_changed_at.isoformat()
        ),
        "is_saved": job.is_saved,
        "review_state": (
            job.review_state
        ),
        "company_tier": (
            job.company_tier
        ),
        "application_status": (
            job.application_status
        ),
        "status_changed_at": (
            None
            if job.status_changed_at is None
            else job.status_changed_at.isoformat()
        ),
        "status_note": (
            job.status_note
        ),
        "applied_at": (
            None
            if job.applied_at is None
            else job.applied_at.isoformat()
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
        exclude_company: str | None = Query(
            default=None,
            description=(
                "Comma-separated company "
                "names to leave out. "
                "Combines with every other "
                "filter."
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
        mark: str | None = Query(
            default=None,
            description=(
                "saved, archived or applied"
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
        max_detected_age_days: int | None = Query(
            default=None,
            ge=1,
            le=3650,
            description=(
                "Hide postings ACE detected more "
                "than this many days ago. Nothing "
                "is deleted; the row still exists."
            ),
        ),
        tier: str | None = Query(
            default=None,
            description=(
                "Employer tiers to keep, comma "
                "separated: BIG_TECH, TOP_TIER, "
                "ESTABLISHED, OTHER."
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

        # Sorts combine, so this parses a comma-separated list rather
        # than validating one name. Unknown keys are dropped, not
        # rejected: a stale bookmark should still return the jobs.
        normalized_sort = (
            SORT_SEPARATOR.join(
                parse_sort(
                    sort
                )
            )
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
                exclude_companies=(
                    _split_csv(
                        exclude_company
                    )
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
                max_detected_age_days=(
                    max_detected_age_days
                ),
                tiers=_split_csv(
                    tier
                ),
                mark=(
                    mark
                    if mark
                    in MARK_FILTERS
                    else None
                ),
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
        exclude_company: str | None = Query(
            default=None,
        ),
        # Accepted so the headline count always describes the rows on
        # screen. A total that disagrees with the list reads as jobs
        # being withheld.
        tier: str | None = Query(
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
        max_detected_age_days: int | None = Query(
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
                exclude_companies=(
                    _split_csv(
                        exclude_company
                    )
                ),
                tiers=_split_csv(
                    tier
                ),
                sources=_split_csv(
                    source
                ),
                search=q,
                max_age_days=(
                    max_age_days
                ),
                max_detected_age_days=(
                    max_detected_age_days
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
        jobs_per_session: int = Query(
            default=0,
            ge=0,
            le=10,
            description=(
                "Include this many top matches "
                "per run, for the feed."
            ),
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
            "sessions": _with_session_jobs(
                session,
                runs=list_discovery_runs(
                    session,
                    limit=limit,
                ),
                per_session=jobs_per_session,
            ),
        }

    @app.get(
        "/api/resume"
    )
    def get_resume(
        session: Session = Depends(
            get_session
        ),
        family: str | None = Query(
            default=None,
        ),
        min_match: int | None = Query(
            default=None,
            ge=0,
            le=100,
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
                role_family=family,
                min_match=min_match,
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
        "/api/applications/external"
    )
    def get_external_applications(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Return applications with no stored posting behind them."""

        rows = list_external_applications(
            session
        )

        return {
            "items": [
                {
                    "id": row.id,
                    "company": row.company,
                    "title": row.title,
                    "applied_at": (
                        None
                        if row.applied_at is None
                        else row.applied_at
                        .isoformat()
                    ),
                    "application_status": (
                        row.application_status
                    ),
                    "url": row.url,
                }
                for row in rows
            ],
            "total": len(
                rows
            ),
        }

    @app.get(
        "/api/marks"
    )
    def get_marks(
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Return how many jobs carry each mark."""

        return mark_counts(
            session
        )

    @app.put(
        "/api/marks/{job_id}"
    )
    def put_mark(
        job_id: int,
        payload: MarkUpdate,
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Set one job's marks.

        Absent fields are left alone, so saving a job never clears a
        review state recorded earlier.
        """

        if session.get(
            JobRecord,
            job_id,
        ) is None:
            raise HTTPException(
                status_code=404,
                detail="unknown job",
            )

        if (
            payload.review_state
            is not None
            and payload.review_state
            not in REVIEW_STATES
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "review_state must be "
                    "reviewed or dismissed"
                ),
            )

        if (
            payload.application_status
            is not None
            and payload.application_status
            not in APPLICATION_STATUSES
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "application_status must be "
                    "one of: "
                    + ", ".join(
                        APPLICATION_STATUSES
                    )
                ),
            )

        record = set_mark(
            session,
            job_id=job_id,
            saved=payload.saved,
            review_state=(
                payload.review_state
            ),
            clear_review=(
                payload.clear_review
            ),
            applied=payload.applied,
            application_status=(
                payload.application_status
            ),
            status_note=(
                payload.status_note
            ),
        )

        session.commit()

        return {
            "job_id": record.job_id,
            "is_saved": record.is_saved,
            "review_state": (
                record.review_state
            ),
            "applied_at": (
                None
                if record.applied_at
                is None
                else record.applied_at
                .isoformat()
            ),
            "application_status": (
                record.application_status
            ),
            "status_changed_at": (
                None
                if record.status_changed_at
                is None
                else record.status_changed_at
                .isoformat()
            ),
            "status_note": (
                record.status_note
            ),
        }

    @app.post(
        "/api/applications/preview"
    )
    def preview_applications(
        file: UploadFile = File(
            ...,
        ),
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Report what importing this file would do, changing nothing.

        Separate from the import itself so a wrong match is seen before
        it is recorded, not after.
        """

        payload = file.file.read()

        try:
            rows = parse_applications(
                payload=payload,
                filename=(
                    file.filename or ""
                ),
            )
        except ApplicationParseError as error:
            raise HTTPException(
                status_code=422,
                detail=str(
                    error
                ),
            ) from error

        preview = preview_import(
            session,
            rows=rows,
        )

        by_number = {
            row.row_number: row
            for row in preview.rows
        }

        return {
            "counts": preview.counts,
            "total": len(
                preview.rows
            ),
            "rows": [
                {
                    "row_number": (
                        match.row_number
                    ),
                    "status": match.status,
                    "method": match.method,
                    "job_id": match.job_id,
                    "company": by_number[
                        match.row_number
                    ].company,
                    "title": by_number[
                        match.row_number
                    ].title,
                    "applied_on": (
                        None
                        if by_number[
                            match.row_number
                        ].applied_on
                        is None
                        else by_number[
                            match.row_number
                        ]
                        .applied_on
                        .isoformat()
                    ),
                    # Named apart from "status" above, which is the
                    # match outcome. One field cannot mean both how
                    # confidently ACE placed the row and where the
                    # application stands.
                    "application_status": (
                        by_number[
                            match.row_number
                        ].status
                    ),
                    "candidates": [
                        {
                            "job_id": (
                                candidate
                                .job_id
                            ),
                            "company": (
                                candidate
                                .company
                            ),
                            "title": (
                                candidate
                                .title
                            ),
                            # Without this the four Palantir options
                            # render identically and the choice cannot
                            # be made at all.
                            "location": (
                                candidate
                                .location
                            ),
                        }
                        for candidate
                        in match.candidates
                    ],
                }
                for match in preview.matches
            ],
        }

    @app.post(
        "/api/applications/import"
    )
    def import_applications(
        payload: ApplicationImport,
        session: Session = Depends(
            get_session
        ),
    ) -> dict:
        """Record applications for the confirmed rows only."""

        recorded = record_external_applications(
            session,
            entries=[
                {
                    "company": entry.company,
                    "title": entry.title,
                    "applied_on": (
                        entry.applied_on
                    ),
                    "status": (
                        entry.status
                        if entry.status
                        in APPLICATION_STATUSES
                        else None
                    ),
                    "url": entry.url,
                }
                for entry in payload.external
            ],
        )

        marked = apply_import(
            session,
            decisions=[
                {
                    "job_id": (
                        decision.job_id
                    ),
                    "applied_on": (
                        decision.applied_on
                    ),
                    "status": (
                        decision.status
                        if decision.status
                        in APPLICATION_STATUSES
                        else None
                    ),
                }
                for decision in (
                    payload.decisions
                )
            ],
        )

        session.commit()

        return {
            "marked": marked,
            "recorded": recorded,
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
