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
    tighten_company,
    title_tokens,
)
from backend.app.applications.parsing import (
    ApplicationRow,
)
from backend.app.db.models import (
    ExternalApplicationRecord,
    JobMarkRecord,
    JobRecord,
)


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

    # Spaceless names, so "Open AI" reaches a stored "OpenAI".
    by_tight: dict[
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
            JobRecord.location,
        )
    ).all()

    for (
        job_id,
        company,
        title,
        url,
        location,
    ) in rows:
        candidate = Candidate(
            job_id=job_id,
            company=company,
            title=title,
            official_url=url,
            location=location or "",
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

        by_tight[
            tighten_company(
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
        dict(
            by_tight
        ),
    )


def preview_import(
    session: Session,
    *,
    rows: list[ApplicationRow],
) -> ImportPreview:
    """Match every row against stored jobs, writing nothing."""

    (
        by_url,
        by_company,
        by_tight,
    ) = _load_indexes(
        session
    )

    # Jobs an application is already recorded against. Lets a row the
    # user resolved by hand on an earlier upload settle itself on the
    # next one, which is what makes re-uploading a daily habit rather
    # than a chore.
    already_applied = frozenset(
        session.scalars(
            select(
                JobMarkRecord.job_id
            ).where(
                JobMarkRecord.applied_at
                .is_not(
                    None
                )
            )
        ).all()
    )

    matches = tuple(
        match_row(
            row,
            by_url=by_url,
            by_company=by_company,
            by_tight=by_tight,
            already_applied=already_applied,
        )
        for row in rows
    )

    return ImportPreview(
        rows=tuple(
            rows
        ),
        matches=matches,
    )


def external_match_key(
    *,
    company: str | None,
    title: str | None,
) -> str:
    """Return the de-duplication identity for a standalone application.

    Normalised on both halves, so the same row in a re-uploaded sheet
    updates the existing record instead of adding a second one.
    """

    return (
        normalize_company(
            company
        )
        + "|"
        + " ".join(
            sorted(
                title_tokens(
                    title
                )
            )
        )
    )


def _applied_instant(
    applied_on,
    *,
    fallback: datetime,
) -> datetime:
    """Turn a sheet's date cell into a stored instant."""

    if isinstance(
        applied_on,
        date,
    ):
        return datetime.combine(
            applied_on,
            time(
                12,
                0,
            ),
            tzinfo=timezone.utc,
        )

    if isinstance(
        applied_on,
        str,
    ) and applied_on:
        try:
            return datetime.combine(
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
            return fallback

    return fallback


def record_external_applications(
    session: Session,
    *,
    entries: list[dict],
    now: datetime | None = None,
) -> int:
    """Store applications that have no stored posting to attach to.

    Each entry is
    ``{"company", "title", "applied_on", "status", "url"}``.

    Re-importing the same sheet updates rather than duplicates, and a
    status already recorded is only overwritten when the new sheet
    actually states one. A blank status column on a later upload must
    not silently erase a rejection recorded earlier.

    Returns:
        How many rows were written or updated.
    """

    stamp = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    written = 0

    for entry in entries:
        company = str(
            entry.get(
                "company"
            )
            or ""
        ).strip()

        title = str(
            entry.get(
                "title"
            )
            or ""
        ).strip()

        if not company or not title:
            # Without both there is nothing to show and nothing to
            # de-duplicate on.
            continue

        key = external_match_key(
            company=company,
            title=title,
        )

        record = session.scalar(
            select(
                ExternalApplicationRecord
            ).where(
                ExternalApplicationRecord
                .match_key
                == key
            )
        )

        if record is None:
            record = (
                ExternalApplicationRecord(
                    company=company,
                    title=title,
                    match_key=key,
                    created_at=stamp,
                )
            )

            session.add(
                record
            )

        record.company = company

        record.title = title

        when = _applied_instant(
            entry.get(
                "applied_on"
            ),
            fallback=stamp,
        )

        record.applied_at = when

        status = entry.get(
            "status"
        ) or None

        if status:
            if (
                record.application_status
                != status
            ):
                record.status_changed_at = (
                    stamp
                )

            record.application_status = (
                status
            )

        elif (
            record.application_status
            is None
        ):
            record.application_status = (
                "applied"
            )

            record.status_changed_at = when

        if entry.get(
            "url"
        ):
            record.url = str(
                entry["url"]
            )

        record.updated_at = stamp

        written += 1

    session.flush()

    return written


def list_external_applications(
    session: Session,
) -> list[ExternalApplicationRecord]:
    """Return every standalone application, most recent first."""

    return list(
        session.scalars(
            select(
                ExternalApplicationRecord
            ).order_by(
                ExternalApplicationRecord
                .applied_at.desc()
                .nullslast(),
                ExternalApplicationRecord
                .id.desc(),
            )
        ).all()
    )


def apply_import(
    session: Session,
    *,
    decisions: list[dict],
    now: datetime | None = None,
) -> int:
    """Record applications for the confirmed rows.

    Each decision is
    ``{"job_id": int, "applied_on": date | None, "status": str | None}``.
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

        status = decision.get(
            "status"
        ) or None

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
            application_status=status,
            now=stamp,
        )

        marked += 1

    drop_external_duplicates(
        session,
        job_ids=seen,
    )

    return marked


def drop_external_duplicates(
    session: Session,
    *,
    job_ids: set[int],
) -> int:
    """Remove standalone records now covered by a real posting.

    An ambiguous row is kept as history until a posting is chosen for
    it, which means choosing one later would leave the application
    listed twice: once as a job mark and once as the placeholder. The
    placeholder is the one to drop, because the posting carries more.

    Returns:
        How many placeholders were removed.
    """

    if not job_ids:
        return 0

    keys = set()

    for job in session.scalars(
        select(
            JobRecord
        ).where(
            JobRecord.id.in_(
                job_ids
            )
        )
    ):
        keys.add(
            external_match_key(
                company=job.company,
                title=job.title,
            )
        )

    if not keys:
        return 0

    removed = 0

    for record in session.scalars(
        select(
            ExternalApplicationRecord
        ).where(
            ExternalApplicationRecord
            .match_key.in_(
                keys
            )
        )
    ):
        session.delete(
            record
        )

        removed += 1

    return removed
