"""Suggest knowledge-base facts from a resume's structure.

Everything produced here is a *suggestion*: it starts unapproved and the
owner verifies, corrects or discards it. Nothing is inferred beyond what
the lines say: no metric is guessed, no skill is added that the text
does not name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.app.matching.skills import extract_skills
from backend.app.studio.sections import (
    BULLET,
    DATE_RANGE,
    Section,
    Structure,
    _point,
    continues_bullet,
)


ENTRY_KINDS = {"experience": "experience", "education": "education", "projects": "project"}

_SPLIT = re.compile(r"\s*(?:\||\u2022|\t| {2,}|,\s+| at | @ |\s[-\u2013\u2014]\s)\s*")


@dataclass
class SuggestedFact:
    kind: str  # experience | education | project | skill | certification | summary
    title: str = ""
    organization: str = ""
    start: str = ""  # "2022-01"
    end: str = ""  # "2023-06" or "present"
    bullets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    evidence: str = ""  # the source lines, verbatim


def _iso(point: tuple[int, int] | None) -> str:
    return f"{point[0]:04d}-{point[1]:02d}" if point else ""


def _entries(section: Section) -> list[tuple[list[str], list[str]]]:
    """Split a section into (header lines, bullet lines) groups."""

    groups: list[tuple[list[str], list[str]]] = []
    header: list[str] = []
    bullets: list[str] = []
    for raw in section.lines:
        line = raw.strip()
        if not line:
            continue
        if BULLET.match(raw):
            bullets.append(BULLET.sub("", raw).strip())
            continue
        if bullets and continues_bullet(bullets[-1], line):
            bullets[-1] = f"{bullets[-1]} {line}"
            continue
        if bullets:
            # A plain line after bullets starts the next entry.
            groups.append((header, bullets))
            header, bullets = [], []
        header.append(line)
    if header or bullets:
        groups.append((header, bullets))
    return groups


def _entry_fact(kind: str, header: list[str], bullets: list[str]) -> SuggestedFact:
    joined = " ".join(header)
    start = end = ""
    m = DATE_RANGE.search(joined)
    if m:
        start = _iso(_point(m.group("start")))
        ongoing = re.fullmatch(r"present|current|now|today", m.group("end").strip(), re.IGNORECASE)
        end = "present" if ongoing else _iso(_point(m.group("end")))
        joined = (joined[: m.start()] + " " + joined[m.end():]).strip()
    parts = [p.strip(" ,|") for p in _SPLIT.split(joined) if p.strip(" ,|")]
    title = parts[0] if parts else ""
    organization = parts[1] if len(parts) > 1 else ""
    if kind == "education":
        # Schools are usually written first, the degree second.
        title, organization = (organization or title), (title if organization else "")
    text = "\n".join(header + bullets)
    return SuggestedFact(
        kind=kind,
        title=title[:200],
        organization=organization[:200],
        start=start,
        end=end,
        bullets=bullets,
        skills=sorted(extract_skills(text)),
        evidence=text,
    )


def suggest_facts(structure: Structure) -> list[SuggestedFact]:
    facts: list[SuggestedFact] = []
    for section in structure.sections:
        if section.kind in ENTRY_KINDS:
            for header, bullets in _entries(section):
                if not header and not bullets:
                    continue
                facts.append(_entry_fact(ENTRY_KINDS[section.kind], header, bullets))
        elif section.kind == "skills":
            for raw in section.lines:
                line = raw.strip()
                for skill in sorted(extract_skills(line)):
                    facts.append(SuggestedFact(kind="skill", title=skill, skills=[skill], evidence=line))
        elif section.kind == "certifications":
            for raw in section.lines:
                line = BULLET.sub("", raw).strip()
                if line:
                    facts.append(SuggestedFact(kind="certification", title=line[:200], evidence=line))
        elif section.kind == "summary":
            text = " ".join(l.strip() for l in section.lines if l.strip())
            if text:
                facts.append(SuggestedFact(kind="summary", title="Summary", bullets=[text], evidence=text))
    # One skill fact per skill, however many lines name it.
    seen: set[str] = set()
    unique: list[SuggestedFact] = []
    for fact in facts:
        if fact.kind == "skill":
            if fact.title in seen:
                continue
            seen.add(fact.title)
        unique.append(fact)
    return unique
