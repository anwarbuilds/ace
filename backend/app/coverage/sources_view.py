"""Every job board ACE reads, as the Sources tab shows it.

Whether a board answers and whether its site allows reading are read from
what the scheduler and the host verdicts already recorded. Nothing here makes
a request.
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
from backend.app.coverage.host_policy import read_targets, refused_hosts
from backend.app.coverage.leads import POLLING, UNDONE
from backend.app.coverage.recovery import dark_sources
from backend.app.db.models import EmployerLead, JobSourceRecord, SourceState
from backend.app.discovery.feed_links import board_key

WORKING = "working"
FIRST_READ = "first_read"
DARK = "dark"
SAYS_NO = "says_no"

STATUS_LABELS = {
    WORKING: "Working",
    FIRST_READ: "First read soon",
    DARK: "Stopped answering",
    SAYS_NO: "Site says no",
}

_SITE_LABELS = {
    "greenhouse": "Greenhouse",
    "ashby": "Ashby",
    "lever": "Lever",
    "smartrecruiters": "SmartRecruiters",
    "workable": "Workable",
    "workday": "Workday",
    "oracle_recruiting": "Oracle",
    "gem": "Gem",
    "eightfold": "Eightfold",
    "eightfold_pcsx": "Eightfold",
    "jibe": "iCIMS Jibe",
    "avature": "Avature",
    "jobposting_sitemap": "Own careers site",
    "ibm": "IBM",
    "bytedance": "ByteDance",
}

# Boards the owner added come first, then whatever is wrong, then the rest.
_ORDER = {DARK: 1, SAYS_NO: 2, FIRST_READ: 3, WORKING: 4}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def site_label(source_type: str) -> str:
    return _SITE_LABELS.get(source_type, source_type.replace("_", " ").title())


def _boards(session: Session, *, now: datetime) -> list[dict]:
    states = {
        board_key(row.source, row.source_account): row
        for row in session.scalars(sa.select(SourceState))
    }

    dark = {board_key(item.source_type, item.source_account): item for item in dark_sources(session, now=now)}

    refused = refused_hosts(session)

    mine: dict[tuple[str, str], datetime] = {}

    for boards, added in session.execute(
        sa.select(EmployerLead.boards, EmployerLead.owner_added_at).where(EmployerLead.owner_added_at.is_not(None))
    ):
        for board in boards or []:
            mine[board_key(board["source_type"], board["source_account"])] = _aware(added)

    out = []

    for row in session.scalars(
        sa.select(JobSourceRecord).where(
            JobSourceRecord.enabled.is_(True),
            JobSourceRecord.source_type.not_in(sorted(MULTI_EMPLOYER_SOURCES)),
        )
    ):
        key = board_key(row.source_type, row.source_account)
        state = states.get(key)
        hosts = {target.host for target in read_targets(row.source_type, row.source_account, row.source_host)}

        if key in dark:
            status = DARK
        elif hosts & refused:
            status = SAYS_NO
        elif state is None:
            status = FIRST_READ
        else:
            status = WORKING

        last = _aware(state.last_success_at) if state is not None else None

        if state is None or status == FIRST_READ:
            last = None

        out.append(
            {
                "company": row.company_name,
                "site": site_label(row.source_type),
                "source_type": row.source_type,
                "source_account": row.source_account,
                "last_read_at": last.isoformat() if last else None,
                "poll_interval_seconds": row.poll_interval_seconds,
                "jobs": state.last_job_count if state is not None else None,
                "status": status,
                "status_label": STATUS_LABELS[status],
                "added_by_you": key in mine or (row.discovery_source or "").lower().startswith("added_by_hand"),
                "added_at": mine[key].isoformat() if key in mine else None,
            }
        )

    return out


def sources_report(
    session: Session,
    *,
    now: datetime,
    show: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    boards = _boards(session, now=now)

    counts = {
        "total": len(boards),
        "working": sum(1 for b in boards if b["status"] == WORKING),
        "first_read": sum(1 for b in boards if b["status"] == FIRST_READ),
        "dark": sum(1 for b in boards if b["status"] == DARK),
        "says_no": sum(1 for b in boards if b["status"] == SAYS_NO),
        "mine": sum(1 for b in boards if b["added_by_you"]),
    }

    chosen = boards

    if show == "mine":
        chosen = [b for b in chosen if b["added_by_you"]]
    elif show == DARK:
        chosen = [b for b in chosen if b["status"] == DARK]
    elif show == SAYS_NO:
        chosen = [b for b in chosen if b["status"] == SAYS_NO]

    text = (query or "").strip().casefold()

    if text:
        chosen = [b for b in chosen if text in b["company"].casefold()]

    chosen = sorted(
        chosen,
        key=lambda b: (
            0 if b["added_by_you"] else 1,
            # Newest addition first, then problems before the quiet majority.
            -(datetime.fromisoformat(b["added_at"]).timestamp() if b["added_at"] else 0),
            _ORDER[b["status"]],
            b["company"].casefold(),
        ),
    )

    dark = [
        {
            "company": item.company_name,
            "site": site_label(item.source_type),
            "source_type": item.source_type,
            "source_account": item.source_account,
            "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
            "dark_since": item.dark_since.isoformat(),
        }
        for item in dark_sources(session, now=now)
    ]

    return {
        "counts": counts,
        "matched": len(chosen),
        "limit": limit,
        "offset": offset,
        "rows": chosen[offset : offset + limit],
        "dark": dark,
    }


def coverage_summary(session: Session) -> dict:
    """The small counts the Coverage tabs carry."""

    leads = session.scalar(sa.select(sa.func.count()).select_from(EmployerLead)) or 0

    polling = session.scalar(
        sa.select(sa.func.count()).select_from(EmployerLead).where(EmployerLead.state == POLLING)
    ) or 0

    sources = session.scalar(
        sa.select(sa.func.count())
        .select_from(JobSourceRecord)
        .where(
            JobSourceRecord.enabled.is_(True),
            JobSourceRecord.source_type.not_in(sorted(MULTI_EMPLOYER_SOURCES)),
        )
    ) or 0

    return {"leads": leads, "polling": polling, "sources": sources}


__all__ = ["coverage_summary", "site_label", "sources_report", "UNDONE"]
