# ACE Next knowledge

Last updated: 2026-10-16

This is the continuity document for the production migration from the legacy
ACE runtime to ACE Next. It contains architecture, verified state, operating
commands, migration controls, deployment steps and remaining owner actions.
It intentionally contains no email address, resume text, answers, credentials
or database dump content because the GitHub repository is public.

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
Docker stack is the current local production system. As audited on 2026-10-16:

- PostgreSQL 16 is healthy and published locally on port 5433.
- The legacy web service is available on port 8000.
- The scheduler is healthy and continues to poll.
- The database is at Alembic revision 0040.

The new checkout is `/home/ubuntu/Documents/ace-next` on branch
`wine-rose-platform`. It contains the approved Next.js interface, all existing
backend logic, Resume Studio, owner authentication, extension pairing, the
Pulls-first workspace and the Oracle deployment kit.

Do not stop, rebuild or migrate the legacy stack during development. Do not run
the new scheduler against a separate writable copy and treat both copies as
authoritative. Final cutover has one short write freeze and a rollback path.

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

Docker services use `restart: unless-stopped`. On the Oracle VM, the scheduler
continues running when the laptop is asleep. The scheduler persists its source
state, respects per-source intervals, backs off on refusals and resumes from
the last successful poll after a restart.

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

Migration 0041 adds nullable `users.google_subject`. Existing password sign-in
and all existing data remain valid when Google is not configured.

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
only `openid email`. The browser flow uses short-lived HttpOnly state and nonce
cookies. The API validates the Google signature, issuer, audience, expiration,
issued time, nonce and `email_verified` claim. The verified email must match the
existing active owner. The first successful login binds Google's stable
subject, and later logins must present the same subject. Google never creates
an ACE user. Google already verifies ownership of the email address, so ACE
does not send a second code after a successful Google callback.

Required cloud values:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=https://YOUR_DOMAIN/api/auth/google/callback
WEB_BASE_URL=https://YOUR_DOMAIN
REQUIRE_LOGIN_EMAIL_CODE=true
RESEND_API_KEY
MAIL_FROM
```

Secrets belong only in the server `.env`, with mode 600. Never put them in this
file, GitHub, an issue or chat.

Sign out revokes the server session and routes to the approved signed-out page.
The Chrome extension must be paired again after moving to a different ACE
origin unless its existing token and endpoint are intentionally migrated.

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

### Phase 2: cloud rehearsal

Follow `deploy/oracle/README.md`. Keep the cloud scheduler stopped while the
legacy scheduler remains authoritative. Verify HTTPS, password sign-in, Google
sign-in, sign out, delivery of the password sign-in code, forgot-password code
delivery, Pulls, application counts, Analytics, Resume Studio, Answers, Settings
and extension pairing.

### Phase 3: final cutover

1. Stop only the legacy scheduler.
2. Take the final dump and inventory.
3. Restore to cloud and run migrations.
4. Compare aggregate inventories.
5. Run the Resume Studio bridge.
6. Start API, web and Caddy, then verify the owner workflow.
7. Start the cloud scheduler.
8. Confirm fresh poll sessions and scheduler health.
9. Keep the old database intact and scheduler stopped during the rollback
   window.

### Phase 4: rollback if required

Stop the cloud scheduler, return DNS to the old service if it was changed, and
restart the old scheduler against the untouched old database. Do not merge two
databases that both accepted writes after cutover without a separate conflict
analysis.

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

## Git and GitHub

The configured remote is `https://github.com/anwarbuilds/ace.git`. The working
branch is `wine-rose-platform`. Never commit `.env`, database dumps, private
screenshots or personal data. Run a secret and personal-data diff review before
push.

At the 2026-10-16 audit, GitHub CLI authentication for `anwarbuilds` was
invalid. Local work can be committed, but pushing requires the owner to run:

```bash
gh auth login -h github.com
gh auth status
git push -u origin wine-rose-platform
```

Do not force-push. Merge to the deployment branch only after the migration
rehearsal and review.

## Information still needed from the owner

The code can be completed and tested without sharing secrets. Cloud activation
and live cutover require these owner actions:

1. Create or identify the Oracle Cloud Always Free tenancy and home region.
2. Choose a domain or subdomain and point it to the VM after provisioning.
3. Create the Google OAuth Web client after HTTPS is available.
4. Enter Oracle, Google, database and required Resend secrets directly into the
   VM `.env`.
5. Reauthenticate GitHub CLI locally.
6. Approve the final scheduler write freeze and production cutover after the
   rehearsal report is reviewed.

## Change log

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
