# ACE System Overview

ACE is a personal career-intelligence platform designed to discover relevant US engineering opportunities, determine whether they match the configured eligibility profile, remember previously seen jobs, rank opportunities, and eventually deliver immediate alerts with official employer application links.

This document is the high-level architecture map for the project.

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
ACE identifies target roles
    ↓
ACE evaluates eligibility
    ↓
ACE remembers previously seen jobs
    ↓
ACE detects newly discovered openings
    ↓
ACE evaluates resume relevance
    ↓
ACE ranks opportunities
    ↓
ACE sends alerts
    ↓
User opens official employer application link
```

The primary product goal is to minimize time spent searching, sorting, and checking irrelevant jobs so the user can spend the available job-search window primarily on applications.

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
- Backend Developer
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
- Artificial Intelligence Engineer
- Machine Learning Engineer
- ML Engineer
- Applied AI Engineer
- Generative AI Engineer
- GenAI Engineer
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

These opportunities remain eligible for discovery and notification, but they are secondary to Software Engineering and AI/ML Engineering.

---

# 3. Current Exclusions

ACE currently rejects opportunities that clearly contain one or more hard blockers.

Examples include:

- outside United States / Remote-US scope
- non-target role families
- clearly senior-level roles
- staff-level roles
- principal-level roles
- lead-level roles
- manager-level roles
- director-level roles
- explicitly PhD-targeted opportunities
- explicit PhD requirements
- explicit doctoral-degree requirements
- clearly excessive required experience
- explicit US citizenship requirements
- explicit US-person requirements
- explicit security-clearance requirements
- explicit statements that current or future sponsorship is unavailable

A PhD that is merely preferred does not cause automatic rejection.

Missing sponsorship information does not cause automatic rejection.

---

# 4. Core Product Invariants

## Eligibility Controls Inclusion

Eligibility determines whether a job belongs in the candidate set.

The intended flow is:

```text
Job
    ↓
Eligibility
    ↓
PASS / STRETCH / REJECT
```

Only after that do ranking and resume relevance operate.

## Resume Relevance Does Not Hide Qualifying Jobs

Later ACE will evaluate each qualifying job against the current resume.

Expected relevance tiers:

```text
HIGH
MEDIUM
MINIMAL
```

These tiers control prioritization and context.

They do not silently remove an otherwise qualifying opportunity.

The intended architecture is:

```text
Eligibility
    ↓
PASS / STRETCH
    ↓
Resume Relevance
    ↓
HIGH / MEDIUM / MINIMAL
    ↓
Ranking
```

## Missing Information Is Not Automatically Negative

For example:

```text
No sponsorship language found
```

means:

```text
UNKNOWN
```

rather than:

```text
REJECT
```

This protects recall, especially for startups and smaller employers whose job descriptions may not explicitly discuss immigration policy.

## Official Application Links Are Preferred

Whenever possible, ACE stores and surfaces the employer's official application URL returned by the ATS.

The desired flow is:

```text
ACE alert
    ↓
official employer careers page
    ↓
apply
```

rather than forcing the user through third-party job aggregators.

## Newly Discovered Qualifying Jobs Should Be Notification Candidates

The intended notification rule is:

```text
NEW
+
target role
+
PASS or STRETCH
    ↓
notification candidate
```

Resume relevance can enrich or prioritize the alert, but it should not suppress it.

---

# 5. High-Level Architecture

Current architecture:

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
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
Role Classification
        ↓
Eligibility Gate
        ↓
Persistence
        ↓
Deduplication
        ↓
New-Job Detection
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

# 6. Module Map

# Module 0 — Project Foundation

## Purpose

Establish a reproducible development environment and source-control workflow.

## Responsibilities

- Python version management
- project-specific virtual environment
- dependency isolation
- Git repository
- GitHub remote
- `.gitignore`
- repository documentation
- consistent testing workflow

## Technologies

- Linux
- Python 3.12
- pyenv
- Python virtual environments
- Git
- GitHub
- VS Code

## Result

ACE has:

- isolated Python runtime
- isolated dependencies
- version-controlled source code
- public GitHub history
- reproducible project structure

## Status

Implemented.

---

# Module 1 — Greenhouse Job Ingestion

## Purpose

Retrieve live job postings directly from employers using Greenhouse.

## Input

A Greenhouse board token.

Example:

```text
databricks
```

## Processing

```text
Greenhouse API
    ↓
HTTP GET
    ↓
JSON payload
    ↓
Greenhouse Adapter
    ↓
normalization
```

## Output

```text
list[CanonicalJob]
```

## CanonicalJob Fields

The current normalized job model includes:

- source
- company
- external job ID
- requisition ID
- title
- location
- description
- official application URL
- publication timestamp
- update timestamp

## Why Normalization Exists

The rest of ACE should not depend directly on Greenhouse field names.

Instead:

```text
Greenhouse
    ↓
Greenhouse Adapter
    ↓
CanonicalJob
```

Future ATS systems will follow the same pattern:

```text
Greenhouse ─┐
Lever ──────┼──→ CanonicalJob
Ashby ──────┘
```

This allows the downstream ACE pipeline to operate on one stable data model regardless of source.

## Reliability Practices

The Greenhouse adapter currently includes:

- explicit HTTP timeout
- descriptive User-Agent
- `raise_for_status()` handling
- full job-description retrieval
- HTML-to-text normalization
- safe handling of missing location values

## Full Description Retrieval

Greenhouse is queried with job content enabled.

Descriptions are converted from HTML into plain normalized text so downstream modules can inspect:

- experience requirements
- education requirements
- sponsorship language
- citizenship language
- skills
- degree requirements

## Testing Strategy

The live Greenhouse API is exercised through a manual smoke-test script.

Automated unit tests do not depend on an external network.

## Status

Implemented.

---

# Module 2 — Role Classification and Eligibility Gate

## Purpose

Determine:

1. whether a posting belongs to an ACE target role family
2. whether the posting contains a deterministic eligibility blocker

These are intentionally separate concerns.

## Role Classification

Each title is mapped into one of:

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

More specific role families are evaluated before generic software engineering.

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

This uses specific-before-general classification precedence.

## Eligibility Outcomes

Every evaluated job receives one of:

```text
PASS
STRETCH
REJECT
```

### PASS

No deterministic hard blocker was detected.

### STRETCH

The job remains visible but contains a meaningful qualification stretch.

### REJECT

A deterministic hard blocker was detected.

## Current Experience Rules

Current MVP rules:

```text
0–2 required years
→ PASS

3 required years
→ STRETCH

4 required years
→ REJECT

4 required years
+ explicit early-career signal
→ STRETCH

5+ required years
→ REJECT
```

Preferred experience is not automatically treated as a hard requirement.

## Seniority Rules

Current clear senior-level title signals include:

- Senior
- Sr.
- Staff
- Principal
- Lead
- Manager
- Director
- Engineer III
- Engineer IV

These are rejected by the current early-career eligibility gate.

## PhD Handling

Reject:

```text
Software Engineer - PhD
PhD Software Engineer Intern
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

The PhD detector uses explicit requirement grammar rather than loose keyword proximity.

This is designed to reduce false rejection.

## Work-Authorization Blockers

Current deterministic blockers include:

- explicit US citizenship requirement
- explicit US-person requirement
- explicit security-clearance requirement
- explicit no-sponsorship language

Examples of sponsorship blockers include phrases such as:

```text
without current or future sponsorship
will not sponsor
cannot sponsor
no visa sponsorship
sponsorship is not available
```

Missing sponsorship language remains unknown and does not automatically reject the job.

## Explainability

Each eligibility decision contains:

- status
- role family
- role priority
- eligibility rule version
- machine-readable reason codes
- human-readable explanations
- extracted experience requirement

This will later allow the web application and alerts to explain why ACE accepted, stretched, or rejected a posting.

## Rule Versioning

Role and eligibility rules are versioned.

Examples:

```text
ROLE_RULE_VERSION
ELIGIBILITY_RULE_VERSION
```

This allows ACE rules to evolve while preserving explainability.

## Automated Tests

Module 2 currently includes deterministic tests covering:

- Software Engineering classification
- Software Development Engineer classification
- AI/ML classification
- Forward Deployed classification
- classification precedence
- role priority
- United States geography
- Remote-US geography
- unspecified remote handling
- non-US rejection
- non-target role rejection
- seniority
- experience thresholds
- preferred experience
- high-experience rejection
- early-career exception behavior
- PhD-targeted titles
- required PhD
- required doctoral degrees
- preferred PhD
- unknown sponsorship
- explicit sponsorship blockers
- citizenship restrictions
- security-clearance restrictions

Current automated suite:

```text
33 tests passing
```

## Live Databricks Validation

A live Databricks Greenhouse board was used as an integration corpus.

During the Module 2 audit snapshot:

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

Major overlapping rejection reasons among target-role jobs included:

```text
SENIOR_TITLE          236
EXPERIENCE_TOO_HIGH   217
OUTSIDE_US             96
PHD_TARGETED_ROLE       2
```

The rejection counts overlap because one job can fail multiple deterministic checks.

The only qualifying opportunity in that snapshot was a Forward Deployed Engineering role.

This result is a live snapshot and is not treated as a permanent expectation.

## Bugs Found During Module 2

### Excessive Experience False Stretch

Earlier logic incorrectly allowed a high-experience role to survive because unrelated degree-substitution language was present.

Example:

```text
7+ years required
+
Bachelor's degree or equivalent experience
```

Incorrect behavior:

```text
STRETCH
```

Correct behavior:

```text
REJECT
```

A regression test now protects this rule.

### PhD Preferred False Rejection

Earlier regex logic interpreted:

```text
Bachelor's or Master's degree required.
PhD preferred.
```

as though the PhD itself were required.

Incorrect:

```text
REJECT
```

Correct:

```text
PASS
```

The PhD matcher was changed to recognize explicit requirement grammar rather than loose proximity between `required` and `PhD`.

A regression test now protects this behavior.

## Known MVP Limitations

Module 2 is intentionally a deterministic MVP.

Current limitations include:

- heuristic US location normalization
- regex-based experience extraction
- finite title-pattern dictionaries
- finite sponsorship phrase dictionaries
- no graduation-window compatibility yet
- no dedicated OPT evidence model yet
- no dedicated STEM OPT / E-Verify evidence model yet
- no dedicated H-1B sponsorship-history model yet
- no semantic job-description classifier yet
- validation so far is primarily against one live employer corpus

These rules should be validated across many employers rather than tuned only to Databricks.

## Status

Implemented as MVP v1.

---

# Module 3 — Persistence and New-Job Detection

## Purpose

Give ACE memory.

Without persistence ACE cannot distinguish:

```text
job already seen yesterday
```

from:

```text
job appeared after the previous polling run
```

## Planned Responsibilities

- PostgreSQL
- database connection management
- database schema
- job persistence
- deduplication
- first-seen timestamp
- last-seen timestamp
- source identity
- job lifecycle
- new-job detection

## Target Flow

Initial poll:

```text
Job A
Job B
Job C
    ↓
stored
```

Later poll:

```text
Job A → already known
Job B → already known
Job C → already known
Job D → NEW
```

Then:

```text
Job D
    ↓
target role?
    ↓
eligible?
    ↓
PASS / STRETCH?
    ↓
notification candidate
```

## Status

Next module.

---

# 7. Future Modules

The exact sequence may evolve during implementation, but the architecture is expected to include the following capabilities.

# Work-Authorization Intelligence

## Purpose

Track immigration/work-authorization evidence independently rather than collapsing everything into one binary sponsorship field.

Expected dimensions include:

- OPT compatibility
- STEM OPT / E-Verify
- future H-1B sponsorship
- citizenship / clearance restrictions

Unknown evidence should remain explicitly unknown.

---

# Resume Intelligence

## Purpose

Evaluate every qualifying job against the user's current resume.

The resume can change over time, so relevance must be recomputed against the latest active resume.

Expected relevance tiers:

```text
HIGH
MEDIUM
MINIMAL
```

Resume relevance may consider:

- technologies
- languages
- frameworks
- systems experience
- AI/ML experience
- backend experience
- cloud experience
- project similarity
- required qualifications
- preferred qualifications

Resume relevance affects prioritization.

It does not redefine eligibility.

---

# Ranking

## Purpose

Determine the order in which qualifying jobs should be reviewed.

Potential signals include:

- role priority
- job freshness
- resume relevance
- work-authorization evidence
- employer signals
- required experience
- application urgency

Ranking must not silently remove qualifying jobs.

---

# Notification Engine

## Purpose

Notify the user when newly discovered qualifying jobs appear.

Target condition:

```text
NEW
+
target role
+
PASS or STRETCH
    ↓
notification candidate
```

Notifications should eventually contain:

- company
- job title
- role family
- role priority
- location
- eligibility status
- resume relevance tier
- experience requirement
- useful explanation
- official employer application URL

The notification mechanism can begin with email and evolve if needed.

---

# Scheduler and Continuous Ingestion

## Purpose

Continuously discover opportunities throughout the day rather than relying only on one daily refresh.

Target behavior:

```text
scheduler
    ↓
source polling
    ↓
normalize
    ↓
persist
    ↓
detect new jobs
    ↓
evaluate
    ↓
notify
```

Different sources may eventually use different polling intervals.

---

# Additional ATS Adapters

The adapter architecture is intended to support multiple employer systems.

Potential future sources include:

```text
Greenhouse
Lever
Ashby
Workday
SmartRecruiters
custom employer career APIs
selected high-quality public job sources
```

Every source should normalize into:

```text
CanonicalJob
```

before entering downstream intelligence.

---

# Web Application

## Purpose

Provide a clean UI for reviewing opportunities without manually searching external job boards.

Expected capabilities include:

- opportunity feed
- role-family filters
- PASS / STRETCH labels
- resume relevance tiers
- freshness indicators
- company information
- eligibility explanation
- official application links
- search
- sorting
- notification state
- application-related workflow if needed later

The initial priority remains job discovery and fast application rather than building UI features for their own sake.

---

# 8. Data Flow

The intended full ACE data flow is:

```text
Employer ATS / Job Source
        ↓
Source Adapter
        ↓
CanonicalJob
        ↓
Role Classifier
        ↓
Eligibility Gate
        ↓
Persistence
        ↓
Deduplication
        ↓
New-Job Detection
        ↓
Work-Authorization Intelligence
        ↓
Resume Relevance
        ↓
Ranking
        ↓
Notification
        ↓
Web Application
        ↓
Official Application Link
```

---

# 9. Testing Strategy

ACE uses several testing layers.

## Unit Tests

Used for deterministic application logic.

Examples:

- role classification
- experience rules
- PhD rules
- eligibility
- persistence logic
- deduplication logic

Unit tests should not depend on external network services.

## Integration Smoke Tests

Used to validate external systems.

Examples:

- Greenhouse API
- PostgreSQL
- email provider
- future ATS integrations

Smoke tests may use real external services.

## Regression Tests

Whenever a real bug is discovered, a test should be added before the fix is considered complete.

Examples already captured:

```text
7-year requirement incorrectly becoming STRETCH
PhD preferred incorrectly becoming REJECT
```

---

# 10. Observability Philosophy

ACE should not behave like a black box.

Important decisions should be inspectable.

Examples:

```text
Role family:
AI_ML_ENGINEERING

Eligibility:
REJECT

Reasons:
EXPERIENCE_TOO_HIGH
SENIOR_TITLE
```

Later operational metrics may include:

- jobs fetched per source
- jobs normalized
- target roles detected
- PASS count
- STRETCH count
- rejection reasons
- new jobs discovered
- notification count
- source failures
- request latency
- duplicate count

---

# 11. Documentation Structure

ACE maintains three primary documentation layers.

## README.md

Purpose:

Public and project-facing summary.

Answers:

```text
What is ACE?
What can it currently do?
How do I run it?
```

## docs/overview.md

Purpose:

Architecture and module map.

Answers:

```text
What modules exist?
What does each module do?
How do the modules connect?
What is currently implemented?
What comes next?
```

This document should remain concise enough to quickly understand the system while still preserving important architectural decisions.

## docs/learning-log.md

Purpose:

Detailed engineering history.

Answers:

```text
What did I learn?
Why was a decision made?
What bugs appeared?
How were they debugged?
What alternatives were considered?
What trade-offs exist?
```

---

# 12. Module Development Workflow

Every ACE module follows the same process.

```text
1. Explain architecture

2. Identify exact affected files

3. Provide complete file contents

4. Run deterministic tests

5. Run real integration smoke test when relevant

6. Inspect real behavior

7. Update documentation
   ├── README.md
   ├── docs/overview.md
   └── docs/learning-log.md

8. Commit and push

9. Move to the next module
```

The objective is to preserve:

- hackathon speed
- code quality
- reproducibility
- architectural clarity
- interview explainability
- durable project knowledge

---

# 13. Current Project Status

Completed:

```text
Module 0
Project Foundation
✅

Module 1
Greenhouse Job Ingestion
✅

Module 2
Role Classification
✅

Module 2
Eligibility Gate
✅

Automated Tests
33 passing
✅

Live Employer Validation
Databricks Greenhouse audit
✅
```

Next:

```text
Module 3
PostgreSQL Persistence
+
Deduplication
+
New-Job Detection
```

The key capability unlocked by Module 3 will be:

```text
ACE remembers what it has already seen
        ↓
new posting appears
        ↓
ACE recognizes it as NEW
        ↓
eligibility check
        ↓
notification candidate
```

That is the foundation required for real-time job alerts.
