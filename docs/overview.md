# ACE System Overview

ACE is a personal real-time career-intelligence platform designed to discover relevant engineering opportunities, normalize employer job data, maintain durable source history, detect job lifecycle changes, evaluate deterministic eligibility, produce alert candidates, and deliver failure-resistant notifications with official employer application links.

This document is the high-level architecture and module map for the project.

For implementation history, debugging notes, trade-offs, and lessons learned, see:

```text
docs/learning-log.md
```

---

# 1. Product Goal

ACE transforms:

```text
manual company/job-board search
    ↓
repeated filtering
    ↓
manual eligibility inspection
    ↓
manual freshness checking
    ↓
manual application-link discovery
```

into:

```text
automated source retrieval
    ↓
canonical normalization
    ↓
durable source memory
    ↓
change detection
    ↓
eligibility intelligence
    ↓
durable notification delivery
```

The long-term product objective is near-real-time awareness of relevant openings across a broad employer set.

---

# 2. Target Opportunity Profile

## Primary Role Families

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
```

Priority:

```text
PRIMARY
```

## Secondary Role Family

```text
FORWARD_DEPLOYED_ENGINEERING
```

Priority:

```text
SECONDARY
```

---

# 3. Recall-Oriented Discovery Policy

ACE is deliberately conservative about missing information.

Core rule:

```text
missing information
!=
negative evidence
```

Examples:

```text
missing sponsorship statement
→ retain

explicit no sponsorship
→ reject
```

```text
generic Remote
→ retain conservatively

Remote Europe
→ reject
```

```text
PhD preferred
→ do not reject solely for preference

PhD-targeted / required
→ reject
```

This policy protects discovery recall across startups and employers whose job descriptions are less standardized.

---

# 4. Core Architectural Invariants

## 4.1 Canonical Data Before Intelligence

All ATS-specific data becomes:

```text
CanonicalJob
```

before persistence or eligibility logic.

```text
Greenhouse ─┐
Lever ──────┼──→ CanonicalJob
Ashby ──────┘
```

Only Greenhouse is currently implemented.

---

## 4.2 Persistence Before Eligibility

Complete normalized source state is persisted before downstream filtering.

```text
ATS
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Evaluation
```

This separates:

```text
what exists
```

from:

```text
what currently qualifies
```

---

## 4.3 Persistence Owns Lifecycle Detection

Persistence emits:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

It does not own eligibility or notification policy.

---

## 4.4 Evaluation Owns Eligibility Decisions

Evaluation consumes changed jobs and emits:

```text
ALERT
SUPPRESS
```

Current mapping:

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

---

## 4.5 Change Detection Is a Computational Gate

Normal evaluation processes:

```text
NEW
UPDATED
REOPENED
```

Normal evaluation does not repeatedly process:

```text
UNCHANGED
```

This allows frequent source polling without re-evaluating the complete employer corpus every time.

---

## 4.6 Baselines Are Metadata, Not A Filter

First successful source snapshot:

```text
persist current jobs
    ↓
establish source baseline
    ↓
NEW jobs are still evaluated
    ↓
freshness policy decides which may alert
```

Baseline suppression was intentionally removed: a company discovered
today may have posted an excellent role yesterday.

Instead, a baseline `NEW` job must additionally look recent before it
may interrupt the user. Non-baseline `NEW` and `REOPENED` jobs carry
their own present-tense evidence and are not age-gated.

Jobs held back by freshness remain persisted and searchable.

---

## 4.7 Empty Snapshots Are Not Trusted

An empty ATS response may indicate failure.

ACE refuses to automatically interpret an unexpectedly empty complete snapshot as:

```text
every active job closed
```

---

## 4.8 Exact Time Is Durable

ACE stores exact timestamps.

Examples:

- employer posting time
- employer update time
- ACE observation time
- outbox creation time
- delivery attempt time
- sent time

Relative strings are computed at presentation time.

---

## 4.9 Notification Must Be Durable Before Transport

ACE does not rely on:

```text
evaluate
→ send email immediately
```

because an SMTP failure after database state has changed could permanently lose the notification.

Instead:

```text
job state
+
evaluation
+
notification outbox
        ↓
database commit
        ↓
external delivery
```

---

# 5. Current High-Level Architecture

```text
Greenhouse API
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
    ↓
PostgreSQL Snapshot Persistence
    ↓
NEW / UPDATED / REOPENED / UNCHANGED / CLOSED
    ↓
Evaluation Candidates
    ↓
Evaluation Service
    ↓
Role Classification
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
    ↓
ALERT / SUPPRESS
    ↓
Notification Renderer
    ↓
PostgreSQL Notification Outbox
    ↓
PENDING
    ↓
Notification Delivery Worker
    ↓
SMTP / Gmail
    ↓
SENT / retry / DEAD
```

The missing infrastructure layer for continuous operation is scheduling.

---

# 6. Module Map

## Module 0 — Project Foundation

Purpose:

- reproducible Python environment
- source control
- dependency isolation
- documentation
- local development hygiene

Status:

```text
IMPLEMENTED
```

---

## Module 1 — Greenhouse Job Ingestion

Purpose:

Retrieve live Greenhouse employer postings and normalize them.

```text
Greenhouse
    ↓
HTTP
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Responsibilities:

- HTTP timeout
- User-Agent
- JSON parsing
- HTML description normalization
- official job URL extraction
- provider timestamps
- canonical job construction

Status:

```text
IMPLEMENTED
```

---

## Module 2 — Role Classification and Eligibility

Purpose:

Determine target role membership and deterministic blockers.

Role families:

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
FORWARD_DEPLOYED_ENGINEERING
OTHER
```

Eligibility:

```text
PASS
STRETCH
REJECT
```

Checks include:

- role family
- geography
- seniority
- experience
- PhD targeting
- citizenship restrictions
- security clearance
- sponsorship blockers

Status:

```text
IMPLEMENTED
```

---

## Module 2.1 — Recall Hardening

Purpose:

Reduce false negatives for startup, early-career, and ambiguous postings.

Validated examples:

```text
Software Engineer I + Remote
→ STRETCH
```

```text
Founding Engineer + San Francisco
→ PASS
```

```text
Product Engineer + Remote
→ STRETCH
```

```text
Software Engineer - New Grad + New York
→ PASS
```

```text
explicit no sponsorship
→ REJECT
```

```text
Remote Europe
→ REJECT
```

Key policy:

```text
unknown
→ preserve recall

explicit blocker
→ reject
```

Status:

```text
IMPLEMENTED
```

---

## Module 3 — PostgreSQL Persistence and Job Lifecycle

Purpose:

Give ACE durable memory and lifecycle awareness.

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
Docker
    ↓
PostgreSQL:5432
```

Technologies:

- PostgreSQL 16
- Docker Compose
- SQLAlchemy 2.x
- psycopg 3
- Alembic
- pydantic-settings

Durable job identity:

```text
source
+
source_account
+
external_id
```

Lifecycle:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

Responsibilities:

- content hashing
- source baseline state
- deterministic snapshot reference time
- snapshot reconciliation
- snapshot deduplication
- N+1 query avoidance
- transaction-safe persistence
- empty-snapshot protection

Status:

```text
IMPLEMENTED
```

---

## Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

Purpose:

Connect source lifecycle changes to eligibility intelligence.

```text
Persistence
    ↓
Evaluation Candidates
    ↓
Evaluation Service
    ↓
Eligibility
    ↓
ALERT / SUPPRESS
```

Domain types:

```text
AlertDisposition
EvaluatedJob
EvaluationBatchResult
```

Normal evaluation accepts:

```text
NEW
UPDATED
REOPENED
```

and ignores normal application evaluation for:

```text
UNCHANGED
CLOSED
```

Source-snapshot orchestration provides an application use case while leaving transaction ownership with the caller.

Status:

```text
IMPLEMENTED
```

---

## Module 5 — Durable Notification Pipeline

Purpose:

Turn alert candidates into real email notifications without losing them when an external transport fails.

Module 5 contains several layers.

### Notification Domain

Responsibilities:

- notification message types
- transport-neutral representation

### Notification Renderer

Converts an evaluated alert into user-facing content.

Notification details include:

- change type
- company
- title
- location
- role family
- priority
- eligibility
- posting age
- exact posting timestamp
- update timestamp
- official employer URL

### SMTP Transport

Responsibilities:

- Gmail SMTP
- STARTTLS
- App Password authentication
- configurable timeout
- configurable sender
- configurable recipient

### Durable Outbox

PostgreSQL table:

```text
notification_outbox
```

Status values:

```text
PENDING
SENT
DEAD
```

### Delivery Worker

Responsibilities:

- select due PENDING rows
- row locking
- SMTP delivery
- successful SENT transitions
- failed-attempt persistence
- retry scheduling
- DEAD state after max attempts

Status:

```text
IMPLEMENTED
```

---

# 7. Database Architecture

Current tables:

```text
jobs
source_states
notification_outbox
```

---

## `jobs`

Stores canonical durable job state.

Primary responsibilities:

- source identity
- normalized job fields
- meaningful content hash
- first-seen time
- last-seen time
- active/closed state

Unique identity:

```text
source
+
source_account
+
external_id
```

---

## `source_states`

Stores polling state for each ATS source account.

Identity:

```text
source
+
source_account
```

Tracks:

- initialization
- last successful source processing
- previous job count

---

## `notification_outbox`

Stores durable external-delivery work.

Important columns include:

```text
dedupe_key
source
source_account
external_id
observation_status
job_content_hash
source_updated_at
recipient
subject
text_body
status
attempt_count
next_attempt_at
created_at
last_attempt_at
sent_at
last_error
```

Unique constraint:

```text
dedupe_key
```

Retry index:

```text
status
+
next_attempt_at
+
created_at
```

Current migration head:

```text
0002
```

---

# 8. Transaction Architecture

The live source operation deliberately uses one database transaction for source mutation and notification creation.

```text
BEGIN

reconcile source snapshot

evaluate NEW / UPDATED / REOPENED jobs

render qualifying alerts

insert PENDING notification_outbox rows

COMMIT
```

Only after this succeeds does SMTP delivery begin.

This prevents:

```text
database changed
+
email generation lost
```

after an application crash.

---

# 9. Notification Deduplication

ACE constructs a stable SHA-256 identity for a logical notification event.

Inputs include:

```text
source
source account
external job ID
observation status
job content hash
provider update timestamp
recipient
```

Not included:

```text
ACE polling time
```

Therefore repeated polling does not create duplicate notification rows for the same logical event.

---

# 10. Delivery Concurrency

The PostgreSQL delivery repository uses:

```text
SELECT ... FOR UPDATE SKIP LOCKED
```

This prepares ACE for multiple workers.

Conceptually:

```text
Worker A
→ locks notification 1

Worker B
→ skips notification 1
→ locks notification 2
```

This avoids concurrent processing of the same due row.

---

# 11. Retry Policy

A failed external delivery remains:

```text
PENDING
```

and stores:

- incremented `attempt_count`
- `last_attempt_at`
- `last_error`
- future `next_attempt_at`

Exponential retry behavior begins:

```text
1st failure
→ +60 seconds

2nd failure
→ +120 seconds

3rd failure
→ +240 seconds
```

with a configured maximum delay.

After maximum attempts:

```text
DEAD
```

The record remains inspectable.

---

# 12. Delivery Guarantee

The notification pipeline provides durable at-least-once processing.

A distributed-system failure window remains possible:

```text
SMTP provider accepts message
    ↓
application crashes
    ↓
database never records SENT
    ↓
message may be retried
```

Exactly-once SMTP delivery cannot be guaranteed without cooperation from the external transport.

ACE chooses:

```text
possible rare duplicate
```

over:

```text
possible permanently lost opportunity
```

---

# 13. Live Source Behavior

A live Databricks Greenhouse run validated the complete source path.

At one checkpoint:

```text
Fetched:    859
UNCHANGED:  859
Evaluated:  0
Queued:     0
Sent:       0
```

This is correct.

ACE does not repeatedly alert on unchanged jobs.

---

# 14. Testing Strategy

Current deterministic suite:

```text
101 tests passing
```

Testing layers include:

## Unit Tests

Validate deterministic application behavior without external services.

## PostgreSQL Integration Tests

Validate:

- persistence
- lifecycle
- outbox schema
- uniqueness
- real inserts
- duplicate suppression
- cleanup

## Live ATS Smoke Tests

Validate:

- Greenhouse connectivity
- normalization
- full source polling

## SMTP Integration Tests

Validate:

- Gmail configuration
- STARTTLS
- authentication
- real message delivery

## Failure-Recovery Tests

Validate:

```text
PENDING
→ forced SMTP failure
→ PENDING + retry
→ successful SMTP retry
→ SENT
```

---

# 15. Validated Module 5 Failure Recovery

Initial state:

```text
status = PENDING
attempt_count = 0
```

Forced transport failure:

```text
SMTP_HOST=127.0.0.1
SMTP_PORT=1
```

Observed:

```text
Attempted:       1
Sent:            0
Retry scheduled: 1
Dead:            0
```

Persisted state:

```text
status = PENDING
attempt_count = 1
last_error = ConnectionRefusedError
sent_at = NULL
```

After resetting the retry timestamp and using normal Gmail:

```text
Attempted:       1
Sent:            1
Retry scheduled: 0
Dead:            0
```

Final state:

```text
status = SENT
attempt_count = 2
sent_at populated
last_error cleared
```

Synthetic rows were then deleted.

---

# 16. Observability Philosophy

ACE should make important decisions inspectable.

Source-level observability:

```text
jobs fetched
unique jobs
duplicates
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
evaluation candidates
```

Evaluation observability:

```text
PASS
STRETCH
REJECT
ALERT
SUPPRESS
rejection reasons
```

Notification observability:

```text
candidates
queued
duplicates
attempted
sent
retry scheduled
dead
last error
```

Future production metrics should include:

- source request latency
- source failure rate
- source-to-detection latency
- notification queue depth
- oldest pending notification age
- delivery success rate
- retry rate
- DEAD count
- worker latency

---

# 17. Current Data Flow

```text
Employer ATS
    ↓
Source Adapter
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Lifecycle
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
Eligibility
    ↓
PASS / STRETCH / REJECT
    ↓
Alert Disposition
    ├── ALERT
    └── SUPPRESS
    ↓
Notification Renderer
    ↓
Durable Notification Outbox
    ↓
PENDING
    ↓
Delivery Worker
    ↓
SMTP
    ↓
SENT / retry / DEAD
```

---

# 18. Current Project Status

```text
Module 0 — Foundation
✅

Module 1 — Greenhouse Ingestion
✅

Module 2 — Role Classification + Eligibility
✅

Module 2.1 — Recall Hardening
✅

Module 3 — PostgreSQL Persistence + Lifecycle
✅

Module 4 — Evaluation Pipeline + Workflow
✅

Module 5 — Durable Notification Pipeline
✅

Automated Tests
101 passing
✅

Alembic
0002 (head)
✅

Live Greenhouse Validation
✅

Real PostgreSQL Validation
✅

Real Gmail SMTP Validation
✅

Durable Outbox Validation
✅

Failure + Retry Recovery Validation
✅
```

---

# 19. Current Limitation

ACE's source pipeline is now functional and durable, but continuous polling is not yet automatic.

Today:

```text
manual/externally triggered run
    ↓
ACE pipeline
    ↓
notification
```

Next:

```text
scheduler
    ↓
automatic repeated source runs
    ↓
ACE pipeline
    ↓
notification
```

---

# 20. Next Architecture Stage

Primary next infrastructure target:

```text
Scheduler / Polling Runtime
```

Responsibilities should include:

- repeated execution
- configurable polling intervals
- company/source registry
- per-source isolation
- failure containment
- operational logging
- potentially concurrent source processing

Then source expansion:

```text
Greenhouse
Lever
Ashby
other startup ATS providers
```

Later intelligence:

```text
work-authorization evidence
resume ingestion
resume relevance
freshness-aware ranking
notification preferences
web application
```

---

# 21. Documentation Structure

ACE maintains:

```text
README.md
→ public/project-facing summary

docs/overview.md
→ current architecture

docs/learning-log.md
→ implementation history and engineering lessons
```

---

# 22. Module Development Workflow

Every module follows:

```text
1. Explain architecture
2. Identify exact affected files
3. Provide complete file contents
4. Run deterministic tests
5. Run real smoke tests when relevant
6. Inspect actual behavior
7. Update documentation
8. Inspect Git diff
9. Commit
10. Push
11. Move to next module
```

For project-file modifications, complete replacement contents are preferred over fragmented patch instructions.