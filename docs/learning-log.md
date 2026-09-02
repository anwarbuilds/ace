# ACE Learning Log

This document records what was built, why it exists, bugs discovered during implementation, engineering decisions, trade-offs, and the concepts learned while building ACE.

---

# Project Setup

## Python Environment

ACE uses Python 3.12.12 selected with `pyenv` and a project-local `.venv`.

Key relationship:

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

Fix:

Clearly excessive required experience remains a hard rejection.

### `PhD preferred` False Rejection

Loose regex proximity caused `PhD preferred` to be treated as `PhD required`.

Fix:

Explicit requirement grammar is used instead.

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

Lesson:

```text
host port != container port
```

## Docker Compose and Persistent Volumes

PostgreSQL runs through Docker Compose.

A named volume preserves database state across container recreation.

Important distinction:

```text
docker compose down
→ stop/remove containers
→ preserve volume

docker compose down -v
→ also delete volume
→ database data removed
```

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

Lesson:

```text
source code
!=
runtime secrets/configuration
```

## Pydantic vs SQLAlchemy

ACE has separate model categories.

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

## Durable Job Identity

ACE uses:

```text
source
+
source_account
+
external_id
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

That snapshot is compared against durable database state.

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

## Persistence Lifecycle

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

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

## Content Hashing

ACE computes a deterministic SHA-256 fingerprint over meaningful normalized content.

Provider bookkeeping update timestamps are excluded.

Lesson:

A provider may change internal timestamps without changing the job posting. Including those timestamps would create false update events.

## N+1 Query Avoidance

Naive design:

```text
for each job:
    SELECT job
```

ACE instead batch-loads existing source identities and compares them in memory.

Lesson:

Database round trips matter at scale.

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

## Empty Snapshot Protection

Dangerous scenario:

```text
provider/API failure
    ↓
0 parsed jobs
```

If treated as authoritative:

```text
all active jobs
→ CLOSED
```

ACE instead rejects an empty complete snapshot.

Lesson:

Systems must be designed for upstream failure, not only valid data.

## Persistence vs Notification Separation

An architecture refinement was made during Module 3.

Persistence originally exposed:

```text
notification_candidates
```

That was too coupled.

It became:

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
→ Should/how should the user be alerted?
```

## Real and Synthetic Validation

Module 3 proved:

- live Databricks idempotent persistence
- baseline behavior
- NEW
- UPDATED
- CLOSED
- REOPENED
- cleanup
- 47 automated tests

---

# Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

## Problem

After Module 3, ACE could independently answer:

```text
What changed?
```

and:

```text
Is this job eligible?
```

but there was no application-level pipeline connecting those answers.

Example:

```text
Persistence:
This job is NEW.

Eligibility:
This job is PRIMARY + PASS.
```

ACE still needed a use case that combined them into:

```text
NEW
+
PRIMARY
+
PASS
→ ALERT candidate
```

## Architecture

Module 4 introduces:

```text
Persistence
    ↓
Evaluation Candidates
    ↓
Evaluation Service
    ↓
Role Classification
    ↓
Eligibility
    ↓
Alert Disposition
```

and then wraps persistence + evaluation in an application workflow:

```text
run_source_snapshot_workflow(...)
```

## Evaluation Domain Types

### `AlertDisposition`

Values:

```text
ALERT
SUPPRESS
```

Important lesson:

Eligibility and alert disposition are not the same concept.

Eligibility asks:

```text
How does the job compare with deterministic candidate rules?
```

Alert disposition asks:

```text
Should this evaluated change continue toward the notification layer?
```

Keeping them separate prevents notification policy from becoming embedded inside eligibility logic.

### `EvaluatedJob`

An evaluated job contains:

```text
CanonicalJob
+
JobObservationStatus
+
EligibilityDecision
+
AlertDisposition
```

This creates one downstream object carrying both:

- source change context
- intelligence context

### `EvaluationBatchResult`

Provides:

```text
evaluated_jobs
alert_candidates
suppressed_jobs

evaluated_count
alert_candidate_count
suppressed_count

pass_count
stretch_count
reject_count
```

This is useful both for product behavior and observability.

## Current Alert Policy

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

Why keep `STRETCH` alertable?

Because ACE is intentionally recall-oriented.

A job requiring 3 years, for example, may still be worth applying to and should be clearly labeled rather than hidden.

Lesson:

```text
ranking uncertainty
should not automatically become
hard exclusion
```

## Why UPDATED and REOPENED Are Re-Evaluated

Normal evaluation includes:

```text
NEW
UPDATED
REOPENED
```

A changed posting may become newly relevant.

Example:

```text
old posting:
5 years required
→ REJECT

employer updates posting:
2 years required
→ PASS
```

If ACE ignored `UPDATED`, it could miss this opportunity.

Similarly:

```text
CLOSED
→ later REOPENED
```

should become eligible for reevaluation.

## Why UNCHANGED Jobs Are Not Re-Evaluated

If a job is unchanged:

```text
same identity
+
same meaningful content
```

there is no need to repeatedly run deterministic intelligence on every poll.

This becomes important when ACE monitors many employers frequently.

Lesson:

```text
change detection
can be used as a computational gate
```

## Baseline Evaluation Suppression

Module 4 preserves Module 3 baseline behavior.

```text
first snapshot
    ↓
jobs persisted
    ↓
evaluation candidates = 0
    ↓
evaluated jobs = 0
    ↓
alert candidates = 0
```

This was verified at the workflow level, not only inside persistence.

Lesson:

Important invariants should be tested through the complete pipeline that depends on them.

## Application Workflow Layer

A thin workflow package was added.

Purpose:

```text
orchestrate domain/application services
without duplicating orchestration everywhere
```

Without it, future callers might each repeat:

```python
snapshot = process_snapshot(...)
evaluation = evaluate_snapshot(snapshot)
```

Possible callers include:

- scheduler
- API
- email worker
- CLI
- background task
- integration tests

Instead they can call one use case:

```text
run_source_snapshot_workflow(...)
```

Lesson:

A workflow/use-case layer can prevent orchestration duplication while keeping individual domain services focused.

## Transaction Ownership

The workflow does not commit or open its own database transaction.

The caller owns the transaction.

This keeps the transaction boundary explicit and preserves the Module 3 design.

Lesson:

The layer that understands the complete operation should own transaction scope.

## Module 4 Unit Tests

Module 4A added evaluation tests covering:

- PRIMARY + PASS → ALERT
- PRIMARY + STRETCH → ALERT
- SECONDARY + PASS → ALERT
- REJECT → SUPPRESS
- UPDATED evaluation
- REOPENED evaluation
- baseline suppression
- mixed PASS/STRETCH/REJECT counts

Module 4B added workflow tests covering:

- baseline persists but is not evaluated
- NEW Software Engineer becomes alert candidate
- NEW Senior Software Engineer is suppressed
- NEW/UPDATED/REOPENED observation statuses survive orchestration
- UNCHANGED jobs do not enter evaluation

After Module 4B:

```text
59 automated tests passing
```

## Real PostgreSQL End-to-End Workflow Test

Module 4C uses real PostgreSQL with synthetic source account:

```text
ace-module4-smoke
```

This avoids changing real Databricks state.

### Pass 1 — Baseline

Input:

```text
A Software Engineer
B Software Engineer
```

Observed:

```text
Baseline:               True
Fetched:                2
Unique:                 2
NEW:                    2
Evaluation candidates:  0

Evaluated:              0
PASS:                   0
STRETCH:                0
REJECT:                 0
Alert candidates:       0
Suppressed:             0
```

This proves first-run suppression end to end.

### Pass 2 — Changed Source

Input:

```text
A unchanged Software Engineer

B updated Software Engineer

C new Software Engineer

D new Senior Software Engineer

E new Machine Learning Engineer
  requires 3 years

F new Forward Deployed Engineer
```

Persistence observed:

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

Evaluation observed:

```text
Evaluated:              5
PASS:                   3
STRETCH:                1
REJECT:                 1
Alert candidates:       4
Suppressed:             1
```

The smoke test asserted each important role/state mapping.

## Alert-Candidate Details

The smoke test prints details suitable for a future notification layer:

```text
Change
Company
Title
Location
Role family
Priority
Eligibility
Posted relative age
Posted exact timestamp
Updated exact timestamp
Official URL
```

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

## Exact Timestamp vs Relative Age

Important design decision:

Do not store:

```text
15 minutes ago
```

because it becomes stale immediately.

Store:

```text
2026-08-29T14:00:00+00:00
```

and compute relative age when rendering.

Lesson:

```text
durable state
should remain absolute

presentation state
can be relative
```

## Timezone Strategy

The Module 4 smoke test renders exact timestamps in UTC for deterministic validation.

Production behavior should eventually be:

```text
store UTC
    ↓
convert at presentation boundary
    ↓
user local timezone
```

This avoids timezone ambiguity in storage while still giving the user natural timestamps.

## Employer Posted Time vs ACE Detection Time

The source already gives ACE employer timestamps:

```text
posted_at
updated_at
```

A future polling layer should also capture:

```text
ACE detected_at
```

These answer different questions:

```text
posted_at
→ When the employer says the job opened

updated_at
→ When the employer says it changed

detected_at
→ When ACE observed the opening/change
```

This will let ACE measure source-to-detection latency.

Example:

```text
Employer posted:
9:14 AM

ACE detected:
9:22 AM

Detection latency:
8 minutes
```

This is not implemented yet.

## Freshness as a Future Ranking Signal

Freshness should later influence ordering, not eligibility.

Possible UX classes:

```text
JUST OPENED
VERY FRESH
FRESH
TODAY
RECENT
```

A future ranking system may combine:

```text
Role priority
+
Eligibility
+
Resume relevance
+
Posting freshness
```

Example trade-off:

```text
HIGH resume relevance
posted 3 days ago

vs

MEDIUM resume relevance
posted 9 minutes ago
```

ACE should be able to prioritize intelligently rather than sorting only by similarity.

The exact ranking policy is not implemented yet.

## Cleanup Discipline

The Module 4 PostgreSQL smoke test deletes its synthetic `jobs` and `source_states` records in a `finally` block.

This means cleanup is attempted even if an assertion fails.

Lesson:

Integration tests should avoid polluting long-lived development state.

## Development Workflow Rule

During Module 4, a workflow preference was reinforced:

```text
new file
→ complete contents

modified file
→ complete replacement contents
```

This reduces copy/paste ambiguity and makes each implementation step reproducible.

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
Evaluation Candidates
    ↓
Source-Snapshot Workflow
    ↓
Role Classification
    ↓
Eligibility
    ↓
ALERT / SUPPRESS
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

Module 4 — Evaluation Pipeline + Workflow
✅

Automated Tests
59 passing
✅

Real PostgreSQL Persistence Validation
✅

Real PostgreSQL Evaluation Workflow Validation
✅
```

---

# Next Architecture Stage

ACE can now produce clean alert candidates.

Next target:

```text
Alert Candidate
    ↓
Notification Renderer
    ↓
Email Delivery
```

Then:

```text
Scheduler / polling
    ↓
repeated employer source checks
    ↓
fast NEW-job detection
    ↓
automatic notification
```

Later stages:

```text
Work-authorization intelligence
Resume ingestion
HIGH / MEDIUM / MINIMAL relevance
Freshness-aware ranking
Additional ATS adapters
Web application
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
