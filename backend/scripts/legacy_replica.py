"""Stream authoritative legacy discovery data into the cloud replica.

The legacy scheduler remains the only discovery writer during the parallel
monitoring period.  ``export`` reads a repeatable snapshot and writes a gzip
JSONL bundle.  ``apply`` transactionally upserts that bundle into the cloud
database while preserving the newer schema and cloud authentication data.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def _database_url() -> str:
    value = os.environ["DATABASE_URL"]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


TABLES: dict[str, dict[str, Any]] = {
    "job_sources": {
        "columns": (
            "id", "source_type", "source_account", "company_name", "enabled",
            "poll_interval_seconds", "discovery_source", "first_discovered_at",
            "last_verified_at", "created_at", "updated_at", "source_host",
        ),
        "conflict": ("id",),
        "where": "TRUE",
    },
    "source_states": {
        "columns": (
            "source", "source_account", "initialized_at", "last_success_at",
            "last_job_count", "http_etag", "http_last_modified",
            "last_unchanged_at", "last_full_fetch_at",
        ),
        "conflict": ("source", "source_account"),
        "where": "TRUE",
    },
    "poll_sessions": {
        "columns": (
            "id", "started_at", "last_activity_at", "jobs_discovered",
            "qualifying_discovered", "notified_at", "boards_checked",
            "postings_checked", "alert_status",
        ),
        "conflict": ("id",),
        "where": (
            "(last_activity_at >= %(since)s OR started_at >= %(since)s) "
            "AND started_at <= %(until)s"
        ),
    },
    "poll_windows": {
        "columns": ("window_start", "complete"),
        "conflict": ("window_start",),
        "where": "window_start >= %(since)s AND window_start <= %(until)s",
    },
    "source_poll_windows": {
        "columns": (
            "window_start", "source_type", "source_account", "poll_attempts",
            "successful_attempts", "failed_attempts", "postings_observed",
            "unchanged_attempts", "partial_snapshot_attempts", "last_attempt_at",
            "last_completed_at", "last_success_at",
        ),
        "conflict": ("window_start", "source_type", "source_account"),
        "where": "(last_attempt_at >= %(since)s OR window_start >= %(since)s) AND window_start <= %(until)s",
    },
    "jobs": {
        "columns": (
            "id", "source", "source_account", "external_id", "company",
            "requisition_id", "title", "location", "description", "official_url",
            "posted_at", "source_updated_at", "content_hash", "first_seen_at",
            "last_seen_at", "is_active", "closed_at", "first_seen_session_id",
            "employment_type",
        ),
        "conflict": ("id",),
        "where": (
            "id IN ("
            "SELECT id FROM jobs WHERE "
            "(first_seen_at >= %(since)s OR source_updated_at >= %(since)s "
            "OR closed_at >= %(since)s) AND first_seen_at <= %(until)s "
            "UNION SELECT job_id FROM job_evaluations WHERE "
            "evaluated_at >= %(since)s AND evaluated_at <= %(until)s"
            ") "
            "AND first_seen_at <= %(until)s"
        ),
    },
    "job_states": {
        "source": "jobs",
        "target": "jobs",
        "columns": ("id", "last_seen_at", "is_active", "closed_at"),
        "where": (
            "(last_seen_at >= %(since)s OR closed_at >= %(since)s) "
            "AND first_seen_at <= %(until)s"
        ),
        "update_only": True,
    },
    "job_evaluations": {
        "columns": (
            "job_id", "eligibility_status", "role_family", "role_priority",
            "rule_version", "reason_codes", "reasons",
            "required_experience_years", "content_hash", "evaluated_at",
            "is_early_career", "requirements_verified", "is_new_grad",
        ),
        "conflict": ("job_id",),
        "where": (
            "job_id IN ("
            "SELECT id FROM jobs WHERE "
            "(first_seen_at >= %(since)s OR source_updated_at >= %(since)s "
            "OR closed_at >= %(since)s) AND first_seen_at <= %(until)s "
            "UNION SELECT job_id FROM job_evaluations WHERE "
            "evaluated_at >= %(since)s AND evaluated_at <= %(until)s"
            ")"
        ),
        "json": ("reason_codes", "reasons"),
    },
    "job_resume_scores": {
        "columns": (
            "job_id", "resume_id", "score", "matched_skills", "missing_skills",
            "scored_at", "related_skills", "algorithm_version", "previous_score",
        ),
        "conflict": ("job_id", "resume_id"),
        "where": (
            "job_id IN ("
            "SELECT id FROM jobs WHERE "
            "(first_seen_at >= %(since)s OR source_updated_at >= %(since)s "
            "OR closed_at >= %(since)s) AND first_seen_at <= %(until)s "
            "UNION SELECT job_id FROM job_evaluations WHERE "
            "evaluated_at >= %(since)s AND evaluated_at <= %(until)s"
            ")"
        ),
        "json": ("matched_skills", "missing_skills", "related_skills"),
    },
    "job_marks": {
        "columns": (
            "job_id", "is_saved", "review_state", "applied_at", "updated_at",
            "application_status", "status_changed_at", "status_note",
        ),
        "conflict": ("job_id",),
        "where": "TRUE",
        "newer": "updated_at",
    },
    "external_applications": {
        "columns": (
            "id", "company", "title", "match_key", "applied_at",
            "application_status", "status_changed_at", "url", "created_at",
            "updated_at",
        ),
        "conflict": ("id",),
        "where": "TRUE",
        "newer": "updated_at",
    },
    "application_answers": {
        "columns": ("id", "label", "value", "sort_order", "updated_at"),
        "conflict": ("id",),
        "where": "TRUE",
        "newer": "updated_at",
    },
    "history_entries": {
        "columns": (
            "id", "kind", "sort_order", "employer", "job_title", "location",
            "is_current", "start_month", "start_year", "end_month", "end_year",
            "description", "updated_at",
        ),
        "conflict": ("id",),
        "where": "TRUE",
        "newer": "updated_at",
    },
    "source_probes": {
        "columns": (
            "id", "company_key", "company_name", "outcome", "detail",
            "source_type", "source_account", "checked_at",
        ),
        "conflict": ("id",),
        "where": "TRUE",
    },
}


ORDER = tuple(TABLES)


def _selected_tables(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ORDER
    selected = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = set(selected).difference(TABLES)
    if unknown:
        raise ValueError(f"unknown replica tables: {', '.join(sorted(unknown))}")
    return selected


def export_bundle(
    *, since: str, until: str, output: Path, tables: tuple[str, ...]
) -> None:
    params = {"since": since, "until": until}
    counts: dict[str, int] = {}
    with psycopg.connect(_database_url(), row_factory=dict_row) as connection:
        connection.execute(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        with gzip.open(output, "wt", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "meta", **params}) + "\n")
            for table in tables:
                spec = TABLES[table]
                columns = ", ".join(spec["columns"])
                source = spec.get("source", table)
                query = f"SELECT {columns} FROM {source} WHERE {spec['where']}"
                count = 0
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
                    for row in cursor:
                        stream.write(
                            json.dumps(
                                {"type": table, "row": row},
                                default=_json_default,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        count += 1
                counts[table] = count
    print(json.dumps({"output": str(output), "counts": counts}, sort_keys=True))


def _upsert_sql(table: str, spec: dict[str, Any]) -> str:
    columns = tuple(spec["columns"])
    conflicts = tuple(spec["conflict"])
    assignments = [column for column in columns if column not in conflicts]
    quoted_columns = ", ".join(columns)
    placeholders = ", ".join(f"%({column})s" for column in columns)
    conflict_sql = ", ".join(conflicts)
    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in assignments
    )
    where = ""
    if newer := spec.get("newer"):
        where = f" WHERE EXCLUDED.{newer} >= {table}.{newer}"
    return (
        f"INSERT INTO {table} ({quoted_columns}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}{where}"
    )


def apply_bundle(*, bundle: Path) -> None:
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, Any] | None = None
    with gzip.open(bundle, "rt", encoding="utf-8") as stream:
        for line in stream:
            payload = json.loads(line)
            kind = payload["type"]
            if kind == "meta":
                meta = payload
                continue
            if kind not in TABLES:
                raise ValueError(f"unknown replica table: {kind}")
            row = payload["row"]
            for column in TABLES[kind].get("json", ()):
                if row[column] is not None:
                    row[column] = Jsonb(row[column])
            rows[kind].append(row)
    if meta is None:
        raise ValueError("replica bundle has no metadata")

    applied: dict[str, int] = {}
    skipped: dict[str, int] = {}
    with psycopg.connect(_database_url()) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                for table in ORDER:
                    table_rows = rows.get(table, [])
                    if table in {
                        "job_evaluations",
                        "job_resume_scores",
                        "job_marks",
                    } and table_rows:
                        job_ids = tuple({row["job_id"] for row in table_rows})
                        cursor.execute(
                            "SELECT id FROM jobs WHERE id = ANY(%s)",
                            (list(job_ids),),
                        )
                        existing_ids = {row[0] for row in cursor.fetchall()}
                        original_count = len(table_rows)
                        table_rows = [
                            row for row in table_rows
                            if row["job_id"] in existing_ids
                        ]
                        skipped[table] = original_count - len(table_rows)
                    if table_rows and TABLES[table].get("update_only"):
                        target = TABLES[table]["target"]
                        assignments = ", ".join(
                            f"{column} = %({column})s"
                            for column in TABLES[table]["columns"]
                            if column != "id"
                        )
                        cursor.executemany(
                            f"UPDATE {target} SET {assignments} WHERE id = %(id)s",
                            table_rows,
                        )
                    elif table_rows:
                        cursor.executemany(_upsert_sql(table, TABLES[table]), table_rows)
                    applied[table] = len(table_rows)
                for table in (
                    "job_sources",
                    "poll_sessions",
                    "jobs",
                    "external_applications",
                    "application_answers",
                    "history_entries",
                    "source_probes",
                ):
                    cursor.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "GREATEST(COALESCE((SELECT max(id) FROM " + table + "), 1), 1), true)",
                        (table,),
                    )
    print(
        json.dumps(
            {"meta": meta, "applied": applied, "skipped": skipped},
            sort_keys=True,
        )
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--since", required=True)
    export.add_argument("--until", required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--tables",
        help="comma-separated table names; defaults to the complete replica set",
    )
    apply = subparsers.add_parser("apply")
    apply.add_argument("--input", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if args.command == "export":
        export_bundle(
            since=args.since,
            until=args.until,
            output=args.output,
            tables=_selected_tables(args.tables),
        )
    else:
        apply_bundle(bundle=args.input)


if __name__ == "__main__":
    main()
