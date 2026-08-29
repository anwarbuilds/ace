# ACE

ACE is a personal real-time career intelligence platform for discovering, filtering, ranking, and alerting on relevant US engineering opportunities.

The project is being built from scratch as an end-to-end backend, data, systems, and full-stack engineering project.

## Product Goal

ACE reduces the manual job-search workflow:

```text
Search job boards
    ↓
Open many irrelevant postings
    ↓
Check location
    ↓
Check seniority
    ↓
Check experience
    ↓
Check work-authorization language
    ↓
Find official company careers page
    ↓
Apply
```

into:

```text
ACE discovers jobs
    ↓
ACE normalizes them
    ↓
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE remembers previously seen jobs
    ↓
ACE detects newly posted opportunities
    ↓
ACE evaluates resume relevance
    ↓
ACE ranks opportunities
    ↓
ACE sends alerts
    ↓
User opens the official employer application link
```

## Target Opportunity Profile

### Geography

- United States
- Remote-US

A generic `Remote` location is not automatically assumed to mean Remote-US.

### Primary Role Families

- Software Engineering / Software Development Engineering
- AI / Machine Learning Engineering

### Secondary Role Family

- Forward Deployed Engineering

### Current Hard Exclusions

ACE currently rejects opportunities that are clearly:

- outside US / Remote-US scope
- outside the configured target role families
- senior, staff, principal, lead, manager, director, or equivalent level
- explicitly targeted to PhD candidates
- explicitly requiring a PhD or doctoral degree
- beyond the configured early-career experience range
- restricted by explicit US citizenship or US-person requirements
- restricted by explicit security-clearance requirements
- explicitly unavailable for current or future sponsorship

A PhD that is only preferred does not cause rejection.

Missing sponsorship information is treated as unknown rather than as rejection.

## Core Product Invariants

### Eligibility Controls Inclusion

Eligibility decides whether a job belongs in the candidate set.

Resume relevance and ranking will only control prioritization.

A qualifying opportunity must not disappear simply because resume relevance is low.

### Resume Relevance Will Not Hide Qualifying Jobs

Planned relevance tiers:

```text
HIGH
MEDIUM
MINIMAL
```

These tiers will help order and explain opportunities, but they will not suppress otherwise qualifying jobs.

### Official Application Links Are Preferred

ACE stores and surfaces the employer's official application URL whenever the ATS provides one.

### Newly Discovered Qualifying Jobs Become Notification Candidates

Target rule:

```text
NEW
+
target role
+
PASS or STRETCH
    ↓
notification candidate
```

## Current Architecture

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
    ↓
Role Classification
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
```

Planned architecture:

```text
Employer Sources
        ↓
Source Adapters
        ↓
CanonicalJob
        ↓
Role Classification
        ↓
Eligibility Gate
        ↓
Persistence
        ↓
Deduplication
        ↓
New-Job Detection
        ↓
Work-Authorization Intelligence
        ↓
Resume Relevance
        ↓
Ranking
        ↓
Notification Engine
        ↓
Web Application
```

## Implemented Modules

### Module 0 — Project Foundation

Implemented:

- Python 3.12 project environment
- `pyenv`
- project-local `.venv`
- Git
- GitHub
- dependency isolation
- repository documentation
- local development files excluded through `.gitignore`

### Module 1 — Greenhouse Job Ingestion

Implemented:

- public Greenhouse Job Board API integration
- explicit HTTP timeout
- descriptive User-Agent
- full job-description retrieval
- HTML-to-text normalization
- provider-specific data normalized into `CanonicalJob`
- manual live integration smoke testing

`CanonicalJob` currently includes:

- source
- company
- external ID
- requisition ID
- title
- location
- description
- official application URL
- publication timestamp
- update timestamp

### Module 2 — Role Classification and Eligibility

Role families:

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
FORWARD_DEPLOYED_ENGINEERING
OTHER
```

Priorities:

```text
PRIMARY
├── SOFTWARE_ENGINEERING
└── AI_ML_ENGINEERING

SECONDARY
└── FORWARD_DEPLOYED_ENGINEERING
```

Eligibility outcomes:

```text
PASS
STRETCH
REJECT
```

Current deterministic checks include:

- US / Remote-US geography
- target role family
- seniority
- PhD-targeted opportunities
- required experience
- citizenship restrictions
- security-clearance restrictions
- explicit sponsorship blockers

Current experience rules:

```text
0–2 required years
→ PASS

3 required years
→ STRETCH

4 required years
→ REJECT

4 required years + explicit early-career signal
→ STRETCH

5+ required years
→ REJECT
```

Preferred experience is not automatically treated as a hard requirement.

## Testing

Current automated backend suite:

```text
33 tests passing
```

Tests cover:

- canonical job creation
- Software Engineering classification
- AI/ML classification
- Forward Deployed classification
- classification precedence
- role priority
- US geography
- Remote-US geography
- seniority
- experience thresholds
- preferred experience
- PhD targeting
- required versus preferred PhD
- sponsorship blockers
- unknown sponsorship
- citizenship restrictions
- security-clearance restrictions

Unit tests do not depend on live external APIs.

## Live Validation

ACE has been validated against the live Databricks Greenhouse board.

One Module 2 audit snapshot contained:

```text
Total Databricks jobs:         855
Detected target-role jobs:     257
Qualifying target-role jobs:     1
```

Target roles detected before eligibility:

```text
Software Engineering:          167
AI / ML Engineering:             6
Forward Deployed Engineering:   84
```

Major overlapping rejection reasons among target-role jobs included:

```text
SENIOR_TITLE          236
EXPERIENCE_TOO_HIGH   217
OUTSIDE_US             96
PHD_TARGETED_ROLE       2
```

These values are only a live snapshot. They are not permanent expectations.

## Important Bugs Already Captured by Regression Tests

### Excessive Experience False Stretch

Earlier logic allowed a `7+ years` posting to become `STRETCH` because unrelated degree-substitution language appeared nearby.

The rule was corrected so clearly excessive required experience remains a hard rejection.

### PhD Preferred False Rejection

Earlier regex logic incorrectly interpreted:

```text
Bachelor's or Master's degree required.
PhD preferred.
```

as a required PhD.

The matcher was changed to detect explicit requirement grammar instead of loose keyword proximity.

## Documentation

ACE maintains three documentation layers:

- `README.md` — project-facing summary and current capabilities
- `docs/overview.md` — system architecture and module map
- `docs/learning-log.md` — implementation history, decisions, bugs, and lessons learned

## Development

Activate the environment:

```bash
source .venv/bin/activate
```

Run automated backend tests:

```bash
python -m pytest backend/tests -q
```

Run the live Greenhouse audit:

```bash
python -m backend.scripts.greenhouse_smoke
```

## Current Status

Completed:

```text
Module 0 — Project Foundation
✅

Module 1 — Greenhouse Job Ingestion
✅

Module 2 — Role Classification
✅

Module 2 — Eligibility Gate
✅

Automated Tests — 33 passing
✅

Live Employer Validation
✅
```

Next:

```text
Module 3
PostgreSQL Persistence
+
Deduplication
+
New-Job Detection
```

Module 3 will give ACE memory so it can distinguish an already-seen job from a newly discovered opportunity.
