"""The ace compatibility checker: one resume against one job.

An *estimated, versioned ace score*, not a prediction of any employer's
system. No employer's ranking is public, so none is imitated. Every
number comes with the evidence behind it, and anything that cannot be
judged says so instead of scoring zero.

Deterministic: the same resume, job and weights always give the same
result. Reuses the skill vocabulary, aliases and relatedness graph in
backend/app/matching so the checker and the job list agree.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from backend.app.intelligence.eligibility import (
    PREFERRED_SECTION_PATTERNS,
    REQUIRED_SECTION_PATTERNS,
    CandidateProfile,
    evaluate_job,
)
from backend.app.matching.skills import (
    COMPILED_SKILLS,
    extract_skills,
    related_skills,
)
from backend.app.models.job import CanonicalJob
from backend.app.studio.sections import BULLET, Structure, date_problems, read_structure


ALGORITHM_VERSION = "ats-2026-10-14-v1"

# How much each part counts toward the overall number. Documented in the
# page and kept here, in one place, so a change is a reviewed diff.
WEIGHTS = {
    "parseability": 0.20,
    "requirements": 0.45,
    "quality": 0.15,
    "fit": 0.20,
}

MIN_JOB_SKILLS = 3

MIN_JOB_CHARS = 400

# A skill named only in a skills list is weaker evidence than one used in
# an experience or project line.
LISTED_ONLY_CREDIT = 0.75

RELATED_CREDIT = 0.5

PREFERRED_WEIGHT = 0.5

# More than this many mentions of one term reads as stuffing.
STUFFING_REPEATS = 6

ACTION_VERBS = frozenset(
    """achieved analyzed architected automated built created cut debugged decreased delivered deployed
    designed developed drove enabled engineered established evaluated expanded implemented improved
    increased integrated launched led maintained managed migrated modeled optimized owned partnered
    prototyped reduced refactored released researched resolved scaled shipped simplified streamlined
    tested trained tuned upgraded wrote""".split()
)


@dataclass
class Evidence:
    skill: str
    level: str  # required | preferred
    state: str  # evidenced | listed_only | related | not_evidenced
    quote: str = ""
    line: int | None = None
    via: str = ""  # for related: the resume skill that earned partial credit


@dataclass
class Finding:
    component: str
    severity: str  # blocker | high | medium | low | info
    message: str


@dataclass
class Assessment:
    algorithm_version: str
    state: str  # scored | insufficient_job_data | unreadable_resume
    aggregate: int | None
    confidence: str  # high | medium | low
    components: dict[str, int | None]
    weights: dict[str, float]
    evidence: list[Evidence] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    recommendations: list[Finding] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _header_pattern(patterns: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"^\W*(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)


_PREFERRED = _header_pattern(PREFERRED_SECTION_PATTERNS)
_REQUIRED = _header_pattern(REQUIRED_SECTION_PATTERNS)


def job_requirements(text: str) -> tuple[frozenset[str], frozenset[str], bool]:
    """Required and preferred skills, and whether the posting had sections.

    A skill named in both counts as required. Without any section headers
    every named skill is treated as required, and confidence drops."""

    required: set[str] = set()
    preferred: set[str] = set()
    mode = "body"
    sectioned = False
    body: list[str] = []
    for line in text.splitlines():
        short = len(line.strip()) <= 80
        if short and _PREFERRED.match(line):
            mode, sectioned = "preferred", True
            continue
        if short and _REQUIRED.match(line):
            mode, sectioned = "required", True
            continue
        found = extract_skills(line)
        if mode == "preferred":
            preferred |= found
        elif mode == "required":
            required |= found
        else:
            body.append(line)
    loose = extract_skills("\n".join(body))
    if not sectioned:
        required |= loose
    else:
        # Skills named only in the description of the role count as
        # required: the job is about them.
        required |= loose - preferred
    preferred -= required
    return frozenset(required), frozenset(preferred), sectioned


def _first_line(structure: Structure, skill: str, kinds: set[str] | None) -> tuple[int, str] | None:
    patterns = COMPILED_SKILLS.get(skill, ())
    ranges: list[tuple[int, int]] = []
    if kinds is None:
        ranges = [(0, len(structure.lines))]
    else:
        for i, s in enumerate(structure.sections):
            if s.kind in kinds:
                end = structure.sections[i + 1].start if i + 1 < len(structure.sections) else len(structure.lines)
                ranges.append((s.start, end))
    for lo, hi in ranges:
        for n in range(lo, hi):
            line = structure.lines[n]
            if any(p.search(line) for p in patterns):
                return n, BULLET.sub("", line).strip()[:180]
    return None


def _evidence(structure: Structure, skill: str, level: str, resume_skills: frozenset[str]) -> Evidence:
    used = _first_line(structure, skill, {"experience", "projects", "summary"})
    if used:
        return Evidence(skill, level, "evidenced", used[1], used[0])
    anywhere = _first_line(structure, skill, None)
    if anywhere:
        return Evidence(skill, level, "listed_only", anywhere[1], anywhere[0])
    neighbours = related_skills(skill) & resume_skills
    if neighbours:
        via = min(neighbours)
        hit = _first_line(structure, via, None)
        return Evidence(skill, level, "related", hit[1] if hit else "", hit[0] if hit else None, via)
    return Evidence(skill, level, "not_evidenced")


def _credit(e: Evidence) -> float:
    return {"evidenced": 1.0, "listed_only": LISTED_ONLY_CREDIT, "related": RELATED_CREDIT}.get(e.state, 0.0)


def _parseability(structure: Structure, text: str, report: dict, findings: list[Finding]) -> int:
    score = 100

    def lose(points: int, severity: str, message: str) -> None:
        nonlocal score
        score -= points
        findings.append(Finding("parseability", severity, message))

    kinds = set(structure.kinds)
    if "experience" not in kinds and "projects" not in kinds:
        lose(20, "high", "No Experience or Projects heading was recognised. Use a plain heading such as Experience.")
    if "education" not in kinds:
        lose(10, "medium", "No Education heading was recognised.")
    if "skills" not in kinds:
        lose(10, "medium", "No Skills heading was recognised.")
    if not structure.emails:
        lose(15, "high", "No email address could be read. Put it in the body as plain text, not in a header or image.")
    if not structure.phones:
        lose(5, "low", "No phone number could be read.")
    if not structure.dates:
        lose(10, "medium", "No date ranges could be read. Write them as Jan 2022 to Present or 2021 to 2023.")
    else:
        work = structure.section("experience")
        if work is not None:
            end = next((x.start for x in structure.sections if x.start > work.start), len(structure.lines))
            if not any(work.start < d.line < end for d in structure.dates):
                lose(10, "medium", "The work entries have no dates. Parsers compute years of experience from them; "
                                   "add a range such as Jan 2023 to Present to each role.")
    for problem in date_problems(structure)[:2]:
        lose(10, "medium", problem)
    if report.get("tables"):
        lose(10, "medium", "The document uses tables. Many parsers read table cells out of order.")
    if report.get("columns"):
        lose(15, "high", "The PDF looks like it has more than one text column, which parsers often merge line by line.")
    if (report.get("pages") or 1) > 2:
        lose(5, "low", f"The document is {report['pages']} pages long; one or two is usual early in a career.")
    if report.get("header_footer_contact"):
        lose(10, "medium", "Contact details sit in the page header or footer, which some parsers skip.")
    return max(0, score)


def _quality(structure: Structure, text: str, findings: list[Finding]) -> int:
    bullets = [b for _, b in structure.bullets if b]
    if not bullets:
        findings.append(Finding("quality", "high", "No bullet points were found, so achievements cannot be judged."))
        return 40
    score = 100
    words = [len(b.split()) for b in bullets]
    quantified = sum(1 for b in bullets if re.search(r"\d", b)) / len(bullets)
    action = sum(1 for b in bullets if b.split()[0].lower().strip(",.") in ACTION_VERBS) / len(bullets)
    if quantified < 0.3:
        score -= 20
        findings.append(Finding("quality", "medium",
            f"{round(quantified * 100)}% of bullets carry a number. Add real figures where you have them; never estimate one."))
    if action < 0.6:
        score -= 15
        findings.append(Finding("quality", "low",
            f"{round(action * 100)}% of bullets open with an action verb such as built, led or reduced."))
    long = sum(1 for w in words if w > 35)
    if long:
        score -= min(15, 5 * long)
        findings.append(Finding("quality", "low", f"{long} bullet(s) run past 35 words; split or tighten them."))
    if re.search(r"(?:^|\s)(?:I|my|me)\s", text):
        score -= 5
        findings.append(Finding("quality", "low", "First person (I, my) appears; resumes usually leave it out."))
    stuffed = []
    for skill in extract_skills(text):
        count = sum(len(p.findall(text)) for p in COMPILED_SKILLS.get(skill, ())[:1])
        if count > STUFFING_REPEATS:
            stuffed.append(skill)
    if stuffed:
        score -= 25
        findings.append(Finding("quality", "high",
            "Repeated keywords read as stuffing: " + ", ".join(sorted(stuffed)) + ". Name each skill where it was used."))
    seen: dict[str, int] = {}
    for b in bullets:
        key = b.lower()[:60]
        seen[key] = seen.get(key, 0) + 1
    repeats = sum(1 for n in seen.values() if n > 1)
    if repeats:
        score -= 10
        findings.append(Finding("quality", "low", f"{repeats} bullet(s) are repeated."))
    return max(0, score)


_DEGREE_REQUIRED = re.compile(
    r"(?P<degree>ph\.?d|doctorate|master'?s|m\.s\.|bachelor'?s|b\.s\.)[^.\n]{0,60}\b(?:required|is required|must)\b",
    re.IGNORECASE,
)


def _fit(job: CanonicalJob, structure: Structure, text: str, profile: CandidateProfile | None,
         findings: list[Finding], unknowns: list[str], facts: dict) -> int:
    decision = evaluate_job(job, profile)
    years = decision.required_experience_years
    have = (profile.experience_years if profile else None)
    facts["required_years"] = years
    facts["your_years"] = have
    score = 100
    if years is None:
        unknowns.append("Required years of experience: not stated.")
    elif have is not None and years > have:
        score -= min(100, 25 * (years - have))
        findings.append(Finding("fit", "high",
            f"The posting asks for {years} years; your profile has {have}. Do not stretch dates to meet it."))
    codes = set(decision.reason_codes)
    sponsorship = {c for c in codes if "SPONSOR" in c.value or "CITIZEN" in c.value or "CLEARANCE" in c.value}
    if sponsorship:
        score -= 50
        findings.append(Finding("fit", "blocker",
            "The posting states a work authorization condition: " + ", ".join(sorted(c.value.lower() for c in sponsorship)) + "."))
    else:
        unknowns.append("Sponsorship: the posting does not refuse it (silence is not a refusal).")
    m = _DEGREE_REQUIRED.search(job.description or "")
    if m:
        wanted = m.group("degree").lower()
        if not re.search(re.escape(wanted.split("'")[0][:3]), text, re.IGNORECASE):
            score -= 20
            findings.append(Finding("fit", "medium", f"The posting requires a {m.group('degree')} degree that the resume does not name."))
    facts["gate"] = decision.status.value
    return max(0, score)


def assess(
    *,
    resume_text: str,
    job: CanonicalJob | None,
    job_text: str = "",
    report: dict | None = None,
    profile: CandidateProfile | None = None,
    weights: dict[str, float] | None = None,
    verified: bool = True,
    kb_skills: frozenset[str] | None = None,
) -> Assessment:
    weights = dict(weights or WEIGHTS)
    report = report or {}
    findings: list[Finding] = []
    unknowns: list[str] = []
    facts: dict = {}
    structure = read_structure(resume_text)

    if len(resume_text.strip()) < 200:
        return Assessment(ALGORITHM_VERSION, "unreadable_resume", None, "low",
            {k: None for k in weights}, weights,
            findings=[Finding("parseability", "blocker",
                "Almost no text could be read from this resume. It may be an image; export it again as text.")])

    parse = _parseability(structure, resume_text, report, findings)
    quality = _quality(structure, resume_text, findings)

    description = job_text or (job.description if job else "")
    required, preferred, sectioned = job_requirements(description)
    total = len(required) + len(preferred)
    facts.update({"required": sorted(required), "preferred": sorted(preferred), "sectioned": sectioned})

    if not verified or len(description.strip()) < MIN_JOB_CHARS or total < MIN_JOB_SKILLS:
        unknowns.append("The job description is too short or unreadable to judge requirements. "
                        "Paste the full description to check against it.")
        return Assessment(ALGORITHM_VERSION, "insufficient_job_data", None, "low",
            {"parseability": parse, "requirements": None, "quality": quality, "fit": None},
            weights, findings=findings, unknowns=unknowns, facts=facts,
            recommendations=_recommend(findings, []))

    resume_skills = extract_skills(resume_text)
    evidence = [_evidence(structure, s, "required", resume_skills) for s in sorted(required)]
    evidence += [_evidence(structure, s, "preferred", resume_skills) for s in sorted(preferred)]
    earned = sum(_credit(e) * (1 if e.level == "required" else PREFERRED_WEIGHT) for e in evidence)
    possible = len(required) + PREFERRED_WEIGHT * len(preferred)
    requirements = round(100 * earned / possible) if possible else 0

    if kb_skills is not None:
        absent = sorted(resume_skills - kb_skills)
        if absent:
            findings.append(Finding("requirements", "medium",
                "Named in this resume but not in your knowledge base: " + ", ".join(absent[:12])
                + ". Add the evidence, or remove the claim."))

    stand_in = job or CanonicalJob(source="pasted", company="", external_id="pasted", title="",
                                   location="", description=description, official_url="")
    fit = _fit(stand_in, structure, resume_text, profile, findings, unknowns, facts)

    components = {"parseability": parse, "requirements": requirements, "quality": quality, "fit": fit}
    aggregate = round(sum(components[k] * weights[k] for k in components) / sum(weights.values()))

    confidence = "high" if total >= 8 and sectioned and len(resume_text) >= 1500 else "medium" if total >= 4 else "low"
    if not sectioned:
        unknowns.append("The posting has no required or preferred headings, so every named skill counts as required.")

    return Assessment(ALGORITHM_VERSION, "scored", aggregate, confidence, components, weights,
        evidence=evidence, findings=findings, unknowns=unknowns, facts=facts,
        recommendations=_recommend(findings, evidence))


_ORDER = {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _recommend(findings: list[Finding], evidence: list[Evidence]) -> list[Finding]:
    recs = [f for f in findings if f.severity != "info"]
    missing_req = [e.skill for e in evidence if e.state == "not_evidenced" and e.level == "required"]
    if missing_req:
        recs.append(Finding("requirements", "high",
            "Required but not evidenced: " + ", ".join(missing_req)
            + ". Add a line only where you really used it; otherwise leave it as a gap."))
    listed = [e.skill for e in evidence if e.state == "listed_only"]
    if listed:
        recs.append(Finding("requirements", "medium",
            "Listed but never shown in use: " + ", ".join(listed)
            + ". Name them in the experience or project line where you used them."))
    return sorted(recs, key=lambda f: _ORDER.get(f.severity, 9))
