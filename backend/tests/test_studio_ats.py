"""Resume Studio: structure reading, fact suggestions and the checker.

Fictional people and companies only. The adversarial cases come from the
brief: synonyms, keyword stuffing, an attractive but false resume, an
unreadable file, inconsistent dates, an SDE II years mismatch, claims
missing from the knowledge base, and a job too thin to judge.
"""

from backend.app.intelligence.eligibility import PROFILES
from backend.app.models.job import CanonicalJob
from backend.app.studio.ats import ALGORITHM_VERSION, assess, job_requirements
from backend.app.studio.facts import suggest_facts
from backend.app.studio.sections import read_structure


RESUME = """Alex Rivera
alex.rivera@example.com | (555) 010-0123 | github.com/alex-rivera-demo

Experience
Software Engineer, Brightmoor Health    Jan 2023 to Present
• Built a FastAPI service in Python that cut claim review time by 40% for 12 clinics
• Migrated reporting from MySQL to Postgres, reducing nightly job time from 3 hours to 25 minutes
• Deployed services on k8s with Helm and wrote alerts for 30 endpoints
Software Engineer Intern, Granite Ledger    May 2021 to Aug 2021
• Developed a Kafka consumer in Python processing 2 million events a day
• Wrote integration tests that raised coverage from 55% to 82%

Projects
Trailhead Maps
• Designed a route planner in TypeScript and React used by 300 hikers

Education
Northfield State University, B.S. Computer Science    2019 to 2023

Skills
Python, TypeScript, FastAPI, PostgreSQL, Kubernetes, Kafka, React, Docker, Git
"""

JOB = """About the role
You will build backend services for our claims platform with a small team.

Minimum qualifications
Bachelor's degree in computer science or equivalent experience.
2+ years building backend services in Python.
Experience with PostgreSQL and Kubernetes in production.
Experience with golang services.

Preferred qualifications
Experience with Kafka and Terraform.
Familiarity with React.

We offer competitive pay, health benefits and a hybrid schedule in Seattle, WA.
"""


def _job(description=JOB, title="Software Engineer II"):
    return CanonicalJob(source="greenhouse", company="Pinecrest AI", external_id="1", title=title,
                        location="Seattle, WA", description=description,
                        official_url="https://boards.example.com/pinecrest/1")


def _check(resume=RESUME, job=None, **kw):
    return assess(resume_text=resume, job=job or _job(), profile=PROFILES["early-career"], **kw)


# Structure and facts -------------------------------------------------


def test_sections_contacts_and_dates_are_read():
    s = read_structure(RESUME)
    assert s.kinds == ["experience", "projects", "education", "skills"]
    assert s.emails == ["alex.rivera@example.com"]
    assert s.phones
    assert len(s.dates) == 3
    assert any(d.ongoing for d in s.dates)


def test_facts_are_suggested_from_entries_never_invented():
    facts = suggest_facts(read_structure(RESUME))
    jobs = [f for f in facts if f.kind == "experience"]
    assert [(f.title, f.organization, f.start, f.end) for f in jobs] == [
        ("Software Engineer", "Brightmoor Health", "2023-01", "present"),
        ("Software Engineer Intern", "Granite Ledger", "2021-05", "2021-08"),
    ]
    assert len(jobs[0].bullets) == 3
    assert "fastapi" in jobs[0].skills
    # Nothing beyond the text: no skill appears that the entry does not name.
    assert "kafka" not in jobs[0].skills
    skills = {f.title for f in facts if f.kind == "skill"}
    assert {"python", "kubernetes", "kafka"} <= skills
    school = next(f for f in facts if f.kind == "education")
    assert school.organization == "Northfield State University"
    assert school.title == "B.S. Computer Science"


# Requirements --------------------------------------------------------


def test_requirements_are_split_into_required_and_preferred():
    required, preferred, sectioned = job_requirements(JOB)
    assert sectioned
    assert {"python", "postgresql", "kubernetes", "go"} <= required
    assert {"kafka", "terraform", "react"} <= preferred
    assert not required & preferred


def test_a_good_resume_scores_with_evidence_quotes():
    a = _check()
    assert a.state == "scored" and a.algorithm_version == ALGORITHM_VERSION
    by = {e.skill: e for e in a.evidence}
    assert by["python"].state == "evidenced" and "FastAPI service in Python" in by["python"].quote
    # Synonyms: Postgres and k8s are the same skills.
    assert by["postgresql"].state == "evidenced"
    assert by["kubernetes"].state == "evidenced"
    assert by["go"].state == "not_evidenced"
    assert by["terraform"].state == "not_evidenced"
    assert any("go" in r.message and r.component == "requirements" for r in a.recommendations)
    assert 0 < a.aggregate < 100
    assert set(a.components) == {"parseability", "requirements", "quality", "fit"}


def test_the_same_inputs_give_the_same_result():
    assert _check().to_dict() == _check().to_dict()


def test_keyword_stuffing_is_penalised():
    stuffed = RESUME + "\nKubernetes " * 12
    good, bad = _check(), _check(stuffed)
    assert bad.components["quality"] < good.components["quality"]
    assert any("stuffing" in f.message for f in bad.findings)


def test_an_attractive_but_false_resume_scores_lower():
    # Every keyword in a skills list, nothing shown in use.
    hollow = """Jordan Vale
jordan.vale@example.com | (555) 010-0199

Experience
Engineer, Quorvane    Jan 2023 to Present
• Worked on various projects with the team
• Helped with tasks as needed

Education
Northfield State University    2019 to 2023

Skills
Python, golang, PostgreSQL, Kubernetes, Kafka, Terraform, React
"""
    honest, false = _check(), _check(hollow)
    by = {e.skill: e for e in false.evidence}
    assert by["go"].state == "listed_only"
    assert false.components["requirements"] < 100
    assert false.components["quality"] < honest.components["quality"]


def test_an_unreadable_resume_is_not_scored():
    a = _check("Scanned image")
    assert a.state == "unreadable_resume" and a.aggregate is None


def test_a_thin_job_is_insufficient_not_zero():
    a = _check(job=_job(description="Great team. Apply now."))
    assert a.state == "insufficient_job_data"
    assert a.aggregate is None and a.components["requirements"] is None
    assert a.components["parseability"] is not None


def test_an_unverified_posting_is_insufficient():
    assert _check(verified=False).state == "insufficient_job_data"


def test_inconsistent_dates_are_flagged():
    bad = RESUME.replace("May 2021 to Aug 2021", "Aug 2021 to May 2021")
    assert any("ends before it starts" in f.message for f in _check(bad).findings)


def test_a_years_mismatch_is_a_fit_finding_not_a_stretch():
    senior = _job(description=JOB.replace("2+ years", "5+ years"))
    a = _check(job=senior)
    assert a.components["fit"] < 100
    assert any("5 years" in f.message for f in a.findings if f.component == "fit")


def test_a_sponsorship_refusal_is_a_blocker():
    refusing = _job(description=JOB + "\nWe are unable to sponsor visas for this role.\n")
    a = _check(job=refusing)
    assert any(f.severity == "blocker" for f in a.findings if f.component == "fit")


def test_claims_missing_from_the_knowledge_base_are_named():
    a = _check(kb_skills=frozenset({"python", "fastapi"}))
    assert any("not in your knowledge base" in f.message and "kubernetes" in f.message for f in a.findings)


def test_an_unsectioned_posting_lowers_confidence_and_says_why():
    flat = "\n".join(l for l in JOB.splitlines() if "qualifications" not in l)
    a = _check(job=_job(description=flat))
    assert a.state == "scored"
    assert any("no required or preferred headings" in u for u in a.unknowns)


def test_layout_problems_from_the_file_count_against_parseability():
    clean = _check()
    messy = _check(report={"tables": 2, "columns": True})
    assert messy.components["parseability"] < clean.components["parseability"]


# A PDF arrives one visual line at a time: wrapped bullets, "|" headers,
# jobs with no dates. Fictional, shaped like a real two-column-free resume.
WRAPPED = """Jordan Vale
Seattle, WA | jordan.vale@example.com | (555) 010-0177

EDUCATION
Northfield State University Seattle, WA
Master of Science in Computer Science June 2025 - December 2026 (Expected)

SKILLS
Languages: Python, TypeScript, Go

WORK EXPERIENCE
Graduate Research Assistant | Example Lab, Northfield State University
• Migrated a Python 3.8 Flask service to Python 3.11, cutting memory use from 1.9 GB to
500 MB and request latency by 40%.
• Built a React and TypeScript interface for annotators, used by a team of
12 linguists.
Software Development Engineer | Example Corp, Bengaluru
• Architected REST APIs in FastAPI serving 50K+ requests a day at under 100ms, backed
by MongoDB and Azure Cosmos DB.
• Led a migration of MongoDB clusters from M30 to
M20, saving 25% at a 99.9% availability SLA.

PROJECTS
Speech Toolkit – Open Source Language Tools | PyTorch, PySide6
• Built a voice activity detection pipeline with forced alignment and
export to ELAN.
"""


def test_wrapped_bullets_stay_one_bullet_and_jobs_stay_whole():
    facts = suggest_facts(read_structure(WRAPPED))
    jobs = [f for f in facts if f.kind == "experience"]
    assert [(j.title, j.organization) for j in jobs] == [
        ("Graduate Research Assistant", "Example Lab"),
        ("Software Development Engineer", "Example Corp"),
    ]
    assert len(jobs[0].bullets) == 2 and jobs[0].bullets[0].endswith("latency by 40%.")
    assert jobs[1].bullets[1] == "Led a migration of MongoDB clusters from M30 to M20, saving 25% at a 99.9% availability SLA."
    # No dates were written for the jobs, so none are invented.
    assert all(j.start == "" and j.end == "" for j in jobs)
    project = next(f for f in facts if f.kind == "project")
    assert project.title == "Speech Toolkit" and len(project.bullets) == 1


def test_wrapped_bullets_count_once_for_quality():
    s = read_structure(WRAPPED)
    assert len(s.bullets) == 5
    assert all(not b[1][0].islower() for b in s.bullets)


def test_work_entries_without_dates_are_flagged():
    a = assess(resume_text=WRAPPED, job=None, job_text=JOB, profile=PROFILES["early-career"])
    assert any("work entries have no dates" in f.message for f in a.findings)
    assert not any("work entries have no dates" in f.message for f in _check().findings)
