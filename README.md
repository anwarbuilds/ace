# ACE

ACE is a personal real-time career intelligence platform for discovering, filtering, ranking, persisting, and eventually alerting on relevant US engineering opportunities.

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
ACE persists source snapshots
    ↓
ACE detects NEW / UPDATED / REOPENED / CLOSED jobs
    ↓
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE evaluates resume relevance
    ↓
ACE ranks opportunities
    ↓
ACE sends alerts
    ↓
User opens the official employer application link
```

The primary product goal is to minimize time spent searching, sorting, and checking irrelevant jobs so the available job-search window can be spent primarily on applications.

## Target Opportunity Profile

### Geography

ACE targets:

- United States
- Remote-US opportunities

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

Resume relevance and ranking will control prioritization, not inclusion.

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

### Persistence Reports What Changed

Persistence is responsible for determining source lifecycle state:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

It does not decide whether an alert should be sent.

The downstream intelligence and notification layers decide whether a changed job should be surfaced.

### First-Run Baselines Must Not Spam Alerts

The first successful source snapshot is treated as historical baseline data.

```text
first source run
    ↓
persist all current jobs
    ↓
establish baseline
    ↓
0 evaluation candidates
```

Only subsequent changes become downstream evaluation candidates.

### Empty Source Snapshots Are Not Trusted as Authoritative

An unexpectedly empty provider response could indicate an upstream failure.

ACE therefore refuses to treat an empty complete snapshot as proof that every job has closed.

## Current Architecture

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
    ↓
PostgreSQL Persistence
    ↓
NEW / UPDATED / REOPENED / UNCHANGED / CLOSED
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
Persistence + Source Lifecycle
        ↓
New/Changed Job Detection
        ↓
Role Classification
        ↓
Eligibility Gate
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

### Module 3 — PostgreSQL Persistence and Job Lifecycle

Module 3 gives ACE durable memory.

#### Infrastructure

Implemented:

- PostgreSQL 16
- Docker Compose
- persistent Docker volume
- local PostgreSQL isolation on host port `5433`
- `psycopg`
- SQLAlchemy 2.x
- Alembic migrations
- environment-based database configuration

#### Database Tables

`jobs` stores durable job records including:

- source
- source account
- external ID
- company
- requisition ID
- title
- location
- description
- official URL
- posted timestamp
- source update timestamp
- content hash
- first-seen timestamp
- last-seen timestamp
- active/closed state

Durable identity:

```text
source + source_account + external_id
```

`source_states` stores:

- source
- source account
- initialized timestamp
- last successful snapshot timestamp
- last successful job count

This prevents first-deployment alert floods.

#### Persistence States

ACE now recognizes:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

#### Content Hashing

ACE computes a deterministic SHA-256 content fingerprint over meaningful normalized job content.

#### Baseline Protection

The first successful snapshot persists historical jobs but produces zero evaluation candidates.

#### Snapshot Deduplication

Duplicate external IDs inside one provider response are collapsed before persistence.

#### N+1 Query Avoidance

Existing jobs for an incoming snapshot are loaded in a batch rather than queried one-by-one.

#### Atomic Transactions

A complete source snapshot is processed inside one transaction.

#### Empty Snapshot Protection

A zero-job provider response is rejected as authoritative input.

#### Live Databricks Validation

Current persisted Databricks state:

```text
Total persisted jobs: 855
Active jobs:          855
Closed jobs:            0
```

Repeated live persistence passes produced:

```text
NEW:                    0
UPDATED:                0
REOPENED:               0
UNCHANGED:            855
CLOSED:                 0
Evaluation candidates:  0
```

#### Synthetic Lifecycle Validation

A dedicated real-PostgreSQL smoke test validates:

```text
baseline
NEW
UPDATED
CLOSED
REOPENED
```

Synthetic records are cleaned up after execution.

## Testing

Current automated backend suite:

```text
47 tests passing
```

Tests cover:

- canonical job creation
- role classification
- classification precedence
- role priority
- geography
- seniority
- experience rules
- PhD rules
- sponsorship/citizenship/clearance rules
- database model structure
- persistent identity constraints
- stable content hashing
- source snapshot behavior
- baseline suppression
- NEW detection
- UPDATED detection
- REOPENED detection
- CLOSED reporting
- duplicate-source-record handling
- empty snapshot rejection

## Development

Activate the environment:

```bash
source .venv/bin/activate
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Check health:

```bash
docker compose ps
```

Apply migrations:

```bash
alembic upgrade head
```

Run tests:

```bash
python -m pytest backend/tests -q
```

Run live Greenhouse eligibility audit:

```bash
python -m backend.scripts.greenhouse_smoke
```

Run live persistence audit:

```bash
python -m backend.scripts.persistence_smoke
```

Run synthetic lifecycle test:

```bash
python -m backend.scripts.persistence_state_smoke
```

Stop services:

```bash
docker compose down
```

## Documentation

ACE maintains three documentation layers:

- `README.md` — project-facing summary and current capabilities
- `docs/overview.md` — system architecture and module map
- `docs/learning-log.md` — implementation history, decisions, bugs, and lessons learned

## Current Status

Completed:

```text
Module 0 — Project Foundation
✅

Module 1 — Greenhouse Job Ingestion
✅

Module 2 — Role Classification + Eligibility
✅

Module 3 — PostgreSQL Persistence + Job Lifecycle
✅

Automated Tests — 47 passing
✅

Live Databricks Persistence Validation
✅

Real PostgreSQL Lifecycle Validation
✅
```

Next major capability:

```text
changed/new job
    ↓
role + eligibility evaluation
    ↓
work-authorization evidence
    ↓
resume relevance
    ↓
notification decision
```
