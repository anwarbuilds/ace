"""Keep official petition evidence on its reviewed, exact employer name."""

from sqlalchemy import select

from backend.app.coverage.identity import shared_board_reason
from backend.app.db.models import CompanyPetitionReportRecord, JobSourceRecord


def petition_reports_for(session, names):
    """Never expand display aliases, acquisitions or subsidiaries into joins.

    A reviewed report is still withheld when the displayed company itself
    denotes a shared or unresolved board. Its legal mapping must be reviewed
    against an actual employer before it can appear under that name.
    """
    names = set(names)
    if not names:
        return []
    sources = session.scalars(select(JobSourceRecord).where(JobSourceRecord.company_name.in_(names))).all()
    blocked = {
        row.company_name for row in sources
        if shared_board_reason(row.source_type, row.source_account)
        or (row.discovery_source or "").startswith((
            "feed_link rejected: identity:", "feed_link rejected: shared:",
        ))
    }
    safe = names - blocked
    if not safe:
        return []
    return session.scalars(
        select(CompanyPetitionReportRecord)
        .where(CompanyPetitionReportRecord.ace_company.in_(safe), CompanyPetitionReportRecord.entity_verified.is_(True))
        .order_by(CompanyPetitionReportRecord.period.desc(), CompanyPetitionReportRecord.id.desc())
    ).all()
