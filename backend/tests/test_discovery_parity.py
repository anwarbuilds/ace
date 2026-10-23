"""Independent discovery is compared without merging or masking misses."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from backend.scripts.discovery_parity import compare_snapshots, read_snapshot, render_markdown


SINCE = "2026-10-23T14:00:00+00:00"


def source(name: str, account: str, success: str | None, enabled: bool = True) -> dict:
    return {"source": name, "account": account, "enabled": enabled, "last_success_at": success}


def job(identity: str, first: str, status: str, account: str = "board") -> dict:
    return {
        "identity": identity, "source": "greenhouse", "account": account,
        "first_seen_at": first, "company": "Example", "title": "Software Engineer",
        "url": "https://example.com/job", "status": status,
        "early_career": True, "years": 2, "rule_version": "fixture",
    }


def snapshot(as_of: str, sources: list[dict], jobs: list[dict], polls: list[dict] | None = None) -> dict:
    return {
        "meta": {"version": 1, "since": SINCE, "as_of": as_of},
        "sources": {(row["source"], row["account"]): row for row in sources},
        "jobs": {row["identity"]: row for row in jobs},
        "polls": polls or [],
    }


def test_comparison_preserves_independent_results_and_snapshot_cutoff() -> None:
    common = "a" * 32
    legacy_only = "b" * 32
    cloud_only = "c" * 32
    after_cutoff = "d" * 32
    poll = {
        "started_at": "2026-10-23T14:30:00+00:00", "new": 2,
        "qualifying": 1, "boards": 10, "postings": 100,
        "sources_attempted": 11, "poll_attempts": 12, "failed_checks": 1,
    }
    legacy = snapshot(
        "2026-10-23T14:55:00+00:00",
        [source("greenhouse", "board", "2026-10-23T14:40:00+00:00"),
         source("greenhouse", "legacy", "2026-10-23T14:40:00+00:00")],
        [job(common, "2026-10-23T14:05:00+00:00", "PASS"),
         job(legacy_only, "2026-10-23T14:25:00+00:00", "PASS", "legacy")],
        [poll],
    )
    cloud = snapshot(
        "2026-10-23T15:00:00+00:00",
        [source("greenhouse", "board", "2026-10-23T14:45:00+00:00")],
        [job(common, "2026-10-23T14:06:00+00:00", "FAIL"),
         job(cloud_only, "2026-10-23T14:20:00+00:00", "PASS"),
         job(after_cutoff, "2026-10-23T14:58:00+00:00", "PASS")],
        [poll, {**poll, "started_at": "2026-10-23T14:45:00+00:00"}],
    )
    report = compare_snapshots(
        legacy, cloud, {1: common, 2: legacy_only},
        {99: common, 100: cloud_only, 101: after_cutoff},
    )
    assert report["recent"]["legacy_new"] == 2
    assert report["recent"]["cloud_new"] == 2
    assert report["recent"]["legacy_only"][0]["comparison"] == "source_not_enabled"
    assert report["recent"]["cloud_only"][0]["comparison"] == "review_after_source_check"
    assert len(report["recent"]["eligibility_mismatches"]) == 1
    assert len(report["windows"]) == 1
    assert "Legacy-only jobs: 1" in render_markdown(report)


def test_later_source_check_does_not_prove_a_miss() -> None:
    identity = "a" * 32
    legacy = snapshot(
        "2026-10-23T14:55:00+00:00",
        [source("greenhouse", "board", "2026-10-23T15:01:00+00:00")], [],
    )
    cloud = snapshot(
        "2026-10-23T15:00:00+00:00",
        [source("greenhouse", "board", "2026-10-23T14:50:00+00:00")],
        [job(identity, "2026-10-23T14:20:00+00:00", "PASS")],
    )
    report = compare_snapshots(legacy, cloud, {}, {1: identity})
    assert report["recent"]["cloud_only"][0]["comparison"] == "check_timing_unknown"


def test_unrecorded_legacy_attempts_remain_unavailable() -> None:
    poll = {
        "started_at": "2026-10-23T14:00:00+00:00", "new": 0,
        "qualifying": 0, "boards": 18, "postings": 200,
        "sources_attempted": None, "poll_attempts": None, "failed_checks": None,
    }
    legacy = snapshot("2026-10-23T14:30:00+00:00", [], [], [poll])
    cloud = snapshot("2026-10-23T14:30:00+00:00", [], [], [poll])
    report = compare_snapshots(legacy, cloud, {}, {})
    assert report["windows"][0]["legacy"]["boards"] == 18
    assert report["windows"][0]["legacy"]["sources_attempted"] is None
    assert "not recorded" in render_markdown(report)


def test_snapshot_rejects_duplicate_job_identity(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.gz"
    rows = [
        {"type": "meta", "version": 1, "since": SINCE, "as_of": SINCE},
        {"type": "job", **job("a" * 32, SINCE, "PASS")},
        {"type": "job", **job("a" * 32, SINCE, "PASS")},
    ]
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="duplicate job identity"):
        read_snapshot(path)
