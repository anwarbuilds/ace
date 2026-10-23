"""Compare independent ACE discovery databases without copying job content.

Run ``export`` inside each API container, then ``compare`` on the two private
gzip files. Numeric IDs are included only to detect unsafe ID reuse. The job
identity is a digest of the unique (source, source_account, external_id) key.
No database writes are performed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path


def export_inventory(output: Path) -> int:
    import psycopg

    output.touch(mode=0o600, exist_ok=True)
    output.chmod(0o600)
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    count = 0
    with psycopg.connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with connection.cursor(name="discovery_inventory") as cursor:
            cursor.execute(
                "SELECT id, md5(jsonb_build_array(source, source_account, "
                "external_id)::text) FROM jobs ORDER BY id"
            )
            with gzip.open(output, "wt", encoding="ascii") as stream:
                for job_id, identity in cursor:
                    stream.write(f"{job_id}|{identity}\n")
                    count += 1
    return count


def read_inventory(path: Path) -> dict[int, str]:
    rows: dict[int, str] = {}
    with gzip.open(path, "rt", encoding="ascii") as stream:
        for line in stream:
            job_id_text, identity = line.rstrip("\n").split("|", 1)
            job_id = int(job_id_text)
            if job_id in rows or len(identity) != 32:
                raise ValueError(f"invalid or duplicate inventory entry in {path}")
            rows[job_id] = identity
    if len(set(rows.values())) != len(rows):
        raise ValueError(f"duplicate job identity in {path}")
    return rows


def compare(legacy: dict[int, str], cloud: dict[int, str]) -> dict[str, int]:
    legacy_keys = set(legacy.values())
    cloud_keys = set(cloud.values())
    return {
        "legacy_jobs": len(legacy),
        "cloud_jobs": len(cloud),
        "shared_job_identities": len(legacy_keys & cloud_keys),
        "legacy_only_job_identities": len(legacy_keys - cloud_keys),
        "cloud_only_job_identities": len(cloud_keys - legacy_keys),
        "same_numeric_id_different_job": sum(
            legacy[job_id] != cloud[job_id]
            for job_id in legacy.keys() & cloud.keys()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    report = commands.add_parser("compare")
    report.add_argument("--legacy", type=Path, required=True)
    report.add_argument("--cloud", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps({"jobs": export_inventory(args.output)}))
    else:
        print(json.dumps(compare(read_inventory(args.legacy), read_inventory(args.cloud))))


if __name__ == "__main__":
    main()
