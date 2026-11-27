"""Workable's public job file, read as pointers to employer postings (DIS-05).

Workable publishes every posting on its own job board, "Jobs by Workable",
in one XML file meant for job boards it does not integrate with:

    https://www.workable.com/boards/workable.xml

It is large (about 865 MB) and sent only compressed: a plain request is
answered 403 "compressed download required". www.workable.com's robots.txt
disallows only /user_password_resets, /admin, /auth/google and /j/, and
Workable's terms (March 2, 2026) are a contract with its customers that says
nothing about the file. The owner approved reading it on 2026-11-24.

Each ``<job>`` carries the posting's shortcode (``referencenumber``), title,
company, city, state, country, remote flag, job type, the employer's whole
description and Workable's own link, ``https://apply.workable.com/j/<code>``,
which opens the employer's posting on Workable. ACE never opens that link
itself: the description is already in the file.

Since November 2026 Workable answers most of ACE's board reads with 429, and
waits are all ACE does about that. The file fills the gap without touching
those boards: ACE keeps only US postings, full-time or with no type stated,
whose title the gate could pass, and drops any posting ACE already holds open
from the employer's own Workable board or as another list's copy (``held``),
matched by shortcode. A copy is a list copy in every count, never coverage.

Only a whole read can close anything. The parse must reach the end of the
file and hold a plausible number of postings, or the read raises and nothing
changes. A whole read closes only this source's own copies the file no longer
lists: a posting read from an employer's board is never closed by the file.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
import re
import tempfile
import time
from xml.etree import ElementTree

import httpx

from backend.app.adapters.http_cache import (
    CacheValidators,
    is_unchanged,
    validators_from_response,
)
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import _flatten


SOURCE = "workable_feed"

ACCOUNT = "jobs"

FEED_URL = "https://www.workable.com/boards/workable.xml"

FEED_HOST = "www.workable.com"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

# A large file: a slow minute between chunks is not a dead connection.
TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=120.0,
    write=30.0,
    pool=30.0,
)

CHUNK_BYTES = 1 << 16

# The file listed 169,426 postings when this reader was written
# (2026-11-24), 72,289 of them in the US. A read with far fewer is not the
# whole file, so it closes nothing: it raises instead.
MIN_POSTINGS = 50_000

# Workable's job types: "Full-time", "Part-time", "Contract", "Temporary",
# "Internship", "Other". An unstated type is left to the gate.
KEPT_TYPES = frozenset(
    {
        "full-time",
        "",
    }
)

LINK_HOST = "https://apply.workable.com/"

# A Workable posting link names its shortcode after "/j/", with or without
# the board's account before it.
POSTING_CODE = re.compile(
    r"apply\.workable\.com/(?:[^/?#]+/)?j/([0-9A-Za-z]{4,})",
    re.IGNORECASE,
)

# Nothing in a job file needs a document type or an entity; refusing them
# keeps the parser away from entity expansion altogether.
_UNSAFE = re.compile(
    rb"<!(?:DOCTYPE|ENTITY)",
    re.IGNORECASE,
)


class IncompleteWorkableFeed(RuntimeError):
    """The file did not arrive whole, so it proves nothing about closures."""


class UnsafeWorkableFeed(ValueError):
    """The file declared a document type or entities, which a job file never needs."""


@dataclass(slots=True)
class FeedStats:
    """What one read of the file held, for the log and the release checks."""

    postings: int = 0
    download_seconds: float = 0.0
    compressed_bytes: int = 0
    us_kept_type: int = 0
    could_pass: int = 0
    held: int = 0
    copies: int = 0
    types: dict[str, int] = field(default_factory=dict)


def posting_code(
    url: str | None,
) -> str | None:
    """The shortcode a Workable posting link names, in capitals."""

    found = POSTING_CODE.search(
        url or ""
    )

    return found.group(1).upper() if found else None


def entries(
    chunks: Iterable[bytes],
) -> Iterator[dict[str, str]]:
    """Every ``<job>`` in the file, as its fields, read as the bytes arrive.

    Raises ``IncompleteWorkableFeed`` when the file ends before its root
    element closes, and ``ElementTree.ParseError`` when it is not XML.
    """

    parser = ElementTree.XMLPullParser(
        events=(
            "start",
            "end",
        )
    )

    head = b""

    root = None

    closed = False

    for chunk in chunks:
        if not chunk:
            continue

        if len(head) < 4096:
            head += chunk[: 4096 - len(head)]

            if _UNSAFE.search(head):
                raise UnsafeWorkableFeed(
                    "The Workable file declares a document type or entities."
                )

        parser.feed(
            chunk
        )

        for event, element in parser.read_events():
            if event == "start":
                if root is None:
                    root = element
                continue

            if element is root:
                closed = True
                continue

            if element.tag != "job":
                continue

            yield {
                child.tag: (child.text or "").strip()
                for child in element
            }

            # Keep memory flat across hundreds of thousands of postings.
            element.clear()
            root.clear()

    parser.close()

    for event, element in parser.read_events():
        if event == "end" and element is root:
            closed = True

    if not closed:
        raise IncompleteWorkableFeed(
            "The Workable file ended before it closed."
        )


def _single_line(
    value: str | None,
) -> str:
    return " ".join(
        (value or "").split()
    )


def _location(
    entry: dict[str, str],
) -> str:
    place = ", ".join(
        part
        for part in (
            _single_line(entry.get("city")),
            _single_line(entry.get("state")),
            "United States",
        )
        if part
    )

    if (entry.get("remote") or "").strip().lower() == "true":
        place += " (Remote)"

    return place


def _posted_at(
    value: str | None,
) -> datetime | None:
    try:
        moment = parsedate_to_datetime(
            (value or "").strip()
        )
    except (TypeError, ValueError, IndexError):
        return None

    if moment is None:
        return None

    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def posting(
    entry: dict[str, str],
    *,
    could_pass: Callable[[str, str], bool],
    stats: FeedStats | None = None,
) -> CanonicalJob | None:
    """One file entry as a copy ACE keeps, or None.

    Cheapest checks first: the country and type are plain fields, the
    title is judged by the gate.
    """

    if (entry.get("country") or "").strip().upper() != "US":
        return None

    kind = (entry.get("jobtype") or "").strip().lower()

    if stats is not None:
        stats.types[kind] = stats.types.get(kind, 0) + 1

    if kind not in KEPT_TYPES:
        return None

    code = _single_line(entry.get("referencenumber")).upper()

    url = (entry.get("url") or "").strip()

    title = _single_line(entry.get("title"))

    company = _single_line(entry.get("company"))

    if not (code and title and company and url.startswith(LINK_HOST)):
        return None

    if posting_code(url) != code:
        return None

    if stats is not None:
        stats.us_kept_type += 1

    if not could_pass(title, company):
        return None

    if stats is not None:
        stats.could_pass += 1

    return CanonicalJob(
        source=SOURCE,
        company=company,
        external_id=code,
        requisition_id=code,
        title=title,
        location=_location(entry),
        description=_flatten(entry.get("description") or ""),
        official_url=url,
        posted_at=_posted_at(entry.get("date")),
        employment_type=(
            "full-time"
            if kind == "full-time"
            else None
        ),
    )


def fetch_workable_feed_jobs(
    *,
    could_pass: Callable[[str, str], bool],
    held: Callable[[set[str]], set[str]] | None = None,
    client: httpx.Client | None = None,
    validators: CacheValidators | None = None,
    min_postings: int = MIN_POSTINGS,
) -> tuple[
    list[CanonicalJob],
    bool,
    CacheValidators,
    FeedStats,
]:
    """Read the file once.

    Returns the copies to keep, whether the file was unchanged, the
    validators to send next time and what the file held. A refusal raises
    ``httpx.HTTPStatusError`` like any board read, so the scheduler's
    refusal backoff applies.
    """

    stats = FeedStats()

    owns_client = client is None

    http = client if client is not None else httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=False,
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/xml",
        # Workable sends the file only compressed; httpx decodes gzip.
        "Accept-Encoding": "gzip",
    }

    if validators is not None:
        headers.update(
            validators.request_headers()
        )

    found: dict[str, CanonicalJob] = {}

    # Workable's server ends a response about a minute after it starts, and
    # the file takes most of that minute to arrive (147 MB at 3.4 MB/s on
    # 2026-11-27). Judging postings while they arrive slowed the transfer
    # past that minute: 61 of 71 reads broke off ("incomplete chunked read").
    # So the compressed file is saved to disk as fast as it comes, and read
    # from there once it is whole.
    spool = tempfile.TemporaryFile()

    try:
        try:
            started = time.monotonic()

            with http.stream(
                "GET",
                FEED_URL,
                headers=headers,
            ) as response:
                if is_unchanged(response):
                    return [], True, validators or CacheValidators(), stats

                response.raise_for_status()

                next_validators = validators_from_response(
                    response
                )

                encoding = (response.headers.get("content-encoding") or "").strip().lower()

                for chunk in response.iter_raw(CHUNK_BYTES):
                    spool.write(chunk)
                    stats.compressed_bytes += len(chunk)

            stats.download_seconds = round(time.monotonic() - started, 1)

        finally:
            if owns_client:
                http.close()

        spool.seek(0)

        if encoding == "gzip":
            reader = gzip.GzipFile(fileobj=spool)
        elif encoding in ("", "identity"):
            reader = spool
        else:
            raise IncompleteWorkableFeed(
                f"The Workable file came in an encoding ACE did not ask for: {encoding}."
            )

        for entry in entries(iter(lambda: reader.read(CHUNK_BYTES), b"")):
            stats.postings += 1

            job = posting(
                entry,
                could_pass=could_pass,
                stats=stats,
            )

            if job is not None and job.external_id not in found:
                found[job.external_id] = job

    finally:
        spool.close()

    if stats.postings < min_postings:
        raise IncompleteWorkableFeed(
            f"The Workable file held {stats.postings} postings, fewer than {min_postings}."
        )

    held_codes = held(set(found)) if held is not None and found else set()

    stats.held = len(held_codes)

    jobs = [
        job
        for code, job in found.items()
        if code not in held_codes
    ]

    stats.copies = len(jobs)

    return jobs, False, next_validators, stats


__all__ = [
    "ACCOUNT",
    "FEED_HOST",
    "FEED_URL",
    "FeedStats",
    "IncompleteWorkableFeed",
    "SOURCE",
    "UnsafeWorkableFeed",
    "entries",
    "fetch_workable_feed_jobs",
    "posting",
    "posting_code",
]
