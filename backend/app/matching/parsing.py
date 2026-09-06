"""Resume text extraction for ACE.

Supports the formats a job search actually produces: PDF exports, Word
documents, and plain text.

Extraction failures are surfaced rather than swallowed. A resume that
silently parsed to an empty string would score every posting at zero and
look like a matching bug rather than an upload problem.
"""

from __future__ import annotations

import io
import re


MAX_RESUME_BYTES = 10 * 1024 * 1024

MIN_EXTRACTED_CHARS = 200


class ResumeParseError(ValueError):
    """Raised when resume text cannot be extracted."""


def _normalize(
    text: str,
) -> str:
    """Collapse whitespace while preserving line structure."""

    without_nulls = text.replace(
        "\x00",
        " ",
    )

    collapsed = re.sub(
        r"[ \t\r\f\v]+",
        " ",
        without_nulls,
    )

    return re.sub(
        r"\n{3,}",
        "\n\n",
        collapsed,
    ).strip()


def _extract_pdf(
    payload: bytes,
) -> str:
    """Extract text from a PDF resume."""

    import pdfplumber

    pages: list[str] = []

    with pdfplumber.open(
        io.BytesIO(
            payload
        )
    ) as document:
        for page in document.pages:
            pages.append(
                page.extract_text()
                or ""
            )

    return "\n".join(
        pages
    )


def _extract_docx(
    payload: bytes,
) -> str:
    """Extract text from a Word resume."""

    import docx

    document = docx.Document(
        io.BytesIO(
            payload
        )
    )

    parts = [
        paragraph.text
        for paragraph
        in document.paragraphs
    ]

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(
                    cell.text
                )

    return "\n".join(
        parts
    )


def extract_resume_text(
    *,
    payload: bytes,
    filename: str,
) -> str:
    """Extract plain text from an uploaded resume.

    Raises:
        ResumeParseError: when the file is empty, too large, an
            unsupported format, or yields too little text to be a
            resume.
    """

    if not payload:
        raise ResumeParseError(
            "The uploaded file was empty."
        )

    if len(
        payload
    ) > MAX_RESUME_BYTES:
        raise ResumeParseError(
            (
                "Resume exceeds the "
                f"{MAX_RESUME_BYTES // (1024 * 1024)} MB "
                "limit."
            )
        )

    lowered = (
        filename or ""
    ).lower().strip()

    try:
        if lowered.endswith(
            ".pdf"
        ):
            text = _extract_pdf(
                payload
            )

        elif lowered.endswith(
            (
                ".docx",
                ".doc",
            )
        ):
            text = _extract_docx(
                payload
            )

        elif lowered.endswith(
            (
                ".txt",
                ".md",
            )
        ):
            text = payload.decode(
                "utf-8",
                errors="replace",
            )

        else:
            raise ResumeParseError(
                (
                    "Unsupported resume "
                    "format. Upload a PDF, "
                    "DOCX, or plain text "
                    "file."
                )
            )

    except ResumeParseError:
        raise

    except Exception as exc:
        raise ResumeParseError(
            (
                "Could not read that file: "
                f"{type(exc).__name__}."
            )
        ) from exc

    normalized = _normalize(
        text
    )

    if len(
        normalized
    ) < MIN_EXTRACTED_CHARS:
        raise ResumeParseError(
            (
                "Only "
                f"{len(normalized)} characters "
                "of text could be read. If this "
                "is a scanned PDF, export a "
                "text-based copy instead."
            )
        )

    return normalized
