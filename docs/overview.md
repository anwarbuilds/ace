# ACE System Overview

ACE is a personal career-intelligence platform designed to discover relevant US engineering opportunities, normalize employer job data, persist source history, detect newly appearing or changed jobs, evaluate eligibility, produce alert candidates, rank opportunities, and eventually deliver notifications with official employer application links.

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
ACE evaluates changed jobs
    ↓
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE produces alert candidates
    ↓
ACE will evaluate work-authorization evidence
    ↓
ACE will evaluate resume relevance
    ↓
ACE will rank opportunities
    ↓
ACE will send notifications
    ↓
User opens the official employer application link
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

## Persistence Before Eligibility

ACE persists the complete normalized employer snapshot before eligibility filtering.

```text
ATS
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Evaluation
```

This keeps source memory independent from current filtering policy.

## Persistence Answers What Changed

Persistence emits:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

It does not decide whether the user should be notified.

## Evaluation Answers Whether a Changed Job Continues

Evaluation consumes changed jobs and produces:

```text
ALERT
SUPPRESS
```

Current policy:

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

This is intentionally recall-oriented.

## Notification Is a Separate Layer

An `ALERT` disposition means:

```text
eligible to continue toward notification
```

It does not yet mean a notification has been delivered.

Notification transport remains separate from evaluation policy.

## Eligibility Controls Candidate Inclusion

Resume relevance will later control prioritization, not hard inclusion.

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
0 evaluation candidates
    ↓
0 alert candidates
```

## Empty Snapshots Are Not Trusted

An unexpectedly empty provider response is not treated as proof that every job closed.

## Exact Time Is Durable; Relative Time Is Presentation

ACE stores exact timestamps.

Relative strings such as:

```text
15 minutes ago
```

are computed when presenting the job.

Planned user-facing timing:

```text
Employer posted
Employer updated
ACE detected
Relative age
```

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
Evaluation Candidates
    ↓
Source-Snapshot Workflow
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

# 5. Module Map

## Module 0 — Project Foundation

Purpose: establish a reproducible development environment and source-control workflow.

Status: implemented.

---

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

---

## Module 2 — Role Classification and Eligibility

Purpose: determine target-role membership and deterministic eligibility blockers.

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

---

## Module 3 — PostgreSQL Persistence and Job Lifecycle

Purpose: give ACE durable memory and source lifecycle awareness.

Infrastructure:

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

Database schema:

- `jobs` stores normalized durable job state
- `source_states` stores source baseline and successful polling state

Durable job identity:

```text
source
+
source_account
+
external_id
```

Persistence lifecycle:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

Other responsibilities:

- content hashing
- baseline protection
- snapshot deduplication
- N+1 query avoidance
- atomic transactions
- empty-snapshot protection

Status: implemented.

---

## Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

Purpose: connect source lifecycle changes to eligibility intelligence and produce clean downstream alert candidates.

Before Module 4:

```text
Persistence
→ What changed?

Eligibility
→ Does this job qualify?
```

After Module 4:

```text
Persistence
    ↓
Evaluation Candidates
    ↓
Evaluation Workflow
    ↓
Eligibility
    ↓
ALERT / SUPPRESS
```

### Evaluation Domain Types

Module 4 introduces:

```text
AlertDisposition
EvaluatedJob
EvaluationBatchResult
```

`AlertDisposition` values:

```text
ALERT
SUPPRESS
```

`EvaluatedJob` carries:

- `CanonicalJob`
- persistence observation status
- `EligibilityDecision`
- alert disposition

`EvaluationBatchResult` contains:

- all evaluated jobs
- alert candidates
- suppressed jobs
- PASS count
- STRETCH count
- REJECT count
- evaluated count
- alert-candidate count
- suppressed count

### Alert Policy

Current mapping:

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

`STRETCH` remains alertable because ACE is designed for recall-first discovery.

### Evaluation Scope

Normal evaluation accepts:

```text
NEW
UPDATED
REOPENED
```

Normal evaluation ignores:

```text
UNCHANGED
CLOSED
```

Baseline snapshots also produce no evaluated jobs.

### Source-Snapshot Workflow

Module 4 introduces:

```text
run_source_snapshot_workflow(...)
```

Its orchestration is:

```text
process_snapshot(...)
    ↓
SnapshotResult
    ↓
evaluate_snapshot(...)
    ↓
EvaluationBatchResult
```

The workflow deliberately does not:

- fetch from Greenhouse
- own notification transport
- own resume ranking
- own the database transaction boundary

This makes it reusable from:

- scheduled workers
- API handlers
- command-line scripts
- notification workers
- integration tests

### Transaction Boundary

The caller owns the transaction:

```text
caller
    ↓
transaction
    ↓
workflow
    ├── persistence
    └── evaluation
```

### Workflow Result

`SourceSnapshotWorkflowResult` contains:

```text
snapshot
evaluation
```

This provides one application-level result with both source lifecycle state and intelligence output.

### Real PostgreSQL End-to-End Validation

Dedicated synthetic source account:

```text
ace-module4-smoke
```

Pass 1 baseline:

```text
Baseline:               True
NEW:                    2
Evaluation candidates:  0
Evaluated:              0
Alert candidates:       0
```

Pass 2 changed state:

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

Expected mappings:

```text
UPDATED Software Engineer
→ SOFTWARE_ENGINEERING
→ PRIMARY
→ PASS
→ ALERT

NEW Software Engineer
→ SOFTWARE_ENGINEERING
→ PRIMARY
→ PASS
→ ALERT

NEW Senior Software Engineer
→ REJECT
→ SUPPRESS

NEW Machine Learning Engineer
→ AI_ML_ENGINEERING
→ PRIMARY
→ STRETCH
→ ALERT

NEW Forward Deployed Engineer
→ FORWARD_DEPLOYED_ENGINEERING
→ SECONDARY
→ PASS
→ ALERT
```

Synthetic records are deleted after execution.

### Posting-Time Presentation

The Module 4 smoke test displays both relative and exact timestamps.

Example:

```text
Posted:      15 minutes ago
Posted at:   2026-08-29 14:00:00 UTC
Updated at:  2026-08-29 14:00:00 UTC
```

Design rule:

```text
database/domain
→ exact timestamps

presentation
→ relative age + local-time rendering
```

The smoke test renders UTC for deterministic validation.

Production notification/UI should convert exact timestamps into the user's display timezone.

### Future Freshness Signal

Freshness is expected to become a ranking input, not an eligibility gate.

Potential presentation classes:

```text
JUST OPENED
VERY FRESH
FRESH
TODAY
RECENT
```

The exact thresholds are not yet implemented.

Planned ranking inputs:

```text
Role priority
+
Eligibility
+
Resume relevance
+
Posting freshness
```

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
Source-Snapshot Workflow
    ↓
Role Classifier
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
    ↓
Alert Disposition
    ├── ALERT
    └── SUPPRESS
```

Future:

```text
ALERT
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
    ↓
Official Employer Application Link
```

---

# 7. Testing Strategy

ACE uses multiple layers.

## Unit Tests

Current deterministic suite:

```text
59 tests passing
```

## Integration Smoke Tests

Used for real external dependencies:

- Greenhouse
- PostgreSQL

## Regression Tests

Real bugs become permanent tests.

Examples:

- excessive-experience false stretch
- `PhD preferred` false rejection

## Persistence Lifecycle Smoke Test

Real PostgreSQL validates:

- baseline
- NEW
- UPDATED
- CLOSED
- REOPENED
- cleanup

## Evaluation Workflow Smoke Test

Real PostgreSQL validates:

- baseline suppression
- changed-job detection
- persistence-to-evaluation handoff
- role classification
- eligibility
- alert disposition
- suppressed job behavior
- cleanup

---

# 8. Observability Philosophy

ACE should not behave like a black box.

Important states and decisions must be inspectable.

Example:

```text
source:
greenhouse

source_account:
databricks

persistence state:
UPDATED
```

Then:

```text
role family:
AI_ML_ENGINEERING

priority:
PRIMARY

eligibility:
STRETCH

alert disposition:
ALERT
```

Future operational metrics may include:

- jobs fetched per source
- unique source jobs
- duplicate source records
- NEW jobs
- UPDATED jobs
- REOPENED jobs
- CLOSED jobs
- evaluation candidates
- evaluated jobs
- alert candidates
- suppressed jobs
- target roles detected
- PASS count
- STRETCH count
- rejection reasons
- notification attempts
- notification successes/failures
- source failures
- request latency
- source-to-detection latency

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

Every ACE module follows:

```text
1. Explain architecture
2. Identify exact affected files
3. Provide complete file contents
4. Run deterministic tests
5. Run real integration smoke tests when relevant
6. Inspect actual behavior
7. Update documentation
8. Commit and push
9. Move to the next module
```

For modified project files, complete replacement contents are preferred over fragmentary patch instructions.

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

Module 4 — Evaluation Pipeline + Source-Snapshot Workflow
✅

Automated Tests
59 passing
✅

Live Greenhouse Validation
✅

Live PostgreSQL Validation
✅

Synthetic Persistence Lifecycle Validation
✅

Synthetic PostgreSQL Evaluation Workflow Validation
✅
```

Next architecture stage:

```text
ALERT candidates
    ↓
Notification rendering
    ↓
Email delivery
    ↓
Polling / scheduling
    ↓
real-time alerts
```

Later:

```text
Work-authorization intelligence
Resume relevance
Freshness-aware ranking
Additional ATS sources
Web application
```
