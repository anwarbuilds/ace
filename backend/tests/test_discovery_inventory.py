"""The comparison must detect ID collisions without mistaking them for parity."""

from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "discovery_inventory.py"
spec = importlib.util.spec_from_file_location("discovery_inventory", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_identity_comparison_detects_cloud_only_and_id_reuse() -> None:
    report = module.compare(
        {1: "a" * 32, 2: "b" * 32},
        {1: "c" * 32, 3: "b" * 32},
    )
    assert report == {
        "legacy_jobs": 2,
        "cloud_jobs": 2,
        "shared_job_identities": 1,
        "legacy_only_job_identities": 1,
        "cloud_only_job_identities": 1,
        "same_numeric_id_different_job": 1,
    }


def test_duplicate_identity_inventory_is_rejected(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.gz"
    with gzip.open(inventory, "wt", encoding="ascii") as stream:
        stream.write(f"1|{'a' * 32}\n2|{'a' * 32}\n")
    with pytest.raises(ValueError, match="duplicate job identity"):
        module.read_inventory(inventory)
