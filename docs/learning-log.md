# ACE Learning Log

This document records what was built, why it exists, bugs discovered during implementation, engineering decisions, and the concepts learned while building ACE.

---

# Project Setup

## Python Environment

ACE uses Python 3.12.12 selected with `pyenv` and a project-local `.venv`.

Key lesson:

```text
pyenv
    ↓
Python version
    ↓
project .venv
    ↓
project dependencies
```

## Git and GitHub

Git provides local version history.

GitHub stores the remote repository.

Key concepts learned:

- repository
- working directory
- staging area
- commit
- commit hash
- branch
- remote
- origin
- push
- `.gitignore`

---

# Module 1 — Greenhouse Job Ingestion

## Problem

ACE needs employer job data directly from ATS systems instead of relying only on third-party aggregators.

## Architecture

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

## What Was Built

Greenhouse-specific payloads are normalized into `CanonicalJob`.

Important lessons:

- adapter pattern
- canonical data models
- HTTP timeout handling
- descriptive User-Agent
- HTML normalization
- live smoke testing

---

# Module 2 — Role Classification and Eligibility Gate

## Problem

ACE needs to distinguish target roles from irrelevant roles and reject deterministic blockers.

## Architecture

```text
CanonicalJob
    ↓
Role Classifier
    ↓
RoleFamily
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
```

## Role Families

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
FORWARD_DEPLOYED_ENGINEERING
OTHER
```

## Important Bugs

### Excessive Experience False Stretch

A high-experience role incorrectly survived because unrelated degree-substitution language was interpreted as an early-career signal.

Fix: clearly excessive required experience remains a hard rejection.

### `PhD preferred` False Rejection

Loose regex proximity caused `PhD preferred` to be treated as `PhD required`.

Fix: explicit requirement grammar is now used.

Key lessons:

- false negatives matter
- regression tests protect real bugs
- real employer data should validate deterministic assumptions
- do not overfit one employer corpus

---

# Module 3 — PostgreSQL Persistence and Job Lifecycle

## Problem

Before Module 3, ACE could fetch, normalize, classify, and evaluate jobs, but every process execution forgot previous runs.

ACE could not answer:

```text
Have I seen this job before?
Is this job genuinely new?
Did the employer change it?
Did it disappear?
Did it reopen?
```

Real-time alerting requires durable state.

---

## Infrastructure Architecture

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

A native PostgreSQL service already occupied host port `5432`, so ACE uses host port `5433`.

Important lesson:

```text
host port != container port
```

Docker allows ACE's PostgreSQL container to keep its internal default `5432` while exposing it as `5433` on the host.

---

## Docker Compose and Persistent Volumes

PostgreSQL runs through Docker Compose.

A named volume preserves database state across container recreation.

Important distinction:

```text
docker compose down
→ stop/remove containers
→ keep volume

docker compose down -v
→ also delete volume
→ database data removed
```

---

## Environment Configuration

ACE stores real local configuration in:

```text
.env
```

and safe example configuration in:

```text
.env.example
```

`.env` is ignored by Git.

Key lesson:

```text
source code
!=
runtime secrets/configuration
```

---

## Database Technologies

### PostgreSQL

Durable relational database.

### psycopg

Python PostgreSQL driver.

### SQLAlchemy

ORM/database abstraction.

### Alembic

Database-schema migration system.

### pydantic-settings

Environment-based application configuration.

---

## Pydantic vs SQLAlchemy

ACE now has two model types.

### `CanonicalJob`

Domain/application representation.

Question answered:

```text
What does a normalized job look like inside ACE?
```

### `JobRecord`

Persistent SQLAlchemy representation.

Question answered:

```text
How is the job stored in PostgreSQL?
```

Separating domain and persistence models reduces coupling.

---

## Database Schema

### `jobs`

Stores durable job state.

Important fields:

```text
id
source
source_account
external_id
company
requisition_id
title
location
description
official_url
posted_at
source_updated_at
content_hash
first_seen_at
last_seen_at
is_active
closed_at
```

### `source_states`

Stores per-source baseline and polling state.

```text
source
source_account
initialized_at
last_success_at
last_job_count
```

---

## Durable Job Identity

Provider-local IDs alone are not sufficient across many employer boards.

ACE uses:

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

A PostgreSQL unique constraint enforces this identity.

Lesson:

```text
application deduplication
+
database constraint
=
defense in depth
```

---

## Alembic

Initial schema migration:

```text
0001_create_jobs_and_source_states
```

Git versions source code.

Alembic versions database schema.

Manual production schema changes should be avoided.

---

## Source Snapshot Model

One complete employer response is treated as a source snapshot.

Example:

```text
Databricks Greenhouse
    ↓
855 jobs
    ↓
one snapshot
```

That snapshot is compared against durable state.

---

## Baseline Protection

First successful source run:

```text
855 current jobs
    ↓
855 NEW to database
    ↓
baseline = true
    ↓
0 evaluation candidates
```

Key lesson:

```text
NEW to database
!=
newly posted after ACE started
```

Without this distinction, first deployment could create hundreds of false alerts.

---

## Persistence Lifecycle

### NEW

Identity does not exist.

### UNCHANGED

Identity exists and meaningful content hash is the same.

### UPDATED

Identity exists and meaningful content changed.

### CLOSED

Previously active job is absent from a successful complete snapshot.

### REOPENED

Previously inactive job appears again.

State flow:

```text
NEW
 ↓
UNCHANGED
 ↓
UPDATED

missing
 ↓
CLOSED

returns
 ↓
REOPENED
```

---

## Content Hashing

ACE computes a deterministic SHA-256 fingerprint over meaningful normalized job content.

Provider bookkeeping update timestamps are excluded.

Why?

Because a provider may change internal timestamps without changing the job posting.

Including such timestamps would generate false `UPDATED` events.

---

## N+1 Query Avoidance

Naive design:

```text
for each job:
    SELECT job
```

For 855 jobs, that can mean approximately 855 database round trips.

ACE instead batch-loads existing source identities and compares them in memory.

Key lesson:

Database round trips matter at scale.

---

## Atomic Transactions

Repository methods do not commit independently.

The caller owns the complete source-snapshot transaction.

```text
successful snapshot
→ COMMIT

failure
→ ROLLBACK
```

This prevents partially persisted source state.

---

## Empty Snapshot Protection

Dangerous scenario:

```text
provider/API failure
    ↓
0 parsed jobs
```

If interpreted as authoritative:

```text
all active jobs
→ CLOSED
```

ACE instead rejects an empty complete snapshot and rolls back.

This is an example of designing for upstream failure.

---

## Persistence vs Notification Separation

An architecture refinement was made during Module 3.

Persistence initially exposed:

```text
notification_candidates
```

That was too coupled.

It was replaced with:

```text
evaluation_candidates
```

Correct separation:

```text
Persistence
→ What changed?

Intelligence
→ Is it relevant/eligible?

Notification
→ Should the user be alerted?
```

---

## Synthetic Lifecycle Smoke Test

A synthetic source account validates real PostgreSQL transitions.

### Pass 1

```text
2 NEW
baseline = true
0 evaluation candidates
```

### Pass 2

```text
1 NEW
1 UPDATED
1 UNCHANGED
2 evaluation candidates
```

### Pass 3

```text
1 CLOSED
```

### Pass 4

```text
1 REOPENED
1 evaluation candidate
```

The test cleans up synthetic data afterward.

Verified cleanup:

```text
source_account = ace-module3-smoke
count = 0
```

---

## Live Databricks Persistence Validation

Current durable source state:

```text
source: greenhouse
source_account: databricks
last_job_count: 855
```

Current database state:

```text
total_jobs:  855
active_jobs: 855
closed_jobs:   0
```

Repeated live polling produced:

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

This demonstrates idempotency.

---

## Debugging Incident — Wrong Smoke-Test File Contents

`backend/scripts/persistence_smoke.py` accidentally contained unrelated test code.

Symptom:

```bash
python -m backend.scripts.persistence_smoke
```

returned immediately with no output.

Because imports succeeded, there was no traceback.

Inspecting the file showed the intended executable script had been overwritten/mixed.

The file was replaced completely and checked using:

```bash
python -m py_compile backend/scripts/persistence_smoke.py
```

Then the live smoke test worked.

Lesson:

A silent Python module can mean the module imported successfully but never reached an executable entry point.

---

## Module 3 Test Status

Final deterministic suite:

```text
47 passed
```

---

## Concepts Learned in Module 3

- PostgreSQL
- Docker
- Docker Compose
- host vs container ports
- named volumes
- environment configuration
- database URLs
- SQLAlchemy ORM
- declarative models
- sessions
- connection pooling
- Alembic migrations
- schema versioning
- primary keys
- composite keys
- unique constraints
- indexes
- transactions
- commit
- rollback
- atomicity
- repositories
- source snapshots
- baselines
- state machines
- SHA-256 hashing
- idempotency
- N+1 query avoidance
- deduplication
- synthetic integration testing
- upstream failure protection
- separation of persistence and notification policy

---

# Current Architecture Checkpoint

```text
Greenhouse API
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
Eligibility
```

Completed:

```text
Module 0 — Foundation
✅

Module 1 — Greenhouse Ingestion
✅

Module 2 — Role Classification + Eligibility
✅

Module 3 — PostgreSQL Persistence + Lifecycle
✅

Automated Tests
47 passing
✅

Live Databricks Persistence Validation
✅

Synthetic PostgreSQL Lifecycle Validation
✅
```

---

# Next Architecture Stage

ACE now knows what changed.

Next target flow:

```text
NEW / UPDATED / REOPENED
    ↓
Role Classification
    ↓
Eligibility
    ↓
Work-Authorization Intelligence
    ↓
Resume Relevance
    ↓
Ranking
    ↓
Notification Decision
```

---

# Documentation Convention

Every completed ACE module updates:

- `README.md`
- `docs/overview.md`
- `docs/learning-log.md`

---

# Module Development Workflow

```text
1. Explain architecture
2. Identify exact affected files
3. Provide complete file contents
4. Run deterministic tests
5. Run integration smoke tests when relevant
6. Inspect actual behavior
7. Update documentation
8. Commit and push
9. Move to the next module
```
