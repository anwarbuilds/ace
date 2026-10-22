"""Dry-run-first importer for reviewed USCIS employer petition decisions.

Input is a normalized, owner-reviewed CSV. It must include the original USCIS
release URL, reporting period and an explicit legal-entity resolution decision.
No fuzzy company matching or DOL LCA to petition conversion occurs here.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from backend.app.db.models import CompanyPetitionReportRecord
from backend.app.db.session import SessionLocal

REQUIRED = {"ace_company", "legal_entity", "period", "report_version", "approvals", "denials", "source_uri", "entity_reviewed"}


def checked_row(row: dict[str, str]) -> dict:
    uri = row["source_uri"].strip()
    parsed = urlparse(uri)
    if parsed.scheme != "https" or parsed.hostname not in {"uscis.gov", "www.uscis.gov"}:
        raise ValueError("source_uri must link to the official USCIS release")
    if row["entity_reviewed"].strip().lower() != "yes":
        raise ValueError("entity_reviewed must be yes after human legal-entity review")
    company, legal, period, version = (row[key].strip() for key in ("ace_company", "legal_entity", "period", "report_version"))
    if not all((company, legal, period, version)):
        raise ValueError("company, legal entity, period and report version are required")
    if not period.startswith("FY "):
        raise ValueError("period must identify the USCIS fiscal year")
    approvals, denials = int(row["approvals"]), int(row["denials"])
    if approvals < 0 or denials < 0:
        raise ValueError("petition decisions cannot be negative")
    return {"ace_company": company, "legal_entity": legal, "period": period, "report_version": version,
            "petition_approvals": approvals, "petition_denials": denials, "source_uri": uri,
            "source_name": "USCIS H-1B Employer Data Hub", "metric_definition": "USCIS I-129 petition decisions", "entity_verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--apply", action="store_true", help="write reviewed records after dry-run inspection")
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED.issubset(set(reader.fieldnames or [])):
            raise SystemExit("CSV is missing required reviewed evidence columns")
        rows = [checked_row(row) for row in reader]
    if len({(r["source_uri"], r["legal_entity"], r["period"], r["report_version"]) for r in rows}) != len(rows):
        raise SystemExit("CSV repeats an official legal-entity report key")
    print(f"validated={len(rows)} mode={'apply' if args.apply else 'dry-run'}")
    if not args.apply:
        return 0
    stamp = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        for row in rows:
            found = session.scalar(select(CompanyPetitionReportRecord).where(
                CompanyPetitionReportRecord.source_uri == row["source_uri"],
                CompanyPetitionReportRecord.legal_entity == row["legal_entity"],
                CompanyPetitionReportRecord.period == row["period"],
                CompanyPetitionReportRecord.report_version == row["report_version"],
            ))
            if found is None:
                session.add(CompanyPetitionReportRecord(**row, first_seen_at=stamp, last_checked_at=stamp))
            else:
                for key, value in row.items():
                    setattr(found, key, value)
                found.last_checked_at = stamp
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
