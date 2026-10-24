# ACE Next knowledge

Last updated: 2026-10-24

This is the continuity document for the production migration from the legacy
ACE runtime to ACE Next. It contains architecture, verified state, operating
commands, migration controls, deployment steps and remaining owner actions.
It intentionally contains no email address, resume text, answers, credentials
or database dump content because the GitHub repository is public.

## Instructions for a new Codex chat

Treat this file as the continuity source for ACE. Read it completely before
changing code or operating production. Then inspect the current Git status and
diff because this document records known state but never overrides newer code
or an explicit owner instruction.

For any interface work, also read the entire approved implementation prompt and
inspect every page of the interactive V2 reference in both themes:

```text
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/CODEX_IMPLEMENTATION_PROMPT.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/ACCEPTANCE_CHECKLIST.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/references/ACE_Wine_Rose_Full_Platform_Demo_v2.html
```

The approved V2 reference has 12 pages: Home, Sign in, Signed out, Pulls,
Opportunities, Applications, Analytics, Resume Studio, Autofill Extension,
Archive, Coverage and Settings. Night and Day are both required. Prototype
navigation, fictional data and the cursor tour must never ship.

Before every task:

1. Read repository instructions, including `web/AGENTS.md` for frontend work.
2. Inspect `git status`, the relevant diff and recent commits. Preserve unrelated
   owner edits. Never use reset, checkout, clean or force push to discard them.
3. Audit the existing implementation before rebuilding anything. Preserve all
   working authentication, jobs, applications, resumes, scheduler, API and
   Chrome extension behavior.
4. Make the smallest complete change, validate it locally and report exact
   results. Do not claim production success from a local development server.
5. Never deploy, migrate production, change DNS, start or stop schedulers, or
   perform destructive data work without the owner's explicit approval for that
   specific operation. Prepare a reviewable result before requesting approval.

## Non-negotiable owner requirements

- The owner explicitly requires both legacy and Oracle discovery systems to
  run during comparison. Each scheduler writes only its own database. The
  laptop's minute cross-database replica cron must remain disabled in this
  mode because job IDs have already diverged.
- Keep both databases intact. Compare outcomes by source identity and time,
  not by numeric job ID or identical total counts. Application changes are
  not synchronized between the two sites while the replica is disabled.
- Production data must come from the real backend. Never use counts, jobs,
  names, scores, health or resume content from the visual demo.
- Pulls is the authenticated landing page.
- Marking Applied must update the opportunity, navigation count, Applications,
  Pulls, Analytics and all other totals immediately, persist after refresh and
  roll back if the save fails. Avoid duplicate application counts.
- Use only the final Wine and Rose V2 design. Do not revive the anthracite
  prototype, old homepage, earlier auth prototypes or automatic cursor tour.
- Night uses deep wine and black. Day uses rose wine and bright white. Preserve
  the exact component geometry, hierarchy, gradients, artwork, typography,
  backgrounds, spacing and lowercase `ace` wordmark. The complete artistic A
  must fit within the desktop viewport on public and signed-out pages.
- No user-facing Unicode em dash is allowed. Avoid en dash punctuation and
  dash-like ornaments. Run static and browser checks across dynamic states.
- Do not expose secrets, personal data, resume text, answers, database dumps or
  session cookies in Git, logs, screenshots, issues or chat.

## Current live state on 2026-10-24

The currently deployed production application commit is
`11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`; schema is `0049 (head)`.
The latest deployment details are in the owner account release section below.

The owner clarified that the legacy site must keep discovering jobs until they
are confident in ACE Next. **Both `ace-scheduler-1` and `oracle-scheduler-1`
are running and healthy, each against its own PostgreSQL database.** The
minute cross-database replica cron is disabled. Do not restart it while both
schedulers run: Oracle produced 4,441 jobs and four Pull sessions during the
temporary cutover interval, so numeric IDs can now collide with future legacy
rows. The previous crontab is saved under
`/home/ubuntu/.local/state/ace-legacy-replica/crontab-before-cutover-20261023`.
Both websites remain available. Discovery results, application changes, and
marks on one site no longer sync automatically to the other. Compare matching
source identities and time windows; exact total counts are not an appropriate
parity signal in independent-discovery mode. Do not merge the databases or
re-enable the old replica without a new reconciliation plan.

### Application release on 2026-10-23

At `2026-10-23T23:10Z`, the owner-approved application release
`b8e30b0b4261257fea25fb8e46f03912c6811990` became live at
`https://ace.opik.net`. It includes Pulls `Early career`, `3 yrs max` and
`Applied before` badges, expanded-window persistence and the corrected
legacy-style sources-polling count. The public health endpoint returned OK
with that exact frontend commit. PostgreSQL, API and web were healthy, migration
was `0044 (head)`, and the privacy-safe inventory showed 963,970 jobs, 2,631
Pull sessions, 1,180 marks and one user. Both schedulers continued writing
fresh Pulls. The cloud scheduler retained its original container ID and stayed
healthy. The legacy scheduler was healthy; the historical replica cron stayed
disabled. The daily cloud backup timer remained active, with the verified
`ace-20261023T144522Z.dump.gz` backup present.

The first activation command omitted `docker compose --env-file .env`, causing
Compose to substitute blank database variables and begin recreating services.
That run was interrupted, then the same approved release was activated with
the explicit environment file. The database volume was not removed. Migration
exited zero and the post-release inventory and live health checks succeeded.
Always pass `--env-file .env` for the Oracle Compose file; its location under
`deploy/oracle/` does not automatically select the repository-root `.env`.
The deployment commands in `deploy/oracle/README.md` were corrected after
this incident. That correction reached the VM with the 2026-10-24 release.

### Autofill application release on 2026-10-24

The owner approved deploying the local autofill batch. Branch
`wine-rose-platform` was pushed, and `/opt/ace` was fast-forwarded to
`d1202fd1e590bc290e88c059109bb35ff114796c`. A fresh pre-release cloud
backup, `private-backups/ace-pre-autofill-20261024T172503Z.dump.gz`, passed
gzip and PostgreSQL archive-list checks. The versioned API, migration and web
images were built, then only PostgreSQL, migration, API, web and Caddy were
included in the activation command. Migration exited zero at `0048 (head)`.
At `2026-10-24T17:29Z`, `https://ace.opik.net/healthz` returned 200 with that
exact frontend commit. API, web, PostgreSQL and both independent discovery
schedulers were healthy; the Oracle scheduler kept its prior container ID.
The laptop's cross-database replica cron remained absent. The privacy-safe
cloud inventory showed 968,535 jobs, 2,704 Pull sessions, 871 applied job
marks, 47 external applications and one user. Cloud and legacy source states
both showed fresh writes after the release.

Migrations `0045` through `0048` added 33 blank answer rows. A separate
guarded transaction then saved 32 exact answers supplied in the owner's
screenshots, only where the matching row was still blank. No existing answer
was overwritten. The answer bank then had 104 rows, 98 filled. The owner
explicitly chose to leave `Eligible for bilateral visa classification` blank
for manual review. No personal answer text was committed to Git.

The web and API are live, but Chrome's unpacked extension is loaded from the
local `extension/` folder. The owner must reload its card at
`chrome://extensions` and reopen or refresh any application tab to use
extension version `1.25.0`. A website deployment cannot update an unpacked
browser extension by itself.

### Owner account release on 2026-10-24

The owner approved the account upgrade, including removal of the email line
beneath the sidebar name. Production was fast-forwarded to
`11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`. Before activation, a
fresh private backup,
`private-backups/ace-pre-owner-profile-20261024T215213Z.dump.gz`, passed a
complete gzip check and PostgreSQL archive-list check. The migration, API and
web images built for the exact commit. Only PostgreSQL, migration, API, web
and Caddy were included in Compose activation. Migration exited zero at
`0049 (head)`.

At `2026-10-24T21:57Z`, the public health endpoint returned HTTP 200 and
`X-Ace-Frontend-Commit` matched the deployed SHA. The API, web, PostgreSQL
and cloud scheduler were healthy. The cloud scheduler kept its prior container
ID. The privacy-safe inventory showed 968,903 jobs, 2,722 Pull sessions,
871 applied job marks, 47 external applications and one owner. The legacy
scheduler was healthy. Cloud and legacy source-state successes were recorded
at `21:57:55Z` and `21:57:54Z` respectively. The old replica cron remains
absent. Anonymous requests to the account and photo endpoints returned 401.
Authenticated Settings and photo interactions were validated locally with an
isolated demo database, not with the owner's production session.

### SmartRecruiters screening autofill release details

The owner supplied screenshots of ServiceNow screening questions and asked for
careful reuse across small wording and employer-name changes. The local
extension update `1.22.0` adds narrow rules for those questions and a dynamic
`Previously employed by Company Name` template. Named employers require a
separate saved answer. Government questions with different time windows,
export-control residency, and the ServiceNow RiseUp program have separate bank
rows. Migration `0045` added those rows blank before the guarded one-time
answer save described above. Signatures and privacy declarations remain manual.

### Workday history date autofill release details

The local extension update `1.23.0` writes native month inputs using their
required `YYYY-MM` value while Workday displays them as `MM/YYYY`. It matches
prefilled employers to saved work history before filling dates, leaves
unmatched or ambiguous jobs alone, and never overwrites an existing date.
An isolated Chromium test covers current and past jobs, out-of-order history,
manually entered dates, and an unmatched employer. The owner must reload the
unpacked extension and the Workday application tab to use this change.

### Workday education and screening autofill release details

The local extension update `1.24.0` selects a Workday Field of Study result
rather than leaving uncommitted search text. For saved `Computer Science`, it
can select Workday's `Computer and Information Science` option when that is
the unique match. Migration `0046` adds five distinct answer rows blank:
spouse-based work authorization, bilateral visa eligibility, current F-1
status, maximum OPT/CPT authorization end date, and Big Four employment in
the prior 18 months. The extension derives the numbered authorization and
sponsorship follow-up only from both saved underlying answers. Existing
answers cover work authorization, future sponsorship, relocation and onsite
availability. The role-specific minimum-experience confirmation remains
manual because it can change with each job. Native date inputs receive ISO
values and are confirmed before ACE reports success. Screenshot values were
not committed to Git. The owner-supplied values were saved separately after
the approved production deployment, except for bilateral visa eligibility.

### Meijer and Verizon Workday screening autofill release details

The local extension update `1.25.0` adds precise matching for the three
Meijer Workday screening pages. Migration `0047` adds 11 blank answer rows for
recruiting-text consent; Meijer group contractor and employment history;
Meijer recruiter contact, current contractor status and six-state residence;
current visa description and OPT status; AI engineering tools, Azure AI
experience range and AI coding tools. Existing saved answers still handle
work authorization, future sponsorship, relocation and hybrid work. The
extension selects the exact `18 years or older` option only when the saved
adult-status answer is Yes; it leaves narrower age bands for the owner.
Tests cover all three page shapes and prove unrelated broad answers leave
these narrower questions blank. Screenshot values were not committed to Git;
the exact saved answers were written to the private production answer bank
after migration.

The same local update covers the Verizon Workday question page. Migration
`0048` adds eight blank rows for authorization to work for any US employer,
current visa sponsorship, combined federal/state/local government employment,
combined non-compete and non-solicitation agreements, family or close personal
ties to an employee, a family board member, personal US military service and
spouse US military service. Future sponsorship and adult status use their
existing saved answers. Matching and browser tests keep each distinct fact
separate, including when only a broader answer has been saved. The owner's
answers shown in screenshots remain outside source code. The bilateral visa
eligibility answer remains blank at the owner's direction.

Earlier on 2026-10-23, the owner approved a cutover, but then clarified that
this did not authorize stopping legacy discovery during the comparison period.
Oracle discovery was briefly stopped and legacy discovery was restarted; Oracle
was then restarted with the replica still disabled. A `docker compose start
scheduler` attempt on the legacy stack ran its old migration dependency, which
exited 255; the legacy schema remained at `0040`, and the existing scheduler
container was started directly. Both schedulers were healthy and recording
fresh source successes at `2026-10-23T15:49Z`.
At `2026-10-23T15:50Z`, both websites returned HTTP 200, both schedulers were
healthy and writing fresh source successes, and the replica cron was absent.
The legacy database had 2,337 enabled of 2,446 sources; Oracle had 2,340 of
2,449. These counts can now change independently and are not a failed replica
signal.

During the temporary cutover, the cloud scheduler `oracle-scheduler-1` was rebuilt from deployed commit
`204f30c5c3712bc31ad89cbbfcafb19ca0f8f762`, started at
`2026-10-23T14:57:01Z`, and was healthy with fresh source successes after
startup. The production app and `/opt/ace` stayed at that commit until the
later application release above. Its database was at migration `0044`. The
Pulls fixes at `5f8ebff` and `d89fb6b` were not deployed by this cutover.
At `2026-10-23T15:00:19Z`, the cloud had created Pull session 2,599 and had
172 source successes since scheduler startup. The stopped legacy database
remained at Pull session 2,598, proving the new window was cloud-generated.

A fresh cloud backup at
`/opt/ace/private-backups/ace-20261023T144522Z.dump.gz` passed gzip and archive
checks and a full restore drill into a temporary database. The restored copy
contained 944,431 jobs, 2,597 Pull sessions, 2,444 job sources, one user, and
migration `0044`. The temporary database was removed. The supplied daily
`ace-backup.timer` is enabled and active. Offsite Object Storage is not
configured, so cloud backups currently reside on the VM; the intact legacy
database is the separate rollback copy.

After the legacy scheduler stopped, a final sync through
`2026-10-23T14:51:26Z` used the running legacy web container because the stopped
scheduler container could not execute the replica helper. The final parity
query matched all documented aggregate lines. A further full-corpus check
found 3,300 stale `jobs.source_updated_at` values in the cloud replica. Those
timestamps alone were copied from the frozen legacy database in one guarded
transaction, and final parity, full source-state and source-catalog hashes,
job counts/content hashes and all shared Pull-session fields matched afterward.
The inactive replica script can miss a full-job update when an ATS-provided
`source_updated_at` predates the sync interval; repair this selection rule
before ever resuming that workflow.

The public `https://ace.opik.net/healthz` returned HTTP 200 during the temporary cutover with
frontend SHA `204f30c5c3712bc31ad89cbbfcafb19ca0f8f762`; API, web, database
and scheduler were healthy. Continue monitoring both schedulers and the backup
timer. The cloud VM remains a single host and is not an absolute uptime
guarantee.

## Historical live state on 2026-10-22

The canonical production URL is `https://ace.opik.net`. Dynu provides the
hostname. Caddy terminates valid HTTPS and redirects the temporary sslip host to
the Dynu hostname. Users should always be directed to `ace.opik.net`.

The cloud host is the Oracle VM at `161.153.89.170`. The deployment checkout is
`/opt/ace`, accessed as `ubuntu` with the local key `~/.ssh/ace_oracle`. Do not
print or copy the key. Production uses `deploy/oracle/compose.yaml` and a mode
600 `/opt/ace/.env`.

The active branch is `wine-rose-platform`. The remote is
`https://github.com/anwarbuilds/ace.git`. Local, GitHub and the deployed checkout
were all verified at commit:

```text
132235c29212feb43f50f59245d540628172c43b
Show real resume files and owner identity
```

The response header `X-Ace-Frontend-Commit` and `/healthz` both reported that
full SHA after deployment. Alembic is at `0043 (head)`. PostgreSQL, FastAPI,
Next.js and Caddy were healthy. The migration job exited successfully. The
cloud scheduler was stopped and remained stopped.

The exact cause of the previously stale cloud interface was a deployment
checkout/build mismatch. Production was still at `16c1c82` while the approved
local and GitHub work had advanced through `bff2293` and `132235c`. A successful
local build or Git push did not update `/opt/ace` or replace its containers. The
fix was to push the approved branch, fast-forward `/opt/ace`, build images with
the SHA embedded, run migration 0043 and recreate only the production database
container, migration, API, web and Caddy dependency set. The named PostgreSQL
volume remained attached and the data inventory was verified afterward.

Latest privacy-safe production inventory after deployment and a successful
legacy replica replay:

| Data | Verified count |
| --- | ---: |
| Jobs | 904,107 |
| Active jobs | 640,223 |
| Poll sessions | 2,511 |
| Source states | 2,320 |
| Job sources | 2,385 |
| Job marks | 1,141 |
| Applied job marks | 821 |
| External applications | 47 |
| Application answers | 71 |
| Resume documents | 5 |
| Resume versions | 5 |
| Resumes | 5 |
| Career facts | 52 |
| Users | 1 |

These historical counts changed while the legacy scheduler and replica were
active. Compare settled pull boundaries instead of treating this table as a
frozen expected value.

The local file `ACE_NEXT_KNOWLEDGE.md` had intentional owner continuity edits
before the latest deployment and was kept out of commit `132235c`. Do not
discard this file merely because Git reports it modified. Review and commit it
only when the owner requests that documentation change to be committed.

## Product objective

ACE is a private career system for one primary owner. It continuously reads
approved employer sources, preserves every discovered posting, evaluates each
role against deterministic eligibility rules, tracks applications, scores jobs
against the active resume, supplies an answer bank to a least-privilege Chrome
extension, and presents the data through the approved Wine and Rose UI.

The production result must preserve all historical data and behavior from the
legacy ACE system. The UI changes, and new Resume Studio and Google sign-in
features are added, but the old data is not discarded or regenerated.

## Repositories and runtime state

The legacy checkout is `/home/ubuntu/Documents/ace` on branch `main`. Its
Docker stack is preserved for rollback. As audited on 2026-10-16, before
cutover:

- PostgreSQL 16 is healthy and published locally on port 5433.
- The legacy web service is available on port 8000.
- The scheduler is healthy and continues to poll.
- The database is at Alembic revision 0040.

The new checkout is `/home/ubuntu/Documents/ace-next` on branch
`wine-rose-platform`. It contains the approved Next.js interface, all existing
backend logic, Resume Studio, owner authentication, extension pairing, the
Pulls-first workspace and the Oracle deployment kit.

Do not rebuild or migrate the legacy stack during development. Keep its
scheduler stopped while Oracle writes. Never treat both databases as
authoritative discovery writers.

## Verified production data inventory

The 2026-10-16 audit used aggregate read-only queries. It did not read or print
resume text, answers, emails or job descriptions.

| Data | Audited count |
| --- | ---: |
| Jobs | 811,176 |
| Active jobs | 609,186 |
| Source states | 2,226 |
| Job sources | 2,284 |
| Job marks | 995 |
| Applied job marks | 708 |
| External applications | 47 |
| Application answers | 71 |
| Legacy resumes | 5 |
| Active legacy resumes | 1 |
| Poll sessions | 2,202 |
| Users | 1 |
| Active API tokens | 0 |
| Resume Studio documents | 0 |
| Career facts | 0 |
| Resume Studio versions | 0 |

This rehearsal snapshot represents 755 tracked applications through 708
applied job marks plus 47 external application rows. This is the confirmed
historical application total to preserve and verify during cutover.

## Architecture

```text
Employer ATS and official feeds
              |
              v
  long-running scheduler
              |
              v
         PostgreSQL
       /      |       \
  FastAPI  analytics  application history
      |
      v
  Next.js server
      |
      v
  Caddy HTTPS proxy
      |
      v
 Owner browser and paired Chrome extension
```

The scheduler, API, web app and PostgreSQL share one database. Next.js forwards
same-origin `/api/*` calls to FastAPI, so the browser does not need CORS. Caddy
terminates HTTPS. Only ports 80 and 443 are public. PostgreSQL and FastAPI stay
inside Docker's private network.

Docker services use `restart: unless-stopped`. Each scheduler persists its own
source state, respects per-source intervals, backs off on refusals and resumes
from its last successful poll after a restart. Both now run against separate
databases for the owner-requested comparison; cross-database replication is off.

## Data ownership and compatibility

The following legacy tables remain authoritative and are used directly by ACE
Next:

- `jobs`, `job_sources`, `source_states`, evaluations and match scores
- `job_marks` and `external_applications`
- `application_answers` and work and education history
- `poll_sessions` and source health telemetry
- `resumes`, including all five historical rows and the active row
- owner, browser session and extension token tables

The new UI reads real API aggregates. It does not use the fictional demo counts
in production. Demo data is created only by `backend.scripts.seed_demo` in a
separate database.

Migration 0041 adds nullable `users.google_subject`. Migration 0042 repairs the
Pulls telemetry columns needed by the V2 API. Migration 0043 adds the owner's
non-null `display_name` with a safe blank default. Existing password sign-in and
all existing data remain valid when Google is not configured.

The legacy resume bridge copies every `resumes` row into a Resume Studio
document and approved master version. It preserves the text, label, timestamp
and history. The active legacy resume becomes the primary Studio version only
when no Studio primary already exists. Suggested career facts are parsed from
that active resume for owner review. The bridge does not activate another
legacy resume and does not rescore jobs. It is idempotent and can be previewed
before commit.

```bash
python -m backend.scripts.backfill_resume_studio
python -m backend.scripts.backfill_resume_studio --apply
```

## Authentication

ACE has one owner. There is no public registration and no second-user data
scope. Passwords use Argon2id. Browser sessions are stored as hashes, mutation
requests require a per-session CSRF token, login attempts are throttled, and
extension tokens can read only answers and work or education history.

Password sign-in uses two steps in production. ACE verifies the password,
sends an eight-character one-time code to the owner's email, and creates the
browser session only after that code is confirmed. Sign-in and password reset
codes expire after 10 minutes, are stored only as SHA-256 hashes, are single
use, and have database-backed issue and guessing limits. Issuing a new code
cancels the previous live code. Password recovery asks for the email code
before accepting a new password, then revokes every existing browser session.

`REQUIRE_LOGIN_EMAIL_CODE=true` is set in the Oracle deployment template. It
makes password sign-in fail closed if Resend is unavailable or missing. Local
development can leave it false; when Resend is configured, the email step is
used regardless of this switch. This local fallback keeps fictional demo and
browser testing usable without sending real mail.

If the restored owner's email is not the desired daily login, run
`python -m backend.scripts.set_owner_email NEW_EMAIL` against the restored
target database. It renames the existing owner rather than creating another
one, preserves all product data, clears an earlier Google subject, revokes
browser sessions and consumes pending email codes. The address is deliberately
not stored in this public document.

Google sign-in uses the OpenID Connect authorization code flow. ACE requests
only `openid email profile`. The browser flow uses short-lived HttpOnly state
and nonce cookies. The API validates the Google signature, issuer, audience, expiration,
issued time, nonce and `email_verified` claim. The verified email must match the
existing active owner. The first successful login binds Google's stable
subject, and later logins must present the same subject. Google never creates
an ACE user. Google already verifies ownership of the email address, so ACE
does not send a second code after a successful Google callback. A verified
Google profile name fills a blank display name. It never changes the owner's
email or authentication scope.

Required cloud values:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=https://ace.opik.net/api/auth/google/callback
WEB_BASE_URL=https://ace.opik.net
REQUIRE_LOGIN_EMAIL_CODE=true
RESEND_API_KEY
MAIL_FROM
```

Secrets belong only in the server `.env`, with mode 600. Never put them in this
file, GitHub, an issue or chat.

Sign out revokes the server session and routes to the approved signed-out page.
The Chrome extension must be paired again after moving to a different ACE
origin unless its existing token and endpoint are intentionally migrated.

## Owner identity and real Resume Studio documents

Commit `132235c` replaced the generic sidebar identity with the authenticated
owner's display name and email. Setup now requires a full name. Settings has a
real My Account form backed by `GET /api/auth/account` and
`PATCH /api/auth/account`. The sidebar reacts to that persisted account state.
An existing owner created before migration 0043 starts with a blank display
name. Enter it in Settings or complete a fresh Google sign-in to populate it.

Resume Studio no longer fabricates a paper-like preview from extracted fields.
For a stored PDF, the page loads the authenticated document-content endpoint
and embeds the actual bytes through a short-lived browser Blob URL. Content
Security Policy explicitly permits same-origin and Blob frames. DOCX and other
non-PDF files show an honest download action because browsers cannot reliably
render them without conversion. Never substitute a generated dummy PDF for a
stored source document. The preview remains protected by the existing owner
session and does not expose a storage path publicly.

Key implementation files:

```text
backend/app/api/routers/auth.py
backend/app/auth/google.py
backend/app/auth/service.py
backend/app/db/models.py
backend/migrations/versions/0043_add_owner_display_name.py
web/src/components/pages/AccountSettings.tsx
web/src/components/shell/Sidebar.tsx
web/src/components/studio/ResumeDocumentPreview.tsx
web/src/app/app/resume-studio/page.tsx
web/src/app/app/settings/page.tsx
web/next.config.ts
```

## Applications and counters

Applications use real `job_marks.applied_at` plus `external_applications`.
Marking a job Applied updates the shell counter optimistically, synchronizes
tabs, persists through the API and refresh, and rolls back if saving fails.
Analytics and Pulls totals come from backend queries over the same PostgreSQL
database.

No application spreadsheet upload is present. Historical external applications
already in PostgreSQL are preserved through database restore.

## Local commands

The legacy production stack can keep running. Use different ports for ACE Next.

Terminal 1, isolated demo API:

```bash
cd /home/ubuntu/Documents/ace-next
.venv/bin/python -m backend.scripts.seed_demo \
  --database-url sqlite:///ace-demo.db
ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db \
  .venv/bin/uvicorn backend.app.api.main:app \
  --host 127.0.0.1 --port 18001
```

Terminal 2, new web app:

```bash
cd /home/ubuntu/Documents/ace-next/web
npm ci
npm run build
API_ORIGIN=http://127.0.0.1:18001 npm run start -- -p 3001
```

Open `http://127.0.0.1:3001`. The demo owner credentials are fictional and are
printed by the seed script. Never seed the production database.

Useful validation:

```bash
cd /home/ubuntu/Documents/ace-next
.venv/bin/python -m pytest backend/tests -q
node extension/test-rules.js
python scripts/no_user_facing_dashes.py

cd web
npm run typecheck
npm run lint
npm run build
npx playwright test
```

The latest account and real-document change passed a focused backend suite of
24 tests, TypeScript, ESLint, the production Next.js build, the source-level
forbidden-dash scan with zero hits, a disposable SQLite migration rehearsal
from 0042 to 0043, and focused Playwright runs in Night and Day. A temporary
generated PDF stored only in the disposable test database was rendered through
the real content path. Production then passed `/healthz`, container health,
schema and aggregate inventory checks.

Review screenshots are stored locally and contain no credentials:

```text
artifacts/account-resume-validation/dark/resume-studio.png
artifacts/account-resume-validation/light/resume-studio.png
artifacts/account-resume-validation/dark/settings.png
artifacts/account-resume-validation/light/settings.png
```

## Safe migration procedure

The migration has four phases.

### Phase 1: rehearsal while legacy stays live

1. Build and test ACE Next against fictional data.
2. Create a consistent PostgreSQL custom-format dump of the legacy database.
3. Restore it into an isolated PostgreSQL instance.
4. Run `alembic upgrade head` against the copy.
5. Capture aggregate inventory before and after restore.
6. Preview and apply the Resume Studio bridge on the copy.
7. Test every UI route, real totals, resume content, auth and extension pairing.
8. Perform a backup restore drill.

The 2026-10-16 rehearsal completed against a private read-only dump of the real
legacy database. PostgreSQL restored the dump without errors, migration 0041
applied, all five legacy resumes became five Studio documents and five approved
versions, one active resume became primary, and 52 suggested facts were created.
A second preview skipped all five resumes, proving idempotency. The live
scheduler remained running and wrote new rows after the dump snapshot, so an
exact comparison against a later live inventory correctly showed drift. Exact
source and target equality is checked during final cutover after the scheduler
write freeze.

After the email verification implementation, the full local validation passed:
1,191 backend tests, 89 Playwright browser tests, 185 extension matcher cases,
TypeScript, ESLint, the production Next.js build, and the source-level
forbidden-dash scan. The Playwright run used an isolated fictional SQLite
database and covered the sign-in code prompt and password reset code form.

`backend.scripts.data_inventory` writes only aggregate counts:

```bash
python -m backend.scripts.data_inventory --output /tmp/ace-before.json
python -m backend.scripts.data_inventory --compare /tmp/ace-before.json
```

The compare must run before Resume Studio backfill because that bridge is
expected to add rows to the three Studio tables.

### Historical phase 2: cloud rehearsal

Follow `deploy/oracle/README.md`. Keep the cloud scheduler stopped while the
legacy scheduler remains authoritative. Verify HTTPS, password sign-in, Google
sign-in, sign out, delivery of the password sign-in code, forgot-password code
delivery, Pulls, application counts, Analytics, Resume Studio, Answers, Settings
and extension pairing.

Before cutover, the local legacy host ran this cron every minute. It was
removed on 2026-10-23:

```text
* * * * * /home/ubuntu/Documents/ace-next/deploy/oracle/sync-legacy-replica.sh >> /home/ubuntu/.local/state/ace-legacy-replica/cron.log 2>&1
```

The replication script first copies newer user-managed application state from
cloud to legacy, then copies legacy discovery state to cloud. Timestamp guards
make newer edits win. A file lock prevents overlap, a five-minute replay overlap
covers transaction boundaries, all writes are idempotent, and the cursor moves
only after the cloud transaction commits. Relevant files:

```text
backend/scripts/legacy_replica.py
deploy/oracle/sync-legacy-replica.sh
deploy/oracle/replica-parity.psql
/home/ubuntu/.local/state/ace-legacy-replica/cursor
/home/ubuntu/.local/state/ace-legacy-replica/cron.log
```

During deployment on 2026-10-22, recreating the API container removed the
temporary `/tmp/legacy_replica.py` helper during one active sync. That run failed
safely, the cursor stayed at the prior boundary, and the next cron run replayed
the interval and advanced successfully through `2026-10-22T00:23:01Z`. This is
expected recovery behavior. After future API replacement, always verify that a
subsequent log entry says `ACE legacy replica synchronized through ...` and that
the cursor advanced. Never edit the cursor forward by hand.

`replica-parity.psql` compares settled pull sessions, complete job identities,
qualifying opportunities, enabled sources and user-managed application data.
Use the same successful cursor as the cutoff on both databases and compare the
output lines exactly. Mutable job and evaluation hashes may change beyond that
cutoff while the legacy scheduler is polling.

### Safe production release during independent comparison

Production deployment requires explicit owner approval each time. Before asking
for it, commit the complete change, run applicable tests, confirm the diff does
not contain secrets or unrelated owner edits, and prepare the exact commit SHA.

After approval:

1. Push `wine-rose-platform` without force.
2. On the VM, confirm `/opt/ace` has no conflicting tracked changes.
3. Fetch and fast-forward to the exact approved SHA.
4. Run `deploy/oracle/prepare-release.sh`. It builds `migrate`, `api` and `web`
   images and does not change running containers.
5. Set `ACE_BUILD_SHA` to the full approved SHA and bring up only the required
   `postgres`, `migrate`, `api`, `web` and `caddy` services using
   `docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build`.
   Do not recreate the
   scheduler as part of an ordinary web/API release; leave both discovery
   schedulers running against their respective databases.
6. Verify the migration exited zero, schema is at head, API/web/PostgreSQL are
   healthy, the cloud scheduler is running and healthy, `https://ace.opik.net/healthz`
   reports OK, and `X-Ace-Frontend-Commit` matches the approved SHA.
7. Run the privacy-safe data inventory, confirm fresh writes by both schedulers,
   and verify the cross-database replica cron remains disabled.

Do not use an unversioned web image. Do not assume a Git push deployed anything.
Do not run `docker compose down`, remove a volume, restore a dump, downgrade a
migration or alter the legacy stack as part of a normal frontend release.

### Historical phase 3: temporary cutover on 2026-10-23, then reversed

The existing cloud database had been continuously replicated and already
included the cloud-only owner and Resume Studio data. Cutover used a verified
cloud backup and isolated restore drill, disabled the minute cron, stopped the
legacy scheduler, ran one final sync, repaired the 3,300 stale source-update
timestamps, confirmed parity, then started the cloud scheduler. The legacy
database remained intact. No full restore was applied over the live cloud
database. The owner then clarified that both discovery systems must stay active
for comparison. The legacy scheduler was restarted, Oracle was restarted, and
the replica cron remained disabled because both databases now contain
independent discovery writes.

### Phase 4: rollback if required

Both systems currently discover independently. Any future switch to one writer
requires deciding how to reconcile job identities, Pull sessions, source state,
and application changes made in either database. Never re-enable the old
ID-based replica cron in independent-discovery mode. Its stale source-update
selection rule also needs repair before any future use.

## Oracle Free Tier operation

The production compose file is `deploy/oracle/compose.yaml`. It runs PostgreSQL,
one migration job, the scheduler, FastAPI, Next.js and Caddy. Full setup,
firewall, restore, Google and backup instructions are in
`deploy/oracle/README.md`.

Oracle's current Always Free documentation allows eligible Ampere A1 compute
within monthly OCPU and memory limits. The planned two OCPU and 12 GB VM fits
those published limits. Oracle may reclaim an idle free instance. Keep daily
backups and verify restores. The account owner must confirm every resource in
the Oracle console is labeled Always Free or Always Free eligible before
creation. Do not enable paid upgrades, paid load balancers or paid databases.

The backup script is `deploy/oracle/backup.sh`. It writes a mode 600 PostgreSQL
custom dump compressed with gzip, retains 14 days locally and can upload to a
private OCI Object Storage bucket when `OCI_BACKUP_BUCKET` is set and the OCI
CLI is configured. The deployment kit includes a 14-day Object Storage
lifecycle rule and a 15 GiB upload ceiling, leaving headroom inside Oracle's
published 20 GB Always Free Object Storage allowance.

## Deferred post-launch retention plan

Do not implement or run this cleanup during migration. Keep the legacy and ACE
Next databases complete through rehearsal, cutover and the rollback window.
Implement this plan only after ACE Next is live, its scheduler and application
history have been verified, and a tested backup exists.

The owner approved a bounded hot-job retention policy to control PostgreSQL
growth without losing application history. The expiration clock is based on a
job's confirmed closure, never its posted date. A posting more than 30 days old
can still be open and must remain available.

Aggregate read-only measurements on 2026-10-19:

| Data | Count or size |
| --- | ---: |
| Total jobs | 845,152 |
| Active jobs | 616,701 |
| Active jobs older than 30 days by posted or first-seen time | 253,713 |
| Closed, unmarked jobs closed more than 30 days ago | 11,379 |
| Job marks | 1,049 |
| Applied job marks | 756 |
| `jobs` total relation size | 2,115 MB |
| `job_evaluations` total relation size | 411 MB |
| `job_resume_scores` total relation size | 180 MB |
| Whole PostgreSQL database | 2,731 MB |

The active backlog must be audited before pruning. The largest groups of
active jobs older than 30 days were Workday 131,192, Oracle Recruiting 40,625,
Greenhouse 34,892 and SmartRecruiters 24,478. Some may be legitimately open;
others may expose source-specific closure gaps. Never infer closure merely from
age, and never mass-close from an empty, partial, refused or failed response.

Retention rules approved for later implementation:

- Keep every active job, regardless of age.
- Keep full job details forever for applied jobs and every application status,
  including screening, interviewing, offer, rejected and withdrawn. The 756
  applied records are negligible compared with the job corpus and remain useful
  application evidence.
- Keep saved jobs and jobs referenced by tailored resume versions or resume
  assessments.
- Protect every manually authoritative mark from automated deletion.
- Delete an unmarked job only after the source has confidently confirmed it
  closed and it has then remained closed for 30 days.
- Delete derived evaluations and resume scores with an eligible deleted job.
- Preserve a compact tombstone before deleting an unmarked job. It must retain
  source, source account, external ID, company, title, content hash, first seen,
  last seen and closed time so an old posting cannot silently return as new.
- Preserve historical analytics in daily aggregate rollups by source, company,
  eligibility and job state before individual history is pruned.
- Keep scheduler source state permanently. Give temporary employer-page
  readings and operational logs their own bounded retention windows.

Implementation order after launch:

1. Audit old active records and correct source-specific closure detection.
2. Add explicit protected-job predicates and tests.
3. Add compact tombstones and teach discovery to consult them.
4. Add daily historical metric rollups and make analytics use them where
   retention would otherwise change historical totals.
5. Add a cleanup command whose default is dry-run and whose report gives counts
   by reason and protected category.
6. Prove that all applied, saved, manually marked and resume-linked jobs are
   excluded from deletion.
7. Take and restore-test a backup before the first real cleanup.
8. Delete in bounded batches, then run `VACUUM (ANALYZE)`. Use a separately
   planned compaction operation only if disk space must be returned to the
   filesystem; ordinary deletion and vacuum primarily make space reusable by
   PostgreSQL.

This policy reduces disk, index, backup and query growth. It does not reduce
the external polling work required to discover jobs, which remains controlled
through source intervals, conditional HTTP requests, backoff and bounded
concurrency.

## Git and GitHub

The configured remote is `https://github.com/anwarbuilds/ace.git`. The working
branch is `wine-rose-platform`. Never commit `.env`, database dumps, private
screenshots or personal data. Run a secret and personal-data diff review before
push.

Git push over the configured HTTPS remote was working on 2026-10-22. Do not
assume credentials remain valid forever; diagnose an actual authentication
failure if one occurs. Do not force-push. Do not merge this branch to `main`
until the owner completes the multi-day legacy comparison and explicitly
approves that merge.

## Outstanding owner decisions and monitoring

The owner wants both legacy and Oracle discovery running until they trust ACE
Next. Monitor scheduler health and comparable source/time-window outcomes on
both sites. Keep the old replica cron disabled because discovery IDs diverged.
Application changes on one site do not sync to the other in this mode.
The owner clarified on 2026-10-23 that they will record new applications in
ACE Next only. Legacy is an independent discovery validation backup. Do not
merge job rows across databases, because doing so would mask missed results.
On 2026-10-23 both scheduler containers were healthy and both health endpoints
returned 200. A read-only job-identity inventory found 944,901 common jobs,
4,157 cloud-only jobs, 119 legacy-only jobs, and 497 numeric job IDs that point
to different jobs in the two databases. The historical ID-based replica now
has a fail-closed guard when Oracle discovery is running. The private inventory
tool in `backend/scripts/discovery_inventory.py` makes this check repeatable.
`backend/scripts/discovery_parity.py` and
`deploy/oracle/compare-independent-discovery.sh` now produce a private,
read-only report of source coverage, fifteen-minute Pulls, qualifying jobs,
unmatched identities, and eligibility differences. The first live report
compared from 08:45 to 09:25 Pacific and found 244 legacy-only and 352
ACE Next-only recent jobs, with no different eligibility decisions among jobs
discovered by both. All four qualifying unmatched jobs were still awaiting a
source check by the other engine, so none was established as a missed job.
One hour later, a second comparison found that 238 of those 244 legacy-only
jobs and 271 of those 352 ACE Next-only jobs had appeared on both sides. The
latest report is `private-reports/latest/report.md` and its complete JSON is
next to it; the folder is private and Git-ignored. A local read-only cron
checks every 15 minutes and produces a full report at most every four hours,
including after a laptop reconnect. It neither changes database rows nor
starts or stops discovery schedulers. The former crontab was saved under
`~/.local/state/ace-discovery-parity/` for rollback. The old replica cron
remains absent.
Legacy has no `sources_attempted` column; the report uses the shared
`boards_checked` measure and labels unavailable attempts as not recorded.
See `deploy/oracle/README.md` for the read-only comparison command and report.
The backup timer is active, but Object Storage offsite backup is not configured.
Arrange an offsite copy if protection against loss of the Oracle VM is desired.
The Pulls badges, expanded-window persistence, and source-count fixes were
deployed in `b8e30b0b4261257fea25fb8e46f03912c6811990` on 2026-10-23.
Do not merge ACE Next to legacy `main` without separate approval.

## Change log

### 2026-10-24, owner account release

- Extended the existing owner account with first name, last name, phone number
  and a private profile photo. Added an additive migration (0049), owner-only
  profile endpoints, and current-password plus email-code verification for
  changing the ACE sign-in address. Gmail connection remains separate.
- Deployed the account change at the approved commit shown above. See
  `docs/architecture/2026-10-24-owner-profile.md` for behavior and rollback
  details. Both discovery schedulers and databases remain independent.

### 2026-10-23

- Restored the owner's intended comparison mode after they clarified that
  stopping legacy discovery was premature. Both schedulers are healthy against
  separate databases. The old replica remains off to prevent ID collisions.
- Recorded the owner-approved one-writer cutover to Oracle discovery, final
  replica cursor, parity evidence and intact legacy copy. This was subsequently
  reversed for independent comparison at the owner's direction.
- Recorded the fresh cloud backup, successful isolated restore drill and active
  daily backup timer. Offsite backup remains unconfigured.
- Recorded the replica edge case affecting 3,300 source-update timestamps and
  its guarded, timestamp-only repair before the cloud scheduler started.
- Clarified that normal app releases must leave the now-running cloud scheduler
  healthy and that the pending Pulls UI release remains separate.

### 2026-10-22

- Recorded the canonical Dynu production URL, Oracle deployment path, deployed
  SHA, migration revision, health evidence and post-deployment aggregate data
  inventory.
- Recorded the exact stale-interface cause: the production checkout and images
  had not advanced with the approved branch.
- Documented the one-writer monitoring architecture, minute replication flow,
  parity boundary rules and safe retry observed during API replacement.
- Documented real stored PDF rendering, non-PDF download behavior, My Account,
  persisted display names and verified Google profile-name import.
- Added the safe release procedure and reaffirmed that normal releases must not
  start the cloud scheduler or alter the legacy stack.
- Replaced obsolete cloud-provisioning actions with the current multi-day
  parity-monitoring and final-cutover decisions.

### 2026-10-19

- Recorded the owner-approved post-launch job retention plan.
- Confirmed that applied records must not be deleted through the current
  `job_marks.job_id` cascading foreign key.
- Replaced the proposed posting-age deletion rule with confirmed-closure plus
  30 days, protected full application history, tombstones and analytics
  rollups. No cleanup was executed.

### 2026-10-16

- Audited the legacy Docker runtime and database with aggregate-only queries.
- Confirmed the legacy database already contains migrations through 0040.
- Confirmed ACE Next preserves the complete legacy backend and includes the
  later bounded resume scoring change.
- Added migration 0041 for a bound Google owner subject.
- Added owner-only Google OpenID Connect with full token verification, secure
  cloud cookies and honest unavailable UI state when configuration is absent.
- Added email verification codes for password sign-in and password recovery,
  including expiration, single use, resend replacement, guessing limits and a
  production fail-closed switch.
- Confirmed that 755 is the complete historical application total to preserve:
  708 applied job marks plus 47 external application rows. Removed the earlier
  incorrect estimate from the migration plan.
- Added the idempotent legacy resume to Resume Studio bridge.
- Added privacy-safe source and target inventory tooling.
- Added the Oracle production Compose, Caddy HTTPS, backup script and operating
  guide.
- Bounded offsite backup retention with a 14-day lifecycle rule and a hard
  upload ceiling so ACE backups cannot silently consume the full free quota.
- Completed a migration rehearsal from a private dump of the real database.
  Restore, migration and the five-resume Studio bridge succeeded. Temporary
  dump and rehearsal database files were deleted afterward.
- Kept the live legacy stack and database untouched.
