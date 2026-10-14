"""What ace itself is doing, said plainly.

Settings shows this so nothing is claimed that is not true: an alert is
"sent" only when a provider accepted it, the scheduler is "live" only
when it polled recently, and a queue job without a score is counted, not
hidden.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.api.queries import (
    _as_utc,
    last_poll_completed_at,
)
from backend.app.config import get_settings
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
    JobSourceRecord,
    PollSessionRecord,
)
from backend.app.intelligence.eligibility import ELIGIBILITY_RULE_VERSION
from backend.app.mail.sender import mail_configured
from backend.app.matching.scoring import MATCHING_ALGORITHM_VERSION
from backend.app.matching.service import get_active_resume


router = APIRouter()

# ace polls every few minutes; longer than this without a successful
# poll means the scheduler has stopped. Same threshold as the UI.
STALE_AFTER = timedelta(
    minutes=45,
)


def _iso(
    moment: datetime | None,
) -> str | None:
    moment = _as_utc(
        moment
    )

    return (
        None
        if moment is None
        else moment.isoformat()
    )


@router.get(
    "/api/system"
)
def get_system(
    session: Session = Depends(
        get_session
    ),
) -> dict:
    """Report scheduler freshness, alert delivery and scoring coverage."""

    settings = get_settings()

    now = datetime.now(
        timezone.utc
    )

    last_poll = last_poll_completed_at(
        session
    )

    week_ago = now - timedelta(
        days=7
    )

    alert_counts = dict(
        session.execute(
            select(
                PollSessionRecord.alert_status,
                func.count(),
            )
            .where(
                PollSessionRecord.notified_at
                >= week_ago,
            )
            .group_by(
                PollSessionRecord.alert_status
            )
        ).all()
    )

    last_sent = session.scalar(
        select(
            func.max(
                PollSessionRecord.notified_at
            )
        ).where(
            PollSessionRecord.alert_status
            == "sent"
        )
    )

    resume = get_active_resume(
        session
    )

    queue = (
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
            JobEvaluationRecord.eligibility_status
            == "PASS",
        )
    )

    queue_total = int(
        session.scalar(
            queue
        )
        or 0
    )

    unscored = queue_total

    if resume is not None:
        unscored = int(
            session.scalar(
                queue.outerjoin(
                    JobResumeScoreRecord,
                    (
                        JobResumeScoreRecord.job_id
                        == JobRecord.id
                    )
                    & (
                        JobResumeScoreRecord.resume_id
                        == resume.id
                    ),
                ).where(
                    JobResumeScoreRecord.job_id.is_(
                        None
                    )
                )
            )
            or 0
        )

    sources = int(
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                JobSourceRecord
            )
            .where(
                JobSourceRecord.enabled.is_(
                    True
                )
            )
        )
        or 0
    )

    return {
        "versions": {
            "gate": ELIGIBILITY_RULE_VERSION,
            "matching": MATCHING_ALGORITHM_VERSION,
        },
        "display_timezone": settings.display_timezone,
        "scheduler": {
            "last_poll_at": _iso(
                last_poll
            ),
            "stale": (
                last_poll is None
                or now - last_poll > STALE_AFTER
            ),
            "sources_enabled": sources,
        },
        "alerts": {
            "address_set": bool(
                settings.alert_email
            ),
            "provider_configured": mail_configured(),
            "last_sent_at": _iso(
                last_sent
            ),
            "last_7_days": {
                (status or "unknown"): count
                for status, count in alert_counts.items()
            },
        },
        "scoring": {
            "resume_active": resume is not None,
            "queue_jobs": queue_total,
            "queue_unscored": unscored,
        },
    }
