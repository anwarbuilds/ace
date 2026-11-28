"""Startup networks in 13 more regions become leads, collected once (DIS-18, owner approved 2026-11-28).

For each network's public job board (Getro boards: jobs.<network>/...), within
its robots.txt and crawl delay: read the sitemap, take each company once, read
one of its job pages (an engineering title first) and keep only the company's
name, its website and the job's original link when that names a board ACE can
read. Nothing else: no job text, no person.

    collect --out networks.json         reads the networks below, writes the companies
    import networks.json [--apply]      puts the ones ACE does not read on Leads (dry run by default)

The lead check then reads each board, or searches by name starting at the
website, and adds a good board through the usual checks.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

# Read on 2026-11-28; the regions without a readable network are recorded in
# the requirements file with the reason.
NETWORKS = (
    {"name": "Detroit Venture Partners network", "region": "Detroit and Ann Arbor", "base": "https://jobs.detroit.vc"},
    {"name": "Drive Capital portfolio", "region": "Columbus", "base": "https://jobs.drivecapital.com"},
    {"name": "Rev1 Ventures portfolio", "region": "Columbus", "base": "https://jobs.rev1ventures.com"},
    {"name": "Launch Tennessee", "region": "Nashville", "base": "https://jobs.launchtn.org"},
    {"name": "Elevate Ventures portfolio", "region": "Indianapolis", "base": "https://jobs.elevateventures.com"},
    {"name": "Edison Partners portfolio", "region": "New Jersey", "base": "https://jobs.edisonpartners.com"},
)

READABLE = frozenset({"greenhouse", "lever", "ashby", "gem", "workday", "oracle_recruiting", "workable"})

_JOB_PATH = re.compile(r"/companies/([^/]+)/jobs/[^/<]+$")
_ENGINEERING = re.compile(r"engineer|developer|software|data|machine-learning|-ml-|-ai-|scientist", re.I)
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _current_job(page: str) -> dict:
    found = _NEXT.search(page or "")
    if not found:
        return {}
    data = json.loads(found.group(1))
    return (((data.get("props") or {}).get("pageProps") or {}).get("initialState") or {}).get("jobs", {}).get("currentJob") or {}


def collect(get=None, sleep=time.sleep) -> dict:
    from backend.app.discovery.detector import detect_source_from_url
    from backend.app.discovery.yc_names import website_host

    client = None
    if get is None:
        client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=False)
        get = client.get
    rows, notes = [], []
    try:
        for network in NETWORKS:
            base = network["base"]
            robots = robotparser.RobotFileParser()
            robots_response = get(base + "/robots.txt")
            robots.parse(robots_response.text.splitlines() if robots_response.status_code == 200 else [])
            delay = max(float(robots.crawl_delay(USER_AGENT) or 0), 1.0)
            if not robots.can_fetch(USER_AGENT, base + "/sitemap.xml"):
                notes.append({**network, "status": "robots refuse the sitemap"})
                continue
            sitemap = get(base + "/sitemap.xml")
            if sitemap.status_code != 200:
                notes.append({**network, "status": f"sitemap answered {sitemap.status_code}"})
                continue
            jobs: dict[str, list[str]] = {}
            for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap.text):
                matched = _JOB_PATH.search(urlsplit(loc).path)
                if matched and urlsplit(loc).netloc == urlsplit(base).netloc:
                    jobs.setdefault(matched.group(1), []).append(loc)
            read = 0
            for company_slug, links in sorted(jobs.items()):
                link = next((url for url in links if _ENGINEERING.search(url)), links[0])
                if not robots.can_fetch(USER_AGENT, link):
                    continue
                sleep(delay)
                page = get(link)
                read += 1
                if page.status_code in (401, 403, 405, 429):
                    notes.append({**network, "status": f"stopped: a job page answered {page.status_code}"})
                    break
                job = _current_job(page.text) if page.status_code == 200 else {}
                organization = job.get("organization") or {}
                name = " ".join(str(organization.get("name") or "").split())
                if not name:
                    continue
                board = None
                detected = detect_source_from_url(str(job.get("url") or ""))
                if detected is not None:
                    source_type = str(getattr(detected.source_type, "value", detected.source_type))
                    if source_type in READABLE:
                        board = {"source_type": source_type, "source_account": detected.source_account,
                                 "source_host": getattr(detected, "source_host", None)}
                rows.append({"network": network["name"], "region": network["region"], "company": name[:255],
                             "host": website_host(organization.get("domain")), "board": board})
            notes.append({**network, "status": "read", "companies": len(jobs), "pages_read": read})
    finally:
        if client is not None:
            client.close()
    return {"collected_at": datetime.now(timezone.utc).isoformat(), "networks": notes, "companies": rows}


def import_leads(data: dict, *, apply: bool) -> dict:
    import sqlalchemy as sa

    from backend.app.coverage.benchmark import normalise_company
    from backend.app.coverage.companies import is_namesake
    from backend.app.coverage.identity import shared_board_reason, staging_host_reason
    from backend.app.coverage.leads import CHECKING, DORMANT, NETWORK, NOREADER
    from backend.app.db.models import EmployerLead, JobSourceRecord
    from backend.app.db.session import SessionLocal
    from backend.app.discovery.feed_links import board_key

    now = datetime.now(timezone.utc)
    counts = Counter()
    with SessionLocal.begin() as session:
        catalog = {
            board_key(t, a)
            for t, a in session.execute(sa.select(JobSourceRecord.source_type, JobSourceRecord.source_account))
        }
        reading = {
            normalise_company(n)
            for (n,) in session.execute(sa.select(JobSourceRecord.company_name).where(JobSourceRecord.enabled.is_(True)))
        }
        rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
        for company in data["companies"]:
            key = normalise_company(company["company"])[:255]
            board = company.get("board")
            if board and (shared_board_reason(board["source_type"], board["source_account"])
                          or staging_host_reason(board["source_type"], board["source_account"], board.get("source_host"))
                          or is_namesake(board["source_type"], board["source_account"])):
                board = None
            if not key:
                counts["skipped"] += 1
                continue
            if key in reading or (board and board_key(board["source_type"], board["source_account"]) in catalog):
                counts["read_by_ace"] += 1
                continue
            details = {NETWORK, f"{NETWORK}:{company['network']}"} | ({f"site:{company['host']}"} if company.get("host") else set())
            boards = [board] if board else []
            row = rows.get(key)
            if row is None:
                session.add(EmployerLead(
                    company_key=key, company_name=company["company"], origin=NETWORK, origin_details=sorted(details),
                    state=CHECKING, reason="A startup in a regional network's job board. ace reads its board or looks for one.",
                    boards=boards, first_seen_at=now, next_check_at=now, updated_at=now,
                ))
                rows[key] = True
                counts["leads_new"] += 1
                continue
            if row is True:
                counts["skipped"] += 1
                continue
            known = {board_key(b["source_type"], b["source_account"]) for b in row.boards or []}
            added = [b for b in boards if board_key(b["source_type"], b["source_account"]) not in known]
            before = set(row.origin_details or [])
            if not added and details <= before:
                counts["already_leads"] += 1
                continue
            row.origin_details = (sorted(details - before) + sorted(before))[:12]
            if added:
                row.boards = added + list(row.boards or [])
                if row.state in (CHECKING, DORMANT, NOREADER):
                    row.state = CHECKING
                    row.next_check_at = now
            row.updated_at = now
            counts["leads_updated"] += 1
        if not apply:
            session.rollback()
    return {"mode": "apply" if apply else "dry-run", **counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="step", required=True)
    col = sub.add_parser("collect")
    col.add_argument("--out", type=Path, required=True)
    imp = sub.add_parser("import")
    imp.add_argument("companies", type=Path)
    imp.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.step == "collect":
        data = collect()
        args.out.write_text(json.dumps(data, indent=1))
        print(json.dumps({"networks": data["networks"], "companies": len(data["companies"])}))
        return 0
    print(json.dumps(import_leads(json.loads(args.companies.read_text()), apply=args.apply)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
