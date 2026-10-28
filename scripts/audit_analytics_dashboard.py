"""Read-only dashboard evidence, intended for stdin in the existing API image.

No Gmail requests, body reads, session creation or database writes. Output has
aggregate counts only, plus anonymous submission timestamps for independently
checking the frontend's calendar arithmetic. Keep output private and ignored.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import analytics_read
from backend.app.api.routers.inbox import _identities
from backend.app.config import get_settings
from backend.app.db.models import JobMarkRecord, ExternalApplicationRecord


def audit(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    identities = _identities(db)
    marks = db.scalar(select(func.count()).select_from(JobMarkRecord).where(JobMarkRecord.applied_at.is_not(None))) or 0
    external = db.scalar(select(func.count()).select_from(ExternalApplicationRecord)) or 0
    ranges = {}
    for days in ("14", "30", "90", "all"):
        d = analytics_read(db, days=days, tz="America/Los_Angeles", now=now, records=True, limit=len(identities) + 1)
        rows = d["records"]
        checks = {
            "identities_match_source_tables": d["total_submitted"] == marks + external == len(identities),
            "record_keys_are_unique": len(rows) == len({row["key"] for row in rows}) == d["submitted"],
            "latest_status_partition": dict(Counter(row["status"] for row in rows)) == d["statuses"],
            "cohort_partition": sum(d["cohort"][key] for key in ("positive", "rejected", "pending", "unknown")) == d["cohort"]["eligible"],
            "timeline_excludes_only_undated": sum(point["count"] for point in d["daily"]) == sum(row["submitted_at"] is not None for row in rows),
            "week_bars_reconcile": sum(point["count"] for point in d["week"]) == d["week_total"],
            "role_totals_reconcile": sum(row["submitted"] for row in d["roles"]) == d["submitted"],
            "company_totals_reconcile": sum(row["submitted"] for row in d["companies"]) == d["submitted"],
            "assessment_evidence_reconciles": sum("online_assessment" in row["event_types"] for row in rows) == d["assessments"],
            "interview_evidence_reconciles": sum(bool({"interview", "interviewing"}.intersection(row["event_types"])) for row in rows) == d["interviews"],
            "timing_buckets_reconcile": sum(row["count"] for row in d["timing"]) == d["timing_sample"],
            "attribution_not_invented": d["attribution"]["resume"] == d["attribution"]["channel"] == "Not recorded" and not d["attribution"]["combinations"],
        }
        public_fields = ("as_of", "timezone", "days", "start", "end", "total_submitted", "submitted", "undated", "week_total", "positive", "assessments", "interviews", "has_outcome_evidence", "statuses", "daily", "granularity", "week", "cohort", "timing", "median_days", "timing_sample", "evidence", "review", "roles", "attribution", "annual", "rejection_summary")
        ranges[days] = {"projection": {key: d[key] for key in public_fields}, "checks": checks,
                       "companies": [{"rank": i + 1, **{key: row[key] for key in ("submitted", "eligible", "responses", "rejections", "assessments", "interviews", "rate")}} for i, row in enumerate(d["companies"])],
                       "verified_companies": len(d["verified_companies"]), "official_reports": len(d["reports"])}
    # Real application keys, company names, titles, answers and mail content
    # never leave the service. Anonymous dates remain private audit material.
    ledger = [{"key": f"audit:{i}", "applied_at": (row.submitted_at.replace(tzinfo=timezone.utc) if row.submitted_at.tzinfo is None else row.submitted_at).isoformat() if row.submitted_at else None} for i, row in enumerate(identities)]
    independent = None
    try:
        from backend.scripts.inbox_analytics_audit import audit as independent_audit
    except ImportError:
        pass
    else:
        independent = independent_audit(db, now=now)
    return {"observed_at": now.isoformat(), "source_sha256": hashlib.sha256(Path(inspect.getfile(analytics_read)).read_bytes()).hexdigest(),
            "applied_marks": marks, "external_applications": external, "identities": len(identities),
            "ranges": ranges, "anonymous_submission_ledger": ledger, "independent_audit": independent,
            "all_checks_pass": all(all(row["checks"].values()) for row in ranges.values()),
            "gmail_calls": 0, "body_reads": 0, "mailbox_completeness_certified": False}


def main() -> int:
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        print("Live audit requires PostgreSQL with enforced read-only transactions.")
        return 2
    engine = create_engine(settings.database_url, connect_args={"options": "-c default_transaction_read_only=on -c jit=off"}, isolation_level="REPEATABLE READ")
    try:
        with Session(engine) as db:
            if db.execute(text("SHOW transaction_read_only")).scalar() != "on":
                raise RuntimeError("Read-only guard unavailable")
            result = audit(db)
            db.rollback()
        print(json.dumps(result, indent=2))
        return 0 if result["all_checks_pass"] else 1
    except Exception as exc:
        print(f"Audit incomplete ({type(exc).__name__}); no private exception details printed.")
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
