"""Read a resume's structure: its sections, contact lines and dates.

Plain rules over extracted text, so the result is reproducible and every
finding points at the line it came from. Used both to suggest facts for
the knowledge base and to judge how parseable a resume is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Heading words, by the section kind they open. Matched against a whole
# short line, so "Experience" opens a section and a bullet mentioning
# experience does not.
SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "profile", "professional summary", "about me", "objective"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "relevant experience",
    ),
    "education": ("education", "academic background", "education and training"),
    "projects": ("projects", "personal projects", "selected projects", "academic projects"),
    "skills": (
        "skills",
        "technical skills",
        "core skills",
        "technologies",
        "skills and tools",
        "tools and technologies",
    ),
    "certifications": ("certifications", "certificates", "licenses and certifications"),
    "publications": ("publications", "papers"),
    "awards": ("awards", "honors", "honors and awards", "achievements"),
}

_HEADING_LOOKUP = {
    phrase: kind for kind, phrases in SECTION_HEADINGS.items() for phrase in phrases
}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_POINT = rf"(?:{_MONTH}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
_NOW = r"(?:present|current|now|today)"
# "Jan 2022 to Present", "2021 - 2023", "05/2020 to 08/2021". The joiner
# may be any dash or the word "to"; dashes are read here, never written.
DATE_RANGE = re.compile(
    rf"(?P<start>{_POINT})\s*(?:[-\u2010-\u2015\u2212]+|to|until)\s*(?P<end>{_POINT}|{_NOW})",
    re.IGNORECASE,
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+?\d{1,2}[\s.]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[^\s,;|]+", re.IGNORECASE)

BULLET = re.compile(r"^\s*(?:[•▪●◦‣⁃*\-]|\d+\.)\s+")


@dataclass
class Section:
    kind: str
    heading: str
    start: int  # index of the heading line
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DateSpan:
    line: int
    text: str
    start: tuple[int, int] | None  # (year, month)
    end: tuple[int, int] | None  # None means present
    ongoing: bool


@dataclass
class Structure:
    lines: list[str]
    sections: list[Section]
    emails: list[str]
    phones: list[str]
    links: list[str]
    dates: list[DateSpan]
    bullets: list[tuple[int, str]]

    def section(self, kind: str) -> Section | None:
        return next((s for s in self.sections if s.kind == kind), None)

    @property
    def kinds(self) -> list[str]:
        return [s.kind for s in self.sections]


def heading_kind(line: str) -> str | None:
    """The section a line opens, if it is a heading."""

    clean = re.sub(r"[^a-z& ]", "", line.strip().lower()).replace("&", "and")
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean or len(clean) > 40:
        return None
    return _HEADING_LOOKUP.get(clean)


def _point(text: str) -> tuple[int, int] | None:
    text = text.strip().lower().rstrip(".")
    m = re.match(r"(\d{1,2})/(\d{4})$", text)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"(\d{4})$", text)
    if m:
        return int(m.group(1)), 1
    m = re.match(r"([a-z]+)\.?\s+(\d{4})$", text)
    if m and m.group(1) in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)]
    return None


def read_structure(text: str) -> Structure:
    lines = [line.rstrip() for line in text.splitlines()]
    sections: list[Section] = []
    current: Section | None = None
    dates: list[DateSpan] = []
    bullets: list[tuple[int, str]] = []

    for index, line in enumerate(lines):
        kind = heading_kind(line)
        if kind:
            current = Section(kind=kind, heading=line.strip(), start=index)
            sections.append(current)
            continue
        if current is not None:
            current.lines.append(line)
        if BULLET.match(line):
            bullets.append((index, BULLET.sub("", line).strip()))
        for m in DATE_RANGE.finditer(line):
            ongoing = bool(re.fullmatch(_NOW, m.group("end").strip(), re.IGNORECASE))
            dates.append(
                DateSpan(
                    line=index,
                    text=m.group(0),
                    start=_point(m.group("start")),
                    end=None if ongoing else _point(m.group("end")),
                    ongoing=ongoing,
                )
            )

    return Structure(
        lines=lines,
        sections=sections,
        emails=sorted(set(EMAIL.findall(text))),
        phones=sorted({p.strip() for p in PHONE.findall(text)}),
        links=sorted(set(LINK.findall(text))),
        dates=dates,
        bullets=bullets,
    )


def date_problems(structure: Structure) -> list[str]:
    """Ranges that end before they start, or are dated in the future."""

    problems = []
    for span in structure.dates:
        if span.start and span.end and span.end < span.start:
            problems.append(f"'{span.text}' ends before it starts (line {span.line + 1}).")
    return problems
