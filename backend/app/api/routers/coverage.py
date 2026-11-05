"""The lead ledger and host verdicts, as the Coverage page reads them.

Read-only. Maintenance in the scheduler keeps both current.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.config import get_settings
from backend.app.coverage.host_policy import hosts_report
from backend.app.coverage.host_terms import TERMS
from backend.app.coverage.leads import leads_report


router = APIRouter()


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


@router.get("/api/coverage/hosts")
def get_hosts(session: Session = Depends(get_session)) -> dict:
    """What each host says about being read, dated, grouped by platform."""

    return hosts_report(session, enforcing=get_settings().host_policy_enforce, terms=TERMS)
