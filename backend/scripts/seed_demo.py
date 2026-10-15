"""Build a demo database so ACE runs where the real one is not.

A cloud session, a fresh clone or a reviewer has no PostgreSQL holding
the live corpus, and without data there is nothing to look at: the UI is
judged by looking, so an empty queue proves nothing.

Everything here is fictional. The repository is public, so no company,
person, answer or application in this file is real. Employers come from
``backend/app/demo/companies.py`` and their links use the reserved
``.example`` domain, which never resolves.

The jobs are not given a verdict. Each is run through the real gate
(``evaluate_job``) and the real scorer (``rescore_corpus``), so the demo
shows what ACE would decide about such postings, and changes when the
rules do.

Usage, from the repository root::

    .venv/bin/python -m backend.scripts.seed_demo --database-url sqlite:///ace-demo.db
    ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db \\
        .venv/bin/uvicorn backend.app.api.main:app --port 8000

Dates are relative to the moment it runs, so re-run it (it starts from
an empty database each time) when the demo has aged.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
import random
import re
import sys

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.answers.catalogue import (
    BOOLEAN,
    CHOICE,
    QUESTIONS,
    options_for,
)
from backend.app.api.marks import set_mark
from backend.app.db.base import Base
from backend.app.db.models import (
    ApplicationAnswerRecord,
    ExternalApplicationRecord,
    HistoryEntryRecord,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    PollSessionRecord,
    SourceState,
)
from backend.app.demo.companies import DEMO_COMPANY_TIERS
from backend.app.intelligence.eligibility import evaluate_job
from backend.app.matching.service import (
    rescore_corpus,
    store_resume,
)
from backend.app.models.job import CanonicalJob
from backend.app.persistence.evaluations import (
    _values_from_decision,
)
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)
from backend.app.persistence.openings import OLD_OPENING_DAYS
from backend.app.auth.service import create_owner


# Sign in to the demo with these. Fictional, and only ever valid for a
# database this script generated.
DEMO_OWNER_EMAIL = "demo@ace.example"

DEMO_OWNER_PASSWORD = "ace demo password"


SEED = 20261014

SOURCE_TYPES = (
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "smartrecruiters",
)

US_LOCATIONS = (
    "Seattle, WA",
    "San Francisco, CA",
    "New York, NY",
    "Austin, TX",
    "Boston, MA",
    "Remote, US",
    "Chicago, IL",
    "Denver, CO",
    "Atlanta, GA",
    "Mountain View, CA",
    "Pittsburgh, PA",
    "Raleigh, NC",
)

ABROAD_LOCATIONS = (
    "London, United Kingdom",
    "Toronto, Canada",
    "Berlin, Germany",
    "Bengaluru, India",
)

SKILL_POOLS = {
    "SOFTWARE": (
        "Python",
        "Java",
        "TypeScript",
        "React",
        "Node.js",
        "PostgreSQL",
        "Redis",
        "Kafka",
        "Kubernetes",
        "Docker",
        "AWS",
        "GCP",
        "gRPC",
        "GraphQL",
        "Terraform",
        "Rust",
        "C++",
        "distributed systems",
        "microservices",
        "REST APIs",
        "CI/CD",
        "Linux",
        "SQL",
    ),
    "ML": (
        "Python",
        "PyTorch",
        "TensorFlow",
        "machine learning",
        "NLP",
        "computer vision",
        "Spark",
        "SQL",
        "Kubernetes",
        "AWS",
        "C++",
        "distributed systems",
    ),
    "FDE": (
        "Python",
        "TypeScript",
        "React",
        "SQL",
        "PostgreSQL",
        "AWS",
        "Docker",
        "REST APIs",
        "machine learning",
        "Linux",
    ),
    "DATA": (
        "Python",
        "SQL",
        "Spark",
        "Kafka",
        "AWS",
        "Terraform",
    ),
}

# (title, skill pool, experience phrase, weight). The gate decides what
# passes; these are only the kinds of posting a real queue sees, in
# roughly the proportions a real corpus holds them.
POSTINGS = (
    ("Software Engineer, New Grad", "SOFTWARE", "new_grad", 9),
    ("Software Engineer I", "SOFTWARE", "zero_two", 8),
    ("Software Engineer, Early Career", "SOFTWARE", "new_grad", 6),
    ("Backend Engineer", "SOFTWARE", "one_plus", 7),
    ("Full Stack Engineer", "SOFTWARE", "two_plus", 6),
    ("Software Engineer II", "SOFTWARE", "two_three", 5),
    ("Platform Engineer", "SOFTWARE", "none", 4),
    ("Software Engineer, Infrastructure", "SOFTWARE", "one_plus", 4),
    ("Frontend Engineer", "SOFTWARE", "zero_two", 4),
    ("Machine Learning Engineer, New Grad", "ML", "new_grad", 6),
    ("Machine Learning Engineer", "ML", "two_plus", 5),
    ("Applied ML Engineer", "ML", "one_plus", 4),
    ("ML Infrastructure Engineer", "ML", "none", 3),
    ("Forward Deployed Engineer", "FDE", "one_plus", 5),
    ("Forward Deployed Software Engineer, New Grad", "FDE", "new_grad", 4),
    ("SDE II", "SOFTWARE", "three_plus", 3),
    ("Software Engineer II", "SOFTWARE", "three_plus", 3),
    ("Senior Software Engineer", "SOFTWARE", "five_plus", 6),
    ("Staff Machine Learning Engineer", "ML", "eight_plus", 2),
    ("Software Engineering Intern, Summer 2027", "SOFTWARE", "intern", 3),
    ("Data Engineer", "DATA", "two_plus", 3),
    ("Data Scientist, New Grad", "DATA", "new_grad", 2),
    ("Software Engineer (Contract)", "SOFTWARE", "contract", 2),
    ("Engineering Manager, Payments", "SOFTWARE", "five_plus", 2),
)

EXPERIENCE = {
    "new_grad": (
        "This role is for new graduates. You will have earned a "
        "Bachelor's or Master's degree in Computer Science or a related "
        "field between December 2025 and August 2027."
    ),
    "zero_two": "0-2 years of professional software experience.",
    "one_plus": "1+ years of professional software engineering experience.",
    "two_plus": "2+ years of experience building production systems.",
    "two_three": "2-3 years of industry experience.",
    "three_plus": "3+ years of professional software engineering experience.",
    "none": (
        "A degree in Computer Science or equivalent practical experience."
    ),
    "five_plus": "5+ years of professional software engineering experience.",
    "eight_plus": "8+ years of experience, including technical leadership.",
    "intern": (
        "This is a 12-week internship for students returning to school "
        "after the summer."
    ),
    "contract": (
        "This is a 6-month contract position with the possibility of "
        "extension."
    ),
}

TEAMS = (
    "Payments",
    "Search",
    "Developer Platform",
    "Storage",
    "Ads Ranking",
    "Identity",
    "Maps",
    "Observability",
    "Growth",
    "Inference",
    "Safety",
    "Billing",
)

NO_SPONSORSHIP = (
    "We are unable to sponsor or take over sponsorship of an employment "
    "visa at this time."
)


@dataclass
class DemoJob:
    """One fictional posting before it is stored."""

    job: CanonicalJob
    account: str
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    pull_index: int


def _slug(
    name: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        name.lower(),
    )


def _description(
    rng: random.Random,
    *,
    company: str,
    team: str,
    pool: str,
    experience: str,
    refuses_sponsorship: bool,
    unreadable: bool,
) -> str:
    """Write a posting body the gate and the scorer can read."""

    if unreadable:
        # Some boards hand over a title and a link and nothing else.
        return f"Join the {team} team at {company}."

    skills = rng.sample(
        SKILL_POOLS[pool],
        k=min(
            len(SKILL_POOLS[pool]),
            rng.randint(4, 7),
        ),
    )

    lines = [
        f"About the team: {company} {team} builds the systems that "
        "millions of people rely on every day.",
        "",
        "What you will do:",
        "Design, build and operate services end to end.",
        "Work with product and design to ship features customers love.",
        "",
        "What we look for:",
        EXPERIENCE[experience],
        "Experience with " + ", ".join(skills[:-1]) + " and " + skills[-1] + ".",
        "Clear written communication and a habit of testing your work.",
        "",
        "This is a full-time position.",
    ]

    if refuses_sponsorship:
        lines.append(
            NO_SPONSORSHIP
        )

    return "\n".join(
        lines
    )


def build_demo_jobs(
    rng: random.Random,
    *,
    now: datetime,
    pulls: list[datetime],
    count: int,
) -> list[DemoJob]:
    """Invent ``count`` postings spread across companies and pulls."""

    companies = list(
        DEMO_COMPANY_TIERS
    )

    weights = [
        weight
        for *_, weight in POSTINGS
    ]

    jobs: list[DemoJob] = []

    for index in range(
        count
    ):
        company = companies[
            index % len(companies)
        ]

        title, pool, experience, _ = rng.choices(
            POSTINGS,
            weights=weights,
        )[0]

        team = rng.choice(
            TEAMS
        )

        if rng.random() < 0.35 and "," not in title:
            title = f"{title}, {team}"

        abroad = rng.random() < 0.08

        location = rng.choice(
            ABROAD_LOCATIONS
            if abroad
            else US_LOCATIONS
        )

        pull_index = min(
            int(
                rng.expovariate(
                    0.06
                )
            ),
            len(pulls) - 1,
        )

        first_seen_at = min(
            pulls[pull_index]
            + timedelta(
                seconds=rng.randint(0, 600),
            ),
            now - timedelta(minutes=12),
        )

        # Most postings were opened a little before ACE first saw them;
        # some boards give no date at all.
        posted_at = (
            None
            if rng.random() < 0.12
            else first_seen_at
            - timedelta(
                hours=rng.randint(1, 72),
            )
        )

        is_active = not (
            pull_index > 6
            and rng.random() < 0.15
        )

        account = _slug(
            company
        )

        source = SOURCE_TYPES[
            sum(map(ord, company))
            % len(SOURCE_TYPES)
        ]

        external_id = str(
            4100000 + index * 37
        )

        jobs.append(
            DemoJob(
                job=CanonicalJob(
                    source=source,
                    company=company,
                    external_id=external_id,
                    requisition_id=f"R-{20000 + index}",
                    title=title,
                    location=location,
                    description=_description(
                        rng,
                        company=company,
                        team=team,
                        pool=pool,
                        experience=experience,
                        refuses_sponsorship=(
                            rng.random() < 0.05
                        ),
                        unreadable=(
                            rng.random() < 0.06
                        ),
                    ),
                    official_url=(
                        f"https://careers.{account}.example"
                        f"/jobs/{external_id}"
                    ),
                    posted_at=posted_at,
                ),
                account=account,
                first_seen_at=first_seen_at,
                last_seen_at=(
                    max(
                        first_seen_at,
                        now - timedelta(minutes=rng.randint(1, 9)),
                    )
                    if is_active
                    else first_seen_at + timedelta(days=rng.randint(1, 5))
                ),
                is_active=is_active,
                pull_index=pull_index,
            )
        )

    # One role posted once per vertical, as some employers do: four real
    # postings that read as one decision, which both UIs fold into a
    # group. Recent, so it lands on the first page.
    # Reposts share one description, as they do on real boards.
    agent_description = _description(
        random.Random(SEED + 1),
        company="Pinecrest AI",
        team="Agents",
        pool="FDE",
        experience="zero_two",
        refuses_sponsorship=False,
        unreadable=False,
    )

    for offset, vertical in enumerate(
        ("Healthcare", "Finance", "Retail", "Legal")
    ):
        external_id = str(
            4900000 + offset
        )

        jobs.append(
            DemoJob(
                job=CanonicalJob(
                    source="ashby",
                    company="Pinecrest AI",
                    external_id=external_id,
                    requisition_id=f"R-49{offset:03d}",
                    title=f"Software Engineer, Agent - {vertical}",
                    location="San Francisco, CA",
                    description=agent_description,
                    official_url=(
                        "https://careers.pinecrestai.example"
                        f"/jobs/{external_id}"
                    ),
                    posted_at=now - timedelta(hours=5),
                ),
                account="pinecrestai",
                first_seen_at=pulls[1] + timedelta(minutes=offset),
                last_seen_at=now - timedelta(minutes=3),
                is_active=True,
                pull_index=1,
            )
        )

    return jobs


def pull_times(
    now: datetime,
) -> list[datetime]:
    """Return pull starts, newest first, on the quarter hour.

    Dense recently and sparse further back, like a real log: the newest
    pull is minutes old, the oldest about six weeks. Many find nothing,
    which a real log shows too.
    """

    anchor = now.replace(
        minute=(now.minute // 15) * 15,
        second=0,
        microsecond=0,
    )

    # Hourly for the last day, then twice a day for about six weeks:
    # more than one page of the activity log, as a real one holds.
    hours_back = list(range(24)) + list(
        range(24, 24 * 42, 12)
    )

    return [
        anchor - timedelta(hours=hours)
        for hours in hours_back
    ]


RESUME_TEXT = """Alex Rivera
Software Engineer

Experience
Software Engineer, Example Analytics (fictional), 2023 to present
Built Python services on AWS backed by PostgreSQL.
Ran Docker deployments through CI/CD pipelines.

Machine Learning Research Assistant, Example State University (fictional)
Trained PyTorch models for computer vision experiments.

Skills
Python, TypeScript, PostgreSQL, Docker, AWS, PyTorch, machine learning, Linux, Git

Education
M.S. Computer Science, Example State University (fictional), expected December 2026
"""

# The richer resume Resume Studio shows: dated entries and bullets, so the
# knowledge base and the checker have something to read. Fictional.
STUDIO_RESUME = """Alex Rivera
alex.rivera@example.com | (555) 010-0100 | github.com/example-alex-rivera

Experience
Software Engineer, Example Analytics    Jan 2023 to Present
\u2022 Built Python services on AWS backed by PostgreSQL that serve 40 internal dashboards
\u2022 Cut deployment time from 30 minutes to 6 by moving builds to Docker and CI/CD
\u2022 Wrote alerting for 25 services, reducing missed incidents by half
Machine Learning Research Assistant, Example State University    Aug 2021 to Dec 2022
\u2022 Trained PyTorch models for computer vision experiments on 120,000 labelled images
\u2022 Developed a data loading pipeline in Python that halved training time

Projects
Trailhead Maps
\u2022 Designed a route planner in TypeScript and React used by 300 hikers

Education
Example State University, M.S. Computer Science    2025 to 2026

Skills
Python, TypeScript, PostgreSQL, Docker, AWS, PyTorch, machine learning, Linux, Git, React
"""


TEXT_ANSWERS = {
    "First name": "Alex",
    "Last name": "Rivera",
    "Full name": "Alex Rivera",
    "Email": "alex.rivera@example.com",
    "Phone": "555-0100",
    "Location": "Seattle, WA",
    "Address": "100 Example Street",
    "Address line 2": "",
    "City": "Seattle",
    "State": "Washington",
    "Postcode": "98101",
    "Country": "United States",
    "LinkedIn": "https://www.linkedin.com/in/example-alex-rivera",
    "GitHub": "https://github.com/example-alex-rivera",
    "Portfolio": "https://alex-rivera.example",
    "University": "Example State University",
    "Field of study": "Computer Science",
    "GPA": "3.8",
    "Graduation date": "12/2026",
    "Years of experience": "3",
    "Language": "English",
    "Earliest start date": "01/2027",
    "Salary expectation": "Open to discussing the range for this role",
    "Why this company": (
        "I want to build reliable systems that many people use, and "
        "this team's work is exactly that."
    ),
}

# Fictional answers to choice questions, by label. Anything not named
# takes the question's first option.
CHOICE_ANSWERS = {
    "Pronouns": "They/them",
    "Gender": "Prefer not to say",
    "Race or ethnicity": "Prefer not to say",
    "Veteran status": "I am not a protected veteran",
    "Disability status": "Prefer not to say",
    "Sexual orientation": "Prefer not to say",
    "Transgender": "Prefer not to say",
}

YES_ANSWERS = {
    "Work authorisation",
    "Need sponsorship in future",
    "At least 18 years old",
    "Role is located in the US",
    "Willing to relocate",
    "Willing to work onsite",
    "Recent graduate",
    "Consent to keep my application on file",
    "Agree to the terms shown",
    "Consent to AI in hiring",
    "Fluent in this language",
    "Experience with this tech stack",
}

def answer_rows() -> list[tuple[str, str]]:
    """Return the fictional answer bank, in catalogue order."""

    rows: list[tuple[str, str]] = []

    for question in QUESTIONS:
        label = question.label

        if question.kind == BOOLEAN:
            value = "Yes" if label in YES_ANSWERS else "No"

        elif question.kind == CHOICE:
            labels = [
                option.label
                for option in options_for(
                    question
                )
            ]

            wanted = CHOICE_ANSWERS.get(
                label
            )

            value = (
                wanted
                if wanted in labels
                else (labels[0] if labels else "")
            )

        else:
            value = TEXT_ANSWERS.get(
                label,
                "",
            )

        rows.append(
            (label, value)
        )

    return rows


WORK_HISTORY = (
    {
        "employer": "Example Analytics",
        "job_title": "Software Engineer",
        "location": "Seattle, WA",
        "is_current": True,
        "start_month": 6,
        "start_year": 2023,
        "description": "Python and TypeScript services on AWS.",
    },
    {
        "employer": "Example State University",
        "job_title": "Machine Learning Research Assistant",
        "location": "Seattle, WA",
        "is_current": False,
        "start_month": 1,
        "start_year": 2022,
        "end_month": 5,
        "end_year": 2023,
        "description": "PyTorch experiments in computer vision.",
    },
)

EDUCATION_HISTORY = (
    {
        "employer": "Example State University",
        "job_title": "M.S. Computer Science",
        "location": "Seattle, WA",
        "start_month": 8,
        "start_year": 2025,
        "end_month": 12,
        "end_year": 2026,
    },
    {
        "employer": "Example Institute of Technology",
        "job_title": "B.S. Computer Engineering",
        "location": "Austin, TX",
        "start_month": 8,
        "start_year": 2018,
        "end_month": 5,
        "end_year": 2022,
    },
)


def _store_jobs(
    session: Session,
    *,
    jobs: list[DemoJob],
    pulls: list[datetime],
    now: datetime,
) -> list[int]:
    """Store jobs, their gate verdicts, sources and pulls."""

    for company in DEMO_COMPANY_TIERS:
        account = _slug(
            company
        )

        source = SOURCE_TYPES[
            sum(map(ord, company))
            % len(SOURCE_TYPES)
        ]

        session.add(
            JobSourceRecord(
                source_type=source,
                source_account=account,
                company_name=company,
                enabled=True,
                poll_interval_seconds=300,
                discovery_source="demo",
                first_discovered_at=pulls[-1],
                last_verified_at=now,
                created_at=pulls[-1],
                updated_at=now,
            )
        )

        session.add(
            SourceState(
                source=source,
                source_account=account,
                initialized_at=pulls[-1],
                last_success_at=now - timedelta(minutes=2),
                last_job_count=0,
            )
        )

    runs = []

    for started_at in pulls:
        run = PollSessionRecord(
            started_at=started_at,
            last_activity_at=started_at + timedelta(minutes=14),
            jobs_discovered=0,
            qualifying_discovered=0,
            boards_checked=len(DEMO_COMPANY_TIERS),
            postings_checked=0,
            notified_at=started_at + timedelta(minutes=15),
            # The demo has no mail provider, so no alert could leave.
            alert_status="unconfigured",
        )

        session.add(
            run
        )

        runs.append(
            run
        )

    # The scheduler writes a window every quarter hour it reads
    # anything, so the last twelve hours are dense with quiet windows
    # between the ones that found something, as a real log is.
    taken = set(
        pulls
    )

    for step in range(
        48
    ):
        started_at = pulls[0] - timedelta(
            minutes=15 * step
        )

        if started_at in taken:
            continue

        session.add(
            PollSessionRecord(
                started_at=started_at,
                last_activity_at=started_at + timedelta(minutes=14),
                jobs_discovered=0,
                qualifying_discovered=0,
                boards_checked=len(DEMO_COMPANY_TIERS),
                postings_checked=len(DEMO_COMPANY_TIERS) * 21,
            )
        )

    session.flush()

    # What each window attempted. One board in every fifth window fails,
    # so a partial failure is visible in the demo.
    for index, run in enumerate(
        session.scalars(
            select(
                PollSessionRecord
            ).order_by(
                PollSessionRecord.started_at.desc()
            )
        )
    ):
        failed = 1 if index % 5 == 3 else 0

        # The failing board answered nothing, so it leaves the boards
        # read successfully; it was still attempted.
        run.sources_attempted = run.boards_checked

        run.boards_checked -= failed

        run.failed_checks = failed

        run.poll_attempts = (
            run.sources_attempted * 3
        )

    ids = []

    for demo in jobs:
        job = demo.job

        record = JobRecord(
            source=job.source,
            source_account=demo.account,
            external_id=job.external_id,
            company=job.company,
            requisition_id=job.requisition_id,
            title=job.title,
            location=job.location,
            description=job.description,
            official_url=job.official_url,
            posted_at=job.posted_at,
            source_updated_at=None,
            employment_type=None,
            content_hash=compute_job_content_hash(
                job
            ),
            first_seen_at=demo.first_seen_at,
            last_seen_at=demo.last_seen_at,
            is_active=demo.is_active,
            closed_at=(
                None
                if demo.is_active
                else demo.last_seen_at
            ),
            first_seen_session_id=runs[
                demo.pull_index
            ].id,
        )

        session.add(
            record
        )

        session.flush()

        values = _values_from_decision(
            evaluate_job(
                job
            ),
            content_hash=record.content_hash,
            evaluated_at=demo.first_seen_at,
        )

        session.add(
            JobEvaluationRecord(
                job_id=record.id,
                **values,
            )
        )

        run = runs[
            demo.pull_index
        ]

        run.jobs_discovered += 1

        run.postings_checked += 40

        opened = job.posted_at or demo.first_seen_at

        if (
            values["eligibility_status"] == "PASS"
            and demo.first_seen_at - opened
            < timedelta(days=OLD_OPENING_DAYS)
        ):
            run.qualifying_discovered += 1

        ids.append(
            record.id
        )

    session.flush()

    for state in session.scalars(
        select(
            SourceState
        )
    ):
        state.last_job_count = sum(
            1
            for demo in jobs
            if demo.account == state.source_account
            and demo.is_active
        )

    return ids


def _store_marks(
    session: Session,
    rng: random.Random,
    *,
    now: datetime,
) -> None:
    """Mark a realistic share of the queue by hand."""

    passing = session.scalars(
        select(
            JobRecord.id
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        )
        .where(
            JobEvaluationRecord.eligibility_status == "PASS",
        )
        .order_by(
            JobRecord.id
        )
    ).all()

    picks = rng.sample(
        list(passing),
        k=min(len(passing), 70),
    )

    statuses = (
        ("applied", ""),
        ("applied", ""),
        ("screening", "Recruiter call booked"),
        ("interviewing", "Onsite loop next week"),
        ("interviewing", ""),
        ("offer", "Offer in hand, deciding"),
        ("rejected", "Rejected after the phone screen"),
        ("withdrawn", ""),
        ("ghosted", ""),
    )

    for index, job_id in enumerate(
        picks
    ):
        if index < 30:
            status, note = statuses[
                index % len(statuses)
            ]

            set_mark(
                session,
                job_id=job_id,
                applied=True,
                applied_at=now - timedelta(days=rng.randint(1, 30), hours=rng.randint(0, 20)),
                now=now,
            )

            set_mark(
                session,
                job_id=job_id,
                application_status=status,
                status_note=note or None,
                now=now - timedelta(days=rng.randint(0, 3)),
            )

        elif index < 45:
            set_mark(
                session,
                job_id=job_id,
                saved=True,
                now=now,
            )

        elif index < 58:
            set_mark(
                session,
                job_id=job_id,
                review_state="reviewed",
                now=now,
            )

        else:
            set_mark(
                session,
                job_id=job_id,
                review_state="dismissed",
                now=now,
            )

    for company, title, days, status in (
        ("Lanternfish", "Software Engineer", 40, "rejected"),
        ("Oakhollow", "Backend Engineer", 33, "ghosted"),
        ("Glimmerline", "ML Engineer, New Grad", 21, "applied"),
    ):
        session.add(
            ExternalApplicationRecord(
                company=company,
                title=title,
                match_key=f"{company.lower()}|{title.lower()}",
                applied_at=now - timedelta(days=days),
                application_status=status,
                status_changed_at=now - timedelta(days=days),
                url=f"https://careers.{_slug(company)}.example/old",
                created_at=now,
                updated_at=now,
            )
        )


def _store_answers(
    session: Session,
    *,
    now: datetime,
) -> int:
    rows = answer_rows()

    for order, (label, value) in enumerate(
        rows
    ):
        session.add(
            ApplicationAnswerRecord(
                label=label,
                value=value,
                sort_order=order,
                updated_at=now,
            )
        )

    for kind, entries in (
        ("work", WORK_HISTORY),
        ("education", EDUCATION_HISTORY),
    ):
        for order, entry in enumerate(
            entries
        ):
            session.add(
                HistoryEntryRecord(
                    kind=kind,
                    sort_order=order,
                    employer=entry["employer"],
                    job_title=entry["job_title"],
                    location=entry.get("location", ""),
                    is_current=entry.get("is_current", False),
                    start_month=entry.get("start_month"),
                    start_year=entry.get("start_year"),
                    end_month=entry.get("end_month"),
                    end_year=entry.get("end_year"),
                    description=entry.get("description", ""),
                    updated_at=now,
                )
            )

    return len(
        rows
    )


def _store_studio(session, *, now: datetime) -> None:
    """Resume Studio: an uploaded DOCX, its suggested facts (some
    verified), a primary master and a few checks. Scores in the job list
    keep coming from RESUME_TEXT, which the primary version holds."""

    import io

    import docx

    from backend.app.db.models import (
        CareerFactRecord,
        JobEvaluationRecord,
        JobRecord,
        JobResumeScoreRecord,
        ResumeVersionRecord,
    )
    from backend.app.studio import service as studio

    document = docx.Document()
    for line in STUDIO_RESUME.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)

    studio.upload(session, filename="alex-rivera-resume.docx", payload=buffer.getvalue(),
                  kind="resume", now=now - timedelta(days=12), primary_if_first=False)
    detailed = session.scalar(select(ResumeVersionRecord))

    primary = ResumeVersionRecord(
        label="Alex Rivera, fall 2026", kind="master", body_text=RESUME_TEXT,
        content_hash=studio.sha256(RESUME_TEXT), status="approved", is_primary=True,
        created_at=now - timedelta(days=12), approved_at=now - timedelta(days=12),
    )
    session.add(primary)

    facts = session.scalars(select(CareerFactRecord).order_by(CareerFactRecord.id)).all()
    for fact in facts:
        if fact.kind in ("experience", "education") or fact.title in ("python", "postgresql", "docker", "aws"):
            studio.update_fact(session, fact.id, changes={"status": "verified"}, now=now - timedelta(days=11))
    project = next((f for f in facts if f.kind == "project"), None)
    if project is not None:
        studio.update_fact(session, project.id, changes={"status": "needs_clarification",
                           "note": "Confirm the user count."}, now=now - timedelta(days=10))

    best = session.execute(
        select(JobRecord.id)
        .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
        .join(JobResumeScoreRecord, JobResumeScoreRecord.job_id == JobRecord.id)
        .where(JobEvaluationRecord.eligibility_status == "PASS", JobRecord.is_active.is_(True))
        .order_by(JobResumeScoreRecord.score.desc().nulls_last(), JobRecord.id)
        .limit(3)
    ).scalars().all()
    for offset, job_id in enumerate(best):
        studio.check(session, version_id=detailed.id, job_id=job_id, now=now - timedelta(hours=6 - offset))
    session.flush()


def seed(
    database_url: str,
    *,
    job_count: int = 360,
    now: datetime | None = None,
) -> dict:
    """Replace whatever is at ``database_url`` with the demo data."""

    now = now or datetime.now(
        timezone.utc
    )

    url = make_url(
        database_url
    )

    if url.get_backend_name() == "sqlite" and url.database:
        Path(
            url.database
        ).unlink(
            missing_ok=True
        )

    engine = create_engine(
        database_url
    )

    if url.get_backend_name() != "sqlite":
        # Refuse to wipe anything but an empty PostgreSQL: the live
        # corpus is on PostgreSQL too, and is not recomputable.
        with engine.connect() as connection:
            from sqlalchemy import inspect

            if inspect(connection).has_table("jobs"):
                count = connection.exec_driver_sql(
                    "SELECT count(*) FROM jobs"
                ).scalar()

                if count:
                    raise SystemExit(
                        "Refusing to seed: this database already "
                        f"holds {count} jobs."
                    )

    Base.metadata.create_all(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    rng = random.Random(
        SEED
    )

    pulls = pull_times(
        now
    )

    jobs = build_demo_jobs(
        rng,
        now=now,
        pulls=pulls,
        count=job_count,
    )

    with factory.begin() as session:
        _store_jobs(
            session,
            jobs=jobs,
            pulls=pulls,
            now=now,
        )

        resume = store_resume(
            session,
            label="Alex Rivera, fall 2026",
            filename="alex-rivera-resume.pdf",
            raw_text=RESUME_TEXT,
            now=now - timedelta(days=12),
        )

        scored = rescore_corpus(
            session,
            resume=resume,
        )

        _store_marks(
            session,
            rng,
            now=now,
        )

        answers = _store_answers(
            session,
            now=now,
        )

    with factory.begin() as session:
        _store_studio(session, now=now)

    # A fictional owner, so the demo runs with sign-in on, exactly as the
    # real app does. The password is public on purpose: it opens only
    # this generated, fictional database.
    with factory.begin() as session:
        create_owner(
            session,
            email=DEMO_OWNER_EMAIL,
            password=DEMO_OWNER_PASSWORD,
            now=now,
        )

    with factory() as session:
        passing = session.scalar(
            select(
                JobEvaluationRecord.eligibility_status
            )
            .where(
                JobEvaluationRecord.eligibility_status == "PASS"
            )
            .limit(1)
        )

        statuses: dict[str, int] = {}

        for (status,) in session.execute(
            select(
                JobEvaluationRecord.eligibility_status
            )
        ):
            statuses[status] = statuses.get(status, 0) + 1

    assert passing, "the demo must hold qualifying jobs"

    return {
        "companies": len(DEMO_COMPANY_TIERS),
        "jobs": len(jobs),
        "statuses": statuses,
        "scored": scored,
        "pulls": len(pulls),
        "answers": answers,
        "owner": DEMO_OWNER_EMAIL,
    }


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a fictional demo database for ACE."
        ),
    )

    parser.add_argument(
        "--database-url",
        default="sqlite:///ace-demo.db",
        help=(
            "Where to build it. A SQLite file is replaced; a "
            "PostgreSQL database must hold no jobs."
        ),
    )

    parser.add_argument(
        "--jobs",
        type=int,
        default=360,
    )

    args = parser.parse_args(
        argv
    )

    summary = seed(
        args.database_url,
        job_count=args.jobs,
    )

    print(
        "demo database ready: "
        + ", ".join(
            f"{key}={value}"
            for key, value in summary.items()
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
