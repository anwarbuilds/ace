# ACE System Overview

ACE is a personal career-intelligence platform designed to discover relevant US engineering opportunities, normalize employer job data, persist source history, detect newly appearing or changed jobs, evaluate eligibility, rank opportunities, and eventually deliver alerts with official employer application links.

This document is the high-level architecture and module map for the project.

For detailed implementation notes, debugging history, trade-offs, and lessons learned, see:

`docs/learning-log.md`

---

# 1. Product Goal

ACE is intended to reduce the manual workflow:

```text
Search job boards
    ↓
Open many irrelevant postings
    ↓
Check location
    ↓
Check experience
    ↓
Check sponsorship
    ↓
Check seniority
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
ACE detects job lifecycle changes
    ↓
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE evaluates work-authorization evidence
    ↓
ACE evaluates resume relevance
    ↓
ACE ranks opportunities
    ↓
ACE sends alerts
    ↓
User opens official employer application link
```

---

# 2. Target Opportunity Profile

## Geography

ACE targets:

- United States
- Remote-US opportunities

A generic `Remote` location is not automatically assumed to mean Remote-US.

## Primary Role Families

### Software Engineering

Examples include:

- Software Engineer
- Software Development Engineer
- Backend Engineer
- Platform Engineer
- Infrastructure Engineer
- Full-Stack Engineer
- Systems Software Engineer
- Distributed Systems Engineer

Role family:

```text
SOFTWARE_ENGINEERING
```

Priority:

```text
PRIMARY
```

### AI / Machine Learning Engineering

Examples include:

- AI Engineer
- Machine Learning Engineer
- ML Engineer
- Applied AI Engineer
- Generative AI Engineer
- LLM Engineer
- AI Software Engineer
- Machine Learning Software Engineer
- AI Infrastructure Engineer
- ML Infrastructure Engineer
- AI Platform Engineer
- ML Platform Engineer
- AI Research Engineer
- Machine Learning Research Engineer

Role family:

```text
AI_ML_ENGINEERING
```

Priority:

```text
PRIMARY
```

## Secondary Role Family

### Forward Deployed Engineering

Examples include:

- Forward Deployed Engineer
- Forward Deployed Software Engineer
- Forward Deployed AI Engineer

Role family:

```text
FORWARD_DEPLOYED_ENGINEERING
```

Priority:

```text
SECONDARY
```

---

# 3. Core Architectural Invariants

## Canonical Data Before Intelligence

Provider-specific payloads are converted to `CanonicalJob` before downstream logic.

```text
Greenhouse ─┐
Lever ──────┼──→ CanonicalJob
Ashby ──────┘
```

## Persistence Happens Before Eligibility Filtering

ACE persists the complete normalized employer snapshot.

```text
ATS
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Role Classification
    ↓
Eligibility
```

This allows ACE to remember jobs even if they are currently rejected, because:

- employer postings can change
- eligibility rules can evolve
- previously irrelevant jobs may become relevant later

## Persistence Reports What Changed

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

It does not decide whether an alert should be sent.

## Eligibility Controls Candidate Inclusion

Eligibility determines whether an opportunity belongs in the candidate set.

Resume relevance does not silently hide qualifying jobs.

## Missing Information Is Not Automatically Negative

For example:

```text
no sponsorship evidence found
→ UNKNOWN
```

not:

```text
REJECT
```

## Official Application Links Are Preferred

ACE surfaces official employer application URLs whenever the source provides them.

## Baseline Runs Must Not Spam Alerts

The first successful snapshot for a source account is historical baseline data.

```text
first successful snapshot
    ↓
persist jobs
    ↓
mark source initialized
    ↓
0 downstream evaluation candidates
```

## Empty Snapshots Are Not Trusted

An unexpectedly empty provider response is not treated as proof that every job closed.

ACE refuses to process such a snapshot as authoritative.

---

# 4. Current High-Level Architecture

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
    ↓
Snapshot Persistence
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
Ranking
        ↓
Notification Engine
        ↓
Web Application
```

---

# 5. Module Map

## Module 0 — Project Foundation

Purpose: establish a reproducible development environment and source-control workflow.

Status: implemented.

## Module 1 — Greenhouse Job Ingestion

Purpose: retrieve live employer postings directly from Greenhouse and normalize them into `CanonicalJob`.

Flow:

```text
Greenhouse API
    ↓
HTTP GET
    ↓
JSON
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Status: implemented.

## Module 2 — Role Classification and Eligibility

Purpose: determine target-role membership and deterministic blockers.

Role families:

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
FORWARD_DEPLOYED_ENGINEERING
OTHER
```

Eligibility states:

```text
PASS
STRETCH
REJECT
```

Status: implemented as deterministic MVP v1.

## Module 3 — PostgreSQL Persistence and Job Lifecycle

Purpose: give ACE durable memory and source lifecycle awareness.

### Infrastructure

```text
ACE Python
    ↓
SQLAlchemy
    ↓
psycopg
    ↓
localhost:5433
    ↓
Docker port mapping
    ↓
PostgreSQL container:5432
```

Technologies:

- PostgreSQL 16
- Docker Compose
- SQLAlchemy 2.x
- psycopg 3
- Alembic
- pydantic-settings

### Database Schema

`jobs` stores every normalized job ACE has observed.

`source_states` stores baseline and successful polling state.

Durable job identity:

```text
source
+
source_account
+
external_id
```

Example:

```text
greenhouse
+
databricks
+
8559344002
```

A database unique constraint protects this identity.

### Persistence Lifecycle

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

### Content Hashing

ACE creates a deterministic SHA-256 content hash over meaningful normalized job content.

Provider update timestamps are excluded to avoid false update events.

### Baseline Protection

The first successful source snapshot establishes historical baseline data and generates zero evaluation candidates.

### Snapshot Deduplication

Incoming duplicate external IDs are collapsed before persistence.

### N+1 Query Avoidance

Existing source jobs are loaded in a batch rather than queried one job at a time.

### Atomic Transactions

Each source snapshot is processed as one transaction.

### Empty Snapshot Protection

Unexpected zero-job snapshots are rejected as authoritative input.

### Evaluation Candidates

Persistence returns:

```text
NEW
UPDATED
REOPENED
```

as downstream evaluation candidates.

Then:

```text
evaluation candidate
    ↓
Role Classification
    ↓
Eligibility
    ↓
future notification policy
```

### Real Databricks Validation

Current state:

```text
Total jobs:   855
Active jobs:  855
Closed jobs:    0
```

Repeated live polling:

```text
Baseline:               False
Fetched:                855
Unique:                 855
Duplicates:               0
NEW:                      0
UPDATED:                  0
REOPENED:                 0
UNCHANGED:              855
CLOSED:                   0
Evaluation candidates:    0
```

### Synthetic PostgreSQL Lifecycle Validation

Synthetic state transitions validate:

- baseline
- NEW
- UPDATED
- CLOSED
- REOPENED

Synthetic data is cleaned up after execution.

Status: implemented.

---

# 6. Current Data Flow

```text
Employer ATS
    ↓
Source Adapter
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Source Lifecycle State
    ├── NEW
    ├── UPDATED
    ├── REOPENED
    ├── UNCHANGED
    └── CLOSED
    ↓
Evaluation Candidates
    ↓
Role Classifier
    ↓
Eligibility Gate
```

Future:

```text
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
    ↓
Official Employer Application Link
```

---

# 7. Testing Strategy

Current deterministic suite:

```text
47 tests passing
```

Integration smoke tests validate:

- Greenhouse API behavior
- PostgreSQL behavior
- persistence lifecycle transitions

---

# 8. Observability Philosophy

ACE should not behave like a black box.

Important states and decisions must be inspectable.

Examples:

```text
source:
greenhouse

source_account:
databricks

persistence state:
UPDATED
```

and:

```text
role family:
AI_ML_ENGINEERING

eligibility:
REJECT

reason codes:
EXPERIENCE_TOO_HIGH
SENIOR_TITLE
```

---

# 9. Documentation Structure

ACE maintains three documentation layers.

## `README.md`

Project-facing summary.

## `docs/overview.md`

Architecture and module map.

## `docs/learning-log.md`

Engineering history, decisions, bugs, and lessons learned.

---

# 10. Module Development Workflow

```text
1. Explain architecture
2. Identify exact affected files
3. Provide complete file contents
4. Run deterministic tests
5. Run integration smoke tests when relevant
6. Inspect actual behavior
7. Update README + overview + learning log
8. Commit and push
9. Move to the next module
```

---

# 11. Current Project Status

```text
Module 0 — Foundation
✅

Module 1 — Greenhouse Ingestion
✅

Module 2 — Role Classification + Eligibility
✅

Module 3 — PostgreSQL Persistence + Job Lifecycle
✅

Automated Tests — 47 passing
✅

Live Greenhouse Validation
✅

Live PostgreSQL Validation
✅

Synthetic Lifecycle Validation
✅
```

Next architecture stage:

```text
NEW / UPDATED / REOPENED
    ↓
role + eligibility
    ↓
work-authorization evidence
    ↓
resume relevance
    ↓
notification decision
```
