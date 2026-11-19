"""Zapply's public new grad lists, read as pointers (DIS-12, 2026-11-18).

Zapply keeps public lists of new grad roles on GitHub, updated every ten
minutes: software (``REPOSITORY``) and, since 2026-11-19, data science and
machine learning (``LISTS``). The software list was renamed from
"New-Grad-Software-Engineering-Positions" to its 2027 name; GitHub still
answers the old one. Its README is the whole listing ("This
repo is display-only: it intentionally contains no raw data files"). Each
row names the company, the role, the place, how long ago it was posted and
a short link that spells the employer's posting:

    https://zapply.jobs/l/d/greenhouse-truveta-6249810004
                              platform   board   posting

ACE reads the README from GitHub's raw file host, the host Simplify's list
is read from, and never zapply's own site. From each row it builds the
employer's own link where the posting's address can be spelled exactly
(Greenhouse, Ashby, Lever, SmartRecruiters, Workable) and keeps the row as a
copy only while ACE does not read that board directly: the same rule as
Simplify's copies.

A Workday row names no data centre and no title slug, so its posting cannot
be spelled exactly (Workday answers a wrong slug with a page that holds no
posting); nor can Phenom, Oracle, Eightfold, BrassRing and a few others.
Since 2026-11-19, with the owner's approval, such a row is still kept as a
copy, linked by zapply's own link, which forwards the owner's click to the
employer's posting: the one exception to "the employer's own link" besides
RippleMatch. ACE itself never opens a zapply link (``is_zapply_link``): the
employer-page check skips it, so the copy is judged on its title and place
and says its requirements are unverified. The copy is dropped once ACE holds
that same posting open from the employer's own board (``held``), so it only
ever fills a gap, such as Workday refusing ACE's reads since 2026-11-16.

zapply's "Visa" column is never read: its terms call that field an
automated estimate, never an employer statement. A copy never counts as
found on the employer's own board.

Terms (README "Data & Reuse", in force since 2026-10-06): use, including
commercial use, with a followed link back to the repository and credit to
Zapply as the data source; listings are not resubmitted to job aggregators
or feeds; enrichment fields are not presented as employer statements.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta, timezone
import re
from typing import NamedTuple
from urllib.parse import urlsplit

import httpx

from backend.app.adapters.http_cache import (
    CacheValidators,
    is_unchanged,
    validators_from_response,
)
from backend.app.models.job import CanonicalJob


ZAPPLY_SOURCE = "zapply"

ZAPPLY_HOST = "zapply.jobs"

# Each list ACE reads, by its source account: the repository its terms ask
# a copy to link back to.
LISTS = {
    "new-grad-swe": "New-Grad-Software-Engineering-Jobs-2027",
    "new-grad-data": "New-Grad-Data-Science-Jobs-2027",
}

REPOSITORIES = {
    name: f"https://github.com/zapplyjobs/{repository}"
    for name, repository in LISTS.items()
}

REPOSITORY = REPOSITORIES["new-grad-swe"]

LIST_URLS = {
    name: (
        "https://raw.githubusercontent.com/zapplyjobs/"
        f"{repository}/main/README.md"
    )
    for name, repository in LISTS.items()
}

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

REQUEST_TIMEOUT_SECONDS = 30.0

# What a copy says of itself. The employer's page, when ACE reads it, gives
# the description the gate judges (verification/employer_page.py).
def placeholder(
    name: str = "new-grad-swe",
) -> str:
    return (
        "Listed on Zapply's new grad list "
        f"({REPOSITORIES[name]}). The link is the employer's own posting."
    )


# What a copy linked by zapply's own link says of itself. Kept short of the
# gate's 400 characters on purpose: the gate then says the requirements are
# unverified, which they are.
def pointer(
    name: str = "new-grad-swe",
) -> str:
    return (
        "Listed on Zapply's new grad list "
        f"({REPOSITORIES[name]}). ACE cannot read this posting on the "
        "employer's own site, so the link goes through Zapply to the "
        "employer's posting. Check its requirements there."
    )


PLACEHOLDER = placeholder()

POINTER = pointer()

# Where ACE holds postings a row names only by an identifier: the zapply
# platform word, and the ACE sources whose external_id is that identifier.
ID_SOURCES: dict[str, tuple[str, ...]] = {
    "apple": ("apple",),
    "bytedance": ("bytedance",),
    "eightfold": ("eightfold", "eightfold_pcsx"),
    "qualcomm": ("eightfold", "eightfold_pcsx"),
    "oracle": ("oracle_recruiting",),
}

_ROW = re.compile(
    r"^\|(.+)\|\s*$",
    re.MULTILINE,
)

_CODE = re.compile(
    r"https://zapply\.jobs/l/d/([A-Za-z0-9][A-Za-z0-9._~-]*)"
    r"(?:\?[A-Za-z0-9._~=&%-]*)?",
)

# A Workday posting's requisition, the last part of its path:
# ".../Software-Engineer_JR2026530221", or "_R-083877", or "_JR1-1" when a
# posting is listed twice.
_WORKDAY_REQUISITION = re.compile(
    r"_([A-Za-z0-9-]+)$",
)

_REPEAT = re.compile(
    r"-\d+$",
)

_BOLD = re.compile(
    r"\*\*(.+?)\*\*",
)

_TAG = re.compile(
    r"<[^>]+>",
)

_UUID = re.compile(
    r"-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)

_NUMBER = re.compile(
    r"-(\d{3,})$",
)

_SHORTCODE = re.compile(
    r"-([0-9A-Fa-f]{8,12})$",
)

_AGE = re.compile(
    r"^(\d+)\s*(mo|m|h|d|w)$",
    re.IGNORECASE,
)

_AGE_UNITS = {
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
    "mo": timedelta(days=30),
}


class ZapplyRow(NamedTuple):
    """One role as zapply's table lists it."""

    company: str
    title: str
    location: str
    posted_at: datetime | None
    code: str
    link: str = ""


def _cell(
    text: str,
) -> str:
    bold = _BOLD.search(
        text
    )

    if bold is not None:
        text = bold.group(1)

    return " ".join(
        _TAG.sub(
            " ",
            text,
        ).split()
    )


def posted_from(
    label: str,
    *,
    now: datetime,
) -> datetime | None:
    """The day a row says its role was posted: "16m", "3h", "2d" or a date.

    A day, not a moment: an age measured from each read would move with
    every read and make an unchanged copy look edited every fifteen
    minutes (the Workday list labels did exactly that until 2026-11-10).
    "2w" or "1mo" says too little to name a day, so it names none.
    """

    text = label.strip()

    age = _AGE.match(
        text
    )

    if age is not None:
        unit = age.group(2).lower()

        if unit in ("w", "mo"):
            return None

        moment = now - int(age.group(1)) * _AGE_UNITS[unit]

        return datetime(
            moment.year,
            moment.month,
            moment.day,
            tzinfo=timezone.utc,
        )

    try:
        day = datetime.strptime(
            text,
            "%Y-%m-%d",
        )
    except ValueError:
        return None

    return day.replace(
        tzinfo=timezone.utc,
    )


def parse_rows(
    markdown: str,
    *,
    now: datetime,
) -> list[ZapplyRow]:
    """Every role row in zapply's README, each link code once."""

    rows: list[ZapplyRow] = []

    seen: set[str] = set()

    for found in _ROW.findall(
        markdown
    ):
        cells = [
            cell.strip()
            for cell in found.split(
                "|"
            )
        ]

        if len(cells) < 6:
            continue

        code = _CODE.search(
            cells[5]
        )

        if code is None:
            continue

        company = _cell(
            cells[0]
        )

        title = _cell(
            cells[1]
        )

        if (
            not company
            or not title
            or code.group(1) in seen
        ):
            continue

        seen.add(
            code.group(1)
        )

        rows.append(
            ZapplyRow(
                company=company,
                title=title,
                location=_cell(
                    cells[2]
                ),
                posted_at=posted_from(
                    _cell(cells[3]),
                    now=now,
                ),
                code=code.group(1),
                link=code.group(0),
            )
        )

    return rows


def employer_link(
    code: str,
) -> str | None:
    """The employer's own posting a link code spells, where it can be spelled exactly."""

    platform, _, rest = code.partition(
        "-"
    )

    platform = platform.lower()

    if platform in ("ashby", "lever"):
        found = _UUID.search(
            rest
        )

        if found is None:
            return None

        board = rest[: found.start()]

        if not board:
            return None

        host = (
            "jobs.ashbyhq.com"
            if platform == "ashby"
            else "jobs.lever.co"
        )

        return f"https://{host}/{board}/{found.group(1).lower()}"

    if platform in ("greenhouse", "sr"):
        found = _NUMBER.search(
            rest
        )

        if found is None or not rest[: found.start()]:
            return None

        board = rest[: found.start()]

        if platform == "greenhouse":
            return f"https://job-boards.greenhouse.io/{board}/jobs/{found.group(1)}"

        return f"https://jobs.smartrecruiters.com/{board}/{found.group(1)}"

    if platform == "workable":
        found = _SHORTCODE.search(
            rest
        )

        if found is None or not rest[: found.start()]:
            return None

        return (
            f"https://apply.workable.com/{rest[: found.start()]}"
            f"/j/{found.group(1).upper()}/"
        )

    return None


def is_zapply_link(
    url: str,
) -> bool:
    """Whether a link is zapply's own, which ACE never opens itself."""

    host = (
        urlsplit(url).hostname
        or ""
    ).lower()

    return host == ZAPPLY_HOST or host.endswith(
        "." + ZAPPLY_HOST
    )


def _slug(
    text: str,
) -> str:
    return re.sub(
        r"[\s_]+",
        "-",
        text.strip().lower(),
    )


def workday_posting(
    code: str,
    boards: Iterable[str],
) -> tuple[str, str] | None:
    """The Workday board (``tenant/site``) and requisition a link code names.

    zapply spells a Workday posting as ``workday-{tenant}-{site}-{req}`` in
    lower case with hyphens, so "boeing/EXTERNAL_CAREERS" reads
    "workday-boeing-external-careers-JR2026530221". Tenants, sites and
    requisitions may all hold hyphens, so the code is read against the
    boards ACE holds, the longest that fits first.
    """

    if not code.lower().startswith(
        "workday-"
    ):
        return None

    rest = code[len("workday-"):].lower()

    best: tuple[str, str] | None = None

    for board in boards:
        tenant, _, site = board.partition(
            "/"
        )

        if not tenant or not site:
            continue

        prefix = f"{_slug(tenant)}-{_slug(site)}-"

        if (
            rest.startswith(prefix)
            and len(rest) > len(prefix)
            and (best is None or len(prefix) > len(best[1]))
        ):
            best = (
                board,
                prefix,
            )

    if best is None:
        return None

    return (
        best[0],
        rest[len(best[1]):],
    )


def workday_requisitions(
    external_id: str,
) -> set[str]:
    """The requisitions a held Workday posting's path ends with, in lower case."""

    found = _WORKDAY_REQUISITION.search(
        external_id.strip().rstrip("/")
    )

    if found is None:
        return set()

    requisition = found.group(1).lower()

    return {
        requisition,
        _REPEAT.sub(
            "",
            requisition,
        ),
    } - {""}


def posting_id(
    code: str,
) -> tuple[tuple[str, ...], str] | None:
    """The ACE sources and identifier a non-Workday link code names, where ACE
    holds that platform's postings under the same identifier."""

    platform, _, rest = code.partition(
        "-"
    )

    sources = ID_SOURCES.get(
        platform.lower()
    )

    if sources is None or not rest:
        return None

    identifier = rest.rsplit(
        "-",
        1,
    )[-1]

    if len(identifier) < 5:
        return None

    return (
        sources,
        identifier,
    )


def parse_list_name(
    source_account: str,
) -> str:
    name = source_account.strip().lower()

    if name not in LIST_URLS:
        raise ValueError(
            f"Unknown zapply list {source_account!r}; known: {sorted(LIST_URLS)}"
        )

    return name


def fetch_zapply_jobs(
    *,
    source_account: str,
    company_name: str = "",
    client: httpx.Client | None = None,
    validators: CacheValidators | None = None,
    read_directly: Callable[[str], bool] | None = None,
    held: Callable[[Sequence[ZapplyRow]], set[str]] | None = None,
    now: datetime | None = None,
) -> tuple[
    list[CanonicalJob],
    bool,
    CacheValidators,
]:
    """Read zapply's list once: the copies, whether it was unchanged, and
    the validators to send next time.

    ``company_name`` is ignored: the list spans many employers. A row
    whose board ACE reads directly gives no copy. A row whose employer link
    cannot be spelled exactly gives a copy linked by zapply's own link,
    unless ``held`` says ACE holds that posting open from the employer.
    """

    name = parse_list_name(
        source_account
    )

    moment = now or datetime.now(
        timezone.utc
    )

    owns_client = client is None

    http = (
        client
        if client is not None
        else httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain, text/markdown",
            },
            follow_redirects=True,
        )
    )

    try:
        response = http.get(
            LIST_URLS[name],
            headers=(
                validators.request_headers()
                if validators is not None
                else {}
            ),
        )

        if is_unchanged(
            response
        ):
            return (
                [],
                True,
                validators
                or CacheValidators(),
            )

        response.raise_for_status()

        next_validators = validators_from_response(
            response
        )

        jobs: list[CanonicalJob] = []

        rows = parse_rows(
            response.text,
            now=moment,
        )

        unspelled = [
            row
            for row in rows
            if employer_link(row.code) is None
            and row.link
        ]

        held_codes = (
            held(unspelled)
            if held is not None and unspelled
            else set()
        )

        for row in rows:
            link = employer_link(
                row.code
            )

            if link is None:
                if not row.link or row.code in held_codes:
                    continue

                description = pointer(name)
                link = row.link

            elif read_directly is not None and read_directly(
                link
            ):
                continue

            else:
                description = placeholder(name)

            jobs.append(
                CanonicalJob(
                    source=ZAPPLY_SOURCE,
                    company=row.company,
                    external_id=row.code,
                    requisition_id=None,
                    title=row.title,
                    location=row.location or "Unknown",
                    description=description,
                    official_url=link,
                    posted_at=row.posted_at,
                    updated_at=None,
                )
            )

    finally:
        if owns_client:
            http.close()

    return (
        jobs,
        False,
        next_validators,
    )
