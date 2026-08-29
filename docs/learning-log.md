# ACE Learning Log

This document records what was built, why it exists, bugs discovered during implementation, engineering decisions, and the concepts learned while building ACE.

---

# Project Setup

## Python Environment

ACE uses Python 3.12.12 selected with `pyenv` and a project-local `.venv`.

### What I Learned

- `pyenv` selects the Python interpreter version.
- `.venv` isolates project dependencies.
- `.venv` belongs to the local development environment and is not committed to Git.
- `requirements.txt` records dependencies required to recreate the Python environment.

### Environment Flow

```text
pyenv
    ↓
Python 3.12.12
    ↓
ACE .venv
    ↓
ACE-specific dependencies
```

---

## Git and GitHub

Git provides local version history.

GitHub stores the remote repository.

### Git Flow

```text
Working Directory
    ↓
git add
    ↓
Staging Area
    ↓
git commit
    ↓
Local Repository
    ↓
git push
    ↓
GitHub
```

### Concepts Learned

- repository
- working directory
- staging area
- commit
- commit hash
- branch
- `main`
- remote
- `origin`
- push
- local versus global Git identity
- GitHub authentication
- `.gitignore`

---

# Module 1 — Greenhouse Job Ingestion

## Problem

ACE needs to retrieve jobs directly from employer hiring systems rather than relying only on third-party aggregators.

Many employers use Applicant Tracking Systems such as Greenhouse.

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

ACE can retrieve live Greenhouse job postings and convert provider-specific JSON into ACE's normalized `CanonicalJob` representation.

The normalized model currently contains:

- source
- company
- external ID
- requisition ID
- title
- location
- description
- official employer URL
- publication timestamp
- update timestamp

## Why a Canonical Model Exists

The rest of ACE should not depend on Greenhouse-specific field names.

Instead:

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Future adapters can produce the same normalized model:

```text
Greenhouse ─┐
Lever ──────┼──→ CanonicalJob → ACE
Ashby ──────┘
```

This is an example of the adapter pattern.

## Network Reliability Decisions

The Greenhouse adapter uses:

- explicit HTTP timeout
- descriptive User-Agent
- `response.raise_for_status()`
- safe handling of missing fields

A third-party network dependency should never be allowed to hang an ACE worker indefinitely.

## Full Description Retrieval

Greenhouse is queried with job content enabled.

HTML descriptions are converted into normalized text.

This allows downstream modules to inspect:

- experience requirements
- degree requirements
- sponsorship language
- citizenship language
- skills
- education

## Testing Strategy

The live Greenhouse API is exercised through a manual smoke-test script.

Unit tests are kept deterministic and independent of the external network.

## Concepts Learned

- ATS
- APIs
- HTTP
- GET requests
- status codes
- JSON
- dictionaries
- lists
- loops
- functions
- type hints
- Pydantic
- immutable models
- adapter pattern
- HTML normalization
- HTTP timeouts
- smoke testing

---

# Module 2 — Role Classification and Eligibility Gate

## Problem

Retrieving every employer job is not useful by itself.

ACE needs to answer two separate questions:

1. Does this posting belong to a target role family?
2. Does this posting contain a deterministic blocker?

These questions are intentionally separated.

## Target Opportunity Profile

### Geography

- United States
- Remote-US

Generic `Remote` is not automatically assumed to mean Remote-US.

### Primary Roles

- Software Engineering / SDE
- AI / Machine Learning Engineering

### Secondary Role

- Forward Deployed Engineering

### Hard Exclusions

ACE currently rejects jobs that clearly contain:

- non-target role family
- non-US geography
- senior/staff/principal/lead/manager/director level
- explicit PhD targeting
- explicit PhD or doctoral-degree requirement
- excessive required experience
- explicit US citizenship or US-person restriction
- explicit security-clearance restriction
- explicit no-sponsorship language

PhD preferred does not automatically reject a job.

Missing sponsorship language does not automatically reject a job.

---

## Architecture

```text
CanonicalJob
    │
    ├──→ Role Classifier
    │       ↓
    │   RoleFamily
    │
    └──→ Eligibility Gate
            ↓
      PASS / STRETCH / REJECT
```

Later:

```text
PASS / STRETCH
    ↓
Resume Relevance
    ↓
HIGH / MEDIUM / MINIMAL
    ↓
Ranking
```

Resume relevance does not control inclusion.

---

## Role Classification

Current role families:

```text
SOFTWARE_ENGINEERING
AI_ML_ENGINEERING
FORWARD_DEPLOYED_ENGINEERING
OTHER
```

Priority:

```text
PRIMARY
├── SOFTWARE_ENGINEERING
└── AI_ML_ENGINEERING

SECONDARY
└── FORWARD_DEPLOYED_ENGINEERING
```

### Specific-Before-General Matching

More specific role patterns must be checked before generic Software Engineering.

Example:

```text
Machine Learning Software Engineer
    ↓
AI_ML_ENGINEERING
```

rather than:

```text
SOFTWARE_ENGINEERING
```

Similarly:

```text
Forward Deployed Software Engineer
    ↓
FORWARD_DEPLOYED_ENGINEERING
```

This prevents generic patterns from capturing titles too early.

---

## Eligibility Outcomes

### PASS

No hard deterministic blocker detected.

### STRETCH

The role remains visible but contains a significant qualification stretch.

### REJECT

At least one deterministic hard blocker was detected.

---

## Experience Rules

Current MVP rules:

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

Preferred experience is not treated as a hard requirement.

---

## PhD Rules

Reject:

```text
Software Engineer - PhD
Machine Learning Engineer - PhD
PhD required
A PhD in Computer Science is required
Doctoral degree required
Doctorate required
```

Do not automatically reject:

```text
PhD preferred
BS / MS / PhD preferred
Bachelor's or Master's required; PhD preferred
```

The final matcher uses explicit requirement grammar rather than loose keyword proximity.

---

## Sponsorship Rule

Explicit language such as:

```text
without current or future sponsorship
will not sponsor
cannot sponsor
no visa sponsorship
```

causes rejection.

No sponsorship statement:

```text
UNKNOWN
```

does not cause rejection.

This supports a recall-first design, especially for startups and smaller employers that may not include immigration details in every posting.

---

## Explainability

Each eligibility decision contains:

- `status`
- `role_family`
- `role_priority`
- `rule_version`
- machine-readable reason codes
- human-readable reasons
- extracted required-experience years

This makes future dashboard explanations possible.

Example:

```text
Role family:
AI_ML_ENGINEERING

Eligibility:
REJECT

Reason codes:
EXPERIENCE_TOO_HIGH
SENIOR_TITLE
```

---

## Rule Versioning

Role and eligibility logic include explicit rule versions.

This makes it possible to evolve the classifier while preserving which rules produced an earlier decision.

---

## Automated Testing

Current suite:

```text
33 tests passing
```

Coverage includes:

- canonical job creation
- Software Engineering classification
- SDE classification
- AI/ML classification
- Forward Deployed classification
- classification precedence
- role priority
- US geography
- Remote-US geography
- unspecified remote behavior
- foreign location rejection
- non-target roles
- senior roles
- experience thresholds
- early-career exceptions
- preferred experience
- high-experience rejection
- PhD-targeted titles
- required PhD
- doctoral degree requirement
- preferred PhD
- unknown sponsorship
- explicit no-sponsorship language
- citizenship restrictions
- security-clearance restrictions

---

## Live Databricks Audit

A live Databricks Greenhouse board was used as a real integration corpus.

During the final Module 2 audit snapshot:

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

Target roles surviving eligibility:

```text
Software Engineering:            0
AI / ML Engineering:             0
Forward Deployed Engineering:    1
```

Main overlapping rejection reasons among target-role jobs:

```text
SENIOR_TITLE          236
EXPERIENCE_TOO_HIGH   217
OUTSIDE_US             96
PHD_TARGETED_ROLE       2
```

The counts overlap because a single job may fail several rules.

The result is only a live snapshot and is not a permanent expectation for Databricks.

---

## Bug 1 — Excessive Experience Incorrectly Became STRETCH

### Observed Behavior

A live posting contained approximately:

```text
7+ years experience
```

but the earlier rule also saw unrelated degree-substitution language such as:

```text
Bachelor's degree or equivalent experience
```

and incorrectly returned:

```text
STRETCH
```

### Why This Was Wrong

A seven-year required-experience threshold is clearly outside the intended early-career search profile.

Degree-substitution wording elsewhere in the description should not weaken that hard blocker.

### Fix

The rule was changed so:

```text
5+ required years
→ REJECT
```

regardless of unrelated degree-substitution text.

### Regression Protection

A dedicated unit test now verifies this behavior.

---

## Bug 2 — `PhD preferred` Incorrectly Became REJECT

### Observed Behavior

The earlier regex interpreted:

```text
Bachelor's or Master's degree required.
PhD preferred.
```

as if the PhD itself were required.

### Root Cause

The regex used loose proximity between:

```text
required
```

and:

```text
PhD
```

Those words belonged to different qualification clauses.

### Fix

The PhD matcher now looks for explicit requirement grammar such as:

```text
PhD required
A PhD in Computer Science is required
Requires a PhD
Must hold a PhD
Doctoral degree required
```

while allowing:

```text
PhD preferred
```

### Regression Protection

A dedicated unit test now protects the preferred-PhD case.

---

## Important Engineering Lessons from Module 2

### Unit Tests Answer

> Does the code behave according to the rules we wrote?

### Live Smoke Tests Answer

> Are those rules sensible against real-world employer data?

Both are necessary.

### False Negatives Matter

ACE is intended to be recall-oriented.

A false negative can hide an opportunity that should have been surfaced.

Therefore:

- missing sponsorship information stays unknown
- preferred qualifications do not become hard requirements
- real corpora are audited before rules are frozen

### Do Not Overfit One Employer

Databricks provided a valuable validation corpus, but ACE should not tune all heuristics to one company's job-board wording.

The rules should be validated again as more ATS sources and employers are added.

---

## Known MVP Limitations

Current Module 2 limitations include:

- heuristic US geography matching
- regex-based experience extraction
- finite title-pattern dictionaries
- finite sponsorship phrase dictionaries
- no graduation-window compatibility yet
- no dedicated OPT evidence model
- no dedicated STEM OPT / E-Verify model
- no dedicated H-1B historical evidence model
- no semantic description classifier
- limited multi-employer validation

These are known limitations, not hidden assumptions.

---

# Current Architecture Checkpoint

ACE currently implements:

```text
Greenhouse API
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
    ↓
Role Classifier
    ↓
Eligibility Gate
    ↓
PASS / STRETCH / REJECT
```

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

Live Databricks Audit
✅
```

---

# Next Module — Module 3: Persistence and New-Job Detection

## Problem

ACE currently processes jobs correctly but has no persistent memory.

Without persistence it cannot know whether a job:

```text
was already seen
```

or:

```text
appeared after the previous poll
```

## Target Capability

Initial poll:

```text
Job A → NEW
Job B → NEW
Job C → NEW
```

Later poll:

```text
Job A → ALREADY_SEEN
Job B → ALREADY_SEEN
Job C → ALREADY_SEEN
Job D → NEW
```

Then:

```text
Job D
    ↓
target role
    ↓
PASS / STRETCH
    ↓
notification candidate
```

Module 3 will introduce PostgreSQL persistence, deduplication, first-seen tracking, last-seen tracking, and new-job detection.

---

# Documentation Convention

Every completed ACE module updates:

## `README.md`

Project-facing summary:

- what ACE is
- what it can currently do
- how to run it
- current status

## `docs/overview.md`

Architecture map:

- module responsibilities
- module boundaries
- how modules connect
- what comes next

## `docs/learning-log.md`

Engineering history:

- concepts learned
- design decisions
- debugging
- bugs
- trade-offs
- regression fixes

---

# Module Development Workflow

Every ACE module follows:

```text
1. Explain architecture

2. Identify exact affected files

3. Provide complete file contents

4. Run deterministic tests

5. Run real integration smoke test when relevant

6. Inspect actual behavior

7. Update documentation
   ├── README.md
   ├── docs/overview.md
   └── docs/learning-log.md

8. Commit and push

9. Move to the next module
```

The goal is to preserve both hackathon speed and a codebase that can be revisited, explained, and defended later.
