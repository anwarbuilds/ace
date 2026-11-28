"""Hacker News "Who is hiring?": each month's companies become leads, read every six hours (DIS-11).

On the first weekday of each month the ``whoishiring`` account posts "Ask HN:
Who is hiring? (Month Year)", and companies reply one top-level comment each,
usually "Company | Role | Place | ... | link". ACE reads the thread through
Hacker News's official public API (``hacker-news.firebaseio.com``, which its
robots.txt allows for ``*.json`` and which has no rate limit), once every six
hours, and only the comments newer than the last one it read: comment ids only
grow, so the newest id read is all ACE remembers.

From each comment ACE keeps the company name and any job board link it
recognises (Greenhouse, Ashby, Lever and the others it reads), or the
company's own website. Nothing else: no comment text, no person's name, no
email. A company ACE does not read goes on Leads as "Hacker News"; the lead
check reads its board, or looks for one by name starting at its website, and
adds a good board through the usual checks. Owner approved 2026-11-28.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import html
import logging
import re
import time
from urllib.parse import urlsplit

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.companies import is_namesake
from backend.app.coverage.identity import shared_board_reason, staging_host_reason
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.feed_links import board_key
from backend.app.discovery.yc_names import website_host

LOGGER = logging.getLogger("ace.discovery.hn_hiring")

API = "https://hacker-news.firebaseio.com/v0"

ACCOUNT = "whoishiring"

ORIGIN = "hn"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

READ_EVERY = timedelta(hours=6)

PAUSE_SECONDS = 0.2

# The account also posts "Who wants to be hired?" and "Freelancer? Seeking
# freelancer?"; only this title is the hiring thread.
THREAD_TITLE = re.compile(r"^Ask HN: Who is hiring\? \(([A-Za-z]+) (\d{4})\)$")

# Its newest submissions hold this month's three threads.
SUBMISSIONS_TO_CHECK = 6

# Boards the lead check can read.
READABLE = frozenset({"greenhouse", "lever", "ashby", "gem", "workday", "oracle_recruiting", "workable"})

# Links that are never a company's own website.
NOT_A_COMPANY_SITE = (
    "ycombinator.com", "news.ycombinator.com", "workatastartup.com", "linkedin.com", "wellfound.com",
    "angel.co", "github.com", "twitter.com", "x.com", "google.com", "docs.google.com", "forms.gle",
    "notion.site", "calendly.com", "medium.com", "youtube.com", "lever.co", "greenhouse.io", "ashbyhq.com",
    "workable.com", "myworkdayjobs.com", "bit.ly", "glassdoor.com", "indeed.com", "arxiv.org", "wikipedia.org",
    "substack.com", "jobs.gem.com", "app.dover.com", "jobs.lever.co", "apply.workable.com",
)

REASON_BOARD = "Posted in Hacker News's Who is hiring? thread with a board ace has not read yet."

REASON_NAME = "Posted in Hacker News's Who is hiring? thread. ace looks for its job board by name."

_TAGS = re.compile(r"<[^>]+>")
_HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)
_BARE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
_PAREN = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*")


class Refused(RuntimeError):
    """The API answered with a refusal."""


@dataclass(slots=True)
class Post:
    company: str
    boards: list[tuple[str, str, str | None]] = field(default_factory=list)
    host: str | None = None


@dataclass(slots=True)
class Reading:
    thread: int | None = None
    thread_title: str = ""
    comments: int = 0
    new_comments: int = 0
    last_id: int = 0
    requests: int = 0
    posts: list[Post] = field(default_factory=list)


def company_of(text: str) -> str | None:
    """The company a comment's first line names, or None when it names none plainly."""

    first = re.split(r"<p>", text or "", maxsplit=1, flags=re.IGNORECASE)[0]
    first = html.unescape(_TAGS.sub(" ", first))
    if "|" not in first:
        return None
    name = first.split("|", 1)[0]
    name = _PAREN.sub(" ", name)
    name = re.sub(r"https?://\S+", " ", name)
    name = " ".join(name.split()).strip(" -:,.")
    if not name or len(name) > 60 or len(name.split()) > 6 or not re.search(r"[A-Za-z]", name):
        return None
    return name


def links_of(text: str) -> list[str]:
    unescaped = html.unescape(text or "")
    found = [html.unescape(link) for link in _HREF.findall(text or "")] + _BARE.findall(unescaped)
    return list(dict.fromkeys(link.rstrip(".,;") for link in found))


def post_of(text: str) -> Post | None:
    company = company_of(text)
    if company is None:
        return None
    post = Post(company=company)
    for link in links_of(text):
        detected = detect_source_from_url(link)
        if detected is not None:
            source_type = str(getattr(detected.source_type, "value", detected.source_type))
            if source_type in READABLE:
                board = (source_type, detected.source_account, getattr(detected, "source_host", None))
                if board not in post.boards:
                    post.boards.append(board)
                continue
        host = website_host(link)
        if post.host is None and host and not any(host == bad or host.endswith("." + bad) for bad in NOT_A_COMPANY_SITE):
            post.host = host
    return post


def _get(get, url: str, reading: Reading):
    response = get(url)
    reading.requests += 1
    if response.status_code in (401, 403, 405, 429) or response.headers.get("cf-mitigated"):
        raise Refused(f"hacker news answered {response.status_code}")
    response.raise_for_status()
    return response.json()


def read(
    get: Callable[[str], httpx.Response],
    *,
    after: int = 0,
    thread: int | None = None,
    pause: Callable[[float], None] = time.sleep,
) -> Reading:
    """The current hiring thread's comments newer than ``after`` (when it is the same thread)."""

    reading = Reading()
    user = _get(get, f"{API}/user/{ACCOUNT}.json", reading) or {}
    for item_id in (user.get("submitted") or [])[:SUBMISSIONS_TO_CHECK]:
        item = _get(get, f"{API}/item/{item_id}.json", reading) or {}
        if THREAD_TITLE.match(item.get("title") or "") and not item.get("deleted"):
            reading.thread, reading.thread_title = int(item["id"]), item["title"]
            kids = [int(kid) for kid in item.get("kids") or []]
            break
        pause(PAUSE_SECONDS)
    else:
        return reading
    since = after if thread == reading.thread else 0
    reading.comments = len(kids)
    newer = sorted(kid for kid in kids if kid > since)
    reading.new_comments = len(newer)
    reading.last_id = max([since, *newer])
    for kid in newer:
        pause(PAUSE_SECONDS)
        comment = _get(get, f"{API}/item/{kid}.json", reading) or {}
        if comment.get("deleted") or comment.get("dead"):
            continue
        post = post_of(comment.get("text") or "")
        if post is not None:
            reading.posts.append(post)
    return reading


def remember(
    session: Session,
    posts: list[Post],
    *,
    now: datetime,
) -> dict:
    """Write the companies ACE does not read into the lead ledger. Registers nothing."""

    from backend.app.coverage.leads import CHECKING, DORMANT, NOREADER

    catalog = {
        board_key(source_type, account): enabled
        for source_type, account, enabled in session.execute(
            sa.select(JobSourceRecord.source_type, JobSourceRecord.source_account, JobSourceRecord.enabled)
        )
    }
    reading = {
        normalise_company(name)
        for (name,) in session.execute(sa.select(JobSourceRecord.company_name).where(JobSourceRecord.enabled.is_(True)))
    }
    rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    counts = {"posts": len(posts), "read_by_ace": 0, "leads_new": 0, "leads_updated": 0, "skipped": 0}
    for post in posts:
        key = normalise_company(post.company)[:255]
        boards = [
            {"source_type": source_type, "source_account": account, "source_host": host}
            for source_type, account, host in post.boards
            if not (shared_board_reason(source_type, account) or staging_host_reason(source_type, account, host)
                    or is_namesake(source_type, account))
        ]
        if not key:
            counts["skipped"] += 1
            continue
        if key in reading or any(catalog.get(board_key(b["source_type"], b["source_account"])) for b in boards):
            counts["read_by_ace"] += 1
            continue
        # A board the catalog holds switched off stays a decision somebody made.
        boards = [b for b in boards if board_key(b["source_type"], b["source_account"]) not in catalog]
        details = {ORIGIN} | ({f"{ORIGIN}:{post.host}"} if post.host else set())
        row = rows.get(key)
        if row is None:
            row = EmployerLead(
                company_key=key, company_name=post.company[:255], origin=ORIGIN, origin_details=sorted(details),
                state=CHECKING, reason=REASON_BOARD if boards else REASON_NAME, boards=boards,
                first_seen_at=now, next_check_at=now, updated_at=now,
            )
            session.add(row)
            rows[key] = row
            counts["leads_new"] += 1
            continue
        known = {board_key(b["source_type"], b["source_account"]) for b in row.boards or []}
        added = [b for b in boards if board_key(b["source_type"], b["source_account"]) not in known]
        before = set(row.origin_details or [])
        if not added and details <= before:
            counts["skipped"] += 1
            continue
        row.origin_details = (sorted(details - before) + sorted(before))[:12]
        if added:
            # First, because the lead check reads only a lead's first few boards.
            row.boards = added + list(row.boards or [])
        if (added or (post.host and f"{ORIGIN}:{post.host}" not in before)) and row.state in (CHECKING, DORMANT, NOREADER):
            row.state = CHECKING
            row.reason = REASON_BOARD if added else REASON_NAME
            row.next_check_at = now
        row.updated_at = now
        counts["leads_updated"] += 1
    session.flush()
    return counts


def _last_mark(
    session: Session,
    now: datetime,
) -> dict:
    since = (now - timedelta(days=40)).date()
    marks = [
        (summary or {}).get(ORIGIN)
        for summary in session.scalars(
            sa.select(RecallRunRecord.summary).where(RecallRunRecord.day >= since).order_by(RecallRunRecord.day)
        )
    ]
    marks = [mark for mark in marks if mark and mark.get("checked_at")]
    return max(marks, key=lambda mark: mark["checked_at"]) if marks else {}


def read_if_due(
    session_factory: Callable,
    *,
    now: datetime,
    allows: Callable[[str], bool],
    get: Callable[[str], httpx.Response],
    pause: Callable[[float], None] = time.sleep,
) -> dict | None:
    """Read the thread every six hours, after the day's score. Returns what was recorded, or None when not due."""

    with session_factory() as session:
        run = session.scalars(sa.select(RecallRunRecord).order_by(RecallRunRecord.day.desc()).limit(1)).first()
        if run is None:
            return None
        last = _last_mark(session, now)
        if last and now - datetime.fromisoformat(last["checked_at"]) < READ_EVERY:
            return None
        run_id = run.id

    mark: dict = {"checked_at": now.isoformat(), "finished": False,
                  "thread": last.get("thread"), "last_id": last.get("last_id", 0)}
    if not allows(f"{API}/user/{ACCOUNT}.json"):
        mark["stopped"] = "hacker news's robots rules refuse ace"
    else:
        try:
            found = read(get, after=int(last.get("last_id") or 0), thread=last.get("thread"), pause=pause)
        except (Refused, httpx.HTTPError, ValueError) as error:
            mark["stopped"] = str(error)[:200] if isinstance(error, Refused) else type(error).__name__
        else:
            if found.thread is not None:
                with session_factory.begin() as session:
                    mark.update(remember(session, found.posts, now=now))
            mark.update({"finished": True, "thread": found.thread, "thread_title": found.thread_title,
                         "last_id": found.last_id or mark["last_id"], "comments": found.comments,
                         "new_comments": found.new_comments, "requests": found.requests})

    with session_factory.begin() as session:
        run = session.get(RecallRunRecord, run_id)
        run.summary = {**(run.summary or {}), ORIGIN: mark}
    LOGGER.info("hn_hiring_read %s", mark)
    return mark


__all__ = ["ORIGIN", "Post", "Reading", "USER_AGENT", "company_of", "links_of", "post_of", "read", "read_if_due", "remember"]
