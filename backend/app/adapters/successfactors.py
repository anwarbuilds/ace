"""SuccessFactors careers sites: one job feed per company (DIS-08, owner approved 2026-11-28).

SAP SuccessFactors' career sites (Recruiting Marketing) serve postings at
``https://<host>/job/<city>-<title>/<id>/``, and their ``/sitemap.xml`` is not a
sitemap but a Google Base RSS feed of every open posting: title with its place,
the whole description, the link, the posting id, the place and the employer.
One request reads a company whole. Their robots.txt disallows only apply,
talent community, services and similar paths, never ``/sitemap.xml`` or
``/job/``.

The board is named by its host, ``jobs.example.com``. The feed is the whole
board, so a read is complete and a posting that leaves it is closed; a feed
with no postings or an answer that is not this feed raises, and closes nothing.
"""

from __future__ import annotations

from collections.abc import Callable
import html
import re
from xml.etree import ElementTree

import httpx

from backend.app.adapters.http_cache import CacheValidators, is_unchanged, validators_from_response
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import _flatten

SOURCE = "successfactors"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

TIMEOUT_SECONDS = 30.0

# Large employers list a few thousand postings; the feed is a few megabytes.
MAX_FEED_BYTES = 40 * 1024 * 1024

_BASE = "{http://base.google.com/ns/1.0}"

_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")

_UNSAFE = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)

# "Software Engineer (Neenah, WI, US, 54956)": the place the feed repeats in the title.
_TITLE_PLACE = re.compile(r"\s*\(([^()]*)\)\s*$")

# The zip code that ends a US place: "Neenah, WI, US, 54956".
_ZIP = re.compile(r",\s*\d{5}(?:-\d{4})?\s*$")


class NotASuccessFactorsFeed(ValueError):
    """The answer was not a SuccessFactors job feed."""


def feed_url(host: str) -> str:
    return f"https://{host}/sitemap.xml"


def board_host(account: str) -> str:
    host = (account or "").strip().lower().rstrip(".").removeprefix("https://").removeprefix("http://").split("/")[0]
    if not _HOST.match(host):
        raise ValueError(f"Not a SuccessFactors board host: {account!r}")
    return host


def _text(item, tag: str) -> str:
    found = item.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_feed(
    body: bytes,
    *,
    company_name: str,
) -> list[CanonicalJob]:
    if _UNSAFE.search(body[:4096]):
        raise NotASuccessFactorsFeed("The feed declares a document type or entities.")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise NotASuccessFactorsFeed("The answer is not XML.") from error
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise NotASuccessFactorsFeed("The answer is not a job feed.")
    jobs: list[CanonicalJob] = []
    seen: set[str] = set()
    for item in channel.findall("item"):
        posting_id = _text(item, f"{_BASE}id") or _text(item, "guid")
        link = _text(item, "link")
        title = " ".join(_text(item, "title").split())
        place = " ".join(_text(item, f"{_BASE}location").split())
        if not (posting_id and link.startswith("https://") and title) or posting_id in seen:
            continue
        seen.add(posting_id)
        repeated = _TITLE_PLACE.search(title)
        if repeated and (not place or repeated.group(1).strip() == place):
            place = place or repeated.group(1).strip()
            title = title[: repeated.start()].strip()
        jobs.append(
            CanonicalJob(
                source=SOURCE,
                company=company_name,
                external_id=posting_id,
                requisition_id=posting_id,
                title=title,
                location=_ZIP.sub("", place),
                description=_flatten(html.unescape(_text(item, "description"))),
                official_url=link,
            )
        )
    if not jobs:
        raise NotASuccessFactorsFeed("The feed lists no postings.")
    return jobs


def fetch_successfactors_jobs(
    *,
    source_account: str,
    company_name: str,
    client: httpx.Client | None = None,
    validators: CacheValidators | None = None,
) -> tuple[list[CanonicalJob], bool, CacheValidators]:
    host = board_host(source_account)
    owns = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"}
    if validators is not None:
        headers.update(validators.request_headers())
    try:
        with http.stream("GET", feed_url(host), headers=headers) as response:
            if is_unchanged(response):
                return [], True, validators or CacheValidators()
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_FEED_BYTES:
                    raise NotASuccessFactorsFeed("The feed is larger than any careers site's.")
            next_validators = validators_from_response(response)
    finally:
        if owns:
            http.close()
    return parse_feed(bytes(body), company_name=company_name), False, next_validators


__all__ = ["SOURCE", "NotASuccessFactorsFeed", "board_host", "feed_url", "fetch_successfactors_jobs", "parse_feed"]
