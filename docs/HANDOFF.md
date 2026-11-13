**Sources fix, November 12 Pacific:** three new grad roles the owner found by hand (Jamf, Dassault Systemes, Corpay) led to two releases, live since 2026-11-13T03:20Z on API and scheduler `ea0b0f1` (PRs #57 and #58, full CI on each). The lead check now adds a good board instead of leaving it waiting for an approval no screen offers (28 added on its first run, Jamf included); a board held twice under other capitals no longer hides the enabled copy; Dassault's careers sitemap is read with the full page description; Dayforce (Corpay's US roles) refuses automated reads and is named, not read. The owner's Jamf and Dassault roles are stored and pass. Proof under `/opt/ace/private-backups/sources-release-20261113T{0239,0315}Z/`; run each folder's `status.py` after any interruption.

**Chat 4 complete, November 10 Pacific:** DIS-04 (Workday tenants with a hyphen are read at their underscore address; seven boards restored; 3,747 stale open jobs on three switched-off duplicate boards closed with owner approval), DIS-07 (Radancy `/en/job/` paths; UnitedHealth, Moody's, L3Harris, Takeda added as an owner-approved batch) and DIS-13 (explained; capped Workday boards cannot close old postings, documented) are done. API and scheduler run `bf75f86` with ten workers and every one-request board at fifteen minutes since 19:52Z; the one-hour measurement passed at 21:03Z (quick boards wait 22 s instead of 92; 222 reads a minute instead of 178; new jobs typical 7.2 min). A wrong learned language-fluency answer was corrected at the owner's request. Proof under `/opt/ace/private-backups/chat4-*-20261110T*/`; after any interruption run each folder's `status.py`.

**Chat 4, part 1, November 10 Pacific:** capacity before growth (OPS-05, DIS-01) is live and verified. PR #55 (tested `e923b48`, full CI `42730614093`: 3,368 backend with two PostgreSQL-only skips, web, browsers 47/59/211 with none skipped) gives boards fair turns (a board starts only when a worker is free, oldest due first, Workday at most 5 and Oracle at most 2 at once), keeps Workday list dates steady (they had made 97% of Workday postings look edited on every read), stops rewriting unchanged postings on every read (last-seen refreshed at most hourly) and adds the owner-approved "Can ace keep up?" box on Coverage, Sources. API and scheduler run `e923b48` since 2026-11-10T02:21Z/02:22Z; the capacity acceptance passed at 04:22Z (quick boards wait a median 20 s instead of 257; 187 reads a minute instead of 151; new jobs typical 8.8 min, 9 in 10 within 16.2; no unexpected error; owner rows, polling settings, Pear, configuration and public checks held). Web `e923b48` since 13:13Z. Proof and rollback: `/opt/ace/private-backups/chat4-capacity-release-20261110T0213Z/`; after any interruption run that folder's `status.py` first. DIS-04, DIS-07 and DIS-13 continue in Chat 4.

# ACE current handoff

**After Chat 3, November 9 evening Pacific:** the owner asked to close the last Chat 3 gap. PR #52, merged as main `3200f0c` after full hosted CI `42702946328`, holds the Workday date fix (extension 1.31.8) and the ELG-05 source fix: feed postings on TikTok, ByteDance, Amazon, Apple and Google are judged on the description ACE already stores from that employer's own system. The owner's visa question, the source health check and the remaining limits are at the top of `ACE_NEXT_KNOWLEDGE.md`; numbers are private in requirements 13.5. The owner approved the release: API and scheduler run main `e25919a` since 2026-11-09T22:42Z, and the final check passed at 23:13Z (every targeted feed posting re-judged and verified, visa-limited copies now reject, owner rows, polling, Pear protection, configuration and public checks held). Proof and rollback: `/opt/ace/private-backups/elg05-release-20261109T2231Z/`. Chat 3 is complete; Chat 4 has not started.

**Workday date fix, November 9 Pacific:** extension source 1.31.8 fixes the self-identification Date that showed today's digits while Workday reported it required. Workday saves its date only when focus leaves the whole box and reads it as of its last screen update; ACE left the box before Workday updated. ACE now writes the whole date through Workday's paste handling after the rest of the form, waits, leaves the box and checks Workday's hidden "current value is" note; Undo uses Workday's cut handling. A new faithful local harness reproduces the old failure and passes with the fix. Extension only, no server change. The owner must Reload ACE; the real-form check is unverified until then. Details: `docs/knowledge/06-extension-autofill.md`.

**Chat 3 gate installed, November 8 Pacific:** API/scheduler run exact tested `9c45ddd`, gate `2026-11-08-v67` and roles v8 from PR #48. Full CI passes 3,300 backend cases (two PostgreSQL-only skips), web and all 316 hosted browser cases; 733 focused fictional cases also pass in the exact image. The reviewed read-only corpus, fresh checked backup, isolated restore, installed backend hashes and protected owner/source/configuration checks pass. One guarded rollback was traced to the same upstream Workday 410 on the old image; preservation was verified before a fresh release.

**Chat 3 accepted, November 9 Pacific.** ELG-02, ELG-03 and ELG-04 are live and verified on gate `2026-11-08-v67` and roles v8 (API/scheduler `9c45ddd`). A read-only classifier explained every residual stale evaluation: the right v67 decision stored under a recomputed hash while the job row kept a hash from an older formula. After a fresh checked backup and isolated restore drill, a guarded, bounded repair through the existing `refresh_stale_evaluations` changed only `content_hash` and `evaluated_at` in `job_evaluations` on proven rows: no decision, job, source, owner or alert write and no gate change. A new final acceptance (`final3`; two earlier failed attempts are kept as receipts) passed: zero stale rows, all and active, in both services; every acceptance and control case and the older Simplify marks; protected owner rows with each change positively attributed (the owner's learned-answer saves and one Inbox automatic rejection with Undo); one Gmail lease; normal polling; log-proven cadence promotions; Pear protection; configuration; public health, auth, assets and 85 logos. No schema, screen or configuration change; host enforcement stays off. ELG-05 stays OPEN by owner choice: older marks work, recent upstream marks are missing. New fictional tests: `backend/tests/test_refresh_stale_evaluations.py`. Follow-up for the next gate release: the backfill CLI still recomputes hashes and would recreate this residue. A few active jobs sit on boards with no good read since September (chat 4, DIS-04). Private proof: `/opt/ace/private-backups/chat3-residual-20261109T1524Z/` and `artifacts/requirements-chat-3-20261107/residual-20261109/`. SmartRecruiters real-form acceptance remains owner-deferred and unverified. Chat 4 has not started.

**SmartRecruiters saved, November 7 Pacific:** PR #36 merged as `bd2997c`; extension source is 1.31.7. Final PR CI `42409518844` and main CI `42410529148` passed: backend/web and 316 hosted browser cases, no browser skips. Local 267 rules, Memory and 118 fictional DOM cases pass. Open shadow-root fields are found/named and explicit native Fill/Undo is proven; ACE’s own cards are excluded. Motivation/sensitive rules, no-submit/no-Applied and quiet non-application behavior remain. The approved zero-question card disables Fill. The owner deferred the real-form check because no SmartRecruiters form is available, plans to Reload ACE and will report recurrence; installed 1.31.7 and real-form acceptance remain unconfirmed. Request private Copy field diagnostics if it fails. Inherited custom button-listbox Undo limitation remains. Chat 3 has not started: ELG-02 through ELG-05 and the borderline-role decision await its separate request. Workday issues/new platforms stay P2. No local Chrome, server release or website runtime change. Private evidence and next-chat prompt: `artifacts/requirements-smartrecruiters-20261107/`.


**Cleanup complete, November 7 Pacific:** the approved one-row recovery, label correction and duplicate-board retirement are verified. The owner chose to keep the reviewed shared board polling for now; it remains unchanged and its ownership concern stays open. Existing job identities, history, marks and applications are preserved. No chat 3 or SmartRecruiters work was started. The separate SmartRecruiters P1 fix requires its own owner-requested chat. Private proof: `artifacts/verify-chats-1-2-20261106/cleanup-progress.md` and requirements 13.5.

**Chat 2 repair live; approved small cleanup complete.** The final Workday correction is live and verified at 2026-11-07T03:39Z, backend fbc44f9. Feed, batch and paste support ordinary readable boards, including short Workday tenants, without inventing employer ownership. An exact address without owner evidence remains unverified in source provenance and cannot inherit sponsorship. Conflicting/shared/failed evidence, the known vendor-board trap and mismatched addresses stay blocked. Existing enabled polling settings, manual Undo, cadence, Pear protection, web 1a08549, schema 0051 and configuration are preserved. No screen or migration change.

Concurrent extension usage caused one safe scheduler rollback. A timestamp-only audit and 57 fictional recovery-guard tests proved normal usage clocks can advance while every owner fact remains strict; a distinct fresh recovery checkpoint passed. Validation: 297 affected local cases, complete hosted backend 2,789 passed with two PostgreSQL-only skips, hosted browser sequence 47/59/206 without skips, read-only previews, fresh checked backup and isolated restore, 211 fictional cases against the built image, exact installed backend hashes, protected records, normal recovery polling and public health/auth/assets. Local full/API route runs stalled and were stopped; complete hosted tests passed. The owner approved restoring the previously deferred board using an existing complete successful read. The one-row recovery and its first normal poll passed, preserving hourly polling, unverified ownership and all other sources; no forced site read or service restart ran. Details, proof and rollback are private at `/opt/ace/private-backups/chat2-repair-20261107T0330Z/` and `artifacts/requirements-chat-2-repair-workday-20261106/`. Never replay completed operators. The one-time shared-board sweep is complete and its suspects are with the owner, unchanged. Signed-in production UI and positive real sponsorship remain unverified. PR #33 contains source and continuity; consult requirements 13.5 before chat 3.

Updated November 6 Pacific after requirements chat 2 completed live verification. This is
the current starting point; the [previous handoff](archive/HANDOFF-before-consolidation-20261030.md)
is preserved as history. Read **all** of [ACE_NEXT_KNOWLEDGE.md](../ACE_NEXT_KNOWLEDGE.md),
[AGENTS.md](../AGENTS.md) and the relevant [knowledge topic](knowledge/README.md)
before changes. Dated pending instructions are not current authorization.

## Requirements programme: start here for new work

New work follows `docs/requirements/2026-11-04-ace-requirements.md`, starting at its section 13:
working method, eleven-chat P0 plan, P0 in simple words and tracker. That file stays out of Git by owner
decision, because this repo is public. `ACE_NEXT_KNOWLEDGE.md` now holds current state, rules and an index;
its full history moved word for word to `docs/archive/ACE_NEXT_KNOWLEDGE-history.md`.
Designs are on a private canvas linked from the top of `ACE_NEXT_KNOWLEDGE.md`. Each chat explains its
items in very simple words, one item and one question at a time, agrees any interface change with the
owner, builds item and interface together, and saves progress before it ends.

## Original requirements releases (superseded by the repair above)

Read-only status recheck at 15:56Z on November 6 confirmed the deployed services healthy and chat 2 state unchanged; current metrics are in the private release/live-status-20261106.json artifact.

The original chat 2 release was verified before the board-addition repair above. PR #32 merged as 58e8762; API/scheduler then ran tested f7702f4, web 1a08549, schema 0051. No screen/migration. Main CI 42234193774 passed first time: backend 2,609/two PostgreSQL-only skips and browser 47/59/206 with none skipped. 232 affected cases, approved real-data read-only audit, six-board preview, snapshot replay, fresh checked backup and real isolated restore pass. Final installed identity/registry/ledger/source-hash/configuration/protected-record/public/monitor verification passed at 15:36Z. Pear VC shared board is off and active shared records withdrawn, preserving history. Private operational false positives caused safe rollbacks; tested corrections completed, product code unchanged. Successful operators must never be replayed. VM proof/rollback: private chat2-release-20261106T1418Z; local artifacts/requirements-chat-2-20261105/. No signed-in production UI claim; positive sponsorship is fixture-tested only. FRS-05 host-permission pickup remains open, details private requirements section 13.5. Owner authorized routine scoped work without repeated approval prompts; pause for serious security issues or actual permission refusals. The repair above supersedes its board-addition acceptance; complete the continuity merge before chat 3.

Chat 1 activated owner-approved exact tested `1a08549550b765f40acc047dd0a82f684c3af58a` at 2026-11-05T22:18Z (14:18 Pacific): migration 0051, API,
scheduler and web. Web still uses that image; API/scheduler now use the repair recorded above. PR #29 merged as `caf1e12e2e44ab6685322470786f73387febb127`; chat 2 is merged as 58e8762. Coverage is now three tabs in plain
words, pasting a job gets an answer on screen, every employer has a lasting record (lead ledger), and every host a dated
robots verdict. Full CI passes, for the first time in the 97 retained runs. A fresh backup and a real restore drill
passed, and 19 protected tables are preserved across the cutover. No signed-in production browser check by the agent.

**Pick up from "Latest state to pick up" in requirements section 13.5.** It holds the remaining host-verdict/refusal follow-up, current permissions, release/rollback and test helpers. OPS-01 and DIS-14 remain verified. DIS-15 and DIS-16 code checks pass and PR #33 is merged; the approved cleanup is complete; follow the private pickup for the separate SmartRecruiters P1 chat before chat 3. Do not replay completed releases or start chat 3 incidentally.

## Assessment invitation headline (previous release)

Owner-approved exact tested web `1e392636d1995533b7aa619340935f7ff5124842`, PR #28,
is live after web-only activation at 2026-11-04T01:26:18Z–01:26:25Z (November 3,
17:26 Pacific), verified 01:26:52Z. Canonical merge is `733b3b8`. The card counts
assessment invitation emails and opens exact email records; stages stay separate.
Fresh hosted review passes 59 browser/2,499 backend cases plus types/lint/build.
Wider CI retains the known 22 extension-browser failures; overall CI is red.
Actual read-only audits, compiled/public proof, protected rows and unrelated
services/configuration preservation pass. No signed-in production browser claim.
API `a48d71b`, extension 1.31.5 and scheduler/Gmail controls remain. Production
checkout stays `8ec89cd` with the intended mounted Caddy edit; web was built from
an isolated exact-source archive. Preserve its mount/inode. Fresh backup and
guarded unexecuted web rollback: `/opt/ace/private-backups/assessment-headline-20261104T0115Z/`.
Current owner-local proof/counts: `artifacts/assessment-release-20261104/REVIEW.md`.

## Extension 1.31.6 on main, owner confirmed installed November 6

1.31.6 only fixes double-clicking the card's grip to reset its position. The owner confirmed this version is installed; the remaining limitations below still apply.

## Extension 1.31.5

Workday dropdown questions were read as per-application generated IDs
(a hidden companion input made each question block look like two), so no
saved or Answers-page answer matched. Fixed with harness regressions; the
card theme now follows the ACE website's Day/Night/System choice. Extension
only; owner must Reload ACE and refresh the tab. SmartRecruiters shadow-root
forms remain unsupported. 1.31.5 adds richer diagnostics; Workday disability
boxes and some self-identification dates still need the owner's diagnostics paste.
See the newest root knowledge entries.

## QUIC transport repair LIVE — preserved during the web release

For the reported `ERR_QUIC_PROTOCOL_ERROR`, Caddy now serves h1/h2 and sends
`Alt-Svc: clear` on both existing sites. The validated graceful proxy reload
activated 2026-11-03T20:42:36Z. Pure Caddyfile PR #27 merged as `e36b61e`.
Runtime/no UDP QUIC listener, eight h1/h2 login/health/auth probes and service/
private-configuration preservation checks pass. Backend/web CI pass; wider
browsers were still running when documented. No application deployment or data/
Gmail/DNS/firewall change ran. Later client/network findings and owner access
confirmation are retained in the private reachability review; transport probes
alone do not prove a user's browser recovery.

Production stays on checkout `8ec89cd` with the intended mounted Caddyfile edit.
Preserve this file and its inode during future checkouts/releases; never restore
older HTTP/3-advertising source incidentally. Fresh private proxy backup/guarded
rollback and proof: `artifacts/site-reachability-20261103/REVIEW.md`.

## Canonical source and workspace

- Repository: `anwarbuilds/ace`; GitHub default and canonical branch: **main**.
- The developed `wine-rose-platform` history was renamed intact, starting at
  `98b112a1d13ffd695be9efc1e2d6dd5e90758536`, including PR #19's reviewed merge
  `9c884dc880e9f4419602a4ab5faec536e171ac6a`. No history flattening or force-push.
- `/home/ubuntu/Documents/ace-next` is a fresh standalone main clone. Its `.git`
  is a directory, common dir is `.git`, and it has no object alternates or
  dependency on the former `~/Documents/ace/.git`. Main is canonical; merged task branches may remain as review history.
- The original eleven registered worktree locations and 29 local branch tips
  are privately preserved. Those registrations/branches and the live stash were
  removed after verified independent recovery. Original folders are inert private
  snapshots, with linked `.git` pointer files removed. `~/Documents/ace` is absent.
- Unpacked Chrome extension path remains `ace-next/extension`. All twelve tracked
  extension files are byte-identical across the swap. No reload or publication ran.
- Private release evidence, design kits and reports were restored and hashed.
  Active `.env` contains fresh example development values. The old configuration
  is ignored/inactive `.env.legacy-retired`, mode 600. Do not source it as setup.
- Fetch main before future changes and push only the reviewed source. Private
  `recovery-20261030/*` tags are local recovery material; **do not push all tags**.

## Outcomes and Role and resume workspace spacing LIVE, 2026-11-01 Pacific

The owner's gap correction includes both Outcomes and Role and resume.
Their old 1460 px centered cap and 64 px bottom padding differed from Overview.
Both now share its full desktop workspace width, 28 px side gutters, 24 px bottom
gutter and minimum viewport height. Their grids fill spare height without
shrinking content; the lower Outcomes cards share a bottom edge. Mobile layout,
metrics, filters, calendar, shell, Inter/Wine/Rose tokens and earlier removals
are unchanged. Only Analytics CSS changes runtime behavior.

Owner-approved exact tested web **`8ec89cd3ff7da0e02950fcaf1e841d45bcb519c1`**, [PR #26](https://github.com/anwarbuilds/ace/pull/26),
merged as `df3d83325e3691a9466313ef1f4f321397e33257`, is LIVE. Web alone activated
2026-11-02T00:55:07Z–2026-11-02T00:55:16Z (16:55 PST); verification completed
2026-11-02T00:56:00Z. Production stays on exact tested `8ec89cd`; later documentation
is not another deployed build. This request supersedes older fixed Outcomes/
Role outer bounds. Never replay completed release operators.

Exact-source review 41368020088 passes 59 Inbox/Analytics browser cases, 2,499
backend/PostgreSQL cases, DOM/calculation checks, types, lint and build. Existing
desktop checks now verify both tabs/themes at 1672×941, 1920×1440 and 2560×1440,
including gutters, card bottoms, minimum height and overflow. Rendered captures
were inspected; hosted records are fictional. Separate actual read-only audits
pass all 44 cohort/timing scopes and 132 weekly windows/924 buckets. No signed-in
production browser claim; local Chrome remains restricted.

Public exact SHA/auth/assets, compiled UI, installed Analytics/invitation audits,
all 375 backend/audit-source hashes, both 19-table protected-row comparisons and
unrelated service/configuration preservation pass. API `a48d71b`, scheduler
`fca4673`, schema 0050/parser 15 and one Gmail monitor lease remain. No backend,
data mutation, manual Gmail, migration, scheduler, auth-session creation,
extension or legacy operation ran. Web logs have no error/traceback.

Fresh backup `/opt/ace/private-backups/workspace-spacing-20261102T0038Z/`
(557,701,497 bytes) passes gzip/catalog/full expansion without a
restore drill/pruning. Actual prior `5244b5c` is retained as
`oracle-web:before-workspace-spacing-20261102T0038Z` with guarded web-only
rollback; never restore old SQL as image rollback. Wider CI 41368120779 retains
exactly the known 25 pass / 22 fail extension names, with no new/resolved failures.
Overall CI remains red. The initial cutover stopped before activation when the
existing Gmail connection changed ready to error during preparation. Exact
HMAC variant checks prove no other grant/control field changed; all 19 protected
table snapshots were identical. Original failure/snapshot are retained. A fresh
checkpoint captured the error state, with the same strict checks passing before
and after web cutover. No Gmail state/grant/settings edit, Gmail call or backend
fix ran; the pre-deployment connection error is a separate issue. Private proof:
`artifacts/analytics-workspace-spacing-20261101/REVIEW.md`.

## Outcomes reference and global UI removal LIVE, 2026-11-01 Pacific

> Status: prior web image; its content/removal contracts remain current.

The owner approved deployment of the reference four-card Outcomes page,
clearer metrics with the 30-day observation window retained, and global removal
of About these metrics and evidence and application CSV controls, including
Role and resume and Companies. Exact tested web **`5244b5c979f325d16142f4db8ba553006f4bffca`** is LIVE at
https://ace.opik.net. [PR #25](https://github.com/anwarbuilds/ace/pull/25) merged
as `2a6f8e505bff6334e70527355be56aca8f031173`. Web alone activated **2026-11-02T00:12:27Z–2026-11-02T00:12:33Z
(16:12 PST)**; verification completed 2026-11-02T00:13:18Z. Production main intentionally
stays at exact tested `5244b5c`; later continuity documents are not another
deployed build. This record supersedes older removal scope and web images.
Never replay completed operators.

The three age-qualified metrics show actual eligible applications, confirmed
responses and Still pending. The unsupported effectiveness-rate card is replaced
by a supported count. Strip/donut/legend share the same four disjoint API groups
and eligible denominator. Empty cohorts have an honest state. Response timing
retains its separate dated sample, median and exact evidence links. Compact
information icons explain those distinctions; Inbox review/Undo remains.
Outcomes ends at its four cards, with recognized hiring progress removed.
The common disclosure/footer is removed from all Analytics tabs; application
CSV controls are also removed from records, Applications and Settings. Existing
JSON/resume exports and protected backend APIs are unchanged. The shared shell,
Inter/Wine/Rose tokens, filters, calendar, KPIs and prior Overview week/chart/
quiet-refresh behavior remain.

Exact-source [review 41364764823](https://github.com/anwarbuilds/ace/actions/runs/41364764823)
passes **59 Inbox/Analytics browser**, **2,499 backend/PostgreSQL**, **131 unique
local DOM/calculation** cases, types, full lint and build. Native Day/Night and
full/mobile captures were inspected against the Outcomes reference. Existing
shell geometry and real-data text differ; no pixel-perfect claim. Streamed
charts must be visible before measuring/capturing; waits were corrected without
weakening bounds assertions. Hosted records are fictional. Separate actual
read-only production audits reconcile cohort partitions/timing across **44
role/period scopes**, plus **132 weekly windows / 924 daily buckets**. No
signed-in production browser or new private hosted export; local Chrome remains
restricted. Private proof: `artifacts/analytics-outcomes-20261101/REVIEW.md`.

Live exact SHA, auth, 15 bundle/font hashes, 85 logos, compiled UI and installed
Analytics/invitation audits pass. All 375 backend/audit-source hashes match.
Both HMAC comparisons preserve preexisting rows across 19 protected tables.
Unrelated service identities/images/starts/mounts and .env/Caddy/Compose hashes,
modes and inodes remain unchanged. Schema 0050/parser 15, one Gmail monitor
lease, background sync and disabled historical rechecks remain. No backend,
migration, scheduler, extension, legacy, manual Gmail, application mutation or
auth-session creation ran. Web logs contain no error/traceback.

Fresh backup `/opt/ace/private-backups/outcomes-20261101T2351Z/` passes gzip,
catalog and full expansion (**557,199,963 bytes**; no restore drill/pruning).
Actual prior `3d578e5` web image is retained as
`oracle-web:before-outcomes-20261101T2351Z` with guarded web-only rollback.
Never restore old SQL as an image rollback. API remains `a48d71b`, scheduler
`fca4673`. [Broader CI 41364768975](https://github.com/anwarbuilds/ace/actions/runs/41364768975)
passes backend/web and retains exactly **25 pass / 22 fail** extension browsers,
with zero new/resolved failed names. Overall CI remains red.

## Analytics chart/interaction release LIVE

> Status: prior web image. Overview interactions remain; newer global removal scope above controls.

The owner requested the Inbox workflow fix, reference-style timeline, actual
weekly comparison/peak text, usable chart data, no unchanged idle reloads and
fast week arrows, then explicitly approved deployment. Exact tested web
**`3d578e5058fa0efd79e16741d0eda9760e1ac2ca`** is LIVE at https://ace.opik.net.
[PR #24](https://github.com/anwarbuilds/ace/pull/24) merged as
`68e2d194141145d1e0e90bdba532426e75838cf4`. Web alone activated during
**2026-11-01T21:37:36Z–21:37:43Z (13:37 PST)**; release verification completed
21:38:08Z. Production main deliberately stays on exact tested `3d578e5`;
later continuity documentation is not another deployed build. This current
record supersedes previous web-release instructions; do not replay operators.

Match and Identity were permanently neutral. They now use existing verified
application links; Verify uses confirmed evidence and Sync requires an active
connection with a real sync timestamp. Complete Gmail search coverage is a
separate fact: only a valid, completed existing job-mail check yields a
percentage, explicitly counting emails. Missing coverage says Not verified
with Check in Inbox. No Gmail check was run and no demo coverage was invented.
This does not unlock employer response-effectiveness rates.

The timeline measures its card width and retains legible Inter ticks, line,
markers, grid and area fill. View chart data opens an accessible native dialog
with exact counts/drilldowns, Escape/focus return and no card resizing. Week
arrows use reconciled Pacific daily aggregates already loaded with the report,
with no report request. Native history preserves filters and back/forward.
Current weeks compare the same elapsed weekday/time; historical weeks compare
complete weeks. The real peak day is included, with no zero-base percentage.
Quiet no-store checks on focus/timer refresh only changed authoritative data,
ignoring read timestamps; evidence notifications, retry and recovery remain.
Failures retain only this mounted selection's last verified output. No local
metrics ledger or browser persistence was added.

The full-workspace/flexible-height Overview and removal of its lower evidence/
export sections remain as requested. Existing shell, Wine/Rose/Inter tokens,
page-level Choose dates calendar, roles, reporting periods, four tabs and
receipt-date interview invitation binding remain. Only Analytics frontend
runtime/test files change behavior; backend and shared shell are untouched.

Exact-source [review 41351759860](https://github.com/anwarbuilds/ace/actions/runs/41351759860)
passes **2,499 backend/PostgreSQL**, **57 Inbox/Analytics browser** and **132
unique DOM/calculation** cases, TypeScript, full lint and build. Both native
Day/Night captures, wider desktop and responsive layouts were inspected. The
first rendered candidate exposed oversized action SVGs and a wrapping label;
CSS was corrected without loosening the original bounds assertions. Tests
prove local week navigation with report requests blocked, actual timer-driven
quiet checks, dialog/card bounds, role/period independence and cross-year weeks.
Hosted captures use isolated fictional data. Actual read-only production
snapshots separately reconcile 132 current/previous/cross-year windows, 924
daily buckets and every cached aggregate across all 44 role/period scopes.
No signed-in production browser or pixel-perfect claim. Local Chrome remains
restricted. Private review/comparisons: ignored
`artifacts/analytics-overview-interactions-20261101/REVIEW.md`.

Live exact SHA, auth, 15 bundle/font hashes, 85 logos, compiled behavior,
installed primary/independent/expanded Analytics and invitation audits pass.
All 375 backend/audit-source hashes match. Both HMAC comparisons preserve
preexisting rows across 19 protected tables. API, scheduler, PostgreSQL, Caddy
and exited migrate identities/images/starts/mounts, .env/Caddy/Compose hashes,
modes and inodes remain unchanged. Schema 0050/parser 15, one monitor lease,
background sync and disabled historical rechecks remain. Web logs have no
error/traceback. No backend, migration, scheduler, extension, legacy, manual
Gmail, application/status mutation or auth session creation ran.

Fresh backup `/opt/ace/private-backups/overview-interactions-20261101T2117Z/`
passes gzip, catalog and full expansion (556,039,613 bytes; no restore drill or
pruning). Actual prior `5c36ea9` web image is retained as
`oracle-web:before-overview-interactions-20261101T2117Z` with guarded web-only
rollback. Never restore old SQL data as an image rollback. API remains
`a48d71be3a33a6188e8fa96f748b4b78ecd19ef0`, scheduler `fca4673`.
Wider [CI 41351764471](https://github.com/anwarbuilds/ace/actions/runs/41351764471)
passes backend/web and retains exactly 25 pass / 22 fail in extension browsers,
with zero new/resolved failed names. Overall CI is not green. No assertions
were skipped or weakened.

## Previous Overview workspace release

> Superseded web image; its full-workspace layout and lower-section removal remain current.

Owner-approved exact tested **`5c36ea98b967e3d8c851a73509d113975f4e5a78`**,
[PR #23](https://github.com/anwarbuilds/ace/pull/23), activated web only during
2026-11-01T20:35:28Z–2026-11-01T20:35:34Z (12:35 PST); release checks completed
2026-11-01T20:35:58Z. Overview now ends at its four chart cards: recognized hiring
progress, the evidence disclosure and footer/export links are removed there.
Those existing views remain on other tabs; CSV and metric APIs are unchanged.

The desktop Overview fills workspace width with 28 px gutters. Its two rows
share remaining height after respecting their own content minima; mobile/short
viewports scroll naturally. This owner request supersedes the earlier fixed
Overview frame bounds. Sidebar, Inter/Wine/Rose tokens and other tabs remain.
Current/historical Pacific-week headings, arrows/reset/forward bound, independent
week data, role/period controls and page-level Choose dates remain unchanged.

Exact-source [review 41346576773](https://github.com/anwarbuilds/ace/actions/runs/41346576773)
passes 2,499 backend/PostgreSQL, 54 Inbox/Analytics browser and 127 unique DOM/
calculation cases, TypeScript, lint and build. Day/Night native and 1920/2560
captures were inspected; strict width/height/absence assertions pass. Hosted
images use fictional data. Separate actual read-only production checks reconcile
132 weeks / 924 buckets across all 44 role/period scopes. No signed-in production
browser or new private hosted capture is claimed. Local Chrome stays restricted.

## Interview invitation headline correction retained (previous release)

The owner identified that the live “Interview invitations” headline still reads
verified application stages rather than recognized invitation emails. Fresh
read-only checks confirm the distinction; do not fabricate a match/status event.
The isolated `analytics-rebuild-invitation-card-20261031` candidate binds that
card to the existing effective interview-email count and exact receipt-date
drilldown, preserving filters, missing-data honesty and the separate stage
explanation. Only two Analytics frontend components change runtime behavior;
backend/classifier/data remain unchanged. Owner-approved exact tested `1eb2808`,
[merged PR #21](https://github.com/anwarbuilds/ace/pull/21), passes 117 local
DOM/calculation checks, route types/TypeScript/lint and hosted review
[41206845680](https://github.com/anwarbuilds/ace/actions/runs/41206845680): 2,499
backend/PostgreSQL and 53 Inbox/Analytics browser cases plus web build. Day/Night
headline and mobile captures are inspected; no local Chrome ran. **Web only**
activated at 2026-10-31T14:09:39Z–14:09:46Z (07:09 Pacific). Wider CI passes backend/web
and retains the same 25/22 extension-browser baseline, with zero new/resolved
failed names; overall CI is not green. Live compiled-page, public SHA/assets/auth,
four-range invitation/drilldown, full installed audit and preservation checks pass.

## Production: current verified sources

Website: **https://ace.opik.net**. Web is exact approved/tested
**`8ec89cd3ff7da0e02950fcaf1e841d45bcb519c1`**, merged by PR #26 as
`df3d83325e3691a9466313ef1f4f321397e33257`. Production `/opt/ace` main tracks
origin/main but intentionally stays at exact tested `8ec89cd`. Later continuity
documentation is not another deployed build.

| Running surface | Verified source revision |
| --- | --- |
| API, Inbox parser 15 | `a48d71be3a33a6188e8fa96f748b4b78ecd19ef0` |
| Web | `8ec89cd3ff7da0e02950fcaf1e841d45bcb519c1` |
| Discovery scheduler | `fca4673033dc92833bbf217182738026f414bf3d` |
| Database schema | `0050` |

Only web changed. Current live verification, fresh backup/rollback and private
proof are described in the first LIVE section above. Preserve those exact
service/data/configuration boundaries; never restore old SQL data as an image
rollback. No signed-in production browser verification is claimed.

## Legacy retirement and recovery

The identified local Compose project was `ace`, rooted at the former
`~/Documents/ace`; production is `oracle` on the VM. The two legacy writers
were stopped, the single comparison cron was removed, and a final custom dump
was taken. An isolated local restore verified all 28 table counts, twelve protected
table hashes and schema 0040. Only that temporary restore database was dropped.
The six original legacy containers are removed. **Volume `ace_ace_postgres_data`
and exact recovery images remain retained indefinitely pending a separate owner
retention decision.** No production service or volume was removed.

No legacy-only application/resume identities were found under the documented
comparison keys at the read-only snapshot. Differing older owner states, source
history and every legacy record remain archive-only; nothing was merged into
production. Private comparison detail is not public documentation.

Recovery entry point:
`/home/ubuntu/ace-private-backups/consolidation-20261030T170532Z/`
(mode 700). It contains `all-history.bundle`, `shared-git.tar.gz`,
`workspaces-private.tar.gz`, `legacy-final.dump.gz`, `legacy-images.tar.gz`, exact manifests, restore and
production proofs, job configurations and original workspace snapshots. Bundle
recovery verified all 63 original refs, the stash and 334 reflog/unreferenced
commits independently. Public `legacy-main-final` points to verified old main
`a3c9449370b7ca070c3bad5d5fc68876eb1e6ccb`; local recovery tags also preserve
restored-workspace, backup and stash histories. See the [full recovery record](operations/platform-consolidation-2026-10-30.md).

## Product contracts and remaining limits

The [rewritten README](../README.md) describes the current routes and workflow.
Preserve Wine and Rose V2, the approved Analytics override and Focus Mode V5.1.
ACE never submits or marks Applied after filling; employer-motivation answers
remain employer-owned. Classification, identity and status permission are separate.
Unlinked recognized email history is not a confirmed application-stage event;
assessment/interview history survives a later rejection. Owner decisions/Undo stay.
Global Gmail historical rechecks remain false and parser-7 stays stopped.

PR #19/Inbox parser 15 release and its exact one-email correction were already
complete before consolidation. Do not replay them. Current Inbox and email
Analytics use the July 1, 2026 Pacific floor; older evidence stays for audit.
Classification precision/recall, complete mailbox observation, submitted-file/
channel attribution and response-effectiveness rates remain unestablished.
Source gaps and refusal backoff remain; no source cadence or scheduler policy
changed. Resume tailoring/export and offsite backup remain limitations.

## Validation and CI

Latest Outcomes/Role spacing verification is recorded above. Wider PR CI 41368120779 passes
backend/web and retains the exact 25 pass / 22 fail extension-browser baseline
with zero new/resolved failed names; dedicated Analytics browser checks pass.
Overall CI remains red. No assertion was disabled or weakened.

Earlier synchronization-source [Analytics review 41167247224](https://github.com/anwarbuilds/ace/actions/runs/41167247224)
passes 2,499 backend/PostgreSQL cases, 53 hosted Inbox/Analytics browser cases,
DOM/calculation checks, TypeScript, full lint and build. Production read-only
reconciliation/source/HTTP/asset checks pass separately; no signed-in production
browser or local Chrome ran. [Wider CI 41167251270](https://github.com/anwarbuilds/ace/actions/runs/41167251270)
passes backend/web but keeps 25 pass / 22 fail in extension browsers, with zero
new/resolved failed names against main's consolidation run. Overall CI is not
green. Dedicated Inbox/Analytics browser verification passes.

The earlier consolidation's fresh dependency installation, focused fictional backend tests, matcher/Memory,
DOM/calculation checks, TypeScript, lint, production web build and demo seeding
passed. Fourteen local HTTP routes passed with a fictional signed-in session;
this is not browser rendering or signed-in production verification. No Chrome ran.
Read the [testing runbook](operations/testing.md); laptop cooling restrictions remain.

The rechecked PR #19 full run
[41075615441](https://github.com/anwarbuilds/ace/actions/runs/41075615441)
failed on 22 extension-browser cases after backend/web passed; later app-browser
steps were skipped. Dedicated Inbox run
[41075606426](https://github.com/anwarbuilds/ace/actions/runs/41075606426) passed.
Consolidation changes documentation/instructions and archive ignore rules only;
backend, web, extension, workflow and Compose runtime bytes are unchanged.
Main pushes run CI with all assertions intact. See the
[current workflow results](https://github.com/anwarbuilds/ace/actions/workflows/ci.yml)
and private final verification for the consolidation run; do not claim overall green.

Consolidation full CI [41140888866](https://github.com/anwarbuilds/ace/actions/runs/41140888866)
on documentation source `a8d2c5d549f552fcfcaaca91c91a0d665ab73a60` completed:
backend and web passed; extension browsers had **25 pass / 22 fail**. Exact
traceback-name comparison with PR #19 found zero new or resolved failed names.
Later application-browser steps were skipped. Overall CI remains red; no test
was disabled or weakened. The final follow-up records these results and the
verified six-image private backup without changing runtime/test/workflow source.

## Future sessions

Use the standalone main checkout and current runbooks. Do not recreate old
worktrees, restore an archived `.git` pointer, run the historical comparison
installer, restart the old replica, or treat archived migration procedures as
setup. Recovery is into a separate folder/database; restarting services or
writing production needs a new specific approval. Continue only the owner's
next requested product work and preserve all private recovery material.
