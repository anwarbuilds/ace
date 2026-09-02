# ACE Learning Log

This document records what was built, why it exists, bugs discovered during implementation, engineering decisions, trade-offs, validation results, and concepts learned while building ACE.

---

# Project Setup

## Python Environment

ACE uses Python 3.12 with `pyenv` and a project-local virtual environment.

```text
pyenv
    ↓
Python runtime
    ↓
project .venv
    ↓
project dependencies
```

Important lesson:

```text
system Python
!=
project Python
```

Development and testing commands should run through the project environment.

---

## Git and GitHub

Git provides local version history.

GitHub stores the remote repository.

Important concepts:

- repository
- working tree
- staging area
- commit
- commit hash
- branch
- remote
- origin
- push
- `.gitignore`

Important workflow lesson:

```text
inspect
→ stage intentionally
→ inspect staged diff
→ commit
→ push
```

Avoid blindly staging unrelated changes.

---

## Secrets

Real runtime secrets belong in:

```text
.env
```

Safe examples belong in:

```text
.env.example
```

`.env` must remain ignored by Git.

Never commit:

- SMTP passwords
- Gmail App Passwords
- API tokens
- production database credentials

Important lesson:

```text
configuration examples
!=
credentials
```

---

# Module 1 — Greenhouse Job Ingestion

## Problem

ACE needs first-party employer job data instead of relying only on third-party aggregators.

The first ATS integration is Greenhouse.

---

## Architecture

```text
Greenhouse API
    ↓
HTTP GET
    ↓
JSON payload
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

---

## What Was Built

Greenhouse-specific payloads are normalized into `CanonicalJob`.

The normalized model protects downstream code from provider-specific schemas.

Fields include:

- source
- company
- external ID
- requisition ID
- title
- location
- description
- official URL
- posting timestamp
- update timestamp

---

## Engineering Lessons

### Adapter Pattern

Downstream layers should depend on the application's canonical model rather than directly depending on Greenhouse.

Future design:

```text
Greenhouse ─┐
Lever ──────┼──→ CanonicalJob
Ashby ──────┘
```

### Explicit HTTP Timeouts

Network calls should never depend on unbounded default waits.

### Descriptive User-Agent

External services should receive an identifiable application User-Agent.

### HTML Normalization

Job descriptions often arrive as HTML.

Eligibility logic should operate on normalized text rather than raw markup.

### Live Smoke Testing

Unit tests are not enough for external integrations.

A real request confirms:

- endpoint behavior
- network behavior
- payload assumptions
- provider compatibility

---

# Module 2 — Role Classification and Eligibility

## Problem

ACE must distinguish relevant engineering opportunities from the much larger employer job corpus.

It also needs deterministic early-career eligibility rules.

---

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

---

## Role Families

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

---

## Eligibility Outcomes

```text
PASS
STRETCH
REJECT
```

`PASS` means no hard blocker was found.

`STRETCH` means the opportunity remains worth surfacing but contains uncertainty or a moderate mismatch.

`REJECT` means a deterministic blocker exists.

---

## Experience Policy

Current required-experience policy:

```text
0–2 years
→ PASS

3 years
→ STRETCH

4 years
→ REJECT

4 years + explicit early-career evidence
→ STRETCH

5+ years
→ REJECT
```

Preferred experience is not automatically interpreted as required experience.

---

## Bug — Excessive Experience False Stretch

A high-experience job incorrectly survived because unrelated degree-substitution language was interpreted as an early-career signal.

The classifier was effectively allowing a weak secondary phrase to override a strong experience requirement.

Fix:

```text
clearly excessive required experience
→ remains a hard rejection
```

Lesson:

```text
weak contextual evidence
should not override
strong explicit requirements
```

Regression tests were added.

---

## Bug — `PhD preferred` False Rejection

Loose proximity-based matching caused language such as:

```text
Bachelor's or Master's required.
PhD preferred.
```

to be interpreted as:

```text
PhD required
```

Fix:

Use explicit requirement grammar rather than loose keyword proximity.

Policy:

```text
PhD preferred
→ not automatically rejected

PhD targeted / explicitly required
→ reject
```

Lesson:

Regex-based eligibility rules require grammar-aware boundaries.

---

## Major Lesson

False negatives matter heavily in job discovery.

ACE should avoid hiding opportunities unless the available evidence is sufficiently deterministic.

---

# Module 2.1 — Recall Hardening

## Motivation

The initial eligibility implementation worked well for structured large-company postings but risked missing startup opportunities.

Startups frequently publish titles such as:

```text
Founding Engineer
Product Engineer
Software Engineer I
```

and often omit:

- sponsorship details
- exact experience requirements
- precise Remote-US wording

Rejecting missing information would produce excessive false negatives.

---

## Recall Rule

The hardened policy became:

```text
unknown
!=
negative evidence
```

Examples:

```text
sponsorship not mentioned
→ retain
```

```text
sponsorship explicitly unavailable
→ reject
```

---

## Generic Remote

A generic:

```text
Remote
```

location does not prove US eligibility.

But it also does not prove non-US eligibility.

Therefore:

```text
generic Remote
→ STRETCH / retained
```

An explicitly non-US location still rejects:

```text
Remote - Europe
→ REJECT
```

This protects discovery recall without pretending the geography is known.

---

## Startup-Oriented Title Coverage

Validated examples:

```text
Software Engineer I
→ SOFTWARE_ENGINEERING
```

```text
Founding Engineer
→ SOFTWARE_ENGINEERING
```

```text
Product Engineer
→ SOFTWARE_ENGINEERING
```

```text
Software Engineer - New Grad
→ SOFTWARE_ENGINEERING
```

---

## Sanity Check Results

Observed behavior:

```text
Software Engineer I
Location: Remote
Decision: STRETCH
Role: SOFTWARE_ENGINEERING
```

```text
Founding Engineer
Location: San Francisco, CA
Decision: PASS
Role: SOFTWARE_ENGINEERING
```

```text
Product Engineer
Location: Remote
Decision: STRETCH
Role: SOFTWARE_ENGINEERING
```

```text
Software Engineer - New Grad
Location: New York, NY
Decision: PASS
Role: SOFTWARE_ENGINEERING
```

```text
Software Engineer
explicit no sponsorship
→ REJECT
```

```text
Software Engineer
Remote - Europe
→ REJECT
```

---

## Lesson

Discovery systems should distinguish:

```text
known blocker
```

from:

```text
missing evidence
```

This is especially important when monitoring startups.

---

# Module 3 — PostgreSQL Persistence and Job Lifecycle

## Problem

Before Module 3, ACE forgot everything when the Python process exited.

ACE could not answer:

```text
Have I seen this job before?
Is it actually new?
Did the employer update it?
Did it disappear?
Did it reopen?
```

Real-time monitoring requires durable state.

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

---

## Port Conflict

A native PostgreSQL service already occupied:

```text
localhost:5432
```

ACE's Docker PostgreSQL therefore uses:

```text
localhost:5433
→ container:5432
```

Lesson:

```text
host port
!=
container port
```

---

## Docker Persistence

A named Docker volume preserves PostgreSQL state across normal container recreation.

```text
docker compose down
→ container removed
→ volume preserved
```

```text
docker compose down -v
→ volume removed
→ database data deleted
```

This distinction matters for development state.

---

## Environment Configuration

Runtime configuration moved into environment variables using `pydantic-settings`.

Benefits:

- no database credentials hardcoded in source
- reproducible local configuration
- clean production path later

---

## Domain Model vs Database Model

### `CanonicalJob`

Answers:

```text
What does a normalized job look like inside ACE?
```

### `JobRecord`

Answers:

```text
How is a job persisted in PostgreSQL?
```

Separating the two prevents persistence details from leaking into domain logic.

---

## Durable Job Identity

ACE uses:

```text
source
+
source_account
+
external_id
```

A PostgreSQL unique constraint enforces the identity.

Lesson:

```text
application deduplication
+
database uniqueness
=
defense in depth
```

---

## Snapshot Model

One complete employer response is treated as one source snapshot.

Example:

```text
Databricks Greenhouse
    ↓
hundreds of jobs
    ↓
one complete source snapshot
```

The new snapshot is reconciled against existing durable state.

---

## Baseline Protection

A first run may produce:

```text
855 current jobs
```

All are new to ACE's database.

They are not necessarily newly posted.

Therefore:

```text
NEW to database
!=
newly opened after ACE began monitoring
```

The first successful snapshot becomes baseline history.

Result:

```text
jobs persisted
evaluation candidates = 0
alerts = 0
```

---

## Lifecycle

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

### NEW

Source identity did not previously exist.

### UPDATED

Identity exists but meaningful normalized content changed.

### UNCHANGED

Identity and meaningful content are unchanged.

### CLOSED

Previously active identity is absent from a trustworthy complete snapshot.

### REOPENED

A previously closed job appears again.

---

## Content Hashing

ACE computes a SHA-256 fingerprint over meaningful job content.

Provider bookkeeping timestamps are intentionally excluded from the content hash.

Why?

A provider may change internal metadata timestamps without changing the actual posting.

Including those timestamps would create false:

```text
UPDATED
```

events.

---

## N+1 Query Avoidance

Naive approach:

```text
for every source job:
    SELECT existing job
```

ACE instead loads relevant existing records in bulk.

Lesson:

Database round trips become expensive as employer coverage grows.

---

## Transaction Ownership

Repository methods do not independently commit.

The caller owns the transaction.

```text
successful snapshot
→ COMMIT

exception
→ ROLLBACK
```

This avoids partially persisted source state.

---

## Empty Snapshot Protection

Dangerous scenario:

```text
API/parser failure
→ 0 jobs
```

Naive interpretation:

```text
every previous job
→ CLOSED
```

ACE rejects unexpectedly empty complete snapshots instead.

Lesson:

Systems must model upstream failure, not only valid input.

---

## Persistence vs Notification Separation

An early persistence design exposed:

```text
notification_candidates
```

This coupled storage and notification policy.

It was renamed/refined to:

```text
evaluation_candidates
```

Correct separation:

```text
Persistence
→ What changed?

Intelligence
→ Does it qualify?

Notification
→ How should it reach the user?
```

This architectural correction became important in Module 5.

---

## Real Validation

Module 3 validated:

- real PostgreSQL connectivity
- live Databricks persistence
- baseline behavior
- NEW
- UPDATED
- CLOSED
- REOPENED
- cleanup

At that point:

```text
47 automated tests
```

were passing.

---

# Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

## Problem

After Module 3:

```text
Persistence
→ knows what changed

Eligibility
→ knows what qualifies
```

but no application-level use case connected them.

ACE needed:

```text
NEW / UPDATED / REOPENED
+
eligibility
→ alert disposition
```

---

## Architecture

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

---

## Evaluation Types

### `AlertDisposition`

```text
ALERT
SUPPRESS
```

Eligibility and alert disposition remain separate concepts.

Eligibility asks:

```text
How does this job compare with deterministic candidate rules?
```

Alert disposition asks:

```text
Should this evaluated change continue toward notification?
```

---

## `EvaluatedJob`

Contains:

```text
CanonicalJob
+
JobObservationStatus
+
EligibilityDecision
+
AlertDisposition
```

This gives downstream systems both lifecycle and intelligence context.

---

## `EvaluationBatchResult`

Provides:

- evaluated jobs
- alert candidates
- suppressed jobs
- evaluated count
- alert count
- suppression count
- PASS count
- STRETCH count
- REJECT count

---

## Alert Policy

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

`STRETCH` stays alertable because ACE is recall-oriented.

Lesson:

```text
uncertainty
should not automatically become
hard exclusion
```

---

## Why UPDATED Jobs Are Re-Evaluated

An employer can change a previously rejected job.

Example:

```text
old:
5 years required
→ REJECT
```

Later:

```text
updated:
2 years required
→ PASS
```

Ignoring updates would miss the newly relevant opportunity.

---

## Why REOPENED Jobs Are Re-Evaluated

A closed job may later return.

```text
CLOSED
→ REOPENED
→ evaluate again
```

---

## Why UNCHANGED Jobs Are Skipped

Repeatedly evaluating unchanged jobs wastes computation.

```text
change detection
→ computational gate
```

This becomes increasingly important when ACE polls many employers frequently.

---

## Baseline Suppression

The Module 4 workflow preserved the baseline invariant:

```text
first snapshot
→ persist
→ no evaluation
→ no alerts
```

Important invariants should be tested through the complete pipeline that depends on them.

---

## Workflow Layer

A reusable workflow coordinates:

```text
process_snapshot(...)
    ↓
evaluate_snapshot(...)
```

without owning:

- ATS fetching
- notification transport
- resume ranking
- transaction creation

Possible callers:

- CLI
- scheduler
- API
- worker
- integration tests

Lesson:

A use-case layer prevents orchestration duplication.

---

## Transaction Boundary

The workflow deliberately does not call `commit()`.

The caller owns transaction scope.

Lesson:

```text
the layer that understands
the complete operation
should own the transaction
```

This later enabled source reconciliation and notification enqueueing to share one transaction.

---

## Real PostgreSQL Workflow Validation

Synthetic source account:

```text
ace-module4-smoke
```

### Pass 1

```text
Baseline:               True
Fetched:                2
NEW:                    2
Evaluation candidates:  0
Evaluated:              0
Alert candidates:       0
```

### Pass 2

```text
Fetched:                6
Unique:                 6
NEW:                    4
UPDATED:                1
UNCHANGED:              1
Evaluation candidates:  5
```

Evaluation:

```text
PASS:                   3
STRETCH:                1
REJECT:                 1
Alert candidates:       4
Suppressed:             1
```

Mappings included:

```text
UPDATED Software Engineer
→ PRIMARY
→ PASS
→ ALERT
```

```text
NEW Machine Learning Engineer
→ PRIMARY
→ STRETCH
→ ALERT
```

```text
NEW Forward Deployed Engineer
→ SECONDARY
→ PASS
→ ALERT
```

```text
NEW Senior Software Engineer
→ REJECT
→ SUPPRESS
```

---

## Posting-Time Presentation

Module 4 added user-facing timing information.

Example:

```text
Posted:     15 minutes ago
Posted at:  2026-08-29 14:00:00 UTC
Updated at: 2026-08-29 14:00:00 UTC
```

Important design:

```text
durable state
→ exact timestamp

presentation
→ relative age
```

Never persist:

```text
15 minutes ago
```

because the value becomes stale.

---

## Employer Time vs ACE Time

Different timestamps answer different questions.

```text
posted_at
→ when employer says job opened
```

```text
updated_at
→ when employer says posting changed
```

```text
detected_at
→ when ACE observed it
```

This later enables source-to-detection latency metrics.

---

## Module 4 Checkpoint

After Module 4:

```text
59 automated tests passing
```

---

# Module 5 — Durable Notification Pipeline

## Problem

After Module 4, ACE could produce:

```text
ALERT candidates
```

but the user still had to inspect terminal output manually.

The next requirement was real notification delivery.

A naive implementation would be:

```text
evaluate job
    ↓
send email
```

This is insufficient for a reliable system.

---

# Module 5A — Notification Rendering

## Goal

Convert an `EvaluatedJob` into a transport-neutral notification.

The renderer includes useful application details rather than sending a generic alert.

Content includes:

- lifecycle change
- title
- company
- location
- role family
- role priority
- eligibility
- posting age
- exact timestamps
- official employer application URL

---

## Relative Job Age

Notifications compute human-readable posting age dynamically.

Examples:

```text
8 minutes ago
2 hours ago
3 days ago
```

The underlying `posted_at` remains exact.

Lesson:

Presentation can be human-friendly without corrupting durable data.

---

## Official Application URL

Every alert should make the shortest possible path to applying visible.

ACE therefore includes the employer-provided official URL when available.

---

# Module 5B — SMTP Email Transport

## Goal

Deliver rendered notifications through real email.

Initial implementation used Gmail SMTP.

Configuration:

```text
smtp.gmail.com
port 587
STARTTLS
```

---

## Gmail Authentication Issue

The first real SMTP attempt failed with:

```text
Application-specific password required
```

A normal Google account password is not valid for this SMTP flow when modern Google security is enabled.

The solution was a Google App Password.

Lesson:

Authentication errors from real external integrations often represent security-policy requirements rather than code defects.

---

## Real Email Validation

A test notification was successfully delivered to Gmail.

This proved:

- environment configuration
- SMTP authentication
- STARTTLS
- sender configuration
- recipient configuration
- message construction
- real external delivery

---

# Module 5C — Durable Notification Outbox

## Reliability Problem

Direct SMTP delivery from the source-processing transaction creates a dangerous failure scenario.

Example:

```text
job marked NEW
    ↓
database commit
    ↓
SMTP fails
```

On the next poll:

```text
job is UNCHANGED
```

Without durable notification state, ACE may never attempt that alert again.

The job would be silently lost.

---

## Transactional Outbox Pattern

The solution is a durable notification outbox.

```text
source processing
+
evaluation
+
notification rendering
+
outbox insert
        ↓
single PostgreSQL transaction
        ↓
COMMIT
        ↓
external delivery worker
```

Now an external outage cannot erase notification intent.

---

## Database Migration

Alembic migration:

```text
0002_create_notification_outbox
```

added:

```text
notification_outbox
```

Current migration state:

```text
0002 (head)
```

---

## Outbox Fields

Important fields include:

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

---

## Outbox Status

```text
PENDING
SENT
DEAD
```

### PENDING

Delivery has not completed.

### SENT

External transport completed successfully.

### DEAD

Maximum delivery attempts were exhausted.

The record remains available for inspection rather than silently disappearing.

---

## Deduplication Design

Notification identity must represent the logical job event, not the time ACE happened to poll.

The dedupe key therefore includes:

```text
source
source_account
external job ID
observation status
meaningful job content hash
source update timestamp
recipient
```

ACE poll time is excluded.

This means:

```text
same job event at 12:00
same job event again at 12:05
→ same notification identity
```

Meaningful content changes produce a different identity.

---

## Bug — Insert Detection Through `rowcount`

The first real PostgreSQL outbox smoke test failed even though the schema was valid.

The repository used:

```python
result.rowcount == 1
```

to determine whether:

```text
INSERT ... ON CONFLICT DO NOTHING
```

created a row.

That behavior is not reliable enough across SQLAlchemy/DBAPI result semantics.

Fix:

```text
INSERT
...
ON CONFLICT DO NOTHING
RETURNING id
```

Then:

```text
returned ID
→ inserted

no returned ID
→ duplicate
```

Lesson:

When the database can explicitly return the result of a mutation, prefer that over driver-dependent row-count assumptions.

A real smoke test then confirmed:

```text
First insert:     True
Duplicate insert: False
Persistent rows:  1
Status:           PENDING
Attempts:         0
```

---

# Module 5C2 — Retry-Safe Delivery Worker

## Goal

Process due PENDING rows and update durable delivery state.

---

## Worker Claiming

The PostgreSQL worker uses:

```text
FOR UPDATE SKIP LOCKED
```

This allows future concurrent workers to process different notifications safely.

Concept:

```text
worker 1 locks row A

worker 2 skips A
and claims B
```

---

## One Notification per Transaction

Delivery draining uses one database transaction per processed message.

Benefits:

- isolated failure handling
- reduced lock duration
- smaller replay scope after worker failure
- easier state reasoning

---

## Retry Scheduling

A failed attempt increments:

```text
attempt_count
```

and stores:

```text
last_attempt_at
last_error
next_attempt_at
```

Initial exponential delays:

```text
attempt 1
→ 60 seconds

attempt 2
→ 120 seconds

attempt 3
→ 240 seconds
```

The delay is capped.

---

## Maximum Attempts

When maximum attempts are reached:

```text
status
→ DEAD
```

This prevents infinite hot-loop retries while preserving operational visibility.

---

# At-Least-Once Delivery Semantics

Perfect exactly-once email delivery cannot be guaranteed.

Possible failure window:

```text
SMTP provider accepts email
    ↓
application process crashes
    ↓
PostgreSQL never records SENT
```

When the worker restarts, it may retry the still-PENDING row.

Therefore a rare duplicate email is theoretically possible.

ACE deliberately chooses:

```text
at-least-once delivery
```

because:

```text
rare duplicate
<
lost important job alert
```

Lesson:

Distributed systems often require selecting the failure mode the product can tolerate better.

---

# Real Durable Delivery Smoke Test

A notification was:

```text
inserted into PostgreSQL
→ PENDING
```

Then the real delivery worker used Gmail.

Observed:

```text
Queued:          True
Attempted:       1
Sent:            1
Retry scheduled: 0
Database status: SENT
Attempt count:   1
```

The message arrived in Gmail.

Synthetic state was cleaned up afterward.

---

# Real Failure-Recovery Validation

The final Module 5 validation intentionally forced SMTP failure.

A test notification began:

```text
status = PENDING
attempt_count = 0
```

The worker was temporarily executed with an invalid local SMTP endpoint.

Observed:

```text
Attempted:       1
Sent:            0
Retry scheduled: 1
Dead:            0
```

PostgreSQL then contained:

```text
status = PENDING
attempt_count = 1
sent_at = NULL
last_error = ConnectionRefusedError
next_attempt_at = future time
```

This proved the notification was not lost.

The retry timestamp was then moved forward for testing.

The normal Gmail worker ran again.

Observed:

```text
Attempted:       1
Sent:            1
Retry scheduled: 0
Dead:            0
```

Final PostgreSQL state:

```text
status = SENT
attempt_count = 2
sent_at populated
last_error cleared
```

The synthetic row was deleted afterward.

This is the most important Module 5 reliability proof.

---

# Live Greenhouse Pipeline

The live Greenhouse runner now performs:

```text
fetch live employer jobs
    ↓
persist/reconcile snapshot
    ↓
evaluate changed jobs
    ↓
create durable outbox rows
    ↓
commit
    ↓
deliver due notifications
```

One live Databricks checkpoint returned:

```text
Fetched:               859
NEW:                     0
UPDATED:                 0
REOPENED:                0
UNCHANGED:             859
Evaluation candidates:   0
```

Therefore:

```text
Alert candidates: 0
Queued:           0
Sent:             0
```

This is correct behavior.

ACE does not re-email unchanged jobs.

---

# Important Operational Distinction

The pipeline is live, but automatic repeated polling is not yet implemented.

Current:

```text
run command
    ↓
live source check
    ↓
possible notification
```

Future:

```text
scheduler
    ↓
automatic repeated runs
    ↓
possible notification
```

This distinction prevents overclaiming "real-time" behavior before the scheduling layer exists.

---

# Module 5 Automated Testing

Module 5 added tests for:

- notification rendering
- exact and relative timestamps
- email transport
- Greenhouse runner behavior
- outbox model
- dedupe keys
- duplicate enqueue behavior
- retry scheduling
- successful SENT transition
- failed PENDING transition
- DEAD transition
- no-due-message behavior

Final regression checkpoint:

```text
101 tests passing
```

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
Role Classification
    ↓
Eligibility
    ↓
ALERT / SUPPRESS
    ↓
Notification Renderer
    ↓
PostgreSQL Outbox
    ↓
PENDING
    ↓
Delivery Worker
    ↓
SMTP
    ↓
SENT / retry / DEAD
```

Completed:

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

Module 5 — Durable Notifications
✅

Automated Tests
101 passing
✅

PostgreSQL
✅

Greenhouse
✅

Gmail SMTP
✅

Failure Recovery
✅
```

---

# Next Architecture Stage

ACE now has a reliable single-run source-to-notification pipeline.

The next infrastructure problem is automatic repeated execution.

Target:

```text
Scheduler
    ↓
Source Registry
    ↓
Employer Polling
    ↓
Existing ACE Pipeline
    ↓
Durable Notifications
```

Important future considerations:

- poll frequency
- rate limits
- employer/source isolation
- transient source failures
- concurrent source execution
- scheduler crash recovery
- per-source monitoring
- source coverage configuration

Then expand source coverage:

```text
Greenhouse
Lever
Ashby
other ATS providers
```

Later intelligence:

```text
work-authorization intelligence
resume ingestion
resume relevance
freshness-aware ranking
startup prioritization
notification preferences
web UI
```

---

# Engineering Lessons So Far

## Keep Provider Logic Behind Adapters

Provider-specific schemas should not infect the rest of the application.

## Persist Before Filtering

Historical source truth should survive changes in eligibility policy.

## Separate Lifecycle From Eligibility

```text
NEW
```

does not mean:

```text
qualified
```

## Separate Eligibility From Notification

```text
PASS
```

does not mean:

```text
email successfully delivered
```

## Missing Information Is Not a Rejection

Especially for startup discovery.

## Use Database Constraints

Application logic alone is insufficient for deduplication.

## Make Important Operations Atomic

Source mutation and notification intent should commit together.

## Treat External Transports as Unreliable

SMTP, APIs, and networks fail.

Reliability must be designed around those failures.

## Prefer Durable Intent Before Side Effects

Persist:

```text
I need to send this
```

before attempting:

```text
send it
```

## Test Failure Paths Deliberately

The successful SMTP test proved the happy path.

The intentionally broken SMTP test proved the architecture.

Both are necessary.

## Exactly-Once Is Often Not Available

Choose product-appropriate delivery semantics explicitly.

## Real Bugs Become Regression Tests

A bug that was difficult once should become cheap to catch forever.

---

# Documentation Convention

Every completed ACE module updates:

- `README.md`
- `docs/overview.md`
- `docs/learning-log.md`

---

# Development Workflow Convention

For code changes:

```text
new file
→ complete contents

modified file
→ complete replacement contents
```

For each module:

```text
1. Explain architecture
2. Identify affected files
3. Provide complete file contents
4. Run targeted tests
5. Run full regression suite
6. Run real integration tests when relevant
7. Inspect behavior
8. Update documentation
9. Inspect staged changes
10. Commit
11. Push
12. Move to next module
```

This workflow is designed to retain hackathon speed without sacrificing traceability or engineering quality.