"""Reading an application history out of a spreadsheet.

People track applications in whatever shape they happened to invent, so
this reads column *meaning* rather than a fixed schema: any header that
plainly names a company, a role, a date or a link is used, and the rest
is ignored.

Nothing here decides which stored job a row refers to. Parsing answers
"what did the file say", matching answers "which posting is that", and
keeping them apart is what lets a bad match be re-run without re-reading
the file.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
)
import io
import re


class ApplicationParseError(Exception):
    """Raised when a file cannot be read as an application list."""


# Header synonyms, lowercase. Longest match wins, so "job title" is not
# mistaken for a company column by the bare word "job".
COLUMN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "company": (
        "company name",
        "employer",
        "organization",
        "organisation",
        "company",
    ),
    "title": (
        "job title",
        "position title",
        "role title",
        "position",
        "title",
        "role",
        "job",
    ),
    "applied_on": (
        "date applied",
        "applied date",
        "application date",
        "applied on",
        "date",
        "applied",
    ),
    "url": (
        "job url",
        "posting url",
        "job link",
        "link",
        "url",
    ),
}


DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
)


@dataclass(
    frozen=True,
    slots=True,
)
class ApplicationRow:
    """One row of a user's application history."""

    row_number: int

    company: str

    title: str

    applied_on: date | None

    url: str | None

    @property
    def is_usable(self) -> bool:
        """Return whether the row names something matchable.

        A URL alone is enough, because it identifies a posting exactly.
        Otherwise both a company and a title are needed: either one on
        its own would match far too many stored jobs.
        """

        if self.url:
            return True

        return bool(
            self.company
            and self.title
        )


def _normalize_header(
    value: str,
) -> str:
    """Reduce a header cell to comparable text."""

    return re.sub(
        r"[^a-z0-9 ]+",
        " ",
        str(
            value or ""
        ).strip().lower(),
    ).strip()


def map_columns(
    headers: list[str],
) -> dict[str, int]:
    """Map known fields to column indexes.

    Synonyms are tried longest first so a header like "job title" binds
    to the title column rather than being claimed by "job".
    """

    normalized = [
        _normalize_header(
            header
        )
        for header in headers
    ]

    mapping: dict[str, int] = {}

    claimed: set[int] = set()

    for field, synonyms in (
        COLUMN_SYNONYMS.items()
    ):
        for synonym in sorted(
            synonyms,
            key=len,
            reverse=True,
        ):
            for index, header in enumerate(
                normalized
            ):
                if (
                    index in claimed
                    or header != synonym
                ):
                    continue

                mapping[field] = index

                claimed.add(
                    index
                )

                break

            if field in mapping:
                break

    return mapping


def parse_date(
    value,
) -> date | None:
    """Parse a date cell, returning None when it cannot be read.

    Unreadable is not an error: the row still identifies an application,
    and the caller decides what to do about a missing date rather than
    losing the whole row over one cell.
    """

    if value in (
        None,
        "",
    ):
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    text = str(
        value
    ).strip()

    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(
                text,
                fmt,
            ).date()
        except ValueError:
            continue

    return None


def _rows_from_csv(
    payload: bytes,
) -> list[list]:
    """Read a CSV or tab separated file into raw cells."""

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "latin-1",
    ):
        try:
            text = payload.decode(
                encoding
            )

            break
        except UnicodeDecodeError:
            continue
    else:
        raise ApplicationParseError(
            "This file is not readable as text."
        )

    sample = text[:4096]

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;\t|",
        )
    except csv.Error:
        dialect = csv.excel

    return [
        row
        for row in csv.reader(
            io.StringIO(
                text
            ),
            dialect,
        )
    ]


def _rows_from_xlsx(
    payload: bytes,
) -> list[list]:
    """Read the first worksheet of a workbook into raw cells."""

    try:
        from openpyxl import (
            load_workbook,
        )
    except ImportError as error:
        raise ApplicationParseError(
            "Excel files need the openpyxl "
            "package. Export as CSV instead."
        ) from error

    try:
        workbook = load_workbook(
            io.BytesIO(
                payload
            ),
            read_only=True,
            data_only=True,
        )
    except Exception as error:
        raise ApplicationParseError(
            "This file could not be opened "
            "as a spreadsheet."
        ) from error

    try:
        sheet = workbook.worksheets[0]

        return [
            list(
                row
            )
            for row in sheet.iter_rows(
                values_only=True,
            )
        ]
    finally:
        workbook.close()


def parse_applications(
    *,
    payload: bytes,
    filename: str,
) -> list[ApplicationRow]:
    """Read an application history file into rows.

    Raises:
        ApplicationParseError: when the file cannot be read, or when no
            column names a company, a role or a link. Failing loudly
            matters here: silently returning zero rows would look
            exactly like "you have not applied to anything".
    """

    name = (
        filename or ""
    ).lower()

    if name.endswith(
        (
            ".xlsx",
            ".xlsm",
        )
    ):
        raw = _rows_from_xlsx(
            payload
        )
    elif name.endswith(
        (
            ".csv",
            ".tsv",
            ".txt",
        )
    ):
        raw = _rows_from_csv(
            payload
        )
    else:
        raise ApplicationParseError(
            "Upload a CSV or an Excel file."
        )

    raw = [
        row
        for row in raw
        if any(
            str(
                cell or ""
            ).strip()
            for cell in row
        )
    ]

    if not raw:
        raise ApplicationParseError(
            "This file has no rows."
        )

    headers = [
        str(
            cell or ""
        )
        for cell in raw[0]
    ]

    mapping = map_columns(
        headers
    )

    if not mapping:
        raise ApplicationParseError(
            "No column named a company, a "
            "role or a link. Expected a "
            "header row with names like "
            "Company, Title, Date applied."
        )

    def cell(
        row: list,
        field: str,
    ) -> str:
        index = mapping.get(
            field
        )

        if (
            index is None
            or index >= len(row)
        ):
            return ""

        return str(
            row[index]
            if row[index] is not None
            else ""
        ).strip()

    parsed: list[ApplicationRow] = []

    for offset, row in enumerate(
        raw[1:],
        start=2,
    ):
        date_index = mapping.get(
            "applied_on"
        )

        raw_date = (
            row[date_index]
            if date_index is not None
            and date_index < len(row)
            else None
        )

        parsed.append(
            ApplicationRow(
                row_number=offset,
                company=cell(
                    row,
                    "company",
                ),
                title=cell(
                    row,
                    "title",
                ),
                applied_on=parse_date(
                    raw_date
                ),
                url=cell(
                    row,
                    "url",
                )
                or None,
            )
        )

    return parsed
