"""Read-only comparison of independent legacy and ACE Next discovery.

Export recent discovery snapshots inside each database container, then compare
them alongside full identity inventories from discovery_inventory.py. Never
write job, evaluation, source, application, or scheduler records.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _private(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)


def export_snapshot(*, since: str, output: Path) -> dict[str, Any]:
    import psycopg

    since_at = _utc(since)
    _private(output)
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    counts = {"sources": 0, "polls": 0, "jobs": 0}
    with psycopg.connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        captured_at = connection.execute("SELECT now()").fetchone()[0]
        with gzip.open(output, "wt", encoding="utf-8") as stream:
            def emit(kind: str, row: dict[str, Any]) -> None:
                stream.write(json.dumps({"type": kind, **row}, separators=(",", ":")) + "\n")

            emit("meta", {"version": 1, "since": _stamp(since_at), "as_of": _stamp(captured_at)})
            for row in connection.execute(
                "SELECT j.source_type, j.source_account, j.enabled, "
                "s.last_success_at FROM job_sources j LEFT JOIN source_states s "
                "ON s.source = j.source_type AND s.source_account = j.source_account "
                "ORDER BY j.source_type, j.source_account"
            ):
                emit("source", {
                    "source": row[0], "account": row[1], "enabled": row[2],
                    "last_success_at": _stamp(row[3]),
                })
                counts["sources"] += 1
            poll_columns = {
                row[0] for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = 'poll_sessions'"
                )
            }
            optional_poll_columns = ("sources_attempted", "poll_attempts", "failed_checks")
            optional_sql = ", ".join(
                name if name in poll_columns else f"NULL::integer AS {name}"
                for name in optional_poll_columns
            )
            for row in connection.execute(
                "SELECT started_at, jobs_discovered, qualifying_discovered, "
                f"boards_checked, postings_checked, {optional_sql} FROM poll_sessions "
                "WHERE started_at >= %s AND started_at < %s ORDER BY started_at, id",
                (since_at, captured_at),
            ):
                emit("poll", {
                    "started_at": _stamp(row[0]), "new": row[1],
                    "qualifying": row[2], "boards": row[3], "postings": row[4],
                    "sources_attempted": row[5], "poll_attempts": row[6],
                    "failed_checks": row[7],
                })
                counts["polls"] += 1
            with connection.cursor(name="recent_discovery_jobs") as cursor:
                cursor.execute(
                    "SELECT md5(jsonb_build_array(j.source, j.source_account, "
                    "j.external_id)::text), j.source, j.source_account, "
                    "j.first_seen_at, j.company, j.title, j.official_url, "
                    "e.eligibility_status, e.is_early_career, "
                    "e.required_experience_years, e.rule_version "
                    "FROM jobs j LEFT JOIN job_evaluations e ON e.job_id = j.id "
                    "WHERE j.first_seen_at >= %s AND j.first_seen_at < %s "
                    "ORDER BY j.first_seen_at, j.id",
                    (since_at, captured_at),
                )
                for row in cursor:
                    emit("job", {
                        "identity": row[0], "source": row[1], "account": row[2],
                        "first_seen_at": _stamp(row[3]), "company": row[4],
                        "title": row[5], "url": row[6], "status": row[7],
                        "early_career": row[8], "years": row[9],
                        "rule_version": row[10],
                    })
                    counts["jobs"] += 1
    return {"as_of": _stamp(captured_at), "counts": counts}


def read_snapshot(path: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"sources": {}, "polls": [], "jobs": {}}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            kind = row.pop("type")
            if kind == "meta":
                if "meta" in snapshot or row.get("version") != 1:
                    raise ValueError("missing or duplicate snapshot version")
                snapshot["meta"] = row
            elif kind == "source":
                key = (row["source"], row["account"])
                if key in snapshot["sources"]:
                    raise ValueError("duplicate source identity")
                snapshot["sources"][key] = row
            elif kind == "poll":
                snapshot["polls"].append(row)
            elif kind == "job":
                key = row["identity"]
                if key in snapshot["jobs"]:
                    raise ValueError("duplicate job identity")
                snapshot["jobs"][key] = row
            else:
                raise ValueError(f"unknown snapshot row: {kind}")
    if "meta" not in snapshot:
        raise ValueError("missing snapshot metadata")
    _utc(snapshot["meta"]["since"])
    _utc(snapshot["meta"]["as_of"])
    return snapshot


def _source_check(snapshot: dict[str, Any], job: dict[str, Any], cutoff: datetime) -> str:
    source = snapshot["sources"].get((job["source"], job["account"]))
    if source is None or not source["enabled"]:
        return "source_not_enabled"
    last_success = source["last_success_at"]
    if last_success is None:
        return "awaiting_source_check"
    if _utc(last_success) > cutoff:
        return "check_timing_unknown"
    if _utc(last_success) < _utc(job["first_seen_at"]):
        return "awaiting_source_check"
    return "review_after_source_check"


def _windows(snapshot: dict[str, Any], cutoff: datetime) -> dict[str, dict[str, int | None]]:
    windows: dict[str, dict[str, int | None]] = defaultdict(lambda: {
        "sources_attempted": None, "boards": 0, "postings": 0,
        "new": 0, "qualifying": 0, "failed_checks": None,
    })
    for poll in snapshot["polls"]:
        started = _utc(poll["started_at"])
        if started + timedelta(minutes=15) > cutoff:
            continue
        start = started.replace(minute=(started.minute // 15) * 15, second=0, microsecond=0)
        bucket = windows[_stamp(start)]
        for field in bucket:
            if poll[field] is not None:
                bucket[field] = (bucket[field] or 0) + poll[field]
    return dict(windows)


def compare_snapshots(
    legacy: dict[str, Any], cloud: dict[str, Any],
    legacy_inventory: dict[int, str], cloud_inventory: dict[int, str],
) -> dict[str, Any]:
    since = _utc(legacy["meta"]["since"])
    if since != _utc(cloud["meta"]["since"]):
        raise ValueError("snapshot cutoffs differ")
    cutoff = min(_utc(legacy["meta"]["as_of"]), _utc(cloud["meta"]["as_of"]))
    legacy_recent = {
        key: job for key, job in legacy["jobs"].items()
        if _utc(job["first_seen_at"]) <= cutoff
    }
    cloud_recent = {
        key: job for key, job in cloud["jobs"].items()
        if _utc(job["first_seen_at"]) <= cutoff
    }
    legacy_keys = set(legacy_inventory.values())
    cloud_keys = set(cloud_inventory.values())
    if not set(legacy["jobs"]).issubset(legacy_keys) or not set(cloud["jobs"]).issubset(cloud_keys):
        raise ValueError("identity inventories must include every snapshot job")
    unmatched: dict[str, list[dict[str, Any]]] = {"legacy_only": [], "cloud_only": []}
    for side, own_jobs, other, other_keys in (
        ("legacy_only", legacy_recent, cloud, cloud_keys),
        ("cloud_only", cloud_recent, legacy, legacy_keys),
    ):
        for identity, job in own_jobs.items():
            if identity in other_keys:
                continue
            unmatched[side].append({**job, "comparison": _source_check(other, job, cutoff)})
        unmatched[side].sort(key=lambda row: (row["status"] == "PASS", row["first_seen_at"]), reverse=True)
    mismatches = []
    for identity in legacy_recent.keys() & cloud_recent.keys():
        left, right = legacy_recent[identity], cloud_recent[identity]
        if left["status"] != right["status"]:
            mismatches.append({
                "identity": identity, "company": right["company"], "title": right["title"],
                "legacy_status": left["status"], "cloud_status": right["status"],
                "legacy_rule": left["rule_version"], "cloud_rule": right["rule_version"],
            })
    enabled_legacy = {key for key, row in legacy["sources"].items() if row["enabled"]}
    enabled_cloud = {key for key, row in cloud["sources"].items() if row["enabled"]}
    legacy_windows = _windows(legacy, cutoff)
    cloud_windows = _windows(cloud, cutoff)
    window_rows = [
        {"start": start, "legacy": legacy_windows.get(start), "cloud": cloud_windows.get(start)}
        for start in sorted(legacy_windows.keys() | cloud_windows.keys(), reverse=True)
    ]
    return {
        "since": _stamp(since), "compared_through": _stamp(cutoff),
        "legacy_as_of": legacy["meta"]["as_of"], "cloud_as_of": cloud["meta"]["as_of"],
        "inventory": {
            "legacy": len(legacy_keys), "cloud": len(cloud_keys),
            "shared": len(legacy_keys & cloud_keys),
        },
        "sources": {
            "legacy_enabled": len(enabled_legacy), "cloud_enabled": len(enabled_cloud),
            "legacy_only": [list(key) for key in sorted(enabled_legacy - enabled_cloud)],
            "cloud_only": [list(key) for key in sorted(enabled_cloud - enabled_legacy)],
        },
        "recent": {
            "legacy_new": len(legacy_recent), "cloud_new": len(cloud_recent),
            "legacy_pass": sum(row["status"] == "PASS" for row in legacy_recent.values()),
            "cloud_pass": sum(row["status"] == "PASS" for row in cloud_recent.values()),
            "legacy_only": unmatched["legacy_only"], "cloud_only": unmatched["cloud_only"],
            "eligibility_mismatches": sorted(mismatches, key=lambda row: row["company"]),
        },
        "windows": window_rows,
    }


def _cell(value: Any) -> str:
    plain = str(value if value is not None else "not recorded")
    plain = plain.replace("\u2014", " - ").replace("\u2013", " - ")
    plain = plain.replace("\n", " ").replace("\r", " ")
    return html.escape(plain, quote=False).replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def _pacific(value: str) -> str:
    return _utc(value).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%b %d, %I:%M %p %Z")


def _comparison_label(value: str) -> str:
    return {
        "source_not_enabled": "Source not enabled",
        "awaiting_source_check": "Source not checked since discovery",
        "review_after_source_check": "Review after source check",
        "check_timing_unknown": "Check timing unknown",
    }[value]


def render_markdown(report: dict[str, Any]) -> str:
    recent = report["recent"]
    sources = report["sources"]
    legacy_review = sum(job["comparison"] == "review_after_source_check" for job in recent["legacy_only"])
    cloud_review = sum(job["comparison"] == "review_after_source_check" for job in recent["cloud_only"])
    legacy_pending_pass = sum(job["status"] == "PASS" for job in recent["legacy_only"])
    cloud_pending_pass = sum(job["status"] == "PASS" for job in recent["cloud_only"])
    lines = [
        "# ACE discovery comparison", "",
        f"Period begins: {_pacific(report['since'])} ({report['since']})",
        f"Compared through: {_pacific(report['compared_through'])} ({report['compared_through']})", "",
        "Both databases remain independent. Application actions belong in ACE Next.",
        "A job seen on only one side is a review lead, not proof of an engine fault.", "",
        "Eligibility REJECT means the discovery rules did not pass the job. It is not an application rejection.", "",
        "## Coverage", "",
        f"Enabled sources: legacy {sources['legacy_enabled']}, ACE Next {sources['cloud_enabled']}.",
        f"New jobs in exported period: legacy {recent['legacy_new']}, ACE Next {recent['cloud_new']}.",
        f"Qualifying new jobs: legacy {recent['legacy_pass']}, ACE Next {recent['cloud_pass']}.",
        f"Legacy-only jobs: {len(recent['legacy_only'])}. ACE Next-only jobs: {len(recent['cloud_only'])}.",
        f"Qualifying jobs found on one side: legacy {legacy_pending_pass}, ACE Next {cloud_pending_pass}.",
        f"Jobs needing review after the other side checked the source: legacy-only {legacy_review}, ACE Next-only {cloud_review}.",
        f"Different eligibility decisions on jobs found by both: {len(recent['eligibility_mismatches'])}.", "",
        "## Fifteen minute pull windows", "",
        "Boards checked is the comparable source count. Sources attempted is shown only where recorded.", "",
        "| Window Pacific | Legacy boards | Next boards | Legacy attempted | Next attempted | Legacy new / qualifying | Next new / qualifying |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for window in report["windows"][:32]:
        left, right = window["legacy"], window["cloud"]
        l_attempts = _cell(left["sources_attempted"]) if left else "offline or no session"
        c_attempts = _cell(right["sources_attempted"]) if right else "offline or no session"
        l_new = f"{left['new']} / {left['qualifying']}" if left else "-"
        c_new = f"{right['new']} / {right['qualifying']}" if right else "-"
        l_boards = _cell(left["boards"]) if left else "offline or no session"
        c_boards = _cell(right["boards"]) if right else "offline or no session"
        lines.append(f"| {_pacific(window['start'])} | {l_boards} | {c_boards} | {l_attempts} | {c_attempts} | {l_new} | {c_new} |")
    for label, key in (("Legacy-only", "legacy_only"), ("ACE Next-only", "cloud_only")):
        jobs = recent[key]
        lines.extend(["", f"## {label} jobs", "",
                      "| Company | Role | Eligibility | Other side | First seen Pacific |",
                      "| --- | --- | --- | --- | --- |"])
        for job in jobs[:80]:
            lines.append(
                f"| {_cell(job['company'])} | {_cell(job['title'])} | "
                f"{_cell(job['status'])} | {_comparison_label(job['comparison'])} | "
                f"{_pacific(job['first_seen_at'])} |"
            )
        if len(jobs) > 80:
            lines.append(f"\nShowing 80 of {len(jobs)}. The JSON report contains every job.")
    lines.extend(["", "## Eligibility differences", "",
                  "| Company | Role | Legacy | ACE Next |",
                  "| --- | --- | --- | --- |"])
    for job in recent["eligibility_mismatches"][:80]:
        lines.append(
            f"| {_cell(job['company'])} | {_cell(job['title'])} | "
            f"{_cell(job['legacy_status'])} | {_cell(job['cloud_status'])} |"
        )
    if len(recent["eligibility_mismatches"]) > 80:
        lines.append("\nThe JSON report contains every eligibility difference.")
    lines.extend(["", "## Source catalog differences", ""])
    for label, key in (("Legacy only", "legacy_only"), ("ACE Next only", "cloud_only")):
        lines.append(f"{label}: {len(sources[key])} enabled sources.")
        for source, account in sources[key][:40]:
            lines.append(f"- {_cell(source)} / {_cell(account)}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--since", required=True, help="timezone-aware ISO timestamp")
    export.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare")
    for name in ("legacy", "cloud"):
        compare.add_argument(f"--{name}-snapshot", type=Path, required=True)
        compare.add_argument(f"--{name}-inventory", type=Path, required=True)
    compare.add_argument("--json-output", type=Path, required=True)
    compare.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export_snapshot(since=args.since, output=args.output)))
        return
    from backend.scripts.discovery_inventory import read_inventory

    report = compare_snapshots(
        read_snapshot(args.legacy_snapshot), read_snapshot(args.cloud_snapshot),
        read_inventory(args.legacy_inventory), read_inventory(args.cloud_inventory),
    )
    _private(args.json_output)
    _private(args.markdown_output)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "compared_through": report["compared_through"],
        "legacy_only": len(report["recent"]["legacy_only"]),
        "cloud_only": len(report["recent"]["cloud_only"]),
        "eligibility_mismatches": len(report["recent"]["eligibility_mismatches"]),
        "markdown_output": str(args.markdown_output),
    }))


if __name__ == "__main__":
    main()
