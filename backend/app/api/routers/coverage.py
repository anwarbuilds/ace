"""The lead ledger, the boards ACE reads and host verdicts, for the Coverage tabs.

Reads only, except taking back a board the owner just added. Maintenance in the
scheduler keeps the data current.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.config import get_settings
from backend.app.coverage.host_policy import hosts_report
from backend.app.coverage.host_terms import TERMS
from backend.app.coverage.leads import leads_report
from backend.app.coverage.service import undo_added
from backend.app.coverage.sources_view import coverage_summary, sources_report


router = APIRouter()


class UndoRequest(BaseModel):
    source_type: str
    source_account: str


@router.get("/api/coverage/summary")
def get_summary(session: Session = Depends(get_session)) -> dict:
    return coverage_summary(session)


@router.get("/api/coverage/leads")
def get_leads(
    state: str | None = Query(default=None, max_length=16),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    """Every employer ACE has heard of, with its state and next check."""

    return leads_report(session, state=state, query=q, limit=limit, offset=offset)


@router.get("/api/coverage/sources")
def get_sources(
    show: str | None = Query(default=None, max_length=16),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    """Every job board ACE reads, and whether each is working."""

    return sources_report(
        session,
        now=datetime.now(timezone.utc),
        show=show,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/api/coverage/hosts")
def get_hosts(session: Session = Depends(get_session)) -> dict:
    """What each host says about being read, dated, grouped by platform."""

    return hosts_report(session, enforcing=get_settings().host_policy_enforce, terms=TERMS)


@router.post("/api/sources/undo")
def post_undo(payload: UndoRequest, session: Session = Depends(get_session)) -> dict:
    """Take back a board the owner added by hand."""

    if not undo_added(session, source_type=payload.source_type, source_account=payload.source_account):
        raise HTTPException(status_code=409, detail="Only a board you added can be taken back.")

    return {"status": "undone"}
