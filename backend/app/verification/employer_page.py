"""Judge a feed posting on the employer's own page, not the feed's word.

The curated feed lists a posting with no description: a placeholder
sentence and a few structured fields. The rules that read requirement
text -- security clearance, citizenship, sponsorship, years of
experience -- therefore never ran on feed postings, and nearly every
one passed unread (364 of 372 on 2026-10-04).

An audit read the employer's own posting page for the 85 of them that
had one ACE could read. Fifty should have been rejected: 43 required a
security clearance, 18 US citizenship, 8 more experience than the user
has. Johns Hopkins APL, General Dynamics, Peraton, Noblis, Deloitte's
government practice. That was the clearance noise the user had been
reporting, and the reason they asked for ACE to rely on companies' own
sources rather than on aggregators.

So before a feed posting is judged, its employer page is read, and the
description found there is what the gate reads -- with the feed's own
structured sentences kept after it. What is read:

- the schema.org ``JobPosting`` an employer page publishes for search
  engines. Nearly every ATS that renders server-side includes one,
  because Google for Jobs requires it.

Pages are fetched only where robots.txt allows, only for postings whose
title could pass at all, at most a set number per poll, and each at most
once a week. A page that could not be read leaves the posting judged as
before, marked unverified -- silence is not rejection.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import html
import json
import logging
import re
from urllib.parse import urlsplit

import httpx
import sqlalchemy as sa

from backend.app.coverage.probing import (
    robots_allows,
)
from backend.app.models.job import CanonicalJob


LOGGER = logging.getLogger(
    "ace.verification",
)


USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

TIMEOUT_SECONDS = 15.0

# New pages read per poll of the feed. The first poll after this was
# built had about five hundred postings to read; the rest go on later
# polls. A page is someone else's server, read once a week at most.
FRESH_READS_PER_POLL = 150

CONCURRENCY = 4

# How long a reading stands. Requirements rarely change once posted; a
# page that could not be read is tried again sooner.
READ_TTL = timedelta(
    days=7,
)

FAILED_TTL = timedelta(
    days=1,
)

# A description shorter than this is a stub -- "Apply now" -- not one
# the gate can read requirements from.
MIN_DESCRIPTION_CHARS = 200

READ = "read"

NO_DESCRIPTION = "no_description"

DISALLOWED = "disallowed"

UNREACHABLE = "unreachable"


@dataclass(
    frozen=True,
    slots=True,
)
class Reading:
    """What one posting page said."""

    status: str

    description: str | None = None


def _flatten(
    text: str,
) -> str:
    text = html.unescape(
        text
    )

    # Block-level tags become breaks, so list items and paragraphs do
    # not run into one another and fuse words across them.
    text = re.sub(
        r"(?i)<\s*(br|/p|/li|/div|/h\d|/ul|/ol)\b[^>]*>",
        "\n",
        text,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(
        text
    )

    text = re.sub(
        r"[ \t\r\f\v]+",
        " ",
        text,
    )

    return re.sub(
        r"\n\s*\n+",
        "\n",
        text,
    ).strip()


def extract_job_description(
    page: str,
) -> str | None:
    """The description from a page's schema.org JobPosting, if any.

    Looked for in every JSON-LD block, at any depth: some pages wrap the
    posting in an ``@graph`` or a list.
    """

    for block in re.findall(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>",
        page,
        re.S | re.I,
    ):
        try:
            data = json.loads(
                block.strip()
            )
        except ValueError:
            continue

        stack = [
            data,
        ]

        while stack:
            node = stack.pop()

            if isinstance(
                node,
                list,
            ):
                stack.extend(
                    node
                )

                continue

            if not isinstance(
                node,
                dict,
            ):
                continue

            kind = node.get(
                "@type"
            )

            kinds = (
                kind
                if isinstance(
                    kind,
                    list,
                )
                else [
                    kind,
                ]
            )

            if "JobPosting" in kinds and node.get(
                "description"
            ):
                description = _flatten(
                    str(
                        node["description"]
                    )
                )

                qualifications = [
                    _flatten(
                        str(
                            node[field]
                        )
                    )
                    for field in (
                        "qualifications",
                        "experienceRequirements",
                        "educationRequirements",
                    )
                    if isinstance(
                        node.get(field),
                        str,
                    )
                ]

                return "\n\n".join(
                    part
                    for part in [
                        description,
                        *qualifications,
                    ]
                    if part
                )

            stack.extend(
                value
                for value in node.values()
                if isinstance(
                    value,
                    (dict, list),
                )
            )

    return None


class RobotsCache:
    """robots.txt per host, fetched once per verifier."""

    def __init__(
        self,
        client: httpx.Client,
    ) -> None:
        self._client = client

        self._texts: dict[str, str | None] = {}

    def allows(
        self,
        url: str,
    ) -> bool:
        parts = urlsplit(
            url
        )

        origin = f"{parts.scheme}://{parts.netloc}"

        if origin not in self._texts:
            self._texts[origin] = self._fetch(
                origin
            )

        return robots_allows(
            self._texts[origin],
            url,
            user_agent=USER_AGENT,
        )

    def _fetch(
        self,
        origin: str,
    ) -> str | None:
        # RFC 9309: a 4xx means no rules; a 5xx or no answer means the
        # rules are unknown, which must be read as disallow.
        try:
            response = self._client.get(
                f"{origin}/robots.txt",
            )
        except httpx.HTTPError:
            return None

        if response.status_code == 200:
            return response.text

        if 400 <= response.status_code < 500:
            return ""

        return None


def read_employer_page(
    url: str,
    *,
    client: httpx.Client,
    robots: RobotsCache,
) -> Reading:
    """Read one posting page, if its site allows it."""

    if not url.startswith(
        ("https://", "http://")
    ):
        return Reading(
            UNREACHABLE,
        )

    if not robots.allows(
        url
    ):
        return Reading(
            DISALLOWED,
        )

    try:
        response = client.get(
            url
        )
    except httpx.HTTPError:
        return Reading(
            UNREACHABLE,
        )

    if response.status_code != 200:
        return Reading(
            UNREACHABLE,
        )

    description = extract_job_description(
        response.text
    )

    if (
        description is None
        or len(description) < MIN_DESCRIPTION_CHARS
    ):
        return Reading(
            NO_DESCRIPTION,
        )

    return Reading(
        READ,
        description,
    )


def merged_description(
    employer_description: str,
    feed_description: str,
) -> str:
    """The employer's description, then the feed's own sentences.

    The feed's sentences are kept because they carry what the feed
    knows -- "does not offer sponsorship" among them.
    """

    return (
        f"{employer_description}\n\n"
        f"{feed_description}"
    ).strip()


class ReadingStore:
    """Readings kept in ``employer_page_readings``, keyed by URL.

    Shared by everything that reads a posting's own page or record: a
    reading is fetched once a week at most, whoever asks for it. Read
    and written in short sessions of their own, never inside a poll.
    """

    def __init__(
        self,
        session_factory: Callable | None = None,
    ) -> None:
        self._session_factory = session_factory

    def _sessions(
        self,
    ):
        if self._session_factory is not None:
            return self._session_factory

        from backend.app.db.session import (
            SessionLocal,
        )

        return SessionLocal

    def load(
        self,
        urls: Sequence[str],
    ) -> dict[str, tuple[Reading, datetime]]:
        """Each stored reading, with when it was taken."""

        from backend.app.db.models import (
            EmployerPageReading,
        )

        if not urls:
            return {}

        with self._sessions()() as session:
            rows = session.scalars(
                sa.select(
                    EmployerPageReading,
                ).where(
                    EmployerPageReading.url.in_(
                        sorted(set(urls))
                    ),
                )
            ).all()

        found: dict[str, tuple[Reading, datetime]] = {}

        for row in rows:
            checked = row.checked_at

            if checked.tzinfo is None:
                checked = checked.replace(
                    tzinfo=timezone.utc,
                )

            found[row.url] = (
                Reading(
                    row.status,
                    row.description,
                ),
                checked,
            )

        return found

    def save(
        self,
        readings: dict[str, Reading],
        *,
        moment: datetime,
    ) -> None:
        """Store fresh readings. An earlier successful reading survives
        a failed one: a posting that has gone is closed by its source,
        not by this."""

        from backend.app.db.models import (
            EmployerPageReading,
        )

        if not readings:
            return

        with self._sessions()() as session:
            for url, reading in readings.items():
                row = session.scalar(
                    sa.select(
                        EmployerPageReading,
                    ).where(
                        EmployerPageReading.url == url,
                    )
                )

                if row is None:
                    session.add(
                        EmployerPageReading(
                            url=url,
                            status=reading.status,
                            description=reading.description,
                            checked_at=moment,
                        )
                    )

                    continue

                if reading.status == READ or row.status != READ:
                    row.status = reading.status

                    row.description = reading.description

                row.checked_at = moment

            session.commit()


def is_stale(
    reading: Reading,
    checked_at: datetime,
    moment: datetime,
) -> bool:
    """Whether a stored reading is due to be taken again."""

    ttl = (
        READ_TTL
        if reading.status == READ
        else FAILED_TTL
    )

    return moment - checked_at >= ttl


class EmployerPageVerifier:
    """Give feed postings the description from the employer's page.

    Readings are kept in ``employer_page_readings`` -- read and written
    in short sessions of their own, never inside a poll transaction.
    """

    def __init__(
        self,
        *,
        session_factory: Callable | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
        worth_reading: Callable[[CanonicalJob], bool] | None = None,
        fresh_reads: int = FRESH_READS_PER_POLL,
        now: Callable[[], datetime] = lambda: datetime.now(
            timezone.utc
        ),
    ) -> None:
        self._store = ReadingStore(
            session_factory
        )

        self._client_factory = client_factory or (
            lambda: httpx.Client(
                timeout=TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml"
                    ),
                },
            )
        )

        self._worth_reading = worth_reading or (
            lambda _job: True
        )

        self._fresh_reads = fresh_reads

        self._now = now

    def __call__(
        self,
        jobs: Sequence[CanonicalJob],
    ) -> list[CanonicalJob]:
        wanted = sorted(
            {
                job.official_url
                for job in jobs
                if self._worth_reading(
                    job
                )
            }
        )

        if not wanted:
            return list(
                jobs
            )

        moment = self._now()

        stored = self._store.load(
            wanted
        )

        readings: dict[str, Reading] = {
            url: reading
            for url, (reading, _checked) in stored.items()
        }

        due = [
            url
            for url in wanted
            if url not in stored
            or is_stale(
                *stored[url],
                moment,
            )
        ][
            :self._fresh_reads
        ]

        if due:
            fresh = self._read_all(
                due
            )

            for url, reading in fresh.items():
                earlier = readings.get(
                    url
                )

                # A page that was read and now cannot be keeps the
                # description it gave: a posting that has gone will be
                # closed by the feed, not by this.
                if (
                    reading.status != READ
                    and earlier is not None
                    and earlier.status == READ
                ):
                    continue

                readings[url] = reading

            self._store.save(
                fresh,
                moment=moment,
            )

            LOGGER.info(
                "employer_pages_read count=%d read=%d",
                len(fresh),
                sum(
                    1
                    for reading in fresh.values()
                    if reading.status == READ
                ),
            )

        verified: list[CanonicalJob] = []

        for job in jobs:
            reading = readings.get(
                job.official_url
            )

            if (
                reading is not None
                and reading.status == READ
                and reading.description
            ):
                job = job.model_copy(
                    update={
                        "description": merged_description(
                            reading.description,
                            job.description,
                        ),
                    },
                )

            verified.append(
                job
            )

        return verified

    def _read_all(
        self,
        urls: list[str],
    ) -> dict[str, Reading]:
        with self._client_factory() as client:
            robots = RobotsCache(
                client
            )

            # robots.txt first, one host at a time, so concurrent page
            # reads never race to fetch the same host's rules.
            for url in urls:
                robots.allows(
                    url
                )

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=CONCURRENCY,
            ) as pool:
                return dict(
                    zip(
                        urls,
                        pool.map(
                            lambda url: read_employer_page(
                                url,
                                client=client,
                                robots=robots,
                            ),
                            urls,
                        ),
                    )
                )
