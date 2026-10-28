# Inbox intelligence upgrade

Status: parser 9 candidate, isolated `inbox-intelligence-20261028` branch based
on released canonical `d5c38dc`. Not deployed. The restored root checkout and
existing `ace-inbox` worktree are preserved. Parser 8 was already released;
the pasted brief's unfinished-parser-8 description is historical.

## Diagnosis and actual evidence

The existing pipeline is Gmail candidate search, metadata label preflight,
plain/HTML extraction, intent classification, application matching, mutation
policy, application event ledger, shared queue projection and Analytics.
Parser 8 fixed pagination/scope and legacy queue projection. It still conflated
assessment mentions and completion with invitations, broad regret/policy with
negative decisions, and generic progression with interviews. Only the opening
Gmail excerpt was retained, often omitting the decisive sentence. Classifier
updates were absent from the old-parser recheck selector, so an unfamiliar
outcome filed as correspondence could remain there after wording improved.

Read-only production inventory and Analytics invariants were freshly measured.
Stored headers/excerpts across historical dates were analyzed first. A bounded,
stratified body sample then used the existing read-only grant, metadata label
checks and paced reads across historical years. Full bodies were processed in
memory and discarded. Only whitelisted recurring linguistic templates and
aggregate indicators left that discovery process. No private texts or real
identities enter fixtures, this document, CI or Git. Private measured values,
body-reading limits and before/after proposals belong in the owner-local review
package, not this public repository.

Observed recurring structures include received-and-will-review receipts,
selected-to-move-forward progression, other-candidate decisions, test completion
and deadline messages, scheduling requests and conditional process descriptions.
Their prevalence is diagnostic, not ground-truth labels. Historical body search
remains heuristic and some messages are unavailable or incomplete. No complete
mailbox recall or perfect semantic recognition is claimed.

## Implementation

The existing classifier remains the single engine in `reconcile.py`.
`read_intent` produces a classification, meaningful explanation, short current
sentence and event variant. `classify` retains its tuple API. Reconciliation
continues separately and now retains a matched identity independently of whether
a mutation is authorized. Conditions, negation, quoted/forwarded history,
explicit contradictions, actual requested actions and applicant-specific
negative decisions control interpretation. Strict positive opt-ins, exact IDs,
authentication, live-only positives, protected stages and Undo remain. Sender
authentication is distinct from employer identity: a subsidiary/agency sender
cannot inherit the only parent application. Workday tenant conflicts stay
unresolved, shared ATS hosts cannot establish employer-owned origin for positive
automation, and other ATS rejection evidence needs exact employer branding or
an explicitly delimited employer identity. No parent aliases are introduced.

A previously recognized outcome cannot silently become passive correspondence
merely because a new parser does not establish it. Shared recheck/dry-run logic
keeps that specific uncertainty visible, including across parser revisions.
Affirmative routine account/practice/alert content can resolve an older false
outcome; a generic subject alone cannot. This deliberately limits backlog
reduction to evidence-supported changes.

The shared body limit is 60,000 characters with a truncation sentinel. Incomplete
outcomes still require review. HTML quote blocks are excluded from intent
extraction; the sandboxed original HTML remains available. New imports and
eligible rechecks retain a decisive excerpt in the existing bounded snippet
column. No body/HTML table or migration is introduced. Complete original mail
continues to load only through the authenticated Gmail viewer.

Completed/cancelled assessments, cancelled interviews and routine status updates
are filed without changing stages or manufacturing Analytics replies. Genuine
document/information requests remain actionable owner tasks. Existing automatic
correspondence can be rechecked under a later parser; owner filings, deferred
choices, recorded decisions and both Undo reasons remain protected. Historical
reprocessing is a proposed production operation requiring owner approval.

Shared SQL/Python workflow states provide separate existing-list filters for
filed evidence, safe-linkage work, owner decisions/actions and routine mail.
Deferred, recorded and synchronization errors retain their existing distinct
surfaces. Owner versus automatic decision provenance remains explicit.

The existing Inbox inspector presents saved classification, linkage, review
reason, policy and the fresh body interpretation/excerpt separately. A new
reading never silently overwrites a protected saved decision. Existing themes,
font, shell, controls, search, pagination and audit/Undo remain. There is no
Analytics visual redesign or projection change and no new review database.

## Public intent catalog

| Intent | Required context | Disqualifying context | Matching/status policy | Review |
| --- | --- | --- | --- | --- |
| Receipt / under review | Application received/submitted or candidate qualifications under review | Later asserted rejection or actual action | May link; no stage or meaningful-reply event | Only incomplete content or material contradiction |
| Rejection | Definite candidate-ending decision, other candidates selected for this candidacy, or personal eligibility refusal | Conditional policy, negation, withdrawal, meeting scheduling failure, generic job closure, quoted history | Existing authenticated unique-match, chronology, final-status and Undo guards | Specific identity, authentication, incomplete-content or protected-stage conflict |
| Assessment invitation / reminder | Candidate requested to complete an actual hiring test or test deadline | Brand alone, account setup, practice/course marketing, completed/cancelled test | Existing positive opt-in/live/exact-ID/employer-origin rules | Linkage or update-policy decision |
| Assessment completed / cancelled | Asserted completion/cancellation of that test | Conditional future completion or negated completion | File evidence; no stage change | Only incomplete content |
| Interview / recruiter screen | Explicit invitation, scheduling request/confirmation or rescheduling | Generic next-stage praise, cancelled meeting, quoted invitation | Existing positive safeguards | Linkage or update-policy decision |
| Interview cancelled | Asserted meeting cancellation | A candidate-ending decision is classified separately | File without inferring rejection | Only incomplete content |
| Recruiter reply | Substantive application discussion | Routine receipt or generic interest | Existing positive safeguards | Existing policy/linkage safeguards |
| Offer | Explicit employment offer or actual attached offer letter | Future conditional letter, ordinary praise or advancement | Strict existing offer safeguards | Existing policy/linkage safeguards |
| Action required | Actual request for documents, candidate details or application action | Routine receipt or generic instructions | Preserve recognized action and matched identity; no automatic stage | Specific employer-site action |
| Routine update | Application progress, generic closure or policy information without applicant-ending decision | Asserted hiring outcome | Searchable correspondence; no stage | No routine owner task |
| Account/job alert/non-job | No applicant-specific hiring outcome | Explicit substantive body outcome defeats generic subject | Ignore routine outcome processing; retain searchability | No routine owner task |
| Material uncertainty | Conflicting outcomes/progress, incomplete evidence, identity/auth/status conflict | An unfamiliar phrase alone | Preserve classification and original evidence | Explain the actual unresolved decision |

## Evaluation, dry-run and release boundaries

`backend/app/inbox/evaluation.py` consumes explicit labels and emits per-category
precision/recall, supports, confusion matrix, Wilson recall intervals, missed/
false rejections and wrong-application mutations. Missing labels/denominators
remain unavailable. An independently adjudicated representative multi-category
corpus is unavailable, so population accuracy and unnecessary-review-rate claims
remain unsupported. The owner explicitly chose existing owner decisions and
reporting those accuracy gaps rather than requesting new labels. Owner-recorded stages can supply a narrow reference; an owner filing
choice is not automatically a semantic gold label. Handwritten fictional tests
are regression checks, not measured real-world accuracy.

`backend/scripts/inbox_classification_audit.py` defaults to incomplete retained
excerpts. Explicit `--read-bodies` runs at most 50 paced eligible reads, uses a
completed all-date candidate listing, enforces read-only PostgreSQL and saves
private resumable proposals after each message. It never calls ingest, apply,
sync, recheck or any mutation endpoint. Protected decisions remain unchanged.
It reports proposed classifications, evidence, safe identity, policy, remaining
review and actual stage-change versus evidence-only effects separately. A
bounded diagnostic sample must never be extrapolated to the whole backlog.

Fictional regressions cover direct/indirect rejection, conditions/negation,
policy, acknowledgement, progression, assessments, scheduling/cancellation,
offers, mixed intent, quoted HTML, long/truncated bodies, conflicting IDs and
employers, passive event purity, correspondence rechecks, owner protection,
metrics and audit purity. Existing Gmail, persistence, full-history, Analytics,
marks, external-application and auth contracts remain. Hosted CI supplies
fictional browser execution and captures because local Chrome is prohibited.
The new review workflow changes no production scheduler.

No deployment, historical mutation, migration, OAuth scope, external AI provider,
scheduler, discovery, extension, auth model, application creation policy,
Resume Studio, Memory or logo change is authorized incidentally. Production
release remains blocked until the exact candidate's tests, audit findings and
accuracy limitations are reviewed and the owner explicitly approves that
operation. Incorrect automatic rejection and wrong-application updates are
release-blocking defects, regardless of queue reduction.
