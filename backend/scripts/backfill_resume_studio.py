"""Preview or apply the idempotent legacy resume bridge.

Examples::

    python -m backend.scripts.backfill_resume_studio
    python -m backend.scripts.backfill_resume_studio --apply
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.studio.legacy import backfill_legacy_resumes


def _engine_options(database_url: str) -> dict:
    if make_url(database_url).get_backend_name() == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    database_url = args.database_url or get_settings().database_url
    engine = create_engine(database_url, **_engine_options(database_url))
    with Session(engine) as session:
        result = backfill_legacy_resumes(session, now=datetime.now(timezone.utc))
        if args.apply:
            session.commit()
        else:
            session.rollback()
    print(
        json.dumps(
            {"mode": "applied" if args.apply else "preview", **asdict(result)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
