"""Private, read-only Inbox/Analytics reconciliation; never reads Gmail bodies.

Run in the API environment. The CLI enforces a PostgreSQL REPEATABLE READ,
READ ONLY transaction. Output contains aggregate measurements only and must stay
in ignored owner artifacts. A successful audit does not measure parser accuracy.
"""
from __future__ import annotations

import inspect
import json
from time import perf_counter
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, event as sql_event, select, text
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import analytics_read, aware
from backend.app.config import get_settings
from backend.app.db.models import ApplicationEventRecord, GmailMessageRecord
from backend.app.inbox import evidence_scope
from backend.app.inbox.company_outcomes import COMPANY_REASON, KIND, event_company
from backend.app.inbox.filed_evidence import DECISIONS as FILED_DECISIONS
from backend.app.inbox.queue import projected_classification, projected_decision
from backend.app.inbox.reconcile import CLASSIFICATION_REASONS, PASSIVE_KINDS


def audit(db: Session, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    messages = list(db.scalars(select(GmailMessageRecord)))
    ledger = list(db.scalars(select(ApplicationEventRecord)))
    undone = {event.undo_of_id for event in ledger if event.undo_of_id}
    company_claims = defaultdict(set)
    for event in ledger:
        if (event.kind == KIND and event.id not in undone and event.previous_status is None
                and event.new_status is None and (not event.occurred_at or aware(event.occurred_at) <= now)):
            employer = event_company(event)
            if employer:
                company_claims[event.gmail_message_id].add(employer.strip().casefold())

    # These are saved Inbox meanings, not a second email text classifier. The
    # independent count deliberately never calls the Analytics evidence helper.
    recognized = []
    for message in messages:
        kind, decision = projected_classification(message), projected_decision(message)
        valid = decision in FILED_DECISIONS
        valid |= decision == "receipt" and kind == "application_confirmation"
        valid |= (decision in {"manual", "automatic"} and message.selected_application_key is not None
                  and kind in set(CLASSIFICATION_REASONS) - {"possible_rejection", "unclear", "unknown"})
        valid |= decision == "unlinked" and kind == "rejection"
        valid |= (decision == "company_rejection" and kind == "rejection"
                  and message.decision_reason == COMPANY_REASON and message.selected_application_key is None
                  and len(company_claims[message.id]) == 1)
        valid |= (decision == "update" and kind in PASSIVE_KINDS
                  and message.decision_reason == CLASSIFICATION_REASONS[kind])
        if valid and evidence_scope.includes(message.received_at) and aware(message.received_at) <= now:
            recognized.append(message)

    ranges = {}
    for days in ("14", "30", "90", "all"):
        queries = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            queries.append(statement.lstrip().split(None, 1)[0].upper())
        sql_event.listen(db.get_bind(), "before_cursor_execute", capture)
        started = perf_counter()
        try:
            d = analytics_read(db, days=days, tz="America/Los_Angeles", now=now, records=True, limit=100000)
        finally:
            sql_event.remove(db.get_bind(), "before_cursor_execute", capture)
        duration_ms = round((perf_counter() - started) * 1000, 1)
        zone = ZoneInfo(d["timezone"])
        expected = Counter(projected_classification(message) for message in recognized
                           if (days == "all" or d["start"] <= aware(message.received_at).astimezone(zone).date().isoformat())
                           and aware(message.received_at).astimezone(zone).date().isoformat() <= d["end"])
        actual = d.get("classified_email_evidence", {}).get("categories", {})
        checks = {
            "effective_email_categories": all(actual.get(kind, 0) == expected[kind] for kind in set(actual) | set(expected)),
            "distinct_email_total": d.get("classified_email_evidence", {}).get("total", 0) == sum(expected.values()),
            "unique_applications": len(d["records"]) == len({row["key"] for row in d["records"]}) == d["submitted"],
            "positive_applications": sum(bool(set(row["event_types"]) & {"recruiter_reply", "online_assessment", "screening", "interview", "interviewing", "offer", "accepted"}) for row in d["records"]) == d["positive"],
            "confirmed_rejections": sum("rejection" in row["event_types"] for row in d["records"]) == d["evidence"]["rejected"],
            "assessments": sum("online_assessment" in row["event_types"] for row in d["records"]) == d["assessments"],
            "interviews": sum(bool(set(row["event_types"]) & {"interview", "interviewing"}) for row in d["records"]) == d["interviews"],
            "latest_status_partition": sum(d["statuses"].values()) == d["submitted"],
            "cohort_partition": sum(d["cohort"][key] for key in ("positive", "rejected", "pending", "unknown")) == d["cohort"]["eligible"],
            "timing_sample": sum(row["count"] for row in d["timing"]) == d["timing_sample"],
        }
        # New exact receipt-date drilldowns must reconcile with every category.
        if "emails" in inspect.signature(analytics_read).parameters:
            for kind in actual:
                detail = analytics_read(db, days=days, tz=d["timezone"], now=now,
                                        emails=True, email_kind=kind, limit=100000)
                rows = detail["email_records"]
                checks[f"email_drilldown_{kind}"] = (detail["email_total"] == actual[kind] == len(rows)
                    == len({row["id"] for row in rows}) and all(row["classification"] == kind for row in rows))
        checks["read_only_statements"] = all(statement in {"SELECT", "SHOW"} for statement in queries)
        ranges[days] = {"email_expected": dict(expected), "email_actual": actual,
                        "applications": d["submitted"], "positive": d["positive"],
                        "assessments": d["assessments"], "interviews": d["interviews"],
                        "rejections": d["evidence"]["rejected"], "checks": checks,
                        "excluded_events": d.get("inbox_audit", {}).get("excluded_events", {}),
                        "duration_ms": duration_ms, "query_count": len(queries)}
    return {"observed_at": now.isoformat(), "ranges": ranges,
            "all_checks_pass": all(all(row["checks"].values()) for row in ranges.values()),
            "gmail_calls": 0, "body_reads": 0, "writes": 0,
            "classification_accuracy_certified": False, "mailbox_completeness_certified": False}


def main() -> int:
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        print("Audit requires PostgreSQL with an enforced read-only snapshot.")
        return 2
    engine = create_engine(settings.database_url, isolation_level="REPEATABLE READ",
        connect_args={"options": "-c default_transaction_read_only=on -c jit=off"})
    try:
        with Session(engine) as db:
            if db.execute(text("SHOW transaction_read_only")).scalar() != "on":
                raise RuntimeError("Read-only guard unavailable")
            result = audit(db)
            db.rollback()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_checks_pass"] else 1
    except Exception as exc:
        print(f"Audit incomplete ({type(exc).__name__}); private exception details withheld.")
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
