# Inbox intelligence upgrade



## Parser 13 candidate: recognize and file before application attribution

Status: follow-up implementation under validation; the parser-12 LIVE record
below remains the deployed state until separately verified activation.

Fresh complete rejection, assessment, interview, offer, recruiter
reply and candidate-action readings can be filed without selecting an
application. `classified_rejection` and `classified_action` are shared SQL/Python
projections over stored `update` plus explicit classifier markers. They do not
create company/application outcomes or change an application status. Matching
candidates and the specific linkage explanation remain available as optional
correction context. Unauthenticated sources carry an explicit unverified
message-meaning flag and never authorize application or company outcomes. Partial
or conflicting meaning and explicit owner holds remain visible for clarification. Existing exact positive automation
still requires its live-message, employer-origin and opt-in safeguards.

The existing Inbox layout provides category counts, assessment/interview/offer
and rejection views, explicit filed labels and optional correction controls.
Analytics presents recognized email progress using receipt dates, separately
from confirmed application-stage counts. A later rejection preserves prior
assessment/interview events; tests exercise that complete sequence. Unknown
company/role attribution is excluded from selected employer/family metrics.
Earlier approved action corrections remain visible through exact legacy markers
without rewriting their rows. The reader also treats a simultaneous rejection
and current assessment request as conflicting meaning, requiring clarification.
No migration, blanket historical replay, scheduler or Resume Studio change.

Local verification passes 754 Inbox/Analytics backend cases and 84 render/DOM
cases. Hosted TypeScript/lint/build and 44 browser cases are pending at this
checkpoint. The bounded current-mail preview stays read-only and server-private;
its complete source/grant/row/evidence seal must match before any authorized
filing. Owner decisions, Undo, application histories and unrelated services
remain protected. No representative population accuracy claim is made.


## Parser 12 LIVE: company evidence and completed guarded history

API/frontend `873ee080fa724fcbe0022ad47939d38c083ca8e9` is live at
https://ace.opik.net, schema 0050, owner-authorized activation October 28 at
21:22 Pacific. Only API/web were replaced. The existing background Gmail
monitor and its Pause, disconnect, quota, shutdown and advisory-lease controls
remain intact; this adds no service, Gmail scope or migration. Extension 1.31.3
and unrelated services remain preserved.

A confirmed employer rejection without an exact role becomes a company evidence
event under the email ledger key, with validated scope/version/company metadata
and no application status transition. The stored email remains `update` with
an exact classifier reason; shared SQL/Python presentation exposes
`company_rejection`. The inspector avoids role selection, retains the source
email and offers event Undo. Company Undo appends a correction and returns only
the email to review. Application identities are never merged or chosen merely
to reduce the queue.

Analytics projects active validated company events separately from exact
application outcomes. It deduplicates repeated email events, observes Undo and
later owner filing, rejects malformed/conflicting claims and uses Gmail receipt
dates in the display timezone. All-time includes email history before the
application register; exact company filters apply. Unknown roles are excluded
from selected role families with explanatory evidence scope, and never enter
application stages, response timing or cohort rates. Assessment and interview
filters expose actionable, completed and cancelled correspondence; 56 fictional
intent regressions cover contextual action language and assertion safeguards.

Separately approved sealed historical filing, exact-application outcomes and
targeted action corrections completed with final preservation and projection
checks. Only the explicitly authorized outcome plan changed application
statuses. Owner choices, Undo, prior ledger entries, Gmail identity/metadata,
outside-cohort mail and unrelated data remain intact. Historical rechecks stay
disabled; exact private manifests and journals do not authorize further replay.
All 355 running backend files, public source/auth/assets, real-mail routes,
filters and monitor lease/sync behavior are verified. Hosted focused validation
passes; overall CI stays red from the demonstrated preserved-extension/runtime
stub mismatch, with broader full app browsers skipped. No signed-in production
browser or representative population precision/recall claim is made. The first
root knowledge section contains exact CI, backup and rollback details.


## Parser 11 live: continuous checks and contextual identity

Status: historical release checkpoint; superseded by the parser-12 LIVE record above.

Status: API/frontend source `5109fcd919b76a588bed848c4ac4bf07d0e5acbc` is **LIVE**
at https://ace.opik.net with owner authorization, 2026-10-28 16:29 Pacific,
schema 0050. Only API/web were replaced; no migration or historical replay.
The first root knowledge section controls exact verification, backup and rollback.
The new historical proposal remains separately unapproved and unapplied.

The API lifespan owns a bounded Gmail monitor for existing ready grants. It
checks about every three minutes, uses a dedicated PostgreSQL advisory lease
across ticks, and never calls historical reclassification or the job discovery
scheduler. A new grant still starts paused. Pause, disconnect and changed grants
remain authoritative; error writes use an atomic conditional update. Shutdown
checks between listing pages, metadata/body reads and ingestion commits retain
unfinished IDs for retry. Quota failures wait at least thirty minutes and honor
longer provider retry instructions. No new service, scope or schema is added.
`GMAIL_BACKGROUND_SYNC_ENABLED=false` disables the monitor.

Matching analyzes explicit title evidence before eliminating future applications.
It never substitutes a past generic title for a named future specific role and
never chooses the nearest submission date. Explicit current-application links
can identify postings on supported Greenhouse, Lever, Ashby, Workday and
SmartRecruiters public URLs. Identities include provider, employer tenant and
posting ID. Redirects, account/session tokens, quoted links, recommendation
sections and arbitrary website query numbers do not qualify. Conflicting
requisitions, role names, employers, links or duplicate application records stay
unresolved. Link extraction is ephemeral; raw link tokens are not retained.

A complete, authenticated, employer-identified rejection that predates **every**
recorded application at that employer can be retained as `unlinked`, with its
classification and decisive evidence intact. Explicit IDs/links pointing to a
future application still require review. Unlinked outcomes are searchable and
shown with their own Inbox filter/count and Analytics evidence-review entry;
they never create applications or confirmed application outcomes. Linking is
optional. The stored decision uses the existing `update` value and the explicit
classifier reason; a shared SQL/Python projection exposes `unlinked`. The prior
API can therefore still search and manually link that correspondence after an
image rollback, without a database downgrade. This is an evidence state, not an age cutoff or an inference that the
owner's newer application was rejected. Partial evidence, authentication or
employer conflicts, contradictory meaning and real candidate actions remain
review tasks. Existing records are not projected into this state automatically:
historical changes require a separately reviewed, source-sealed cohort plan.

The intent reader also handles short role-qualified application decisions such
as the fictional “Your application for Data Scientist was rejected,” with
conditional, negation, quoted-example and question safeguards. Public learning
events need substantive event/registration purpose, rather than one adjective.
Polite comparative decisions need asserted candidate-specific application
context, contrasting closer-fit applicants and a later explicit reference to
this role's decision; punctuation in named roles is supported. Quotes, examples,
conditional references, current review, offers and interviews retain safeguards.
Google-authenticated parent domains for subdomain senders additionally require a passed aligned DKIM identity; unrelated signatures and explicit DMARC failures stay blocked. This uses Google's own first authentication result, consistent with [Gmail authentication guidance](https://support.google.com/mail/answer/180707) and the identifier-alignment distinction in [RFC 9989](https://www.rfc-editor.org/rfc/rfc9989.html).
Automatic versus owner provenance no longer treats a machine explanation
starting “You applied...” as an owner decision. Positive automation keeps the
existing strict opt-in/live/exact-ID/employer-origin policy.

Fictional regressions cover these paths, wrong-target counterexamples, shared
SQL/Python states, Analytics exclusion, provider errors, concurrent owner Pause,
shutdown and actual frontend render/interaction behavior. Population precision,
recall and complete mailbox observation remain unmeasured without independent
labels and provider coverage; passing examples are not a perfect-accuracy claim.

Exact-source verification: 1,921 full backend, 687 focused backend, 38 hosted
Inbox/Analytics browser cases, render/DOM, TypeScript/lint/build pass. The full
workflow's extension browser failure reproduces canonical and skips later app
browsers; overall CI remains red. A read-only PostgreSQL lease exclusion/release
check, all 350 running backend source hashes, exact public web assets, real-mail
route probes and actual new ingestion are separately verified in production.
Cutover and subsequent legitimate ingestion are distinct preservation intervals.
No signed-in production browser session was created. Private actual measurements
and the historical proposal are in the ignored owner-local release package.

Parser 10 follow-up LIVE at API source `6ee2eb2`, schema 0050, PR #12 merged: distinguish optional coding lessons,
account access, public digests and financial/administrative notices from hiring
outcomes using substantive content. Recognize branded assessment invitations,
due-in reminders, actual offers and named test completion; extract visible text
from mislabelled HTML. Workday display text does not create a second employer;
nested generic titles do not defeat a unique longer exact title. Duplicate roles,
subsidiaries, authentication, chronology and positive-update policies remain guarded.

The owner separately approved cleanup of an explicit historical pending cohort,
with application statuses, owner decisions and Undo preserved. The new
`backend.scripts.inbox_historical_cleanup` defaults to read-only preview, reads
at most 50 known messages per invocation through label preflight, and seals the
reviewed source/cohort/grant/plan. Apply rereads each body and reconciles current
application records, compares the prepared result and locked email fingerprint,
then changes only email classification/filing fields and appends an email audit
event. It never invokes status automation. Pause, grant changes, protected owner
work, changed evidence or reconciliation stop the operation. A guarded row
rollback appends corrections and refuses later owner work. The global historical
recheck switch remains disabled. Private plans, backups and measurements must
stay outside public source. The explicitly enumerated cleanup is complete; original statuses/owner choices and evidence identities remain unchanged. Exact measurements and reference conflicts are private in `artifacts/inbox-intelligence-review-20261028/backlog-cleanup/RELEASE.md`.

Earlier parser-9 release (superseded for API; frontend retained): owner-approved source `95f4a97318d10935c9183341627ff78f08f0a85b` at
https://ace.opik.net, parser 9/schema 0050; PR #11 merged. The earlier reviewed
classifier source was 7657b62. The released source adds a server default-off
historical-recheck control required by the deployment approval; classification
and matching semantics are unchanged. The root checkout and concurrent worktree
keep their application code. Complete release evidence and limits are in the
first LIVE section of `ACE_NEXT_KNOWLEDGE.md` and the ignored owner-local
`artifacts/inbox-intelligence-review-20261028/release/RELEASE.md`.

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
reprocessing remains separately disabled and requires owner approval. The server
default-off `GMAIL_HISTORICAL_RECHECKS_ENABLED` control governs both eligible
stale counts/selection and recheck execution; new-message processing continues.

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

Released application source `95f4a97318d10935c9183341627ff78f08f0a85b` passes hosted
review run 40726740989: 422 focused backend, 22 calculation/render, 55 DOM and
36 Inbox/Analytics browser tests, TypeScript, lint and production build. Full
backend passes 1,676 plus 258 matcher cases. Full run 40726749948 passes
47 extension and 36 focused browser tests; broader browsers finish 167 passed /
19 failed, all 19 names shared with canonical run 40615561429 (165/21).
Full CI is not green; identical failed names do not prove identical causes.
The private release record retains exact source/verification and comparison.

The owner-local review package is
`artifacts/inbox-intelligence-review-20261028/REVIEW.md`. Its 14 deliverables
contain the complete observed-backlog proposal, actual counts, narrow existing
owner-reference metrics, matching abstentions, protected disagreements and final
fictional Day/Night desktop/mobile captures. Public docs contain no private
measurements. All observed unresolved records were inspected, including bounded
supplemental reads of known pending records absent from current search, with
metadata preflight. This is not a full-body census or semantic mailbox-recall
certification. Unestablished earlier outcomes remain visible review work.

Live verification confirms parser 9/schema 0050, exact API/frontend source and
retained scheduler/PostgreSQL/Caddy identities. Cutover snapshots preserve every
pre-existing protected row/event; concurrent owner activity is retained and
reported separately. No historical reclassification or restore ran. Read-only
live mail/viewer, filters, disabled recheck, public assets/auth and Analytics
checks pass. The stopped operator and owner-stop/143 remain unchanged.

No deployment, historical mutation, migration, OAuth scope, external AI provider,
scheduler, discovery, extension, auth model, application creation policy,
Resume Studio, Memory or logo change is authorized incidentally. The owner approved the specific API/frontend release after review;
it is now live. Later releases and historical reclassification require their own
explicit approval, retaining the documented accuracy limitations. Incorrect automatic rejection and wrong-application updates are
release-blocking defects, regardless of queue reduction.
