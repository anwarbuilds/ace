"""Previewing and applying an imported application history.

Import is two steps on purpose. The first reads the file and reports
what it believes, changing nothing. The second writes only the rows the
user confirmed. A one-step import would mean the first time you see a
wrong match is after it has already been recorded.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.marks import set_mark
from backend.app.applications.matching import (
    AMBIGUOUS,
    MATCHED,
    UNMATCHED,
    UNUSABLE,
    Candidate,
    RowMatch,
    match_row,
    normalize_company,
    normalize_url,
)
from backend.app.applications.parsing import (
    ApplicationRow,
)
from backend.app.db.models import JobRecord


@dataclass(
    frozen=True,
    slots=True,
)
class ImportPreview:
    """What an import would do, before anything is written."""

    rows: tuple[ApplicationRow, ...]

    matches: tuple[RowMatch, ...]

    @property
    def counts(self) -> dict:
        """Return how many rows fell into each outcome."""

        tally = {
            MATCHED: 0,
            AMBIGUOUS: 0,
            UNMATCHED: 0,
            UNUSABLE: 0,
        }

        for match in self.matches:
            tally[match.status] = (
                tally.get(
                    match.status,
                    0,
                )
                + 1
            )

        return tally


def _load_indexes(
    session: Session,
) -> tuple[
    dict[str, Candidate],
    dict[str, list[Candidate]],
]:
    """Index every stored job by URL and by company.

    Built once per import rather than queried per row: a few hundred
    rows against thirty thousand jobs would otherwise be a few hundred
    table scans.
    """

    by_url: dict[str, Candidate] = {}

    by_company: dict[
        str,
        list[Candidate],
    ] = defaultdict(
        list
    )

    rows = session.execute(
        select(
            JobRecord.id,
            JobRecord.company,
            JobRecord.title,
            JobRecord.official_url,
        )
    ).all()

    for (
        job_id,
        company,
        title,
        url,
    ) in rows:
        candidate = Candidate(
            job_id=job_id,
            company=company,
            title=title,
            official_url=url,
        )

        key = normalize_url(
            url
        )

        # First writer wins. Duplicate URLs across sources describe the
        # same posting, so either identifies it correctly.
        if key and key not in by_url:
            by_url[key] = candidate

        by_company[
            normalize_company(
                company
            )
        ].append(
            candidate
        )

    return (
        by_url,
        dict(
            by_company
        ),
    )


def preview_import(
    session: Session,
    *,
    rows: list[ApplicationRow],
) -> ImportPreview:
    """Match every row against stored jobs, writing nothing."""

    by_url, by_company = _load_indexes(
        session
    )

    matches = tuple(
        match_row(
            row,
            by_url=by_url,
            by_company=by_company,
        )
        for row in rows
    )

    return ImportPreview(
        rows=tuple(
            rows
        ),
        matches=matches,
    )


def apply_import(
    session: Session,
    *,
    decisions: list[dict],
    now: datetime | None = None,
) -> int:
    """Record applications for the confirmed rows.

    Each decision is ``{"job_id": int, "applied_on": date | None}``.
    A row without a usable date still counts as applied, stamped with
    the import time, because the fact of applying matters more than the
    day and dropping the row would lose it silently.

    Returns:
        How many jobs were marked.
    """

    stamp = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    marked = 0

    seen: set[int] = set()

    for decision in decisions:
        job_id = decision.get(
            "job_id"
        )

        if job_id is None:
            continue

        job_id = int(
            job_id
        )

        if job_id in seen:
            continue

        seen.add(
            job_id
        )

        if session.get(
            JobRecord,
            job_id,
        ) is None:
            continue

        applied_on = decision.get(
            "applied_on"
        )

        when = stamp

        if isinstance(
            applied_on,
            date,
        ):
            when = datetime.combine(
                applied_on,
                time(
                    12,
                    0,
                ),
                tzinfo=timezone.utc,
            )
        elif isinstance(
            applied_on,
            str,
        ) and applied_on:
            try:
                when = datetime.combine(
                    date.fromisoformat(
                        applied_on
                    ),
                    time(
                        12,
                        0,
                    ),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                when = stamp

        set_mark(
            session,
            job_id=job_id,
            applied=True,
            applied_at=when,
            now=stamp,
        )

        marked += 1

    return marked
