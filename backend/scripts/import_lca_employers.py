"""Visa filings become name leads (DIS-10): the Department of Labor's LCA disclosure files.

DOL refuses automated downloads, so the owner downloads each quarter's files
in a browser (OFLC Performance Data, "LCA Programs (H-1B, H-1B1, E-3)"). This
script has two steps:

    aggregate FILE.xlsx [...] --out employers.json
        Reads the files row by row and keeps, per employer, how many certified
        full-time H-1B filings for software, data and machine learning roles it
        made at US work sites. Only the employer name, trade name, job code,
        state and decision date are read: the files' contact names, emails,
        phone numbers and addresses are never read or kept.

    import employers.json [--apply] [--min-filings N]
        Puts each employer ACE does not already read on Leads as "Visa
        filings", most filings first; the lead check then looks for its own job
        board by name and adds a good one through the usual checks. A dry run
        by default. Names only: no posting, no link, and nothing about a
        company's sponsorship is inferred for a job.

Every name match is exact on the normalised name; there is no fuzzy match, no
parent or subsidiary inference, and petitions or LCAs are never read as hires.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Standard Occupational Classification codes for the roles the owner applies to:
# software developers, web developers, computer and information research
# scientists, data scientists and other computer occupations (machine learning
# engineers are often filed there).
SOC_PREFIXES = ("15-1252", "15-1254", "15-1221", "15-2051", "15-1299")

KEPT_STATUSES = frozenset({"certified", "certified - withdrawn"})

READ_COLUMNS = (
    "CASE_STATUS", "DECISION_DATE", "VISA_CLASS", "SOC_CODE", "FULL_TIME_POSITION",
    "EMPLOYER_NAME", "TRADE_NAME_DBA", "WORKSITE_STATE", "H_1B_DEPENDENT",
)

ORIGIN = "visa_filings"

REASON = "Filed visa applications for software roles last year. ace looks for its job board by name."


def rows(path: Path):
    """Each row as a dict of the read columns only."""

    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True)
    try:
        sheet = book[book.sheetnames[0]]
        it = sheet.iter_rows(values_only=True)
        header = [str(cell or "").strip().upper() for cell in next(it)]
        missing = [name for name in READ_COLUMNS if name not in header]
        if missing:
            raise SystemExit(f"{path.name}: missing columns {missing}")
        index = {name: header.index(name) for name in READ_COLUMNS}
        for row in it:
            yield {name: row[position] if position < len(row) else None for name, position in index.items()}
    finally:
        book.close()


def kept(row: dict) -> bool:
    return (
        str(row["CASE_STATUS"] or "").strip().lower() in KEPT_STATUSES
        and str(row["VISA_CLASS"] or "").strip().upper() == "H-1B"
        and str(row["FULL_TIME_POSITION"] or "").strip().upper() == "Y"
        and str(row["SOC_CODE"] or "").strip().startswith(SOC_PREFIXES)
        and bool(str(row["WORKSITE_STATE"] or "").strip())
    )


def aggregate(paths: list[Path]) -> dict:
    from backend.app.coverage.benchmark import normalise_company

    filings: Counter[str] = Counter()
    names: dict[str, Counter[str]] = defaultdict(Counter)
    dependent: Counter[str] = Counter()
    last: dict[str, str] = {}
    read = 0
    for path in paths:
        for row in rows(path):
            read += 1
            if not kept(row):
                continue
            legal = " ".join(str(row["EMPLOYER_NAME"] or "").split())
            trade = " ".join(str(row["TRADE_NAME_DBA"] or "").split())
            key = normalise_company(legal)
            if not key:
                continue
            filings[key] += 1
            names[key][trade or legal] += 1
            if str(row["H_1B_DEPENDENT"] or "").strip().lower() == "yes":
                dependent[key] += 1
            decided = row["DECISION_DATE"]
            day = decided.date().isoformat() if isinstance(decided, datetime) else str(decided or "")[:10]
            if day > last.get(key, ""):
                last[key] = day
    employers = [
        {
            "key": key,
            "name": names[key].most_common(1)[0][0][:255],
            "filings": count,
            "h1b_dependent_share": round(dependent[key] / count, 2),
            "last_decision": last.get(key),
        }
        for key, count in filings.most_common()
    ]
    return {
        "files": [path.name for path in paths],
        "aggregated_at": datetime.now(timezone.utc).isoformat(),
        "rows_read": read,
        "filings_kept": sum(filings.values()),
        "employers": employers,
    }


def import_leads(data: dict, *, apply: bool, min_filings: int) -> dict:
    import sqlalchemy as sa

    from backend.app.coverage.benchmark import normalise_company
    from backend.app.coverage.leads import CHECKING
    from backend.app.db.models import EmployerLead, JobSourceRecord
    from backend.app.db.session import SessionLocal

    now = datetime.now(timezone.utc)
    counts = Counter()
    with SessionLocal.begin() as session:
        reading = {
            normalise_company(name)
            for (name,) in session.execute(sa.select(JobSourceRecord.company_name).where(JobSourceRecord.enabled.is_(True)))
        }
        leads = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
        for employer in data["employers"]:
            if employer["filings"] < min_filings:
                counts["below_min"] += 1
                continue
            key = normalise_company(employer["name"])[:255] or employer["key"][:255]
            if key in reading or employer["key"] in reading:
                counts["read_by_ace"] += 1
                continue
            row = leads.get(key) or leads.get(employer["key"])
            if row is True:
                # Two filed names that reduce to one company: the first, with more filings, is already on Leads.
                counts["same_company_again"] += 1
                continue
            if row is not None:
                if ORIGIN not in (row.origin_details or []):
                    row.origin_details = sorted(set(row.origin_details or []) | {ORIGIN})[:12]
                    row.updated_at = now
                counts["already_leads"] += 1
                continue
            session.add(EmployerLead(
                company_key=key, company_name=employer["name"], origin=ORIGIN, origin_details=[ORIGIN],
                state=CHECKING, reason=REASON, boards=[], first_seen_at=now, next_check_at=now, updated_at=now,
            ))
            leads[key] = True
            counts["leads_new"] += 1
        if not apply:
            session.rollback()
    return {"mode": "apply" if apply else "dry-run", "min_filings": min_filings, **counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="step", required=True)
    agg = sub.add_parser("aggregate")
    agg.add_argument("files", nargs="+", type=Path)
    agg.add_argument("--out", type=Path, required=True)
    imp = sub.add_parser("import")
    imp.add_argument("employers", type=Path)
    imp.add_argument("--apply", action="store_true")
    imp.add_argument("--min-filings", type=int, default=1)
    args = parser.parse_args()
    if args.step == "aggregate":
        data = aggregate(args.files)
        args.out.write_text(json.dumps(data, indent=1))
        print(json.dumps({k: v for k, v in data.items() if k != "employers"} | {"employers": len(data["employers"])}))
        return 0
    print(json.dumps(import_leads(json.loads(args.employers.read_text()), apply=args.apply, min_filings=args.min_filings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
