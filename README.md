# ACE

ACE is a personal real-time career intelligence platform for discovering, normalizing, persisting, evaluating, ranking, and eventually notifying on relevant US engineering opportunities.

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
ACE persists complete source snapshots
    ↓
ACE detects NEW / UPDATED / REOPENED / CLOSED jobs
    ↓
ACE evaluates changed jobs
    ↓
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE produces alert candidates
    ↓
ACE will evaluate resume relevance
    ↓
ACE will rank opportunities
    ↓
ACE will send notifications
    ↓
User opens the official employer application link
```

The main objective is to minimize time spent searching, sorting, and checking irrelevant postings so the user's dedicated application time can be spent primarily on applying.

---

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

---

## Core Product Invariants

### Canonical Data Before Intelligence

Provider-specific ATS payloads are normalized into `CanonicalJob` before persistence or intelligence.

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Future ATS adapters should produce the same canonical representation.

### Persistence Happens Before Eligibility Filtering

ACE persists the complete normalized employer snapshot before downstream eligibility filtering.

```text
ATS
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Evaluation
```

This means ACE can remember jobs even if they are currently rejected, because:

- employer postings can change
- eligibility rules can evolve
- a previously irrelevant job can later become relevant
- historical source state is valuable independently from notification policy

### Persistence Reports What Changed

Persistence answers:

```text
What changed in the source?
```

using:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

Persistence does not decide whether the user should be notified.

### Evaluation Decides Whether a Changed Job Continues

The evaluation layer receives only changed jobs that persistence has designated as evaluation candidates.

Current mapping:

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

`ALERT` currently means:

```text
continue toward the future notification layer
```

It does not yet mean an email or push notification was actually sent.

### Resume Relevance Will Not Hide Qualifying Jobs

Planned relevance tiers:

```text
HIGH
MEDIUM
MINIMAL
```

These tiers will control ranking and explanation, not hard inclusion.

A qualifying opportunity should not disappear simply because resume relevance is lower.

### Official Application Links Are Preferred

ACE stores and surfaces the employer's official application URL whenever the ATS provides one.

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
    ↓
0 alert candidates
```

Only later source changes become downstream evaluation candidates.

### Empty Source Snapshots Are Not Trusted as Authoritative

An unexpectedly empty provider response could indicate an upstream failure.

ACE refuses to treat an empty complete snapshot as proof that every job has closed.

### Store Exact Timestamps; Compute Relative Time at Presentation

ACE preserves exact timestamps such as:

- employer `posted_at`
- employer `updated_at`

Relative labels such as:

```text
15 minutes ago
3 hours ago
2 days ago
```

are computed at display or notification time rather than stored in the database.

A future polling/notification layer will also expose ACE detection time.

---

# Current Architecture

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
Evaluation Candidates
    ↓
Evaluation Workflow
    ↓
Role Classification
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
    ↓
ALERT / SUPPRESS
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
Changed-Job Evaluation
        ↓
Role Classification
        ↓
Eligibility Gate
        ↓
Work-Authorization Intelligence
        ↓
Resume Relevance
        ↓
Freshness-Aware Ranking
        ↓
Notification Engine
        ↓
Web Application
```

---

# Implemented Modules

## Module 0 — Project Foundation

Implemented:

- Python 3.12 project environment
- `pyenv`
- project-local `.venv`
- Git
- GitHub
- dependency isolation
- repository documentation
- local development files excluded through `.gitignore`

## Module 1 — Greenhouse Job Ingestion

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

## Module 2 — Role Classification and Eligibility

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

## Module 3 — PostgreSQL Persistence and Job Lifecycle

Module 3 gives ACE durable memory.

Implemented:

- PostgreSQL 16
- Docker Compose
- persistent Docker volume
- local PostgreSQL host port `5433`
- `psycopg`
- SQLAlchemy 2.x
- Alembic
- environment-based database configuration
- durable source identity
- SHA-256 content hashing
- baseline protection
- snapshot deduplication
- N+1 query avoidance
- atomic transactions
- empty-snapshot protection
- NEW / UPDATED / REOPENED / UNCHANGED / CLOSED lifecycle handling

At the Module 3 live Databricks checkpoint:

```text
Total persisted jobs: 855
Active jobs:          855
Closed jobs:            0
```

A synthetic real-PostgreSQL smoke test also validates baseline, NEW, UPDATED, CLOSED, and REOPENED behavior.

## Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

Module 4 connects persistence changes to the intelligence layer.

Before Module 4:

```text
Persistence
→ NEW / UPDATED / REOPENED / UNCHANGED / CLOSED

Eligibility
→ PASS / STRETCH / REJECT
```

After Module 4:

```text
Persistence
    ↓
Evaluation Candidates
    ↓
Evaluation Workflow
    ↓
Role Classification
    ↓
Eligibility
    ↓
ALERT / SUPPRESS
```

### Evaluation Types

Module 4 adds:

- `AlertDisposition`
- `EvaluatedJob`
- `EvaluationBatchResult`

### Current Alert Policy

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

### Evaluation Scope

Only:

```text
NEW
UPDATED
REOPENED
```

enter normal job evaluation.

```text
UNCHANGED
CLOSED
```

do not enter normal application-alert evaluation.

Baseline snapshots also produce zero evaluated jobs.

### Source-Snapshot Workflow

Module 4 adds:

```text
run_source_snapshot_workflow(...)
```

which coordinates:

```text
process_snapshot(...)
    ↓
SnapshotResult
    ↓
evaluate_snapshot(...)
    ↓
EvaluationBatchResult
```

The workflow is intentionally reusable by future:

- scheduled workers
- API endpoints
- CLI tools
- notification jobs
- integration tests

Transaction ownership remains with the caller.

### Real PostgreSQL End-to-End Validation

Synthetic baseline:

```text
2 jobs persisted
0 evaluation candidates
0 alert candidates
```

Second poll:

```text
Fetched:                6
Unique:                 6
NEW:                    4
UPDATED:                1
REOPENED:               0
UNCHANGED:              1
CLOSED:                 0
Evaluation candidates:  5
```

Evaluation:

```text
Evaluated:              5
PASS:                   3
STRETCH:                1
REJECT:                 1
Alert candidates:       4
Suppressed:             1
```

The test demonstrates:

```text
UPDATED Software Engineer
→ PRIMARY
→ PASS
→ ALERT

NEW Software Engineer
→ PRIMARY
→ PASS
→ ALERT

NEW Machine Learning Engineer
→ PRIMARY
→ STRETCH
→ ALERT

NEW Forward Deployed Engineer
→ SECONDARY
→ PASS
→ ALERT

NEW Senior Software Engineer
→ REJECT
→ SUPPRESS
```

Synthetic PostgreSQL records are cleaned up after the smoke test.

### Freshness Presentation

The end-to-end smoke test displays:

- company
- title
- location
- source change
- role family
- role priority
- eligibility
- relative posting age
- exact posting timestamp
- exact update timestamp
- official application URL

Example:

```text
Change:      NEW
Company:     ACE Module 4 Synthetic Company
Title:       Software Engineer
Location:    Seattle, Washington
Role family: SOFTWARE_ENGINEERING
Priority:    PRIMARY
Eligibility: PASS
Posted:      15 minutes ago
Posted at:   2026-08-29 14:00:00 UTC
Updated at:  2026-08-29 14:00:00 UTC
Official URL: https://example.com/jobs/C
```

Relative age is presentation-only. Exact timestamps remain the durable source of truth.

---

# Testing

Current automated backend suite:

```text
59 tests passing
```

The suite covers:

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
- evaluation disposition
- PASS/STRETCH alertability
- REJECT suppression
- NEW/UPDATED/REOPENED evaluation
- baseline evaluation suppression
- source-snapshot workflow orchestration
- observation-status preservation through evaluation

Integration smoke tests validate:

- live Greenhouse ingestion
- real PostgreSQL persistence
- synthetic persistence lifecycle transitions
- real PostgreSQL persistence-to-evaluation workflow

---

# Development

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

Run synthetic persistence lifecycle test:

```bash
python -m backend.scripts.persistence_state_smoke
```

Run the Module 4 real PostgreSQL workflow smoke test:

```bash
python -m backend.scripts.source_snapshot_workflow_smoke
```

Stop services:

```bash
docker compose down
```

Do not use `docker compose down -v` unless the PostgreSQL volume should intentionally be deleted.

---

# Documentation

ACE maintains three documentation layers:

- `README.md` — project-facing summary and current capabilities
- `docs/overview.md` — system architecture and module map
- `docs/learning-log.md` — implementation history, decisions, bugs, and lessons learned

---

# Current Status

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

Module 4 — Evaluation Pipeline + Source-Snapshot Workflow
✅

Automated Tests — 59 passing
✅

Live Databricks Persistence Validation
✅

Real PostgreSQL Lifecycle Validation
✅

Real PostgreSQL Evaluation Workflow Validation
✅
```

Next major capability:

```text
ALERT candidates
    ↓
notification rendering
    ↓
email delivery
    ↓
polling / scheduling
    ↓
real-time job alerts
```

Later intelligence stages will add:

```text
work-authorization evidence
resume relevance
freshness-aware ranking
multi-source coverage
web UI
```
