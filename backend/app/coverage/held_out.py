"""Test lists: job lists ACE is scored against and never reads (REC-03).

A list ACE reads cannot measure ACE. Simplify looked like near perfect
coverage only because ACE ingests it. So the job lists split into two sets
that never overlap:

* reading lists, which help ACE find jobs (Simplify, and later zapply,
  FreeHire and Jobright as pointers), and
* test lists, kept here, which only the daily score opens.

Nothing that finds jobs may read a test list: not a feed, not a reader,
not the lead check, not a pasted link. ``is_held_out`` names every address
that belongs to one, the polite reader and the public feed reader refuse
them, and ``held_out_rows`` finds any stored row that came from one. A test
fails if any of these ever lets one through.

HiringCafe was considered as an outside comparison and left out on
2026-11-16: its terms page answers automated readers with a bot check.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import sqlalchemy as sa
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class HeldOutList:
    """One test list, as the daily score reads it."""

    key: str
    label: str
    repo: str
    url: str
    # "employer": rows link the employer's own posting.
    # "short": rows link a short redirect, so they match by company and title.
    links: str


HELD_OUT_LISTS: tuple[HeldOutList, ...] = (
    HeldOutList(
        key="speedyapply",
        label="speedyapply new grad USA",
        repo="speedyapply/2027-SWE-College-Jobs",
        url=(
            "https://raw.githubusercontent.com/"
            "speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md"
        ),
        links="employer",
    ),
    HeldOutList(
        key="vanshb03",
        label="vanshb03 new grad",
        repo="vanshb03/New-Grad-2027",
        url=(
            "https://raw.githubusercontent.com/"
            "vanshb03/New-Grad-2027/main/README.md"
        ),
        links="short",
    ),
)

# Whole GitHub accounts, so a renamed or next year's list is covered too
# (both lists were "2026" until they renamed themselves "2027").
HELD_OUT_OWNERS = frozenset({"speedyapply", "vanshb03"})

# vanshb03's short links. Following one reads the test list's own redirect.
HELD_OUT_HOSTS = frozenset({"vansh.nyc"})

# The lists ACE may read, by GitHub account or site. Never a test list.
READING_LISTS = frozenset({"simplifyjobs", "zapply", "freehire", "jobright", "jobright-ai"})

_GITHUB_HOSTS = frozenset(
    {
        "github.com",
        "www.github.com",
        "raw.githubusercontent.com",
        "api.github.com",
        "codeload.github.com",
        "objects.githubusercontent.com",
        "media.githubusercontent.com",
    }
)

# Text that marks a stored row as taken from a test list.
_MARKERS = tuple(sorted(HELD_OUT_OWNERS | HELD_OUT_HOSTS))


class HeldOutListRead(RuntimeError):
    """Something that finds jobs tried to read a test list."""


def _github_owner(host: str, path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if host == "api.github.com" and len(parts) >= 2 and parts[0] in {"repos", "users", "orgs"}:
        return parts[1].lower()
    return parts[0].lower() if parts else ""


def is_held_out(url: str | None) -> bool:
    """Say whether an address belongs to a test list."""

    if not url:
        return False
    text = url.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        return False
    if any(host == blocked or host.endswith("." + blocked) for blocked in HELD_OUT_HOSTS):
        return True
    if host in _GITHUB_HOSTS:
        return _github_owner(host, parts.path) in HELD_OUT_OWNERS
    if host.endswith(".github.io"):
        return host.removesuffix(".github.io") in HELD_OUT_OWNERS
    return False


def refuse_held_out(url: str) -> None:
    """Stop a job-finding read of a test list, loudly."""

    if is_held_out(url):
        raise HeldOutListRead(f"{url} is a test list; only the daily score may read it")


def held_out_rows(session: Session) -> dict[str, int]:
    """Count stored rows that came from a test list. Every count must be zero.

    Read only. It looks at what a job-finding read would leave behind: a board,
    a job's link, or a lead's origin and boards.
    """

    from backend.app.db.models import EmployerLead, JobRecord, JobSourceRecord

    def matching(*columns) -> sa.ColumnElement[bool]:
        return sa.or_(
            *(
                sa.func.lower(sa.cast(column, sa.Text)).contains(marker)
                for column in columns
                for marker in _MARKERS
            )
        )

    def count(model, *columns) -> int:
        return int(
            session.scalar(sa.select(sa.func.count()).select_from(model).where(matching(*columns)))
            or 0
        )

    return {
        "boards": count(JobSourceRecord, JobSourceRecord.source_account, JobSourceRecord.source_host),
        "jobs": count(JobRecord, JobRecord.official_url, JobRecord.source_account),
        "leads": count(EmployerLead, EmployerLead.origin_details, EmployerLead.boards),
    }
