"""Aggregate Inbox-to-Analytics audit. No Gmail reads, private text or writes.

Run alongside inbox_coverage_report.py: that report measures the mailbox IDs;
this report checks the stored evidence and Analytics projection. CLI requires
PostgreSQL and uses a repeatable, read-only snapshot. Tests call audit() with
isolated fictional SQLite sessions. Neither report can certify unseen wording.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import POSITIVE, STAGE_KIND, analytics_read, aware
from backend.app.api.routers.inbox import PENDING, _identities
from backend.app.config import get_settings
from backend.app.db.models import ApplicationEventRecord, GmailMessageRecord, JobMarkRecord, ExternalApplicationRecord
from backend.app.inbox.reconcile import PARSER_VERSION
from backend.app.inbox.queue import projected_decision, history_cutoff


def audit(db: Session, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    identities = {a.key: a for a in _identities(db)}
    messages = list(db.scalars(select(GmailMessageRecord)))
    ledger = list(db.scalars(select(ApplicationEventRecord)))
    undone = {e.undo_of_id for e in ledger if e.undo_of_id}
    active = [e for e in ledger if e.id not in undone and e.kind != "undo"
              and e.actor in {"owner", "verified_automation"}]
    by_message: dict[int, list] = defaultdict(list)
    for e in active:
        if e.gmail_message_id and e.application_key in identities:
            by_message[e.gmail_message_id].append(e)
    marked = db.scalar(select(func.count()).select_from(JobMarkRecord).where(JobMarkRecord.applied_at.is_not(None))) or 0
    external = db.scalar(select(func.count()).select_from(ExternalApplicationRecord)) or 0
    output = {"observed_at": now.isoformat(), "parser": PARSER_VERSION, "identities": len(identities),
              "persisted_applied_marks": marked, "persisted_external_applications": external}
    possible_duplicates: dict[tuple, set[str]] = defaultdict(set)
    for app in identities.values():
        if app.submitted_at:
            signature = (" ".join(app.company.casefold().split()), " ".join(app.title.casefold().split()), aware(app.submitted_at).date())
            possible_duplicates[signature].add(app.key.split(":", 1)[0])
    # A matching label/date can still describe separate requisitions. Flag it
    # for review without merging identities or claiming a definite duplicate.
    output["potential_cross_history_duplicate_groups"] = sum(len(kinds) > 1 for kinds in possible_duplicates.values())
    ranges = {}
    all_rows = {}
    for days in ("14", "30", "90", "all"):
        d = analytics_read(db, days=days, tz="America/Los_Angeles", now=now, records=True, limit=100000)
        rows = d["records"]
        checks = {
            "unique_rows": len(rows) == len({r["key"] for r in rows}) == d["record_total"] == d["submitted"],
            "lifetime_matches_persisted_applications": d["total_submitted"] == marked + external,
            "status_partition": sum(d["statuses"].values()) == d["submitted"],
            "cohort_partition": sum(d["cohort"][key] for key in ("positive", "rejected", "pending", "unknown")) == d["cohort"]["eligible"],
            "assessment_matches_records": sum("online_assessment" in r["event_types"] for r in rows) == d["assessments"],
            "rejection_matches_records": sum("rejection" in r["event_types"] for r in rows) == d["evidence"]["rejected"],
        }
        ranges[days] = {"submitted": d["submitted"], "statuses": d["statuses"], "evidence": d["evidence"],
                        "dated_rejections": d["rejection_summary"]["dated"], "assessments": d["assessments"],
                        "interviews": d["interviews"], "checks": checks}
        if days == "all":
            all_rows = {r["key"]: r for r in rows}
    output["ranges"] = ranges
    recorded = [m for m in messages if m.decision in {"automatic", "manual"}]
    reconciliation: Counter = Counter()
    for m in recorded:
        key = m.selected_application_key
        if key not in identities:
            reconciliation["missing_selected_application"] += 1
            continue
        linked = by_message[m.id]
        if len({e.application_key for e in linked}) > 1:
            reconciliation["conflicting_application_targets"] += 1
            continue
        linked = [e for e in linked if e.application_key == key]
        if not linked:
            reconciliation["no_active_confirmed_application_event"] += 1
            continue
        for e in linked:
            kind = STAGE_KIND.get(e.new_status, "unknown") if e.kind == "manual_correction" else e.kind
            if e.kind == "manual_correction" and e.new_status == "screening" and m.classification == "online_assessment":
                kind = "online_assessment"
            if kind not in POSITIVE | {"rejection"}:
                reconciliation["non_outcome_event"] += 1
                continue
            if e.occurred_at and aware(e.occurred_at) > now:
                reconciliation["future_outcome_timestamp"] += 1
                continue
            app = identities[key]
            if e.occurred_at and app.submitted_at and aware(e.occurred_at) < aware(app.submitted_at):
                seconds = (aware(app.submitted_at) - aware(e.occurred_at)).total_seconds()
                reconciliation["outcome_before_mark_within_24h" if seconds <= 86400 else "outcome_before_submission_over_24h"] += 1
            evidence = next((item for item in all_rows[key]["evidence"] if item["kind"] == kind), None)
            if not evidence:
                reconciliation["missing_outcome_type_in_analytics"] += 1
            elif evidence["message_id"] == m.id:
                reconciliation["counted_with_email_link"] += 1
            elif evidence["message_id"]:
                reconciliation["same_application_kind_deduplicated_to_another_email"] += 1
            else:
                reconciliation["only_undated_status_fallback_no_email_link"] += 1
    output["recorded_messages"] = len(recorded)
    output["recorded_message_reconciliation"] = dict(reconciliation)
    cutoff = history_cutoff(db)
    output["review_queue"] = {"inbox_pending": sum(projected_decision(m, cutoff) in PENDING for m in messages),
                              "analytics_pending": sum(d["review"].get(key, 0) for key in ("needs_review", "exact_preview", "deferred")),
                              "deferred": sum(m.decision == "deferred" for m in messages)}
    output["orphan_active_outcome_events"] = sum(
        e.application_key.startswith(("job:", "external:")) and e.application_key not in identities
        and e.kind in POSITIVE | {"rejection", "manual_correction"} for e in active)
    output["projection_checks_pass"] = all(all(r["checks"].values()) for r in ranges.values())
    issue_keys = {"missing_selected_application", "conflicting_application_targets", "no_active_confirmed_application_event",
                  "future_outcome_timestamp", "missing_outcome_type_in_analytics", "only_undated_status_fallback_no_email_link"}
    output["recorded_events_need_review"] = sum(reconciliation[key] for key in issue_keys)
    output["owner_filed_outcome_worded_emails"] = sum(
        m.classification in POSITIVE | {"possible_rejection", "rejection"} and m.decision == "receipt"
        and m.decision_reason.startswith("You marked") for m in messages)
    # This report never reads Gmail, so a green arithmetic check cannot certify
    # exhaustive observation or claim that every employer email was captured.
    output["mailbox_coverage_certified"] = False
    return output


def main() -> int:
    settings = get_settings()
    if not settings.database_url.startswith("postgresql"):
        print("Production audit requires PostgreSQL with enforced read-only transactions.")
        return 2
    engine = create_engine(settings.database_url, connect_args={"options": "-c default_transaction_read_only=on -c jit=off"},
                           isolation_level="REPEATABLE READ")
    try:
        with Session(engine) as db:
            result = audit(db)
            db.rollback()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["projection_checks_pass"] else 1
    except Exception as exc:
        # Never print exception parameters, SQL bind values or private rows.
        print(f"Read-only audit could not finish ({type(exc).__name__}). No result is certified.")
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
