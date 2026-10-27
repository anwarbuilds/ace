# Adopt answers and reuse compatible context, 2026-10-26

Status: **API deployed with the owner's explicit approval**, source
`9d05673248ce6ead30652e62bb1d5e569404848c`, activated
2026-10-27T00:57:27Z (2026-10-26 17:57 Pacific). Extension source is **1.30.0**;
the owner still needs to Reload the unpacked extension and refresh employer
tabs. No Web Store publication or migration. Website remains `1fee671`.

## Owner decision and cause

The owner reported repeating screening questions despite having completed them
on earlier applications and requested adoption and reuse when meaning/context
match, without requiring identical wording. This supersedes the blanket ban on
reusing the specific factual binary screenings described below. It does not
approve indiscriminate sensitive reuse, company substitution or employer-motivation
capture. Filling remains explicit, from Fill, toolbar Fill or Alt+A.

The previous API rejected protected/company questions outright. Earlier extensions
can acknowledge their completion on one form but cannot save them for the next.
Routine equivalence also accepts few paraphrases; identical duplicate records
were treated as conflicts. Finally, a committed answer entered before the Memory
response was ready was not retried after connection.

## Final behavior

- Real committed applicant edits under the existing auto-save setting can save
  eligible answers without duplicate approval. A delayed Memory connection
  retries the still-current trusted edit. It never starts a passive fill.
- Existing native/custom control adapters must verify actual committed state.
  Only successful private saving earns the compact "saved for next time"
  receipt. Failed saving preserves local completion, explains the failure and
  provides Retry. Unknown options and uncommitted search text stay unlearned.
- Common routine prompt and verb variations match while question type,
  negation, numeric values and timeframe qualifiers remain significant.
  Identical duplicate answers can resolve; disagreeing records require correction.
- The reviewed binary screening catalog covers exact two-status/four-status US
  eligibility questions, combined present/future visa sponsorship, named-employer
  work relationships, temporary-work history, interview history, a 12-month
  agency-submission question and the complete current/former-employer
  post-employment-obligations question. It does not derive a compound answer from
  a narrower stored fact or generalize a simple non-compete answer to all duties.
- Named employer and subsidiary scope remain part of identity. Previous and
  ever scopes differ. Relative company wording and an unspecified work country
  bind to the original hiring tenant/site. Shared Greenhouse/Lever/Ashby/etc.
  hosts use their tenant path; Workday site paths and Oracle sites stay separate.
  Explicit US sponsorship wording stays distinct from unspecified-country wording.
- The new `scoped` Memory policy requires the reviewed fact, exact computed
  concept/scope and an exact Yes/No answer. Ordinary answers retain the existing
  `reusable` policy. The existing `reuse_policy` column is sufficient; no schema
  change. Old entries are retained. No answer-bank/history rows are rewritten.
- Corrections and deletion invalidate the current form's reuse copy. Existing
  employer values are never overwritten. Memory edits retain revision guards.
- Motivation is excluded before reading any value. Attestations, signatures,
  consent, demographic questions and unsupported protected facts remain manual.
  No submit, navigation, Applied, permission or Gmail behavior is added.

Previously rejected saves cannot be reconstructed from past closed forms.
Existing saved profile facts still work. A newly eligible answer must be
committed once with the updated API/extension before later reuse is available.

## Validation and boundaries

- 82 fictional DOM contracts pass against actual extension scripts, including
  cross-application adoption, company/subsidiary/status isolation, implicit ATS
  tenant isolation, late connection, save failure, Workday-style custom choice
  to native choice transfer and correction of an earlier form copy.
- 173 fictional backend Memory/auth/logo tests pass. Shared JSON cases check
  JavaScript/Python scope parity, endpoint idempotency, policy, authentication,
  invalid/unsafe facts and revision conflicts.
- 258 matcher cases, Memory safety/scope/paraphrase checks, JavaScript syntax,
  TypeScript, lint, zero-hit forbidden-dash scan and whitespace checks pass.
- Browser cases are collection only. Chrome remains prohibited by cooling;
  actual employer DOM, installed MV3 behavior and new visual screenshots are
  not verified. No source assertions are called production verification.

Changed runtime files: `extension/{memory,content}.js`, manifest and the existing
Memory input/write handler in `backend/app/api/main.py`, plus
`backend/app/answers/screening.py`. Tests and supporting documentation accompany
those changes. The website, logo service, discovery, existing Inbox work,
authentication model, schema and application tracking are preserved.

## Approved production release, 2026-10-26

The owner explicitly said "Deploy." after the prepared change was presented.
PR #5 was integrated by fast-forward into `wine-rose-platform` at `9d05673`.
A fresh private PostgreSQL backup passed gzip and restore-catalog verification:
`/opt/ace/private-backups/memory-context-20261026/database.dump.gz`,
470,305,554 bytes. The previous API image is retained as
`oracle-api:before-memory-context`. No data restore was performed.

Built only the API image, then activated it with
`docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build --no-deps --wait --wait-timeout 180 api`.
The running healthy API matches the prepared image ID
`sha256:f0a2546982ff00316276f71081654dff70ef01ec35fd393da6a93814855aede3`.
Running `main.py`, `screening.py`, branding discovery and source hashes match
local tested source. Web, scheduler, PostgreSQL and Caddy container IDs and
private environment checksum stayed unchanged. Schema remains `0050`; no
migration, scheduler invocation, Gmail sync or employer submission was run.

Before/after release aggregate counts were identical: 1,231 job marks, 892
Applied marks, 47 external applications, 104 answer-bank rows, 67 Memory rows,
111 career facts, 2 history entries, 5 resumes, 6 resume documents, 6 resume
versions and 1 user. These are timestamped checks, never UI constants.

Public HTTPS verification completed 2026-10-27T00:59:08Z:

- `/healthz` returned 200 with healthy API and unchanged web SHA `1fee671`.
- Anonymous Memory access returned 401. Temporary owner-session access returned
  200 with no-store and 67 existing records; no answers were printed.
- Intentionally invalid fictional scoped and reserved-namespace writes returned
  the new handler's specific 422 refusals without saving a record. Memory count
  remained 67. Each temporary verification session was revoked in `finally`.
- Signed-in Pulls, Inbox and Analytics returned 200. The five new company logo
  assets still matched local hashes.
- All 20 focused screening tests passed inside the running API image against
  isolated fictional SQLite fixtures. The test process overrides the inherited
  production email-code requirement and web URL to local fixture settings;
  service configuration is unchanged. The initial run without these overrides
  passed 18 catalog cases but failed two pairing fixtures before reaching the
  handler. This was a test-environment issue, not a production sign-in change.

The API now accepts eligible private scoped saves. The installed browser build
and actual Workday interaction remain unverified; no Chrome was launched due
to cooling restrictions. Reload 1.30.0, refresh the employer tab, keep auto-save
enabled and commit an eligible answer once. Confirm "saved for next time";
use explicit Fill on the next context-compatible question. Previously rejected
saves cannot be recovered from closed forms. Reliable-Inbox P1 to P6 remain an
unimplemented plan; this release does not implement or activate that work.
