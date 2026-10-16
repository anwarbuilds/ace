"""Write a privacy-safe aggregate inventory for migration verification."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import (
    ApplicationAnswerRecord,
    CareerFactRecord,
    ExternalApplicationRecord,
    JobMarkRecord,
    JobRecord,
    JobSourceRecord,
    PollSessionRecord,
    ResumeDocumentRecord,
    ResumeRecord,
    ResumeVersionRecord,
    SourceState,
    UserRecord,
)


MODELS = (
    JobRecord,
    SourceState,
    JobSourceRecord,
    JobMarkRecord,
    ExternalApplicationRecord,
    ApplicationAnswerRecord,
    ResumeRecord,
    PollSessionRecord,
    UserRecord,
    ResumeDocumentRecord,
    CareerFactRecord,
    ResumeVersionRecord,
)


def _engine_options(database_url: str) -> dict:
    if make_url(database_url).get_backend_name() == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def inventory(session: Session) -> dict:
    """Return counts only, with no emails, resume text, answers or job text."""

    tables = {model.__tablename__: _count(session, model) for model in MODELS}
    return {
        "format": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "checks": {
            "active_jobs": int(
                session.scalar(
                    select(func.count())
                    .select_from(JobRecord)
                    .where(JobRecord.is_active.is_(True))
                )
                or 0
            ),
            "enabled_sources": int(
                session.scalar(
                    select(func.count())
                    .select_from(JobSourceRecord)
                    .where(JobSourceRecord.enabled.is_(True))
                )
                or 0
            ),
            "applied_job_marks": int(
                session.scalar(
                    select(func.count())
                    .select_from(JobMarkRecord)
                    .where(JobMarkRecord.applied_at.is_not(None))
                )
                or 0
            ),
            "active_resumes": int(
                session.scalar(
                    select(func.count())
                    .select_from(ResumeRecord)
                    .where(ResumeRecord.is_active.is_(True))
                )
                or 0
            ),
            "primary_resume_versions": int(
                session.scalar(
                    select(func.count())
                    .select_from(ResumeVersionRecord)
                    .where(ResumeVersionRecord.is_primary.is_(True))
                )
                or 0
            ),
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args(argv)

    database_url = args.database_url or get_settings().database_url
    engine = create_engine(database_url, **_engine_options(database_url))
    with Session(engine) as session:
        result = inventory(session)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if args.compare:
        expected = json.loads(args.compare.read_text(encoding="utf-8"))
        if (
            expected.get("tables") != result["tables"]
            or expected.get("checks") != result["checks"]
        ):
            raise SystemExit("data inventory differs")
        print("data inventory matches")


if __name__ == "__main__":
    main()
