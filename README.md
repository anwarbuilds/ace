# ACE

ACE is a personal real-time career-intelligence platform for discovering, normalizing, persisting, evaluating, and notifying on relevant engineering opportunities.

The project is being built from scratch as an end-to-end backend, data, systems, reliability, and full-stack engineering project.

ACE currently has a working pipeline from a live Greenhouse job board through PostgreSQL lifecycle tracking, deterministic eligibility evaluation, durable notification queuing, and real Gmail delivery.

Continuous scheduling is not implemented yet, so source checks still need to be triggered manually or by a future scheduler.

---

# Product Goal

ACE reduces the manual job-search workflow:

```text
Search company career pages
    ↓
Open many irrelevant postings
    ↓
Check role
    ↓
Check location
    ↓
Check seniority
    ↓
Check experience
    ↓
Check work-authorization language
    ↓
Find official application link
    ↓
Apply
```

into:

```text
ACE polls employer ATS
    ↓
ACE normalizes jobs
    ↓
ACE persists complete source snapshots
    ↓
ACE detects NEW / UPDATED / REOPENED / CLOSED jobs
    ↓
ACE evaluates only meaningful changes
    ↓
ACE identifies target roles
    ↓
ACE evaluates deterministic eligibility
    ↓
PASS / STRETCH become alert candidates
    ↓
ACE renders notification details
    ↓
ACE durably stores the notification in PostgreSQL
    ↓
ACE delivers through email
    ↓
User opens the official employer application link
```

The objective is to spend less time repeatedly searching and sorting job boards and more time applying quickly to relevant opportunities.

---

# Target Opportunity Profile

## Geography

ACE targets:

- United States
- Remote-US opportunities

A generic `Remote` posting without explicit geography is retained conservatively rather than automatically rejected.

Explicitly non-US opportunities remain excluded.

---

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
- Product Engineer
- Founding Engineer when clearly engineering-focused
- Software Engineer I
- New Grad Software Engineer

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

---

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

# Eligibility Philosophy

ACE uses a recall-oriented filtering strategy.

The system should aggressively reject deterministic blockers while avoiding rejection when important information is simply missing.

Core rule:

```text
unknown
!=
negative
```

Examples:

```text
no sponsorship statement
→ do not reject

explicitly no sponsorship
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
→ do not reject solely for that reason

PhD-targeted / PhD-required role
→ reject
```

---

# Current Hard Exclusions

ACE currently rejects opportunities that are clearly:

- outside US / Remote-US scope
- outside configured target role families
- senior, staff, principal, lead, manager, director, or equivalent level
- explicitly targeted toward PhD candidates
- explicitly requiring a PhD or doctoral degree
- beyond the configured early-career experience range
- restricted by explicit US-citizenship or US-person requirements
- restricted by explicit security-clearance requirements
- explicitly unavailable for current or future sponsorship

A PhD that is merely preferred is not itself a rejection reason.

Missing sponsorship information is treated as unknown rather than negative evidence.

---

# Experience Policy

Current deterministic experience policy:

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

---

# Core Architectural Invariants

## Canonical Data Before Intelligence

Provider-specific ATS payloads become `CanonicalJob` before persistence or eligibility logic.

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Future ATS adapters should emit the same canonical representation.

---

## Persistence Before Eligibility

ACE stores the complete normalized employer snapshot before eligibility filtering.

```text
ATS
    ↓
CanonicalJob
    ↓
Persistence
    ↓
Evaluation
```

This lets ACE remember jobs independently from current policy.

A rejected job may later:

- change
- reopen
- become relevant
- be re-evaluated under updated rules

---

## Persistence Answers What Changed

Persistence emits:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

Persistence does not decide notification eligibility.

---

## Evaluation Answers Whether a Change Continues

Normal evaluation receives:

```text
NEW
UPDATED
REOPENED
```

and currently maps:

```text
PASS
→ ALERT

STRETCH
→ ALERT

REJECT
→ SUPPRESS
```

`UNCHANGED` jobs are not repeatedly re-evaluated.

`CLOSED` jobs do not enter normal application-alert evaluation.

---

## Baselines Must Not Spam Alerts

The first complete source snapshot establishes historical state.

Baseline is **lifecycle metadata, not an evaluation filter**. ACE
deliberately does *not* suppress evaluation on a source's first
snapshot:

```text
first successful poll
    ↓
persist all current jobs
    ↓
baseline = true
    ↓
NEW jobs ARE evaluated
    ↓
freshness policy decides which may alert
```

Blanket baseline suppression was removed on purpose. If ACE discovers a
company today and that company posted an excellent role yesterday, ACE
must still alert.

The cost of that decision is that a first snapshot also reports every
long-open posting as `NEW` — because `NEW` means *new to ACE*, not
*recently opened*.

Freshness resolves this without reintroducing suppression:

| Observation | Baseline | Rule |
| --- | --- | --- |
| `NEW` | yes | must also be posted within `MAX_ALERT_POSTING_AGE_DAYS` |
| `NEW` | no | always alertable — it appeared after an established snapshot |
| `REOPENED` | any | always alertable — reopening is current evidence |
| `UPDATED` | any | must be posted within the freshness window |

A posting with **no stated date** on a baseline snapshot does not alert,
unless `ALERT_ON_UNKNOWN_POSTING_AGE=true`. This is safe rather than
lossy: a source is baseline exactly once, so every genuinely new posting
from that source afterwards alerts unconditionally.

A job held back by freshness is **still persisted, still active, and
still searchable**. Freshness controls notification volume, never
inclusion.

---

## Empty Snapshots Are Not Trusted

An unexpectedly empty ATS response could represent an upstream failure.

ACE does not interpret it as:

```text
all jobs closed
```

without trustworthy source evidence.

---

## Exact Time Is Durable

ACE stores exact timestamps such as:

- employer `posted_at`
- employer `updated_at`
- ACE observation timestamps
- outbox creation time
- delivery attempt time
- successful delivery time

Relative values such as:

```text
15 minutes ago
3 hours ago
2 days ago
```

are computed when rendering.

---

# Durable Notification Invariant

ACE never relies on sending an email directly from volatile application memory.

The current design is:

```text
source reconciliation
        +
eligibility evaluation
        +
notification rendering
        +
PENDING outbox insert
        ↓
ONE DATABASE TRANSACTION
        ↓
COMMIT
        ↓
external delivery begins
```

This means an SMTP failure does not destroy the alert.

---

# Notification Outbox

PostgreSQL table:

```text
notification_outbox
```

Important states:

```text
PENDING
SENT
DEAD
```

A qualifying alert is first persisted as:

```text
PENDING
```

Only after the external SMTP transport succeeds does ACE store:

```text
SENT
```

Failures remain retryable.

---

# Notification Deduplication

Each logical notification has a deterministic SHA-256 deduplication identity.

The identity includes meaningful event information such as:

```text
source
+
source account
+
external job identity
+
lifecycle event
+
job content version
+
provider update version
+
recipient
```

ACE poll time is deliberately excluded.

Therefore:

```text
same event detected again later
→ same dedupe key
→ no duplicate outbox row
```

Meaningful job changes can generate new notification events.

---

# Retry Policy

Delivery failures use exponential backoff.

Default behavior begins approximately:

```text
attempt 1 failure
→ retry after 60 seconds

attempt 2 failure
→ retry after 120 seconds

attempt 3 failure
→ retry after 240 seconds
```

The delay is capped.

After the maximum configured attempts, the row becomes:

```text
DEAD
```

for operational inspection rather than disappearing silently.

---

# Delivery Semantics

SMTP cannot guarantee mathematically perfect exactly-once delivery.

There is an unavoidable distributed-systems edge case:

```text
Gmail accepts message
    ↓
process crashes before PostgreSQL records SENT
    ↓
worker may retry
```

ACE therefore deliberately prefers:

```text
at-least-once delivery
```

over risking permanent alert loss.

For a job-alert system, a rare duplicate is safer than silently missing an important opening.

The same guarantee applies to digests. A digest is rendered and sent
inside the transaction that records its result, so a crash between
"Gmail accepted" and "PostgreSQL committed" can resend one digest. It
can never lose one.

---

# Digest Delivery

ACE is a digest, not a firehose.

```text
job 1 ┐
job 2 ├── one delivery window ──> ONE EMAIL
job 3 ┘
```

```text
zero qualifying jobs  ->  zero emails
many qualifying jobs  ->  one email
```

## Windows

Delivery windows are local wall-clock times in
`NOTIFICATION_DIGEST_TIMEZONE`. One or two windows per day are allowed;
more is a configuration error.

A window opens at its configured time and stays open until the next
window, or until local midnight for the last window of the day. Nothing
is deliverable between midnight and the first window, which is what
bounds ACE to at most one or two emails per local calendar day.

A window fires **once**, and only when it has something to report. An
empty window is released rather than consumed, so a strong afternoon
posting can still be delivered inside the morning window if the morning
had nothing.

## Durability

Two database facts cooperate:

| Fact | Guarantees |
| --- | --- |
| `notification_digests.digest_key` UNIQUE | one delivery per window per recipient |
| `notification_outbox.digest_id` | one candidate is delivered in exactly one digest |

Because window identity lives in a UNIQUE constraint rather than in
process memory, a worker restart cannot resend a window that has already
been delivered. Restarting the container three times does not produce
three digests.

## Candidate freezing

Candidates are assigned to a digest once, on its first delivery attempt.
Retries resend that same frozen set rather than absorbing rows that
arrived meanwhile.

This keeps an SMTP outage from producing an ever-growing digest, and
keeps *the digest that was sent* equal to *the candidates that were
marked delivered*. Rows arriving after assignment go to the next window.

## Failure handling

```text
send fails      -> digest stays PENDING, exponential backoff, rows stay PENDING
attempts spent  -> digest DEAD, its rows DEAD (visible, never deleted)
another worker  -> SKIP LOCKED, no double send
```

DEAD candidates can be returned to the queue once the transport is
healthy:

```bash
python -m backend.scripts.manage_pending_notifications --requeue-dead --apply
```

## Ordering

Digest entries are ordered most-actionable first, deterministically:

1. role priority — primary families before secondary
2. eligibility — `PASS` before `STRETCH`
3. posting age — freshest first, unknown age last
4. company and title — stable alphabetical tie-break

A retry therefore renders an identical email to the first attempt.

## Size

`NOTIFICATION_DIGEST_MAX_JOBS` caps one digest. The remainder is
reported in the digest itself and delivered in the next window, rather
than producing an email long enough for Gmail to clip.

---

# Role Scope Rules

Two exclusions reflect explicit user preference rather than a hard
blocker in the posting.

## Hardware-oriented embedded roles

Roles whose work is fundamentally about hardware are out of scope:
firmware, boards, silicon, and bare-metal targets.

```text
hardware title      -> reject   (decisive)
3+ hardware markers -> reject   (description-only path)
1-2 mentions        -> keep     (a passing mention is not the job)
```

Title signals are decisive because a hardware title reliably states what
the job is. The description-only path deliberately requires several
distinct signals, so an ML or platform role that merely mentions
embedded targets stays in scope.

Markers are matched on word boundaries, including simple plurals. Naive
substring matching would read "uart" inside "Stuart".

## C / C++ only roles

```text
C or C++ stated, nothing else   -> reject
C or C++ plus any other language -> keep
no language stated               -> keep (silence is not rejection)
```

A posting requiring "C++ and Python" is in scope. A posting requiring
only C++ is not. The rule reads the stated requirement, not the job
title: a role titled "Software Engineer, C++" that asks for C++ *and*
Python remains in scope.

Detection of "other" languages is deliberately generous, because a false
positive there keeps a job, which matches ACE's recall-first stance.
Short ambiguous tokens (`Go`, `R`) are matched case-sensitively so
ordinary prose does not register as a language.

## Ambiguous country codes

`CA` is California in a US address and Canada in an international one.
Explicit non-US country signals are therefore checked *before* the
US-state match, so "Ottawa, ON, CA" is correctly excluded while
"Ontario, California" is not.

---

# Web Application

A read-only surface over the same PostgreSQL database the scheduler
writes.

```text
scheduler  -> writes jobs, lifecycle, evaluations
web app    -> reads them
```

It never fetches from an ATS, never evaluates eligibility inline, and
never sends email, so it cannot become a second, divergent source of
truth.

## Why evaluations are materialized

Eligibility is a pure function of a job's normalized content, so the
decision is cached in `job_evaluations` rather than recomputed per
request. That lets the web app filter and sort in SQL instead of loading
the whole corpus into Python.

The table stores `content_hash` and `rule_version`, so a stale decision
is *detectable* rather than silently wrong:

```bash
# report what needs rebuilding
python -m backend.scripts.backfill_job_evaluations

# rebuild it
python -m backend.scripts.backfill_job_evaluations --apply

# force a full rebuild
python -m backend.scripts.backfill_job_evaluations --apply --all
```

The table is derived data. Dropping it costs nothing but a rebuild,
which is why eligibility deliberately does not live on `JobRecord`.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /` | Single-page UI |
| `GET /api/jobs` | Filtered, sorted, paginated listing |
| `GET /api/stats` | Headline counts |
| `GET /api/facets` | Available filter options |
| `GET /healthz` | Service and database health |
| `GET /docs` | Generated OpenAPI documentation |

`/api/jobs` accepts `status`, `family`, `priority`, `company`, `source`,
`q`, `max_age_days`, `active_only`, `sort`, `limit`, `offset`.

Page size is capped server-side so a hostile `limit` cannot request the
whole corpus.

## Running it

```bash
docker compose up -d web
# then open http://localhost:8000
```

The UI has no build step and no `node_modules`: it is one static HTML
file with vanilla JavaScript, served by FastAPI.

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
    ↓
Notification Renderer
    ↓
PostgreSQL Notification Outbox
    ↓
PENDING
    ↓
Delivery Worker
    ↓
SMTP / Gmail
    ↓
SENT / retry / DEAD
```

Continuous automatic polling is the next infrastructure stage.

---

# Implemented Modules

## Module 0 — Project Foundation

Implemented:

- Python 3.12 environment
- `pyenv`
- project-local `.venv`
- Git
- GitHub
- dependency isolation
- `.gitignore`
- project documentation structure

Status:

```text
COMPLETE
```

---

## Module 1 — Greenhouse Job Ingestion

Implemented:

- public Greenhouse Job Board API integration
- explicit HTTP timeout
- descriptive User-Agent
- complete job-description retrieval
- HTML-to-text normalization
- canonical job normalization
- live API smoke testing

`CanonicalJob` includes:

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

Status:

```text
COMPLETE
```

---

## Module 2 — Role Classification and Eligibility

Implemented deterministic role and eligibility intelligence.

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
- citizenship
- clearance
- explicit sponsorship blockers

Status:

```text
COMPLETE
```

---

## Module 2.1 — Recall Hardening

Module 2.1 hardened discovery behavior for startup and ambiguous postings.

Validated behavior includes:

```text
Software Engineer I + generic Remote
→ STRETCH
→ retained
```

```text
Founding Engineer + US location
→ PASS
```

```text
Product Engineer + generic Remote
→ STRETCH
→ retained
```

```text
Software Engineer - New Grad + US location
→ PASS
```

```text
explicit sponsorship unavailable
→ REJECT
```

```text
Remote Europe
→ REJECT
```

The important policy is:

```text
absence of evidence
!=
evidence of ineligibility
```

Status:

```text
COMPLETE
```

---

## Module 3 — PostgreSQL Persistence and Job Lifecycle

Implemented:

- PostgreSQL 16
- Docker Compose
- persistent Docker volume
- host port `5433`
- psycopg 3
- SQLAlchemy 2.x
- Alembic
- environment-based configuration
- durable source identity
- SHA-256 content hashing
- baseline protection
- snapshot deduplication
- N+1 query avoidance
- atomic source transactions
- empty-snapshot protection
- lifecycle detection

Lifecycle:

```text
NEW
UPDATED
REOPENED
UNCHANGED
CLOSED
```

Durable identity:

```text
source
+
source_account
+
external_id
```

Status:

```text
COMPLETE
```

---

## Module 4 — Evaluation Pipeline and Source-Snapshot Workflow

Module 4 connects lifecycle changes to deterministic intelligence.

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

Evaluation types:

- `AlertDisposition`
- `EvaluatedJob`
- `EvaluationBatchResult`

Normal evaluation processes:

```text
NEW
UPDATED
REOPENED
```

and ignores unchanged jobs.

The application workflow keeps transaction ownership with its caller.

Status:

```text
COMPLETE
```

---

## Module 5 — Durable Notification Pipeline

Module 5 turns alert candidates into real, failure-resistant email notifications.

Implemented:

- notification domain types
- deterministic notification renderer
- employer posting timestamps
- relative posting age
- official application links
- SMTP transport
- Gmail STARTTLS support
- Gmail App Password authentication
- runtime transport configuration
- PostgreSQL notification outbox
- migration `0002`
- deterministic notification deduplication
- PENDING / SENT / DEAD lifecycle
- retry scheduling
- exponential retry backoff
- multiple-worker-safe PostgreSQL claiming with `FOR UPDATE SKIP LOCKED`
- manual pending-notification worker
- live Greenhouse runner integration
- real Gmail smoke tests
- real failure/recovery smoke test

Validated retry lifecycle:

```text
PENDING
attempt_count = 0
    ↓
forced SMTP failure
    ↓
PENDING
attempt_count = 1
last_error populated
    ↓
retry
    ↓
SENT
attempt_count = 2
last_error cleared
```

Status:

```text
COMPLETE
```

---

# Database Schema

Current durable tables:

```text
jobs
source_states
job_sources
job_evaluations
notification_outbox
notification_digests
```

`notification_outbox` additionally carries:

```text
payload    JSONB  -- structured alert content captured at enqueue time
digest_id  BIGINT -- the digest that owns this candidate
```

`status` domain:

```text
PENDING | SENT | DEAD | SUPPRESSED
```

`SUPPRESSED` is terminal and auditable. It marks a candidate retired by
policy rather than delivered, so the historical backlog is preserved
instead of deleted.

Current Alembic revision:

```text
0006
```

---

# Testing

Current backend regression suite:

```text
400 tests passing
```

The suite covers:

- canonical job creation
- Greenhouse normalization
- target-role classification
- classification precedence
- role priority
- startup-role recall
- geography
- ambiguous Remote handling
- seniority
- experience rules
- PhD rules
- sponsorship rules
- citizenship restrictions
- clearance restrictions
- database model structure
- persistent identity
- content hashing
- snapshot lifecycle
- baseline lifecycle metadata
- alert freshness policy
- digest window scheduling
- digest grouping and ordering
- NEW detection
- UPDATED detection
- REOPENED detection
- CLOSED reporting
- empty snapshot protection
- evaluation policy
- alert/suppression policy
- source workflow behavior
- notification rendering
- SMTP transport behavior
- notification outbox deduplication
- notification delivery state transitions
- digest restart safety
- digest retry and dead-letter behavior
- pending-backlog classification
- retry scheduling
- DEAD-state behavior
- live Greenhouse runner behavior

Integration validation includes:

- live Greenhouse API
- real PostgreSQL
- lifecycle smoke tests
- evaluation workflow smoke tests
- real Gmail SMTP delivery
- real durable outbox delivery
- intentional SMTP failure
- successful PostgreSQL-backed recovery

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

Check PostgreSQL:

```bash
docker compose ps
```

Apply migrations:

```bash
alembic upgrade head
```

Check migration revision:

```bash
alembic current
```

Run all tests:

```bash
python -m pytest backend/tests -q
```

Run Greenhouse ingestion audit:

```bash
python -m backend.scripts.greenhouse_smoke
```

Run persistence audit:

```bash
python -m backend.scripts.persistence_smoke
```

Run persistence lifecycle smoke test:

```bash
python -m backend.scripts.persistence_state_smoke
```

Run source-snapshot workflow smoke test:

```bash
python -m backend.scripts.source_snapshot_workflow_smoke
```

Run notification-outbox PostgreSQL smoke test:

```bash
python -m backend.scripts.outbox_smoke
```

Run real durable email-delivery smoke test:

```bash
python -m backend.scripts.outbox_delivery_smoke
```

Run one live Databricks Greenhouse poll:

```bash
python -m backend.scripts.run_greenhouse
```

Retry currently due notification rows:

```bash
python -m backend.scripts.send_pending_notifications
```

Send a simple SMTP configuration test:

```bash
python -m backend.scripts.send_test_email
```

Stop PostgreSQL:

```bash
docker compose down
```

Do not run:

```bash
docker compose down -v
```

unless the local PostgreSQL volume should intentionally be destroyed.

---

# Secrets

Real runtime credentials belong in:

```text
.env
```

`.env` must remain ignored by Git.

Safe placeholders belong in:

```text
.env.example
```

Never commit:

- Gmail passwords
- Gmail App Passwords
- API keys
- tokens
- production database credentials

---

# Documentation

ACE maintains three documentation layers:

- `README.md` — project-facing capabilities and development commands
- `docs/overview.md` — architecture and module map
- `docs/learning-log.md` — implementation history, debugging, trade-offs, and lessons learned

---

# Current Status

```text
Module 0 — Project Foundation
✅

Module 1 — Greenhouse Job Ingestion
✅

Module 2 — Role Classification + Eligibility
✅

Module 2.1 — Recall Hardening
✅

Module 3 — PostgreSQL Persistence + Job Lifecycle
✅

Module 4 — Evaluation Pipeline + Workflow
✅

Module 5 — Durable Notification Pipeline
✅

Automated Tests
101 passing
✅

Live Greenhouse Validation
✅

Live PostgreSQL Validation
✅

Real Gmail Delivery
✅

Durable Outbox Validation
✅

SMTP Failure + Retry Recovery
✅

Alembic
0002 (head)
✅
```

---

# Next Architecture Stage

ACE can now detect and durably notify when a source poll runs.

The next major capability is automatic repeated source execution:

```text
Scheduler
    ↓
source registry
    ↓
periodic employer polling
    ↓
Greenhouse / future ATS adapters
    ↓
existing ACE pipeline
    ↓
durable notifications
```

After scheduling, major future intelligence stages include:

```text
additional ATS adapters
startup/company coverage expansion
work-authorization intelligence
resume ingestion
resume relevance
freshness-aware ranking
notification preferences
web UI
operational monitoring
```