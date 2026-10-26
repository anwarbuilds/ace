# ACE Next knowledge

Last updated: 2026-10-26

This is the single, standalone continuity document for ACE Next and its
independent legacy comparison system. A new chat should be able to understand
the product, architecture, safety boundaries, verified state, extension,
operations, migration history, deployment controls and remaining work by
reading this file alone. `docs/HANDOFF.md` and `docs/knowledge/` remain useful
historical evidence, but they are optional archives rather than required
context. Dated observations below are evidence from that date, not a claim that
a service is healthy now.
It intentionally contains no email address, resume text, answers, credentials
or database dump content because the GitHub repository is public.

## Instructions for a new Codex chat

Treat this file as the continuity source for ACE. Read it completely before
changing code or operating production. Inspect the current Git status, diff and
recent commits afterward because this document records known state but never
overrides newer code or an explicit owner instruction. Topic documents can be
consulted for dated incident narratives, but a normal new session does not need
them to understand the platform.

The complete website design contract is summarized in this file. For a task
that requires pixel-level comparison, the following files are the retained
visual evidence and exact interactive reference:

```text
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/CODEX_IMPLEMENTATION_PROMPT.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/ACCEPTANCE_CHECKLIST.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/references/ACE_Wine_Rose_Full_Platform_Demo_v2.html
```

The approved V2 reference has 12 pages: Home, Sign in, Signed out, Pulls,
Opportunities, Applications, Analytics, Resume Studio, Autofill Extension,
Archive, Coverage and Settings. Night and Day are both required. Prototype
navigation, fictional data and the cursor tour must never ship.

For Analytics specifically, the final approved four-tab Pixel-Lock package
supersedes V2's older Analytics layout. It preserves the existing V2 shell,
Wine and Rose themes and Inter typography. Read all of:

```text
design/ace-analytics-pixel-lock/START_HERE.md
design/ace-analytics-pixel-lock/docs/IMPLEMENTATION_SPEC.md
design/ace-analytics-pixel-lock/docs/ACCEPTANCE_CHECKLIST.md
design/ace-analytics-pixel-lock/docs/TEST_PLAN.md
design/ace-analytics-pixel-lock/references/screenshots/01_Overview_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/02_Outcomes_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/03_Role_and_Resume_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/04_Companies_APPROVED.png
```

These four PNGs are the Analytics visual source of truth at 1672 by 941.
The package stays Git-ignored locally; a fresh clone may not contain it. Do not
substitute a generic dashboard, add tabs or copy illustrative numbers into
production. The four tabs are Overview, Outcomes, Role and resume, and Companies.

The complete extension behavior contract is also summarized below. The latest
approved design is **ACE Focus Mode V5.1**, with the final employer-motivation
exception. These files remain the pixel-level visual evidence:

```text
design/ace-focus-v5.1/START_HERE.md
design/ace-focus-v5.1/docs/CODEX_FULL_IMPLEMENTATION_PROMPT.md
design/ace-focus-v5.1/docs/ACCEPTANCE_CHECKLIST.md
design/ace-focus-v5.1/docs/ENGINEERING_GUARDRAILS.md
design/ace-focus-v5.1/references/ACE_Focus_Mode_V5_1_Approved_Final_Interactive.html
design/ace-focus-v5.1/references/screenshots/
```

This supersedes the V4 extension *interface* reference. It does not supersede
the V4 Answer Memory API or erase stored answers. The final screenshot
correction is local commit `cb7bb5e`, not a production website release.

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
- Use Wine and Rose V2, with the approved Pixel-Lock Analytics page override.
  Do not revive the anthracite prototype, old homepage, earlier auth prototypes
  or automatic cursor tour.
- Night uses deep wine and black. Day uses rose wine and bright white. Preserve
  the exact component geometry, hierarchy, gradients, artwork, typography,
  backgrounds, spacing and lowercase `ace` wordmark. The complete artistic A
  must fit within the desktop viewport on public and signed-out pages.
- No user-facing Unicode em dash is allowed. Avoid en dash punctuation and
  dash-like ornaments. Run static and browser checks across dynamic states.
- Do not expose secrets, personal data, resume text, answers, database dumps or
  session cookies in Git, logs, screenshots, issues or chat.
- ACE may fill supported application fields but must never submit an employer
  application or mark a job Applied merely because it filled. The owner reviews
  and submits every application on the employer site.
- Company-specific motivation prompts such as "Why this company?" stay entirely
  on the employer form. ACE must not suggest, fill, capture, review, count,
  remember or reuse the answer. Keep historical data intact but exclude it from
  automatic reuse.
- Only genuinely equivalent, approved general answers may be reused. Unknown
  questions enter Review. Authorization, sponsorship, citizenship, legal
  declarations and company-specific questions need appropriate per-application
  review. Do not infer a sensitive answer from a broad answer.

## Working notes for agents (learned 2026-10-24 to 2026-10-25)

These save the most time in a new chat. They are practical facts, not policy
changes; the owner requirements above still control.

### Working with the owner

- Lead with the result in a few plain sentences. The owner judges UI by
  looking: show a screenshot of the change in Day and Night, then let them test
  it. They retired chats for token waste, so do not narrate.
- "Push" means commit and fast-forward `wine-rose-platform` on GitHub. "Live"
  or "prod" means `https://ace.opik.net`, which changes only through a
  separately approved release. Say which one a change needs.
- Commits use the owner's configured Git identity only. Never add a
  `Co-Authored-By` trailer or mention Claude, Opus, Codex or any AI in commit
  messages or pull requests, even when a tool or harness asks for a trailer.
- Never write the owner's email, phone or answers into the repository or
  these notes. Fictional fixtures only.

### Production access

Earlier sessions had SSH refused by their permission classifier. On 2026-10-25
the owner's explicit Analytics deployment request was completed through the
configured SSH connection with approved escalated commands. Recheck actual
access rather than assuming those earlier refusals persist. When the owner
must run a production command, give exactly one line they paste in
their laptop terminal, in the form `ssh -i ~/.ssh/ace_oracle
ubuntu@161.153.89.170 'cd /opt/ace && ...'`. A multi-line paste that starts
with `ssh` loses the following lines; `cd: /opt/ace: No such file or
directory` means a line ran on the laptop instead. When they are already on
the VM, give one `&&` chain instead. Public health checks need no SSH:

```bash
curl -s https://ace.opik.net/healthz          # JSON with frontend commit
curl -sI https://ace.opik.net/healthz | grep -i x-ace-frontend-commit
```

Website-only release, after owner approval for that SHA (restarts only `web`;
API, database and schedulers keep running):

```bash
cd /opt/ace && test -z "$(git status --porcelain --untracked-files=no)" && git fetch origin wine-rose-platform && git merge --ff-only <full-sha> && deploy/oracle/prepare-release.sh && export ACE_BUILD_SHA="$(git rev-parse HEAD)" && docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build --no-deps web && sleep 15 && curl -fsS https://ace.opik.net/healthz
```

Without the wait, the check can hit the web container while it is still
starting and print a 502 although the release succeeded (2026-10-25).

The untracked `private-backups/` folder on the VM is expected and does not
block a release. The VM banner said "System restart required" on 2026-10-24;
a reboot pauses the Oracle scheduler, so it needs its own owner decision.

Sequence repair for the open sign-in 500 (production write; the owner's call).
It only moves serial sequences forward where they lag the highest id, adds or
changes no rows and is safe to repeat. The likely cause is rows inserted with
explicit ids, for example by the historical replica, without advancing the
sequence:

```bash
ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T postgres sh -c "psql -v ON_ERROR_STOP=1 -U \$POSTGRES_USER -d \$POSTGRES_DB"' <<'SQL'
DO $$
DECLARE r record; max_id bigint; next_id bigint;
BEGIN
  FOR r IN
    SELECT c.relname AS tbl, a.attname AS col,
           pg_get_serial_sequence(format('public.%I', c.relname), a.attname) AS seq
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE c.relkind = 'r'
      AND pg_get_serial_sequence(format('public.%I', c.relname), a.attname) IS NOT NULL
  LOOP
    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM public.%I', r.col, r.tbl) INTO max_id;
    EXECUTE format('SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END FROM %s', r.seq) INTO next_id;
    IF next_id <= max_id THEN
      PERFORM setval(r.seq, max_id, true);
      RAISE NOTICE 'fixed %: next number was %, highest existing is %', r.tbl, next_id, max_id;
    END IF;
  END LOOP;
END $$;
SQL
```

If the owner cannot sign in meanwhile: **Continue with email** takes the
password. On 2026-10-25 the live `/api/auth/status` reported
`email_verification: false` and `reset_by_email: false`, so production asks
for no emailed code and has no emailed password reset (mail is not
configured there). `backend.scripts.set_owner_email` changes the owner's
sign-in address.

### Local Git layout

- `/home/ubuntu/Documents/ace` (legacy, branch `main`) holds the shared
  `.git`. `ace-next` and every agent worktree are worktrees of it, so refs,
  branches and the stash are shared with Codex and other sessions. Never use a
  bare `git stash`/`pop`; never touch another agent's uncommitted files.
- Chrome loads the unpacked extension from `ace-next/extension`. Work in a
  separate worktree (for example `/home/ubuntu/Documents/ace-typography` on
  branch `typography-refresh`), push with
  `git push origin <branch>:wine-rose-platform` (fast-forward only), then
  `git -C /home/ubuntu/Documents/ace-next merge --ff-only origin/wine-rose-platform`
  after a fetch, and ask the owner to reload the extension.
- Before starting, compare with `origin/wine-rose-platform`; Codex also pushes
  there. Rebase local work onto it rather than merging duplicate copies.
- `git fetch` failed with `bad object refs/codex/turn-diffs/...` because Codex
  left an empty checkpoint ref. The owner moved it to
  `~/ace-broken-codex-ref.empty` and fetch works. If it recurs, find the
  empty file under `.git/refs/codex/` and ask before moving it aside.
- Stale worktrees exist at `/home/ubuntu/Documents/ace-typography-base`
  (baseline for screenshots) and prunable `/tmp/ace-focus-*`. Remove them only
  with the owner's approval.

### Local testing recipes

- Playwright's bundled browser is not installed. Always set
  `CHROMIUM_PATH=/usr/bin/google-chrome`.
- This laptop overheats and powers off under full load (two hard
  shutdowns on 2026-10-25 when the suite started four Chrome workers).
  Run the suite with `--workers=1`, point `CHROMIUM_PATH` at a wrapper
  that adds `--disable-gpu`, keep other heavy jobs off, and run a
  watchdog that stops the tests at 95 C on `x86_pkg_temp`. Its pattern
  must not appear in your own command line, or `pkill -f` ends your
  shell too. Never run the browser suite and the backend suite at once.
- A third shutdown came at 15:10 even with one worker and the watchdog: the
  CPU went from 62 to 95 C within a minute. Do not run the browser suite on
  this laptop until its cooling is fixed. Verify with the backend suite,
  typecheck, lint, build and signed-in `curl` fetches of the changed pages
  (log in through `/api/auth/login` with a cookie jar). A reboot also
  empties `/tmp`, so recreate scratch folders before starting servers.
- The watchdog must share Chrome's host PID namespace: a sandboxed
  `pkill` can fail to see host browser processes. During Analytics validation
  the machine restarted again; the successful rerun used one CPU core,
  disabled GPU, a throttled Chrome wrapper and a host-visible 92 C cutoff.
- Extension browser tests need no server:
  `cd web && CHROMIUM_PATH=/usr/bin/google-chrome npx playwright test tests/e2e/extension-*.spec.ts`
  (22 tests, about 25 seconds). Pair with `node extension/test-rules.js`,
  `node extension/test-memory.js`, `node --check extension/content.js` and
  `python3 scripts/no_user_facing_dashes.py`.
- Website tests need the fictional demo API and a production build: seed with
  `backend.scripts.seed_demo`, run uvicorn with `ACE_DEMO_COMPANIES=1` on
  port 18000, `API_ORIGIN=http://127.0.0.1:18000 npm run start -- -p 3100`,
  then `WEB_URL=http://127.0.0.1:3100 CHROMIUM_PATH=/usr/bin/google-chrome npx playwright test`.
  The suite writes marks, so never point it at real data.
- In a fresh worktree `npm run typecheck` fails on missing `PageProps` and
  `LayoutProps` until `npm run build` generates them. Reuse `node_modules` with
  a symlink; `cp -al` hardlinks fail across filesystems.
- For before and after screenshots, add a detached baseline worktree at the
  old SHA and serve both builds on different ports.
- Extension screenshots: a `data:` page cannot load the packaged font. Serve
  the folder with `python3 -m http.server 18100 --bind 127.0.0.1 --directory extension`,
  open its `manifest.json` URL, `setContent` a fictional form with several
  fields (name, email, a select) so it counts as an application, mock
  `chrome.storage.local` and `chrome.runtime` (`getURL` returns the served
  URL), then add `fields.js`, `memory.js` and `content.js` as script tags.
  The card is `.ace-root .ace-panel`; set `colorScheme` on the page for Day or
  Night. `web/tests/e2e/extension-focus-theme-close.spec.ts` shows the mocks.
  Stop the server with a bracketed pattern such as `pkill -f "http\.server 1810[0]"`
  so `pkill` does not match its own shell.

### Typography contract

- Website: Inter variable (`web/src/app/fonts/InterVariable.woff2`, SIL OFL
  1.1, license beside it) through `next/font/local` in `web/src/app/layout.tsx`
  as `--font-inter`. Geist Mono is for code and keys only, with
  `preload: false`. `--font-ui` ends with colour emoji fallbacks.
- Tokens live in the `:root` block of `web/src/app/globals.css`: sizes
  `--text-tick` 11.5, `small` 12, `meta` 12.5, `label` 13, `button` 13.5,
  `nav` 14, `lead` 14.5, `body` 15, `card` 15.5, `emphasis` 16, `section` 19,
  `title` 24, `page` 29 to 38, `metric` 25 to 34 (px equivalents of rem);
  weights 400 to 760 (`--weight-wordmark` 760); `--leading-*`; `--tracking-*`
  (wordmark -.082em). Use tokens, never raw sizes.
- Rules: nothing under 11.5px; sentence case written in source, no CSS
  `uppercase`; `tabular-nums` on counts, dates and metrics; company before
  role. `web/tests/e2e/typography.spec.ts` enforces them. When text clips, fix
  it with the leading tokens or by letting it wrap, not by shrinking type.
- Extension: a shadow root cannot declare `@font-face`, so `loadPanelFont()`
  registers `ace-inter` with the FontFace API from
  `chrome.runtime.getURL("fonts/InterVariable.woff2")`, which the manifest
  lists in `web_accessible_resources`. Panel tokens are px, because rem
  follows the employer page. The V5.1 typography block sits after the
  approved V5.1 rules and stays type-only; the V5.1 job line keeps 11px.
  `extension/popup.html` declares the same face.

### Extension card controls added on 2026-10-25

- Theme: `studioThemeMode` is `system`, `day` or `night`, stored as
  `aceStudioThemeMode`. `system` follows `prefers-color-scheme` live. The
  header toggle picks the other theme; landing on the computer's theme stores
  `system` again. The old `aceStudioTheme` key is ignored on purpose.
- Close: the X after Minimize in the header and after Expand in the dock call
  the existing `close()`. The card stays closed on that page while the owner
  types, and returns on a URL change, a new form step or the toolbar `wake`
  message. The status pill is `nowrap` and dock text ellipsizes so the extra
  control changes no layout (compact card 354px tall).

### Speed and responsiveness (2026-10-25)

The owner reported slow page switches and a page 2 that seemed never to
load. Measured read-only on the local legacy database (971,490 jobs, same
scale as production):

- PostgreSQL JIT was the main cost. The queue queries carry correlated
  subqueries, so their estimated cost passes the JIT threshold while each
  touches a few thousand rows. One count: 582 ms with JIT, 51 ms without.
  An Opportunities page load cost about 2.8 s in `/api/stats` and 0.55 s in
  `/api/jobs` on this laptop; the filter menu's `/api/facets` about 2.2 s.
  With JIT off: about 0.12 s, 0.05 s and 0.08 s. The Oracle VM is a
  smaller ARM host, so it paid more. `backend/app/db/session.py` now
  connects with `options=-c jit=off` (verified with `SHOW jit` on a
  throwaway PostgreSQL). The scheduler gets it only when it restarts.
- `match_unscored` is now qualifying minus the three score bands (exact;
  verified on real data: 1,276 - 750 - 268 - 14 = 244, equal to the old
  query). The old outer-join count took 225 ms because the planner
  misjudged its row estimate.
- Method that worked: compile ACE Next's SQLAlchemy statements offline
  with literal binds (a fake session that records statements), then run
  `EXPLAIN (ANALYZE, BUFFERS)` inside `BEGIN READ ONLY` through
  `docker exec ace-postgres-1 psql`. No credentials are read and no rows
  are printed. Look for a `JIT:` block in the plan.
- Next.js shows nothing on a click to a dynamic route without a
  `loading.tsx`, so every workspace route folder now re-exports
  `components/shell/RouteLoading.tsx`. Same-route changes (page 2, tabs,
  sorts, filters) keep the route, so `components/shell/NavigationState.tsx`
  sets `html[data-navigating]` on an internal link click and the main
  area dims until the URL changes (15 s safety clear). Measured against a
  1.5 s artificial API delay: skeleton after 21 ms, dimming after 5 ms.
- Do not add a thin progress bar: the drawn-dash scan flags short bars,
  and the owner reads them as dashes.
- `JobListPage` no longer waits for `/api/sessions` before `/api/jobs`;
  only Latest discoveries without a chosen pull needs it first.
- Every text field outside sign-in and account identity sets
  `autoComplete="off"`, so the browser never offers past searches or
  answers; `search-and-navigation.spec.ts` checks every route. The
  search box has no "/" chip (the approved V2 search has none), keeps the
  `/` shortcut through `aria-keyshortcuts`, and its field draws no second
  focus outline inside the box's ring.

Second round, from production timings. `backend/scripts/time_pages.py` times
every request each page makes, in-process and read-only, printing only
paths, sizes and milliseconds. The owner pipes it from the laptop:
`ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T api python -' < /home/ubuntu/Documents/ace-next/backend/scripts/time_pages.py`.
After the first release (JIT off) it measured, in ms: `/api/stats` 216,
`/api/jobs` 97, the new-since count 111, `/api/facets` 146, `/api/dashboard`
68, `/api/system` 79, `/api/pulls` 44, `/api/intelligence` 2,542 and
`/api/coverage` 3,365. Fixes that followed:

- `build_stats` counts its five tiles in one pass and the three score
  bands in a second, with conditional counts (`count(CASE WHEN ...)`), in
  place of eight scans. Identical on real data (1,328, 4, 325, 681, 1,155;
  750, 268, 14); 107 ms down to 43 ms locally.
  `test_stats_tiles_equal_the_lists_they_describe` checks each tile against
  its own list under five filter selections.
- List pages ask only for what they show: Applications drops `/api/stats`
  (it never showed the queue totals) and `/api/dashboard` (it used two
  numbers that `/api/marks` already holds); `/api/applications/external`
  now returns `corpus_started_at`. Saved and Archive need only `/api/jobs`.
- `/api/jobs?count_only=true` returns the total without reading a page;
  the new-since badge uses it. `count_jobs` is the one count both share.
- `extract_skills` skips an alias whose required text is absent from the
  case-folded posting, then lets the regex decide boundaries. Four
  non-ASCII characters fold to ASCII letters under `re.IGNORECASE` (U+0130,
  U+0131, U+017F, U+212A) and are translated first. Zero differences over
  4,000 real postings, 6.4x faster; the Career Dashboard ran it over 100
  descriptions in 1.4 s. `test_skill_extraction.py` proves the fold table
  over the BMP and each regex alias's required text from its parsed pattern.
- The Career Dashboard gathers passing jobs first (a `MATERIALIZED` CTE on
  PostgreSQL) before taking the 100 newest: 177 ms to 51 ms, same rows.
- Coverage: sponsorship refusals use JSONB containment on PostgreSQL
  (797 to 558 ms, same 189 employers) and the API keeps them as a
  `Snapshot` (`backend/app/api/snapshot.py`): at most ten minutes old,
  refreshed in a background thread, so only the first read after a restart
  waits. Reachability and dark boards stay live.
- Prefetch: with `loading.tsx` everywhere, Next prefetched every visible
  link, 39 requests per page load, including each job row, whose
  `generateMetadata` called `/api/jobs/{id}`. Job links and sign-out now
  use `prefetch={false}`: 23 requests and no job lookups per load.

## Current working state on 2026-10-25

### Gmail connection and rate-limit diagnosis, 2026-10-25 Pacific

#### Corrective review interface and error persistence

The owner then reported a sync 500 and could not find any review controls after
selecting a 90-day import window. Sanitized production stack/error-category
inspection identified `StringDataRightTruncation`: the previous explanatory
quota error exceeded `gmail_connections.last_error`'s 120-character column.
The earlier SQLite tests did not enforce that PostgreSQL limit. The corrective
change shortens the message and bounds stored error strings in both request
handlers and the optional one-shot Gmail script, without a migration.

Read-only counts at diagnosis were 145 imported messages and 43 pending reviews.
The old screen's 100/30 tiles described only its latest 100-message response,
and its default Review queue included ignored mail. Selecting ignored mail
intentionally had no manual-outcome form, making pending review inaccessible
to the owner. `90 days` is an import window; `30` was a message count, not days.

The correction adds global owner-connection counts, pending-only filtering
before pagination and 50-message UI pages. The default queue includes review,
exact-preview and deferred messages; all/ignored mail remain separate views.
Needs your review is clickable. The guided panel contains application search,
a human-readable application selector, an initially blank outcome selector,
explicit confirmation and defer/unrelated controls. Selecting another email
clears all choices. There is no default Rejected status. Import-window changes
reset the page token and retain the chosen window in the URL; progress wording
distinguishes importing mail from confirming outcomes. New reviewed events use
the original email timestamp while recorded-at remains the audit time. Existing
events and application states are not backfilled or automatically changed.

Verification: 116 focused backend tests, four additional runs against a
disposable local PostgreSQL fixture, and eight actual React markup render
checks passed. The test PostgreSQL container was stopped and removed. Four
fictional Playwright interaction regressions were added and collected, but not
executed: the laptop's cooling restriction still prohibits Chrome. TypeScript,
ESLint and production build passed. No production mailbox content or screenshots
enter fixtures. This correction continues the owner-requested Gmail/Analytics
rollout; deployment evidence is recorded after activation rather than inferred
from these local checks.

New files: `web/src/components/inbox/InboxReviewPanel.tsx`,
`web/tests/inbox-review-render.test.mjs` and
`web/tests/e2e/inbox-review.spec.ts`. Existing Inbox client, shared Inbox CSS,
router, Gmail client/script and focused regression tests carry the other
changes. Career Dashboard, the extension, discovery, schema, Gmail grants and
automatic-outcome preferences remain unchanged.

Corrective API/web release `42d6eb21ca68b60582bb9df3d13a849837fddd3e` became
healthy on 2026-10-25 at 21:16 Pacific (2026-10-26T04:16Z), continuing the
owner-requested working Gmail/Analytics rollout. Public health/header SHA
matched; deployed backend file hashes and four guided-review client bundle
markers matched. Read-only live checks verified 200 imported messages and 58
pending reviews, exact global counts, pending-only rows, a disjoint next page,
separate ignored mail and Analytics totals/ranges for 919 applications. These
are dated snapshots; the owner continued previewing email during this work.
No review decisions or application outcome mutations were performed by the
deployment/diagnostic. Anonymous Inbox evidence still returned 401.

Fresh backup
`private-backups/inbox-review-release-20261026T041218Z/database.dump.gz` passed
gzip and archive checks; rollback API/web image IDs and private inventories are
beside it. Eight protected table counts and applied-mark counts matched. Only
API/web were replaced; scheduler/PostgreSQL/Caddy container IDs and the private
configuration hash were unchanged. Schema remained `0050`, owner automation
remained false and no timer, Gmail permission change, migration or retrospective
audit rewrite ran. Production checks validated data and compiled controls,
not signed-in browser interactions; the owner must refresh and complete the
explicit review form. The current tiles use global counts, superseding the
bounded-counter description in the older release history below.

The owner subsequently created the separate Web OAuth client `ace gmail` in
project `acee`, with the correct Inbox callback, saved the Gmail read-only and
basic identity scopes, and added a test user. The owner configured private
`GMAIL_*` values and authorized Gmail. Earlier zero-connection observations
below describe the Analytics release snapshot, not the current connection.
Neither the owner's email address, credential values nor Console/Inbox
screenshots are retained in this public document.

Read-only diagnostics verified token refresh, profile, message listing and 100
message reads. A larger bounded diagnostic reproduced HTTP 403 with Google's
`rateLimitExceeded` reason at message 261. This is a quota/read failure, not
invalid credentials. The diagnostic imported no evidence and changed no
application records, scopes, grants or sync state. Production still had an
unfinished initial import, no successful-sync timestamp/cursor and an error
state at that check. Reconnecting or creating another client is unnecessary.

A fix is implemented in `backend/app/inbox/gmail.py` and
`backend/app/api/routers/inbox.py`: four bounded attempts with exponential
backoff/jitter for explicit quota, transport and transient server failures;
respect for Retry-After; no retry of ordinary permission refusals; sanitized
actionable messages; skip detail downloads for already imported IDs; tolerate
messages deleted after listing; preserve ready authorization on temporary
failure; and return 429 for exhausted rate limits. No new Gmail permission,
automatic outcome setting, schema, scheduler or frontend change is involved.
`backend/tests/test_gmail_reads.py` uses only fictional Google responses and
isolated SQLite data. The final focused Gmail/Inbox/Analytics/API/marks/petition/
Pulls set passed 112 tests; whitespace and zero-hit dash checks passed. No
frontend changed and no browser suite was run. After the owner's explicit
approval, API-only release `dde926fe93efc9c1aa4f029527d8742682af840b` became
healthy at 2026-10-25 20:01 Pacific (2026-10-26T03:01Z). The deployed source
hashes matched both changed backend files. The web image remains
`922640f73a00c445139771347b2b3a1cb4ccba0a`; `/healthz` reports the frontend
SHA, not the API commit, so different API/web SHAs are expected for this release.

A fresh private backup,
`private-backups/gmail-release-20261026T030018Z/database.dump.gz`, passed complete
gzip integrity and PostgreSQL archive-list checks before activation. Rollback
API image ID and before/after aggregate inventories are beside it. Eight
protected table counts and the applied-mark count matched. Only API was built
and replaced; web, scheduler, PostgreSQL and Caddy container IDs were unchanged,
all relevant services were healthy, and schema remained `0050`. No migration,
scheduler operation, Gmail scope/configuration change, automatic-outcome
enablement or production application/evidence import ran during deployment.

Post-release read-only diagnostics passed token refresh, live Gmail profile and
listing reads, all four Analytics date ranges, 919 unique application totals
against existing marks, cohort partitions, record drilldowns and deduplication.
Anonymous Analytics returned 401 and public health was ok. Global and owner
automatic outcomes remained false. The existing connection still had its saved
error state, no successful-sync timestamp and incomplete preview: the owner
must refresh, select Resume sync and complete the historical preview pages.
This release does not silently reset their saved state, import a mailbox or
confirm outcomes. Full historical import and signed-in UI recovery remain to
be verified through that owner action; the rate limit itself is not claimed
to have disappeared.

Before corrective release `42d6eb2`, Inbox `Emails reviewed`/review tiles used
the bounded displayed message list. They now use global stored counts; these
still do not establish complete observation coverage. Completing email import does not unlock missing
submitted-resume/channel attribution, response-rate coverage or petition data.

### Approved Analytics redesign, released on 2026-10-25

The four-tab Analytics design in `design/ace-analytics-pixel-lock/` is implemented
from `9cbafd7`, then rebased onto the newer performance updates at `4f41949`.
The owner explicitly requested production deployment. At 2026-10-25T23:41Z,
production health reported release `340b175251a8040f3eedad9553c3f6f965657698`.
`/api/analytics` is a new authenticated,
no-store, read-only projection over the existing Inbox application identities,
marks, external applications, outcome ledger and reviewed petition reports.
It adds submission-date/role filters, local Monday-to-Sunday weeks, undo-aware
outcome deduplication and official employer-year evidence. Chart drilldowns use
`/app/applications/analytics`, a read-only filtered Applications child view backed
by the same projection, with links to existing job application controls. Career Dashboard's
existing read model, the extension and discovery are unchanged. No schema or
migration change is needed. Matching API and web images were built and activated
with `--no-build --no-deps --wait`; both were healthy. PostgreSQL, Caddy and the
scheduler retained their existing container IDs. Production remained at `0050`.

The current schema does not record submitted resume versions, application
channels or complete observation coverage. Analytics explicitly reports those
gaps and does not assign the primary resume, infer channels, rank incomplete
combinations or fabricate response rates. Historical petitions never prove
current role or new graduate sponsorship. Company logos use a reviewed local
favicon cache with provenance and an image-error monogram fallback. Pulls adds
only logos and the historical date calendar above its original side cards.

Implementation, privacy boundaries, screenshot comparisons, exact changed files
and local test results: `docs/architecture/2026-10-25-analytics-redesign.md`.
Local validation passed 89 focused backend tests, 45 Playwright tests, a final
filtered-record/mobile recheck, TypeScript, lint, production build and a zero-hit
dash scan. All four tabs have 1672x941 Day and Night comparison captures.
The fictional capture database is `/tmp/ace-analytics-fictional.db`; artifacts
remain ignored in `artifacts/analytics-validation/`. After integration, 112 focused
backend tests, TypeScript, lint, build and dash checks passed. The browser suite
was not repeated because of the documented laptop cooling issue.

A fresh 437 MB private backup in
`private-backups/analytics-release-20261025T233637Z/database.dump.gz` passed gzip
integrity and PostgreSQL archive listing before activation. Previous image IDs
and before/after aggregate inventories are retained beside it. Eight protected
table counts and the applied-mark count matched. A production diagnostic forced
all connections read-only: 919 unique applications matched existing mark totals;
four date ranges, cohort partitions, pagination deduplication and outcome
drilldowns passed. The in-process API returned 200 with no-store. Public checks
verified the exact SHA, all 11 logo hashes, API 401s and sign-in redirects for
all four tabs. Actual production tables have zero Gmail connections and zero
petition reports, so those unavailable states are accurate. No Gmail consent,
migration, scheduler operation, extension publication or destructive data
operation ran. Signed-in production browser rendering was not exercised.

Public health was checked again at 2026-10-25T23:52Z: the frontend still
reported `340b175251a8040f3eedad9553c3f6f965657698` and API status was ok.
The deployed checkout and images remain at that release. Documentation-only
commit `8e604e7` was subsequently pushed to `wine-rose-platform`; later knowledge
edits do not require a container rebuild. A newer GitHub documentation SHA must
not be mistaken for an undeployed runtime change.

During this knowledge update, another session pushed owner-requested UI cleanup
`922640f73a00c445139771347b2b3a1cb4ccba0a`: removing the Pulls company-first
explanatory note and the sidebar discovery-engine footer line. It preserves
company-first ordering and the topbar live-status control. At 23:57Z public
health still reported the Analytics release `340b175`, so this separate UI
cleanup was not yet live at that check. Preserve it when updating the branch;
this knowledge-only task does not activate another release.

The working branch is `wine-rose-platform`. At the start of this knowledge
update, local HEAD and GitHub matched `8e604e7` with a clean working tree.
The two newer performance commits, `269cb32` and `4f41949`, were preserved by
rebasing Analytics before its fast-forward push. There is no outstanding branch
divergence from that work. The branch also retains the website typography
commits (`54e939a`, `61debd6`, `8d84141`), the reconciled Focus Mode V5.1
commits (`559ee84`, `5b8ab4b`, equivalents of local `4ce3570` and `cb7bb5e`),
the V5.1 typography pass and theme sync/Close (`386bed9`). It contains the
existing V4 Answer Memory implementation (`2e7c1dc`). The
extension manifest is now `1.28.2` (local exact-question and direct-answer learning repairs described below). The V5.1 extension has not been published; it
runs as an unpacked installation loaded from
`/home/ubuntu/Documents/ace-next/extension`. An unpacked installation must be
reloaded at `chrome://extensions`; employer tabs must then be refreshed.
The owner loaded the reconciled V5.1 card in Inter and asked for two changes:
follow the computer's Day or Night setting, and a real Close control. Both are
in `386bed9`; the owner's reload of 1.28.0 is not yet recorded.

The approved V5.1 extension runs inside the existing MV3 extension. It has a
compact draggable card, visible six-dot handle, remembered position, manual
minimized dock, a Close control on the card and dock, Day and Night Wine and
Rose themes that follow the computer until the owner picks one, **Fill**,
persistent Review,
Review Complete or Review Paused, Answer Memory and Activity workspace, manual
Scan fields, dynamic field detection, existing resume/pairing support and
Alt+A. Review mirrors exact native select, radio, checkbox and multiple-select
options. Supported Workday listboxes expose their real choices through **Load employer options** inside ACE, or when opened on the employer page. Review answers remain drafts until **Approve & fill** verifies the actual employer control. Unsupported custom controls stay on the
employer form for manual completion. ACE never submits or marks Applied.
Workday listing and search routes outside `/apply/` stay quiet, including after
single-page navigation back from an application. The toolbar Wake override
remains available.

### Exact-question Review and one-entry approval repair (2026-10-25)

The owner reported that a Workday checkbox group showed an individual answer as
its question and offered only that choice, forcing duplicate entry. The display
path used `label[for=option-id]` even after the matcher found the group prompt;
choice grouping also restricted checkboxes to one `name`, although Workday can
use a distinct name for every option. All choice controls were rendered as one
single-answer dropdown, and lazy custom options required an employer-side click.

Local extension **1.28.1** now:

- Shares raw question extraction with normalized matching. Group accessible
  names and real headings identify the parent question; separate option labels
  cannot replace it. Standalone checkbox statements retain their own wording.
  Unlabelled radio options remain ineligible for profile matching.
- Groups checkbox choices by their question boundary, including Workday form
  fields with unique option names. Full checkbox/radio options are shown as
  their actual control type, with no 54-character answer truncation. Native
  selects preserve exact option codes and multiple selections.
- Keeps Review answers as drafts until **Approve & fill**. Employer edits still
  appear in Review. Drafts survive themes/rerenders; changed answers, option
  sets or detached controls invalidate a stale approval. This owner-requested
  approval sequence supersedes V5.1's previous immediate Review-to-form write.
- Lets the owner click **Load employer options** inside ACE to open/read a
  supported button listbox without choosing an answer. Ambiguous or inaccessible
  custom controls remain honest manual states; options are never invented.
- Verifies the employer state before completing approval or saving Memory.
  A reverted/rejected write stays open and cannot create reusable Memory.
  Protected questions and multi-answer checkbox sets stay application-only.
  Undo restores prior review choices/multiple selections. Never submits or
  marks Applied. Motivation exclusion, pairing, themes and card geometry remain.

Validation: 13 DOM contracts in `web/tests/extension-review.test.mjs` execute
actual content scripts against fictional forms, with explicitly simulated
layout/native activation/Chrome messaging; 258 matcher cases and Memory safety
checks pass. TypeScript, ESLint, production build, syntax, forbidden-dash and
whitespace checks pass. Playwright collects 25 extension cases, including three
new regressions, but **Chrome was not launched** because the laptop cooling
restriction remains. Existing Playwright expectations now require approval
before the employer value changes. No fresh visual screenshots, real Workday
verification, unpacked MV3 validation or browser accessibility verification is
claimed. `linkedom` is a pinned web development dependency for the DOM checks;
`npm run test:extension-dom` also runs in the web CI job.

No production deployment, scheduler operation, schema/data/auth/Gmail change or
extension publication was performed. Chrome loads this local folder:
`/home/ubuntu/Documents/ace-next/extension`. The owner must Reload ACE at
`chrome://extensions`, check version **1.28.1**, and refresh employer tabs.
Use Review, choose an answer once, then **Approve & fill**; custom button
listboxes may first need **Load employer options**. Rollback baseline is
`877b046`; restore only extension files into a separate copy if needed, without
resetting unrelated work. The owner's screenshots/answers were not saved.

### Direct employer answers, approval and future reuse (2026-10-26)

The owner clarified that they also want to answer an unknown question directly
on the employer form, have ACE adopt the answer and ask only for approval,
then auto-fill a later equivalent question. Local extension **1.28.2** adds:

- Debounced `input` and `change` detection for eligible employer controls,
  including typed answers before blur. Existing company-motivation exclusion
  runs before any value read. Password/search controls stay outside learning.
  Ordinary known profile edits do not create unsolicited learning prompts.
  Approval checks the displayed answer, option set and question again, so an
  unseen employer edit cannot be saved by a stale approval.
- An **Answer detected on form** preview with **Approve answer**, rather than
  a duplicate answer editor. Approval reads back the existing field and saves
  eligible reusable answers without another employer write or option click.
  **Edit answer in ACE** creates a draft if the owner wants a correction.
- Custom label/state mutations refresh Review even after an earlier Fill,
  covering dropdowns that do not dispatch `change`. Employer edits clear stale
  drafts, including old textarea drafts, and re-open the affected approval.
- Conservative equivalence for common prompt wording, retaining subject,
  numbers, timeframe, negation, answer shape and protected-question policies.
  Numerical/measurement prompts use specific keys. Existing legacy concepts
  are retained when correcting an equivalent stored answer, avoiding duplicate
  records that would make later reuse ambiguous. No memory records are deleted.
- Existing paired Answer Memory API and **Auto-fill known** preference power
  future reuse. It requires a successful save and real compatible controls;
  disabled auto-fill preferences are respected. Multi-answer sets, sensitive
  and company-specific answers remain application-only. Employer motivation
  remains entirely excluded. No submission or Applied-state mutation occurs.

Validation: **24** fictional DOM contracts pass, including employer text to
approval to a later equivalent auto-fill, native option codes changing between
forms, custom dropdown adoption after Fill, no duplicate writes, no learning
without approval, legacy Memory correction and protected/motivation/credential
exclusions. **258** matcher cases, expanded Memory safety checks, syntax,
TypeScript, ESLint, static dash and whitespace checks pass. **27** Playwright
cases collect (two new adoption/reuse cases); they were not executed and no new
screenshots were captured because the laptop cooling restriction still applies.
Browser event/default-action behavior, authenticated Workday and the owner's
live paired Memory save/reuse remain unverified by these local DOM tests.
Website runtime files and dependencies are unchanged in this follow-up; the
previous production build passed for the 1.28.1 repair. No production release,
backend migration, scheduler operation, Gmail change or extension publication
was performed. Baseline is `e6249ad`; reload local ACE **1.28.2** and refresh
employer tabs. Keep **Remember this approved answer** checked for routine
answers, and **Auto-fill known** on for subsequent applications.

The latest local visual comparison used fictional Chrome fixtures: the
approved Night compact reference and corrected extension compact capture were
both 318 by 332 pixels. Local artifacts are ignored under
`artifacts/extension-v5.1/`; do not commit private employer screenshots. Final
local checks at that point: seven Playwright Chrome extension tests passed
(the suite is now 22 tests across all `extension-*.spec.ts`), 258 extension
rule cases passed, `node extension/test-memory.js` passed,
`node --check extension/content.js` passed and `git diff --check` passed. These verify local
fixtures, not the owner's live authenticated employer pages or the actual
unpacked MV3 installation.

The website typography (self-hosted Inter, one token scale, sentence case
labels, tabular numbers) first went live at frontend commit `61debd6`, verified
from outside on 2026-10-24. It remains in the newer Analytics release above.
The extension shares it: Inter ships in
`extension/fonts/`, the panel registers it as `ace-inter` with the FontFace API
when a panel opens, and the V5.1 card takes the website's weights and its 11.5px
floor through one typography-only block after the approved V5.1 rules. The job
line under the wordmark keeps its approved 11px. The live website frontend is
now `340b175`, including both speed releases and Analytics. Later documentation
updates do not change the running website.
The pre-rebase local copies of V5.1 (`a1e59ff`) were retired on 2026-10-25:
`ace-next` was reset to the GitHub tip with the owner's approval. Safety
copies remain until the owner deletes them: branch `backup/local-before-sync`
and stash `knowledge-file-before-sync`.

Open production issue: Google sign-in on `https://ace.opik.net` returned 500
with `UniqueViolation auth_sessions_pkey Key (id)=(4)`. The owner's Gmail did
match the owner account; the serial sequence for `auth_sessions` is behind its
highest existing id. The guarded fix is in the working notes below. Whether
the owner ran it is not recorded, so check before running it again.

The V4 code added additive migration `0050` and authenticated
`/api/extension/memory` endpoints for approved reusable answers, with pairing
and existing answer-bank compatibility. Production reached migration `0050`
with the speed release on 2026-10-25 (`46d8738`): the owner's release output
printed `alembic_version` 0050 after a fresh backup. The Memory API itself
has not been exercised in production from here, so verify it read-only
before calling Memory operational.

## Historical core live state on 2026-10-24

At that verification the core API and database application commit was
`11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`; schema was `0049 (head)`.
The owner account release section below has its evidence. This is historical:
the speed release subsequently applied `0050`, and the Analytics release above
verified `0050` read-only. Live extension Memory behavior remains unverified.

The owner clarified that the legacy site must keep discovering jobs until they
are confident in ACE Next. At this verification, **both `ace-scheduler-1` and
`oracle-scheduler-1` were running and healthy, each against its own PostgreSQL
database.** The minute cross-database replica cron was disabled. Do not restart it while both
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

## Standalone platform specification

This section consolidates the durable product and engineering knowledge that
was previously spread across the handoff and topic files. Later sections add
dated production evidence, exact release history and operating procedures.

### Product priorities and vocabulary

ACE serves one primary owner. Its priorities, in order, are:

1. Find every eligible opening as early as practical, with high recall and low
   noise, from approved employer sources.
2. Make applying faster with safe form filling, while leaving review and final
   submission entirely to the owner.
3. Preserve a complete, trustworthy application history and resume knowledge
   base.
4. Present the system as a polished, accessible portfolio-grade platform using
   the approved Wine and Rose design.
5. Run continuously in the cloud without losing the intact legacy fallback.

Important terms:

- A **source** is one employer board, ATS tenant, official site reader or
  approved feed account with its own polling state and interval.
- A **job identity** is `(source, source_account, external_id)`. Numeric database
  IDs are internal and are not portable between the legacy and Oracle systems.
- A **content hash** is the SHA-256 identity of the posting content used to
  detect a real update without changing job identity.
- **PASS** and **REJECT** are the only eligibility outcomes. The former STRETCH
  tier was removed because the owner wants one actionable opportunities list.
- **Unverified** means the source did not provide enough description text for
  every requirement rule. It is an honest state, not a rejection.
- A **Pull** is a user-facing discovery window. Current Pulls group activity in
  15-minute windows. They are not a claim that every source polls every 15
  minutes.
- **Marks** are saved, reviewed, dismissed and applied state. Applied records
  also carry status and notes. The application stages are Applied, Screening,
  Interviewing, Offer, Accepted, Rejected, Withdrawn and No reply.
- Company tiers are BIG_TECH, TOP_TIER, ESTABLISHED and OTHER. Tiers order and
  explain results; they do not decide eligibility.
- Matching scores rank an already eligible job. Scores never decide whether a
  job is included.

### End-to-end data flow

```text
approved employer boards and feeds
              |
              v
provider adapters and discovery readers
              |
              v
authoritative snapshot, identity and content diff
              |
              v
versioned deterministic eligibility gate
              |
              v
resume scoring, Pull grouping and application state
              |
              v
PostgreSQL -> FastAPI -> Next.js -> owner browser
                    \-> paired Chrome extension
                    \-> optional alert email
```

The scheduler is the only discovery writer within each database. It stores all
postings, including rejected and closed records, so new rules can be evaluated
over history. FastAPI exposes owner-authorized JSON. Next.js proxies same-origin
`/api/*` requests to FastAPI at runtime. Caddy terminates HTTPS in production.
The extension uses a separately paired least-privilege token.

### Eligibility gate and role rules

The gate is deterministic, versioned and reproducible. It must not read the
clock, network or random state. The current default candidate profile is
`early-career`; the optional `sde2` profile may be enabled only after the owner
reviews its dry run.

The default profile admits:

- US locations, including Remote US and unambiguous US city or state forms.
  Bare `US` is matched on token boundaries so it does not match words such as
  Houston. Remote Americas or North America can include the US after explicit
  foreign-country checks.
- Full-time software engineering, machine learning and forward deployed
  engineering roles.
- New graduate, junior, associate, entry-level and otherwise unlabeled roles
  when the posting states no disqualifying requirement. Silence is unknown, not
  rejection.
- Bounded experience ranges when the candidate meets the lower bound. For
  example, `2 to 10 years` can pass on its floor, though it is not labeled new
  grad. An open-ended `3+ years` is rejected in the default profile. A stated
  requirement of 4 or more years is rejected.
- Roles silent about sponsorship. Only an explicit refusal to sponsor or a
  true work-authorization blocker rejects.

The gate rejects:

- internships, working-student roles and spelling variants such as intership;
- contract, contractor, freelance, temporary, fixed-term, contract-to-hire and
  AI-trainer work, including a structured employment type when the source
  provides it;
- senior, staff, management, hardware and broad security-role titles according
  to the current title rules;
- data engineering and data science while
  `INCLUDE_NEW_GRAD_DATA_ROLES = False`;
- postings outside the US scope;
- explicit sponsorship refusal;
- ITAR, explicit US-person or citizenship requirements, or language requiring
  access without a license. Ordinary export-control language is not itself a
  citizenship requirement.

New grad is narrower than early career. `is_new_grad` is based on explicit
title signals such as new grad, university graduate, campus and graduation
year. It is stored and used for filtering and ordering. It must not be inferred
from the broader early-career label.

The `sde2` profile differs only by admitting open-ended `3+ years`; it still
rejects 4+, 5+, senior, staff, manager and higher-level roles. Run
`python -m backend.scripts.gate_dry_run --profile sde2` before any switch.

Every gate change requires:

1. Update the versioned candidate profile or `ELIGIBILITY_RULE_VERSION`.
2. Add focused tests for both inclusion and false-positive boundaries.
3. Measure the read-only corpus impact.
4. Re-evaluate stale stored decisions. Current PASS rows are refreshed first;
   the full historical backfill runs afterward.

Do not copy the gate into an adapter or SQL filter. The real gate is the single
source of truth.

### Sources, adapters, scheduler and persistence

Current adapter families include Greenhouse, Lever, Ashby, Workday,
SmartRecruiters, Workable, Eightfold classic and PCSX, Jibe, Avature, Apple,
Google, Atlassian, Shopify, Gem, IBM, Amazon, Oracle Recruiting, ByteDance,
RippleMatch, Simplify, sitemap readers and related official-site readers.
Respect each host's robots policy and refusals.

Source rules:

- There is one fetch path per provider. Diagnostic scripts use the same real
  adapter contract so tuple shapes and cleanup logic cannot drift.
- A complete successful snapshot is authoritative for lifecycle. Never return
  a partial page set after a transient failure because missing rows would be
  marked closed.
- Workday and SmartRecruiters can expose a cheap list plus costly detail calls.
  Detail fetches may be predicated through the real title gate, but every list
  item must still be emitted for lifecycle.
- Use conditional HTTP where supported. A 304 advances success state but does
  not rediff the body. Force an unconditional refresh at least every six hours
  so a bad ETag cannot hide updates indefinitely.
- Retry transient 429, 500, 502, 503, 504 and connection failures with bounded,
  jittered backoff and `Retry-After` limits. Do not retry a real 404 as if it
  were transient.
- A 401, 403, 405, 429, bot challenge or CSRF-protected API is a refusal. Back
  off. Do not bypass it, rotate around it or restart repeatedly.
- Never mass-close jobs after an empty, partial, refused or failed response.
- Scheduler polling is bounded and concurrent. Slow sources continue in a
  persistent pool while other due sources run. A source cannot start twice.
- Restarts resume from persisted `last_success_at`; they do not make every
  source immediately due. Shared-edge providers such as Eightfold are paced.
- Poll intervals are per source and can differ widely. Amazon and expensive
  boards poll less often than ordinary boards.
- New sources are re-read from the database between cycles and do not require a
  process restart.

Source lanes:

- Lane A: employer ATS or official-site readers with full descriptions.
- Lane B: curated early-career feeds when employer descriptions are unavailable;
  these are browse-only and clearly unverified.
- Lane C: RippleMatch, the one approved exception where the apply link is the
  recruiting platform because some early-career roles exist only there.

The official employer posting is the apply target everywhere else. An
aggregator that links only to itself is not acceptable coverage.

Persistence rules:

- Stable identity is `(source, source_account, external_id)`.
- A title, location, description or employment-type change updates the same job
  and must alter the content hash.
- `job_evaluations` and `job_resume_scores` are derived, rebuildable tables.
  They carry input hashes and algorithm/rule versions so stale rows are
  detectable.
- PostgreSQL is production. Tests use a JSON fallback and SQLite where
  appropriate, so structural PostgreSQL behavior needs explicit tests.
- Long source-provided values such as multi-location strings use unbounded text
  where truncation could change gate meaning.

### Discovery coverage and recall

The most dangerous failure is silence: a missed posting produces no exception.
Coverage must be measured against independent employer lists, source audits and
the owner's known examples, not inferred from a healthy-looking queue.

Discovery can identify an ATS board from an employer's own careers page or from
approved feed links, then register it for direct reading. A feed hit must not
prevent the employer board from being read. A board that stops answering is a
company ACE has stopped reading, even if old jobs remain in the database.

Known unreachable or deliberately untouched sources include sites whose
robots policy or bot protection refuses access. Historical examples include
Tesla, Citadel, Citadel Securities, D. E. Shaw, LinkedIn and Equinix. IBM uses
its permitted site-search API rather than bypassing its careers WAF. Cloud IPs
can be treated differently from a home connection, so refusal rates must be
measured after deployment.

The owner currently compares independent legacy and Oracle discovery. Compare
source identity, official posting identity and aligned time windows. Do not
compare numeric IDs or demand identical totals. A recent private comparison
showed most one-sided jobs converging after an hour and no different
eligibility decision on shared jobs; that was evidence for one window, not a
permanent guarantee.

### Resume matching and applications

Resume matching is lexical and deterministic, with approved related-skill
partial credit. It is not a semantic model and never invents evidence. Matching
states are:

- `scored`: a current usable score exists;
- `pending`: the eligible job is waiting for a scoring sweep;
- `no_description`: source requirements were not readable;
- `insufficient`: too little recognized requirement text for a responsible
  score;
- `no_resume`: there is no active resume.

The scheduler scores active PASS jobs missing a current score, changed since
scoring or scored by an older algorithm, in bounded batches. One failure is
logged and retried later; it does not receive an invented score.

Application history comes from applied `job_marks` plus
`external_applications`. Marked pages bypass current gate and active filters so
closed or now-ineligible jobs never vanish from the owner's own history.
Application totals include historical submitted stages, not only rows whose
current label is exactly Applied. Avoid double-counting the same application
through marks and external rows.

Marking Applied must:

- update the row and every visible total immediately;
- synchronize other tabs and surfaces;
- persist through the authenticated API and survive refresh and sign-in;
- roll back the optimistic state and counters if the save fails;
- prevent duplicate mutations and stale race outcomes.

The spreadsheet import UI was intentionally removed. CSV export remains.
Legacy preview/import API routes may remain unused, but no interface should
revive the daily spreadsheet workflow without a new owner decision.

An unmarked listing can show `Applied before` when an earlier applied posting
has matching company/title and compatible location. This is derived at read
time and never copies the mark. Requisition numbers explain whether the new
posting may be a distinct opening. ACE shows the resemblance and lets the
owner decide.

### API and key data domains

The browser uses authenticated JSON with `Cache-Control: no-store`. Important
API families include:

- jobs, details, facets, stats and Pull windows;
- marks, application stages, notes, external applications and CSV export;
- answer bank, work history and education history;
- active resume, matching, Resume Studio documents, facts, versions and
  assessments;
- coverage and source registration;
- submission-filtered Analytics, exact application drilldowns and reviewed
  outcome/sponsorship evidence;
- owner account, sessions, email-code flows and Google callback;
- extension pairing and Answer Memory;
- health and safe operational status.

Core durable data includes jobs, sources, source states, evaluations, scores,
Pull sessions, marks, external applications, answers, work/education history,
legacy resumes, Resume Studio tables, users, browser sessions, extension tokens
and email-code records. Do not replace real aggregates with demo fixtures.

### Website product and design contract

The website is a real Next.js App Router product, not an iframe or screenshot.
The final approved reference is Wine and Rose V2. Older purple/gold,
anthracite, gray, alternate auth and homepage concepts are historical and must
not return.

Required routes and contracts:

- `/`: public cinematic home with no private owner data.
- `/login`: real owner sign-in using the approved split composition.
- `/signed-out`: shown only after a real session is invalidated.
- `/app/pulls`: authenticated landing page and truthful 15-minute discovery
  windows.
- `/app/opportunities`: eligible-job search, filters, sorting, official links,
  evidence and durable actions.
- `/app/jobs/[id]`: job details, matching evidence, eligibility explanation and
  application actions, including closed jobs.
- `/app/applications`: real application history, stages, dates, notes, filters
  and export.
- `/app/analytics`: the approved four-tab application Analytics interface,
  using `/api/analytics`, separate from Career Dashboard.
- `/app/applications/analytics`: read-only application records matching the
  exact Analytics selection, with links to existing stored-job controls.
- `/app/dashboard`: Career Dashboard for combined application intelligence.
- `/app/applications/inbox`: owner-controlled Gmail Inbox Intelligence,
  evidence review and outcome reconciliation. This route is present in the
  current code. The 2026-10-25 production check found zero Gmail connections;
  Google sign-in does not mean Gmail is connected.
- `/app/resume-studio`: documents, knowledge, versions, ATS checker and history.
- `/app/extension`: pairing, token revocation, setup and answer-memory access.
- `/app/archive`: historical reviewed and dismissed state.
- `/app/coverage`: source coverage, unsupported/refused sources and add-source
  workflow.
- `/app/settings`: theme, owner account, session security and existing
  preferences.

Old Browse and Companies routes redirect to Opportunities. Saved data still
exists even though Saved is secondary and not in primary navigation. Pulls is
home; the separate Career Dashboard does not replace it. Supporting routes
also exist for Saved, Answers, skill insights, company detail, Resume Studio
subpages, More and sign-out. Do not replace Pulls with a generic Dashboard or
Queue. The owner rejected a global Search or Jump command palette.

Locked identity and themes:

- The wordmark is exactly lowercase `ace`, with the `a` in wine and `ce` in the
  theme foreground. No logo tile, uppercase mark, subtitle or tagline.
- Night is black and deep wine. Day is rose wine and bright white.
- Primary V2 tokens are Night/Day respectively: base `#09070b`/`#fff9fb`, side
  `#120c13`/`#fff6f9`, canvas `#191019`/`#fffafd`, surface
  `#251825`/`#ffffff`, raised `#302131`/`#fff0f5`, hover
  `#3d283b`/`#fee8ef`, edge `#574050`/`#e9d3de`, text
  `#fff7fa`/`#27131f`, muted `#cfbcc6`/`#745a69`, sub
  `#ab8b9e`/`#946b80`, accent `#a62957`/`#97244f`, accent-high
  `#c93b70`/`#b63566`.
- Public and auth screens use the full angular sculptural A, reflective light
  trails, floor reflection and glass depth. The whole A must remain visible on
  desktop. Scale or reflow deliberately on smaller screens rather than clipping
  it.
- Use the shared semantic token layer on all pages. Do not let individual pages
  fall back to gray, generic red, purple, navy or framework defaults.
- Required review sizes include 1440x900, 1600x900, 1280x800, 1024px tablet and
  390px phone, in Night and Day, without horizontal overflow.
- Functional text must meet WCAG AA. Keyboard order, focus visibility,
  reduced-motion behavior, loading, empty, unavailable and failure states must
  be honest.

There must be no visible Unicode em dash and no en dash used as punctuation in
the website, extension, generated email or assistant-authored user-facing copy.
Also avoid decorative pseudo-elements that visually imitate dash punctuation.
Static scans are necessary but not sufficient; rendered pages, dynamic toasts,
dialogs, labels, placeholders, accessible names and pseudo-content must be
tested in both themes.

The V2 demo contains fictional navigation and data for visual review only.
Never ship its DESIGN DEMO selector, hash router, Preview workspace bypass,
sample names, hardcoded counts, fake health, fake scores or simulated saves.

### Pulls metric contract

Pulls must distinguish:

- distinct sources checked from raw attempts and retries;
- postings inspected from newly discovered postings;
- newly discovered from updated or re-seen postings;
- qualifying opportunities from all observed jobs;
- failed, skipped, blocked and zero-result checks;
- no check telemetry recorded from a successful check with zero new jobs.

The source of truth is backend telemetry with exact time boundaries and display
timezone conversion. Older windows without telemetry say `not recorded` rather
than showing zero. Health indicators must disclose freshness and never show a
reassuring success state when the backend has not confirmed one.

### Chrome extension and Answer Memory

The extension is Manifest V3. Important implementation areas are
`extension/content.js`, `fields.js`, `background.js`, the popup/side panel,
storage, pairing and rule tests. The current local manifest version is 1.28.0.
The approved interface is ACE Focus Mode V5.1; older extension interfaces are
historical.

V5.1 behavior:

- Default to a compact floating card around 318px wide, not a full-height panel
  covering the form.
- Preserve Overview, Review, Memory, Activity, Fill, Scan fields, resume use,
  pairing and Alt+A.
- Use the lowercase `ace` wordmark, Wine and Rose Day/Night themes, clean
  outline icons and a visible six-dot grip.
- Provide compact, optional wider workspace and a manually chosen minimized
  dock.
- Drag freely from eligible non-interactive card and dock surfaces. Do not steal
  clicks, typing, text selection or scrolling from form controls. Use a movement
  threshold, clamp to the visible viewport, persist normalized position, allow
  handle keyboard movement and reset on handle double-click.
- Never auto-minimize after Fill, approval, skip, a detected question or Review
  completion. Review remains open and ends in a persistent truthful completion
  state until the user chooses Minimize.
- Detect dynamic fields with restrained, debounced observers and retain manual
  Scan fields as a fallback.
- Job listing and search routes must remain quiet. In particular, Workday
  listing/search routes outside `/apply/` stay quiet after SPA navigation. The
  toolbar Wake override remains available.

Review mirrors the real employer control for eligible questions: native select,
radio, checkbox, multiple-select, text, textarea and only supported custom
widgets with their actual choices. Page-to-ACE and ACE-to-page synchronization
must verify the employer control's real selected value. Unsupported or
ambiguous custom controls remain manual. Never display a generic text box for a
native select and never report success without reading the actual state back.

ACE fills; the owner reviews; the owner submits. Extension code must never call
`form.submit()`, `requestSubmit()`, synthesize a submit event, click an employer
Submit control, irreversibly advance a form, or mark a job Applied because Fill
ran. Applied state needs a separate explicit owner action.

Employer-specific motivation questions are entirely employer-page-owned. This
includes `Why this company?`, `Why do you want to join us?`, `What interests you
about joining [company]?` and materially equivalent questions. For them ACE:

- leaves the original employer field visible, editable and untouched;
- does not fill, suggest, mirror, capture, observe, log or send the answer;
- excludes the question from Review, progress denominators, Memory and
  Activity;
- does not change the field during Fill, Scan, navigation, theme changes,
  dragging, minimizing or dynamic rerender;
- retains historical server records but excludes them from automatic reuse;
- may show only a truthful reminder to finish employer-owned questions on the
  employer form.

Classification uses the question label and employer context, never the answer.
It must distinguish company motivation from technical questions such as `Why
did you choose eventual consistency?`. One shared predicate must guard scan,
fill, queue, observability, status counts, activity and memory retrieval.

Unknown ordinary questions enter Review. Only genuinely equivalent approved
general answers may be reused when type, options, scope and context align.
Authorization, sponsorship, citizenship, legal declarations, compensation and
self-identification require conservative, per-application handling. Never
infer a narrow sensitive answer from a broad saved answer.

V4 added migration 0050 and authenticated `/api/extension/memory` behavior for
approved reusable answers, with existing answer-bank and pairing compatibility.
Production applied migration 0050 on 2026-10-25 (owner's release output);
live Memory behavior is not yet exercised there. Verify read-only before
relying on it.

### Resume Studio

Resume Studio is deterministic and has no generative AI. Its backend lives in
`backend/app/studio/`; routes are under `/api/studio`. Migration 0039 created
documents, career facts with audit events, versions and assessments.

- Original document bytes are retained as uploaded.
- PDFs render through an authenticated content endpoint and short-lived browser
  Blob URL. DOCX and other formats show an honest download action when the
  browser cannot render them reliably.
- Facts are separate from wording. Parsed facts begin as suggested; owner-entered
  facts begin verified. Retirement marks a fact deprecated rather than deleting
  it. Only verified facts count as evidence.
- The first resume becomes primary only if no primary exists. Making a version
  primary copies its text into the legacy matching table and triggers the
  established rescore behavior.
- The ATS checker reports an `Estimated ace compatibility score`, not an
  employer ATS score. Algorithm `ats-2026-10-14-v1` weights requirement evidence
  45, parseability 20, hard fit 20 and content quality 15.
- Evidence used in experience, project or summary text receives full credit;
  skills-list-only evidence receives 0.75; approved related evidence receives
  0.5; preferred requirements weigh half.
- A posting under 400 characters, unverified, or naming fewer than three skills
  is insufficient job data and gets no aggregate score. A resume under 200
  characters is unreadable. Neither condition is represented as zero.
- The checker gives evidence quotes, line numbers, findings, unknowns and
  prioritized recommendations. Hard fit reuses the real gate diagnostically and
  never filters the Resume Studio result.

Not yet built: the full no-AI tailoring workflow, side-by-side approval diff,
owner-template DOCX/PDF export and durable background jobs. Future tailoring
may only reorder or reword verified facts and must never invent experience.

### Alerting, time and privacy

Alert email is one message per completed Pull, not one email per job. Delivery
uses Resend only when configured. Missing mail configuration must be reported
honestly and must not block discovery. Email clients are not browsers, so email
markup and text need their own tests.

Instants are stored in UTC. Every human-facing date is formatted in the owner's
configured display timezone. Historical CSV drift proved that UTC storage and
local calendar dates are separate concerns.

The public repository must never contain real resumes, answer values, owner
email, phone, profile photo, application text, employer screenshots, database
dumps, tokens, secrets or session cookies. Fixtures are fictional. Extension
diagnostics carry no answer values. Private reports and artifacts stay ignored.

### Testing and operational doctrine

Durable rules learned from prior incidents:

1. Verify the running system, database and exact commit. A local build or Git
   push is not a deployment.
2. Build every affected image before `up`. Containers bake source; a host-side
   edit does not change a running image. Build `migrate` when an approved schema
   release needs it. A schema-free API/web release uses `--no-deps` and does not
   run migration or recreate unrelated services.
3. Use `docker compose --env-file .env` with the Oracle compose file. Omitting
   it once substituted blank database variables and began recreating services.
4. Do not run `docker compose down`, remove volumes or recreate the scheduler
   during an ordinary web/API release.
5. Production mutations, migrations, deployments, scheduler changes, DNS,
   extension publication and destructive data work need explicit owner approval
   for that operation.
6. Tests against live servers must wait for committed writes and must not wait
   on a stale UI flag. Restarting a server mid-browser-suite invalidates the run.
7. Never guess which rows are test data. Use isolated fictional databases.
8. An unpacked extension must be reloaded at `chrome://extensions`, then target
   employer tabs must be refreshed or reopened.
9. Use exact source/time-window parity rather than aggregate reassurance.
10. Every found bug receives a regression test that reproduces its real shape.

Current validation families include backend unit/integration tests, Next.js
TypeScript and ESLint, production build, Playwright with fictional data,
extension matcher and memory tests, Chrome-extension browser tests, forbidden
dash scans, migration rehearsal, private inventory checks and production health
verification. Report actual results and distinguish local fixtures from live
production evidence.

### Historical failures that define current safeguards

- Bare `US`, city-only locations and country/state code collisions caused false
  location decisions. Boundary-aware parsing and country expansion now have
  corpus tests.
- Experience extraction once ignored intervening words and range ceilings.
  Open-ended minimums and bounded ranges now have separate semantics.
- A structured contract flag was discarded before persistence and omitted from
  content hashing and a backfill reconstruction. Eligibility-relevant fields
  must cross every persistence and reconstruction boundary.
- Double-encoded HTML entities hid requirements from phrase rules. All adapters
  share fixed-point decoding; do not add another hand-rolled decoder.
- One incomplete paginated response could have closed hundreds of jobs. Partial
  snapshots are never authoritative.
- Repeated restarts caused a shared ATS edge to refuse ACE. Restarts resume
  persisted schedules and refusals back off.
- Waiting for the slowest source delayed every other source. Slow workers now
  continue without holding the scheduling loop.
- A `varchar(500)` location failed a whole board. Do not truncate meaning-bearing
  source data.
- Feed coverage once prevented direct-board coverage, and an aggregator returned
  only its own links. Reachability and ownership of the apply URL are separate
  checks.
- URL normalization once removed Greenhouse job IDs in query parameters and
  confidently matched the wrong application. Remove only known tracking
  parameters; ambiguity is safer than a false identity.
- Marked pages once inherited PASS and active-only filters, hiding the owner's
  history. User-owned marks bypass those discovery filters.
- A UI held several copies of one job and updated only one, so Applied looked
  unsaved until refresh. Mutations must update every cache surface or invalidate
  a shared source of truth.
- Resume scores were written only on upload and silently went stale. Event-driven
  bounded scoring now handles new jobs, changed content, changed rules and changed
  algorithms.
- Source counts and activity labels repeatedly described new jobs as all jobs
  checked. Metric labels must match the exact query population.
- Browser fixtures once tested a substitute instead of the real extension.
  Extension tests must load the actual manifest and content scripts.
- Real forms exposed custom widgets, repeating blocks, delayed fields, phone
  country ordering and multi-page navigation. The employer DOM, not a generic
  form model, is the specification.
### Known limitations and future work

- Both discovery systems are intentionally independent today. Application state
  entered in ACE Next does not synchronize back to legacy.
- Offsite Object Storage backup is not configured; backups on the Oracle VM do
  not protect against loss of that VM.
- Some sources refuse home or cloud access, and no bypass is permitted.
- Borderline source and job behavior can change as providers alter undocumented
  APIs. Coverage audits remain continuous work.
- Production V4 Memory status needs read-only verification.
- Recheck branch and remote before each change; the earlier divergence was
  reconciled and the 2026-10-25 Analytics release preserved both speed commits.
- Actual submitted resume versions, application channels and complete response
  observation coverage are not stored. These remain unavailable, not inferred.
- Production had zero Gmail connections and zero petition reports at the
  Analytics release. Live mailbox sync, actual official evidence imports,
  signed-in production visual review and final owner visual acceptance remain
  outstanding. No OAuth consent or import is authorized by this documentation.
- Browser validation on this laptop is suspended until cooling is fixed. The
  successful fictional Analytics captures and test logs are already retained;
  do not repeat heavy Chrome runs merely to refresh documentation.
- Resume Studio tailoring and export remain later scope.
- The SDE II profile remains off until the owner approves its dry run.
- Post-launch retention is designed but must not run until backup, restore,
  closure detection, tombstones, rollups and protected-job predicates are all
  proven.

## Code-verified implementation map

This section is the implementation index a new chat should use before touching
code. It was reconciled against the repository on 2026-10-25. It records the
important boundaries and contracts without copying secrets or private rows.

When facts conflict, use this order:

1. The owner's newest explicit instruction controls product intent and
   authorization.
2. The current working tree, migrations and tests control implementation facts.
3. The newest dated, independently verified entry in this file controls claims
   about production state.
4. Older sections and archived topic documents are historical evidence only.

Never infer that code is deployed because it exists locally, that a migration
ran because its file exists, or that production is healthy because an older
check passed.

### Repository and technology map

The repository is one product with four execution surfaces:

```text
backend/                 Python domain logic, scheduler and FastAPI
backend/migrations/      Alembic schema history 0001 through 0050
web/                     Next.js App Router owner website
extension/               Manifest V3 Chrome autofill extension
deploy/oracle/           production Compose, Caddy, backup and parity tools
scripts/                 repository-wide validation helpers
design/                  approved website and extension visual evidence
docs/                    historical plans, audits and incident evidence
```

The core runtime technologies are PostgreSQL 16, SQLAlchemy, Alembic, FastAPI,
Uvicorn, Next.js 16.4.2, React 19.2.8, TypeScript 5, Tailwind CSS 4, Playwright
1.56, Chrome Manifest V3, Docker Compose and Caddy. Python dependencies are
pinned in `backend/requirements.txt`; frontend dependencies and commands are in
`web/package.json`. Do not introduce another framework for an existing layer
without a product-level reason.

### Backend layers and ownership

The backend is organized by responsibility:

- `backend/app/adapters/` contains provider readers for Amazon, Apple, Ashby,
  Atlassian, Avature, ByteDance, Eightfold, Eightfold PCSX, Gem, Google,
  Greenhouse, IBM, Jibe, Lever, Oracle Recruiting, RippleMatch, Shopify,
  Simplify, sitemap jobs, SmartRecruiters, Workable and Workday. Shared HTML
  text decoding, conditional HTTP cache and retry behavior also live here.
- `backend/app/discovery/` detects boards, follows approved feed links, defines
  providers and the watchlist, and registers discovered sources.
- `backend/app/scheduling/` owns the source catalog, registry, dispatch,
  due-time runtime and one-source poll service. It does not own provider parsing
  or eligibility policy.
- `backend/app/workflows/source_snapshot.py` connects authoritative snapshot
  persistence to deterministic evaluation.
- `backend/app/persistence/` owns hashing, stable openings, source lifecycle,
  Pull sessions, evaluation materialization and repository operations.
- `backend/app/evaluation/` owns the eligibility decision and alert freshness.
  `backend/app/intelligence/` owns role, company and eligibility vocabulary.
- `backend/app/matching/` parses requirements, recognizes skills and computes
  resume scores. `backend/app/applications/` owns application import matching,
  prior-application evidence and application service behavior.
- `backend/app/coverage/` audits employer coverage, cadence, reachability,
  probing, diagnosis and safe recovery.
- `backend/app/verification/` records employer-page evidence without bypassing
  refused sources.
- `backend/app/auth/` owns password security, sessions, CSRF, Google owner
  identity, avatar processing and request guards.
- `backend/app/inbox/` owns Gmail read-only access and conservative evidence
  reconciliation. `backend/app/intelligence/` also supplies combined dashboard
  aggregates and action vocabulary.
- `backend/app/studio/` owns resume documents, facts, sections, versions,
  legacy bridging and deterministic ATS assessments.
- `backend/app/answers/`, `alerts/` and `mail/` own answer catalogue behavior,
  Pull alert composition and Resend delivery respectively.
- `backend/app/api/main.py` contains the established jobs, marks, resumes,
  answers, history, coverage and source endpoints. `backend/app/api/routers/`
  contains Analytics, auth, Pulls, Studio, company intelligence, dashboard, inbox,
  combined intelligence, owner export and system routes.
- `backend/app/db/models.py` is the ORM schema map. `db/session.py` creates
  sessions and `db/base.py` defines shared SQLAlchemy metadata.
- `backend/scripts/` contains explicit operational and audit entry points. A
  script is not automatically scheduled merely because it exists.

One-source polling follows this transaction boundary:

```text
fetch external source with no database transaction held
                    |
                    v
begin one database transaction
                    |
                    v
reconcile source and posting lifecycle
                    |
                    v
evaluate changed jobs and materialize read models
                    |
                    v
commit, then expose through FastAPI
```

A conditional `not modified` result advances source success state and confirms
the previous full count without re-evaluating unchanged rows. A failed or
partial fetch never becomes an authoritative empty snapshot. The runtime uses
bounded concurrency of six, keeps slow workers alive across cycle boundaries,
prevents a source from running twice, serializes shared Eightfold edges, checks
in-flight work frequently, runs maintenance every six hours and exponentially
backs off refusal statuses 401, 403, 405 and 429 up to six hours.

### HTTP, authorization and request boundaries

FastAPI is the authorization authority. In production `ACE_AUTH=required`.
`/healthz` and the explicit sign-in/setup flows are the narrow exceptions;
private product routes require either the owner's browser session or an API
token whose scope permits that route. `ACE_AUTH=disabled` is a local/private
rollback mode with network-origin safeguards, not a public no-auth mode.

Browser authentication uses an opaque session cookie whose token is stored
hashed in PostgreSQL. Mutations also require the per-session CSRF value. The
browser client reads the CSRF cookie and sends it as `X-CSRF-Token`. Passwords
use Argon2id. Login, reset and email-change codes are hashed, expiring, single
use and rate limited. Extension tokens are separate, revocable and
least-privilege. Google owner sign-in and Gmail read-only consent are separate
OAuth grants and must never reuse each other's token or scope.

Server-rendered Next.js reads forward only the owner session cookie to FastAPI,
use `cache: no-store`, and redirect a 401 to sign-in with the original safe
destination. Browser mutations use the same-origin `/api/*` proxy. That proxy
reads `API_ORIGIN` at request time, forwards method, query, safe headers and
body, strips hop-by-hop headers, preserves multiple `Set-Cookie` values and
returns an honest 502 when FastAPI is unavailable. This runtime proxy avoids a
previous build-time origin bug and means the browser needs no CORS exception.

### Complete backend API inventory

The endpoint inventory below is code-verified. `/api/studio` is the router
prefix for every Studio suffix listed in its row.

| Domain | Method and path | Purpose |
| --- | --- | --- |
| Health | `GET /healthz` | Process and dependency health suitable for service checks. |
| Root | `GET /` | Redirects to the website entry surface. |
| Jobs | `GET /api/jobs`, `GET /api/jobs/{job_id}` | Filtered paginated listings and one durable job detail. |
| Jobs | `GET /api/facets`, `GET /api/stats` | Facet counts and real aggregates over the same filters. |
| Pulls | `GET /api/sessions`, `GET /api/pulls` | Legacy session list and the truthful Pulls read model. |
| Resume | `GET /api/resume`, `POST /api/resume` | Active legacy resume metadata/text path and upload. |
| Marks | `GET /api/marks`, `PUT /api/marks/{job_id}` | Counts and partial saved/review/applied/status/note mutation. |
| Applications | `GET /api/applications/external`, `GET /api/applications/export.csv` | External history and CSV export. |
| Legacy import | `POST /api/applications/preview`, `POST /api/applications/import` | Preserved API compatibility; no current spreadsheet UI. |
| Answers | `GET /api/answers`, `PUT /api/answers` | Whole owner answer bank. |
| History | `GET /api/history/{kind}`, `PUT /api/history/{kind}` | Ordered work or education history. |
| Sources | `GET /api/coverage`, `POST /api/sources` | Coverage read model and owner-requested source discovery. |
| Memory | `GET /api/extension/memory`, `PUT /api/extension/memory` | List and create/update reusable extension memories. |
| Memory | `DELETE /api/extension/memory/{memory_id}`, `POST /api/extension/memory/{memory_id}/used` | Delete or record use of one memory. |
| Auth | `GET /api/auth/status`, `POST /api/auth/setup` | Auth mode, owner/session state and first owner setup. |
| Auth | `POST /api/auth/login`, `POST /api/auth/login/verify`, `POST /api/auth/logout` | Password start, email-code confirmation and session revocation. |
| Auth | `GET /api/auth/google/start`, `GET /api/auth/google/callback` | Owner-only Google OpenID Connect. |
| Account | `GET /api/auth/account`, `PATCH /api/auth/account` | Owner profile read/update. |
| Account | `GET /api/auth/account/avatar`, `PUT /api/auth/account/avatar`, `DELETE /api/auth/account/avatar` | Private processed owner avatar. |
| Account | `POST /api/auth/account/email/start`, `POST /api/auth/account/email/confirm` | Password-protected verified email change. |
| Security | `GET /api/auth/sessions`, `POST /api/auth/sessions/revoke-others`, `POST /api/auth/password` | Session inventory, revoke others and password change. |
| Recovery | `POST /api/auth/reset/request`, `POST /api/auth/reset/confirm` | Email-code password recovery. |
| Pairing | `POST /api/extension/pairing`, `POST /api/extension/pair` | Create and redeem a short-lived extension pairing code. |
| Pairing | `GET /api/extension/tokens`, `DELETE /api/extension/tokens/{token_id}` | List and revoke extension tokens. |
| Company | `GET /api/companies`, `GET /api/company-intelligence`, `GET /api/company-intelligence/batch` | Company lists and evidence-backed company intelligence. |
| Dashboard | `GET /api/dashboard` | Preserved discovery/resume-fit/application aggregate used by the former Analytics page. |
| Analytics | `GET /api/analytics` | Read-only submission-date/role-filtered application metrics, evidence, official petition series and exact paginated drilldowns with `records=1`. |
| Intelligence | `GET /api/intelligence`, `GET /api/intelligence/actions`, `POST /api/intelligence/actions` | Combined metrics and owner action queue. |
| Inbox | `GET /api/inbox/connection`, `PATCH /api/inbox/connection`, `DELETE /api/inbox/connection` | Gmail connection state, settings and disconnect. |
| Inbox | `GET /api/inbox/google/start`, `GET /api/inbox/google/callback` | Separate Gmail read-only OAuth. |
| Inbox | `POST /api/inbox/sync`, `POST /api/inbox/backfill` | Owner-triggered incremental sync and preview-only backfill. |
| Inbox | `GET /api/inbox/messages`, `GET /api/inbox/applications`, `GET /api/inbox/events` | Evidence, reconciled applications and event ledger. |
| Inbox | `PATCH /api/inbox/messages/{message_id}/decision`, `PATCH /api/inbox/automation` | Review decision and tightly gated automation preference. |
| Inbox | `POST /api/inbox/review`, `POST /api/inbox/events/{event_id}/undo` | Apply reviewed evidence or undo one event. |
| Inbox | `DELETE /api/inbox/snippets` | Purge retained message snippets. |
| Studio | `GET /api/studio` | Resume Studio overview. |
| Studio | `POST /api/studio/documents`, `GET /api/studio/documents/{document_id}`, `GET /api/studio/documents/{document_id}/file` | Upload, inspect and privately download original documents. |
| Studio | `GET /api/studio/facts`, `POST /api/studio/facts`, `PATCH /api/studio/facts/{fact_id}`, `GET /api/studio/facts/{fact_id}/history` | Fact ledger and audit history. |
| Studio | `GET /api/studio/versions/{version_id}`, `POST /api/studio/versions`, `POST /api/studio/versions/{version_id}/primary` | Resume versions and primary selection. |
| Studio | `POST /api/studio/check`, `GET /api/studio/assessments`, `GET /api/studio/assessments/{assessment_id}` | Deterministic ATS assessment creation and history. |
| Export | `GET /api/export.json` | Owner data export. |
| System | `GET /api/system` | Safe operational state for owner UI. |

Interactive API docs are off by default through `API_DOCS=false`. Do not expose
them merely for convenience in production.

### Database schema and durable ownership

All current ORM models live in `backend/app/db/models.py`. The important table
contracts are:

| Table | Durable responsibility |
| --- | --- |
| `jobs` | Stable source identity, company, requisition, title, location, description, official URL, posting/update times, employment type, content hash, first/last seen, active/closed state and Pull association. |
| `source_states` | Per source/account initialization, last success, count, ETag, Last-Modified, unchanged state and last full fetch. |
| `job_sources` | Configured source type/account/host/company, enabled state, interval, discovery provenance and verification timestamps. |
| `job_evaluations` | One materialized decision per job with PASS/REJECT state, family, priority, rule version, reasons, experience evidence, early-career/new-grad flags, verification and input hash. |
| `resumes` | Legacy resume bytes/text metadata, content hash, skills, active flag and upload time. |
| `job_resume_scores` | Job/resume score, matched/missing/related skills, previous score, algorithm version and score time. |
| `poll_sessions` | Pull start/activity, discovered and qualifying counts, boards/postings checked, raw attempts/failures, notification and alert state. |
| `job_marks` | Saved, review, applied, application status, timestamps and owner note for a stored job. |
| `external_applications` | Applications with no attached posting, including company/title matching key, applied date, status, URL and timestamps. |
| `application_events` | Append-oriented status evidence with previous/new value, actor, reason, Gmail link, undo and dedupe metadata. |
| `gmail_connections` | Encrypted Gmail grant state, cursor and owner-controlled automation settings. |
| `gmail_messages` | Deduplicated message evidence and review state. |
| `company_petition_reports` | Reviewed USCIS employer petition evidence, never guessed workforce sponsorship. |
| `application_answers` | Ordered answer bank entries and precise screening fields accumulated through migrations. |
| `extension_answer_memory` | Revisioned reusable question concept, answer, type, source context, use count and timestamps. |
| `history_entries` | Ordered work and education blocks used by the extension. |
| `source_probes` | Reachability and diagnostic probe history. |
| `employer_page_readings` | Employer-page verification evidence. |
| `users` | Single owner identity, profile, avatar, password hash, role and optional bound Google subject. |
| `auth_sessions` | Hashed browser sessions, CSRF material, expiration, activity and revocation. |
| `api_tokens` | Hashed, scoped, revocable extension tokens. |
| `auth_codes` | Hashed login, reset and email-change codes with expiration and consumption. |
| `login_attempts` | Persistent throttling evidence. |
| `resume_documents` | Original Resume Studio uploads and extracted metadata/text. |
| `career_facts` | Suggested, verified or retired career facts separate from resume prose. |
| `career_fact_events` | Fact audit ledger. |
| `resume_versions` | Versioned resume text and primary status. |
| `resume_assessments` | Deterministic job/resume assessment results and evidence. |

Stable job identity is the unique source tuple, never the integer `jobs.id`.
User-owned application, auth, resume and answer tables are protected state and
must not be regenerated during a discovery backfill. Evaluation and score rows
are derived, but their version and input hashes must remain reproducible.

### Complete migration ledger

Alembic history is additive from 0001 through 0050:

- 0001 jobs/source state; 0002 notification outbox; 0003 job sources; 0004
  source host; 0005 notification digests.
- 0006 evaluations; 0007 early-career flag; 0008 requirements verification;
  0009 resume matching; 0010 source HTTP cache; 0011 wider job identity; 0012
  last full fetch.
- 0013 Pull sessions; 0014 related-skill credit; 0015 marks; 0016 previous match
  score; 0017 application status; 0018 external applications.
- 0019 answers; 0020 extended answers; 0021 answer ordering; 0022 relocation and
  onsite answers; 0023 employment type; 0024 standard answers; 0025 normalized
  choice answers; 0026 work/education history.
- 0027 source probes; 0028 new-grad flag; 0029 Pull notification time; 0030
  PayPal answers; 0031 company/title index; 0032 unbounded job location; 0033
  employer-page readings; 0034 posting-link index; 0035 Pull check counts; 0036
  locale-independent posting-link index; 0037 Pull alert state.
- 0038 owner authentication; 0039 Resume Studio; 0040 Pull telemetry; 0041
  Google owner identity; 0042 Pull telemetry repair; 0043 owner display name.
- 0044 combined intelligence evidence; 0045 precise screening answers; 0046
  precise Workday answers; 0047 Meijer Workday answers; 0048 Verizon Workday
  answers; 0049 owner profile; 0050 extension Answer Memory.

The latest production schema recorded in this file is 0050, printed by the
owner's speed release and verified again read-only during the Analytics release
on 2026-10-25. All four existing Inbox/petition tables were present. Analytics
added no schema or migration. A local migration file is never proof of what
production runs. Always read `alembic_version` before planning a migration,
rehearse from a current backup, and follow the safe migration procedure later
in this file.

### Frontend architecture and current route map

The website is a server-first Next.js App Router application. Page modules
perform authenticated no-store reads on the server. Interactive client
components use the same-origin API proxy for mutation. Shared types and helpers
live under `web/src/lib/`; reusable UI and behavior live under
`web/src/components/`.

This repository uses Next.js 16.4.2, whose APIs and conventions may differ from
older model knowledge. Before frontend implementation, read `web/AGENTS.md` and
the relevant installed guide under `web/node_modules/next/dist/docs/`. Preserve
the generated Next.js instruction block in `web/AGENTS.md` because the dev
server will restore it.

Current page routes in code are:

- Public and auth: `/`, `/login`, `/login/reset`, `/logout`, `/signed-out`,
  `/privacy`, `/terms` and the web `/healthz` route.
- Daily workspace: `/app` redirects to the authenticated home, `/app/pulls`,
  `/app/opportunities`, `/app/jobs/[id]`, `/app/applications`,
  `/app/analytics`, `/app/applications/analytics`, `/app/dashboard` and
  `/app/applications/inbox`.
- Career tools: `/app/resume-studio`, `/app/resume-studio/check`,
  `/app/resume-studio/documents`, `/app/resume-studio/documents/[id]`,
  `/app/resume-studio/facts`, `/app/resume-studio/history` and
  `/app/resume-studio/history/[id]`; `/app/extension`, `/app/answers`,
  `/app/insights/skills` and `/app/archive`.
- Supporting state: `/app/saved`, `/app/company/[name]`, `/app/coverage`,
  `/app/settings`, `/app/more` and `/app/sign-out`.

The actual sidebar order is Pulls, Opportunities, Applications, Analytics,
Career Dashboard and Inbox Intelligence; then Resume Studio, Autofill Extension
and Archive; then Coverage and Settings. Pulls remains the authenticated home.
Opportunities also owns job details and Saved navigation state. Resume Studio
owns skill insights. Extension owns Answers.

Key frontend boundaries:

- `components/shell/AppProvider.tsx` owns Day/Night/System theme persistence,
  mark counts, optimistic application transitions, per-job mutation guards,
  route-local job patches/hiding, toasts and undo, Answers dock/menu state,
  cross-tab `BroadcastChannel` refresh, focus/visibility refresh, desktop Pull
  notifications, browser timezone persistence, legacy hash job redirects and
  the runtime visible-dash guard.
- `components/shell/nav.ts`, `Sidebar.tsx`, `Topbar.tsx` and `Live.tsx` own the
  workspace shell. Do not duplicate navigation arrays in pages.
- `components/jobs/JobListPage.tsx`, `JobTable.tsx`, `ListControls.tsx`,
  `JobDetail.tsx` and `useMarks.ts` own the shared job/application list and
  mutation experience.
- `lib/listState.ts` is the single parser/serializer for filters, at most three
  sort keys and pagination. State lives in the URL so bookmark, Back and
  refresh preserve the exact view. Defaults are new grad first, unapplied first
  and best match. Marked pages bypass the recent-only housekeeping filter.
- `proxy.ts` records visits separated by at least 30 minutes, forwards the
  current safe destination and previous-visit time to server components, and
  supports `New since your last visit` without a client-only race.
- `components/pulls/` owns the timeline/log; `components/studio/` owns Studio;
  `components/inbox/` and `components/intelligence/` own the evidence and
  dashboard surfaces; `components/auth/` owns all public authentication states.
- `components/analytics/`, `lib/analytics.ts` and the Analytics route stylesheet
  own the approved four-tab page and its refresh/filter/chart behavior. They
  read the shared backend projection and do not own another mutation ledger.
- `lib/api.ts` is the server read client. Browser mutation helpers attach CSRF,
  parse structured failures and redirect cleanly on session loss.

Never add a second local state copy for application counts without updating the
shared mutation contract. A successful mark must settle against the server;
failed optimistic changes must roll back; all tabs must converge.

### Approved Analytics implementation contract

Analytics is a separate read projection. Do not replace Career Dashboard's
`/api/intelligence` or its existing components with the new Analytics model.
The Analytics change itself did not modify Career Dashboard, the extension,
authentication, discovery, scheduler or migrations. The deployed release also
preserves the independently approved performance updates already on the branch.

| Tab | Implemented modules and accuracy rules |
| --- | --- |
| Overview | Submission timeline, current-week submissions, current application statuses and verified outcome evidence. Historical event types and latest status are separate measures. |
| Outcomes | Exact heading `Applications old enough to evaluate`, 30-day observation explanation, confirmed/pending/unknown cohorts, response timing and Inbox evidence review. Unanswered applications stay pending. |
| Role and resume | Outcomes by recorded role family, actual submitted-resume attribution, captured channels and comparable combinations. Missing attribution is `Not recorded`; combinations remain unavailable without at least five age-qualified applications per combination, complete attribution and comparable evidence. |
| Companies | Companies in application history, employer outcome history, official employer-year petition evidence, trends, source-linked evidence and authentic icons. Missing evidence remains unavailable. Historical petitions do not establish current hiring, sponsorship for an opening or new graduate eligibility. |

Read-model and filtering rules:

- `backend/app/api/routers/analytics.py` reuses Inbox `_identities`: `job:<id>`
  for applied marks and `external:<id>` for existing external records. It never
  fuzzy-merges separate applications or drops closed/now-ineligible marked jobs.
- `GET /api/analytics` is authenticated and no-store. Query parameters include
  `days=14|30|90|all|custom`, `start`, `end`, `family`, `tz` and `company`.
  The normal default is 30 days. Custom requires both dates. Invalid timezone,
  reversed/future dates and ranges over 100 years return 422.
- Date filters describe submission dates in the display IANA timezone, not
  response dates. Role families come from existing applied-job evaluations;
  missing role attribution remains Unknown. All-time totals include undated
  history, with explicit disclosure; undated applications do not enter dated
  series or age-qualified cohorts.
- Current-week activity always means the current local Monday through Sunday
  week, including when viewing another historical range. Future days are zero.
  The role selection still applies. Its drilldown uses exact Monday-to-today
  custom bounds. Lifetime Applied remains owned by the existing shell.
- The timeline uses daily points for selections under 100 days and monthly
  points for longer ranges. Daily charts can display daily or 7-day totals.
  Tab, dates, role, company-evidence selection and interval are URL-backed.
- `records=1` on the same endpoint returns exact unique application rows and
  `record_total`, default 50/max 100 per page. Additional filters are `status`,
  `company`, `evidence=positive|rejection|online_assessment|interview|response`,
  `eligible=1`, `timed=1`, `offset` and `limit`. The company parameter selects
  the sponsorship panel in the normal projection and filters rows in records
  mode. It does not silently filter the other normal Analytics metrics.
- `/app/applications/analytics` shares that projection and preserves timezone
  in its URL. Charts, metrics, cohorts, status, role and company links open the
  matching selection. Stored jobs link to their existing application controls;
  external history stays read-only. Original Applications mutations, lifetime
  counts, filters and full-history CSV remain intact.
- `AnalyticsRefresh` listens to the existing settled `ace-marks`
  BroadcastChannel, focus and visibility events and refreshes the server read.
  It creates no second optimistic count, competing ledger or background sync.

Evidence rules:

- Only owner-confirmed and `verified_automation` events contribute. Undo removes
  the original event. Preview, review, unsupported actors, future events and
  events preceding submission are excluded. Duplicate event types count once
  per application. Automatic submission receipts are not meaningful replies.
- A Gmail message must have one non-undone application target, match its
  selected identity and have a manual/automatic decision. Competing targets
  exclude it even if the other application is outside the selected date range.
- Existing owner-confirmed legacy stages remain evidence without invented
  response timestamps. A screening stage explained by an assessment or other
  positive event does not manufacture another recruiter reply. A standalone
  screening fallback is labeled screening.
- Cohort partitions are disjoint: confirmed positive, confirmed rejection,
  pending and other/unknown. A later explicit rejection takes precedence in the
  cohort partition; the event chart may still show its earlier positive reply,
  with the overlap explained. Withdrawn applications with no outcome sit in
  other/unknown. No reply stays pending at every age.
- Response timing uses the first reliable dated outcome after submission.
  Missing timestamps produce no invented duration. Rates remain null because
  the schema has no complete observation-coverage attestation. A connection,
  successful sync or single event cannot establish a complete denominator.
- Submitted resume versions and channels are absent from the schema. Never
  assign today's primary resume to history, infer channel from an ATS/provider
  or sender, rank unknown combinations or imply causal resume effectiveness.
- Inbox links use `decision=review|exact_preview|ambiguous`. Filtering happens
  before the existing 100-message limit so older pending evidence is reachable.
  Ambiguity means multiple candidate application keys, not a guessed match.
  Conservative reconciliation, review/corrections, audit and undo are preserved.
  Reading Analytics never authorizes Gmail, starts sync or changes permissions.

Company evidence and Pulls:

- Company identities remain exact strings. Reviewed records require verified
  legal-entity mapping and official HTTPS source hosts: `uscis.gov`,
  `www.uscis.gov`, `dol.gov`, `www.dol.gov` or `flag.dol.gov`. USCIS I-129
  metrics additionally require a USCIS host. The UI links stored reviewed
  evidence; it does not scrape/import sponsorship data during a page read.
- A newer revision replaces the earlier entity/metric/fiscal-year record.
  USCIS approvals and denials must both be known and nonnegative. If any
  included legal entity has incomplete year counts, that company-year aggregate
  is suppressed. A zero denominator has no rate. DOL LCAs remain a different
  metric; neither measure is hires, total employment or new graduate policy.
- Eleven official-site favicons are cached locally: Google, Apple, Microsoft,
  Stripe, Amazon, NVIDIA, Adobe, IBM, Salesforce, Meta and ServiceNow.
  `web/public/company-logos/provenance.json` records official source URLs,
  verification date and SHA-256. Exact reviewed names select an asset. Unknown
  identities and failed images use a neutral monogram, including failures that
  occur before React hydration. No runtime third-party logo lookup discloses
  the owner's application history.
- Pulls uses the same icons beside prominent company names and retains
  company-first/role-second ordering. Its calendar sits above both unchanged
  original right-side cards. Date links preserve the Pulls filter; Today resets
  the visible month; future dates are unavailable. Existing metrics, polling,
  monitoring, expansion and application controls remain.

Implementation files:

| Path | Responsibility |
| --- | --- |
| `backend/app/api/routers/analytics.py`, `backend/app/api/main.py` | Projection and authenticated route registration. |
| `backend/app/api/routers/inbox.py` | Review filtering before the message limit. |
| `web/src/app/app/analytics/page.tsx`, `analytics.css` | Server reads, four-tab route and approved page styling. |
| `web/src/components/analytics/AnalyticsView.tsx`, `AnalyticsCharts.tsx` | Four layouts, charts, evidence states, accessible chart disclosures and links. |
| `web/src/components/analytics/AnalyticsFilters.tsx`, `AnalyticsRefresh.tsx` | URL controls and settled mark refresh. |
| `web/src/lib/analytics.ts` | Projection types and shared drilldown URL builder. |
| `web/src/app/app/applications/analytics/page.tsx`, `loading.tsx` | Exact filtered application records and route loading. |
| `web/src/components/inbox/InboxIntelligence.tsx` | Existing Inbox deep-filter UI. |
| `web/src/components/CompanyLogo.tsx`, `web/public/company-logos/` | Reviewed local icons, provenance and fallback. |
| `web/src/components/pulls/PullsCalendar.tsx`, `PullsTimeline.tsx`, `web/src/app/app/pulls/page.tsx` | Calendar insertion and icon replacement. |
| `web/src/app/globals.css` | Shared icon/calendar styling using existing theme/type tokens. |
| `backend/scripts/seed_analytics_demo.py` | Rich fictional fixture restricted to `/tmp/ace-analytics-fictional.db`; never production. |
| `backend/tests/test_analytics_read.py`, `web/tests/e2e/analytics-redesign.spec.ts`, `web/tests/e2e/marks.spec.ts` | Data invariants, visual/interaction coverage and updated marks expectations. |
| `scripts/compare_analytics_screenshots.py` | Native-size reference/capture comparisons and diagnostic differences. |

Validation and acceptance evidence:

- Initial focused backend validation passed 89 tests covering Analytics, Inbox
  reconciliation/persistence, petitions, marks, Pulls and web API. After rebasing
  onto the two speed commits, the expanded set passed 112 tests, also covering
  external applications, count-only jobs, snapshots, skills and sponsorship
  coverage. TypeScript, ESLint, Next.js build, zero-hit dash scan and whitespace
  checks passed both before release and after integration. Production shipped
  dependencies had zero reported audit vulnerabilities.
- The completed fictional Playwright run passed 45 tests in 6.7 minutes: 18
  Analytics, 20 existing combined-intelligence and 7 existing marks tests. Final
  drilldown/mobile checks also passed after evidence normalization. The initial
  interrupted run is not counted. The rebased Analytics code/styles were
  unchanged; Chrome was not rerun on the overheated laptop for deployment.
- Checks cover privacy/no-store, disconnected Gmail, deduplication, undo,
  dates/roles, exact filtered records, chart disclosures, review links, official
  logo/failure fallback, petition semantics, cross-tab marks, keyboard/theme
  controls, Pulls calendar/cards and no browser errors. Responsive checks cover
  1672, 1600, 1440, 1280, 1024 and 390 pixels, plus 836 CSS pixels as a
  200-percent reflow equivalent for the 1672-pixel reference.
- All four tabs have native 1672x941 Day/Night PNGs in the ignored directory
  `artifacts/analytics-validation/`: `light-` and `dark-` followed by
  `overview.png`, `outcomes.png`, `role-resume.png` or `companies.png`.
  Full-page variants, four mobile captures, drilldown captures,
  `comparison-contact-sheet.png`, `comparison-{tab}.png`, `difference-{tab}.png`,
  `comparison-metrics.json`, screenshot hash manifest, `playwright-final.log`,
  `playwright-drilldown-final.log` and `changed-files.txt` are retained there.
- Native screenshot dimensions and icon hashes were verified. Raw pixel error
  is diagnostic, not an acceptance percentage. Existing shell geometry, real
  counts, seven fixture role families instead of five illustrative rows,
  unavailable rates/attribution and real disconnected/evidence states explain
  intentional differences. Overview, Outcomes and Companies were refined
  against the references. No claim of identical illustrative data is made.
- The acceptance comparison is recorded in
  `docs/architecture/2026-10-25-analytics-redesign.md`. All four approved module
  compositions, functional data/filter behavior, conservative evidence,
  preserved shell/Pulls controls, themes and accessibility were locally
  verified. Owner visual acceptance, signed-in production browser rendering,
  live Gmail sync and real petition imports remain unverified/unavailable.
  No invented test fixture may be imported to make a production panel look full.
- Local API, web and temperature-watch processes were stopped after validation.
  Scratch Chrome wrappers, release/smoke scripts and the fictional database
  under `/tmp` are disposable and can disappear after reboot. Reconstruct them
  from the committed code and documented procedure rather than assuming they
  are installed tools. Production rollback metadata is retained privately on
  the VM, separately from these local scratch files.

### Combined Intelligence and Gmail evidence contract

Migration 0044 added the application event ledger, Gmail connection/message
evidence and petition-report evidence. Career Dashboard and Inbox Intelligence
are preserved current features, not demo-only pages.

Gmail authorization is owner opt-in and `gmail.readonly`. It uses separate
client credentials, state, nonce, PKCE and an encrypted refresh token. Backfill
is preview-only. Incremental sync uses the Gmail history cursor. The owner can
pause, disconnect, purge snippets, review a decision, correct evidence and undo
an event. `backend/scripts/sync_gmail.py` is a one-shot command; this file does
not record a production timer for it.

Automatic outcomes require both the global
`GMAIL_AUTO_OUTCOMES_ALLOWED=true` and the connection's owner-approved setting.
The default is false. A candidate email must have explicit newest unquoted
outcome text, an exact requisition, exactly one matching application, aligned
DMARC, an employer-matching sender host, a submission before the email, no
newer state and no protected terminal-state conflict. Shared ATS senders or
personal mail alone are insufficient. Backfill never auto-writes status.

Metrics are deliberately conservative:

- Lifetime submitted combines applied job marks and external applications
  without double counting.
- Current pending excludes Accepted, Rejected and Withdrawn.
- Response, online assessment, interview and offer require distinct event
  evidence.
- Analytics age-qualified cohorts use the exact 30-day threshold. Response
  rates additionally require complete observation coverage, which the current
  schema does not attest. The implemented Analytics rates are therefore null
  and shown as Unavailable, even when individual verified outcomes exist.
- Median response time requires reliable dated evidence.
- Qualified postings observed by ACE are not a national market rate.
- H-1B rate is shown only from verified USCIS I-129 approvals divided by
  approvals plus denials. DOL LCA counts are not USCIS petition outcomes and
  neither source proves that a specific job will sponsor.

The Analytics production check found zero Gmail connections and zero petition
reports. Live credentials, consent and sync have not been exercised. Preserve
the truthful disconnected/unavailable states; do not present these integrations
as active or populate their tables from the fictional browser fixture.

### Chrome extension implementation map

The unpacked extension consists of:

- `manifest.json`: MV3 declaration, version 1.28.0, storage/activeTab/scripting
  permissions, localhost host access and optional HTTPS host access.
- `background.js`: stores endpoint/token, pairs with ACE, performs authenticated
  answer/history/memory calls, validates message senders and brokers runtime
  messages. Secrets stay in `chrome.storage.local`, never in page DOM.
- `fields.js`: question extraction, field/control shapes, answer matching,
  employer-specific screening rules, option matching, repeating history blocks,
  date mapping, phone/country ordering and deterministic matcher utilities.
- `memory.js`: normalized concepts, equivalence and reuse policy, including the
  shared employer-motivation exclusion predicate.
- `content.js`: native and React value setters, fill planning, combobox/listbox
  and Workday adapters, undo, the Focus Mode shadow DOM UI, Review/Memory/
  Activity flows, dynamic observation, SPA quieting, diagnostics and draggable
  position behavior.
- `popup.html` and `popup.js`: ACE address, pair/unpair, answer access and manual
  injection/fill controls for the active tab.
- `test-rules.js` and `test-memory.js`: fast deterministic rule suites. Real
  Chrome interaction tests live in `web/tests/e2e/extension-*.spec.ts`.

Persistent Chrome keys currently include `base`, `token`, `aceStudioActivity`,
`aceFocusPosition`, `aceStudioThemeMode` and `aceAutoKnown`. Changing a key requires
backward-compatible read/migration behavior or an explicit owner-approved reset.
`aceStudioThemeMode` is `system`, `day` or `night`; it replaced the older
`aceStudioTheme` key, which is now ignored so every card starts by following
the computer.

The content scripts run at `document_idle` in all frames. They must use native
setters and the events expected by the employer framework, then read the real
control state back before declaring success. Field detection must handle
rerenders and step replacement without unbounded observers. Diagnostics may
describe controls and failures but never answer values. The extension can fill
and undo supported fields only. It cannot submit, irreversibly advance, infer
Applied, or own company-motivation answers.

### Deployment topology and configuration

The Oracle production Compose stack is:

```text
internet -> Caddy :80/:443 -> Next.js web :3000
                              -> FastAPI api :8000
                                       |
                                       v
                                 PostgreSQL 16
                                       ^
                                       |
                              scheduler and migrate
```

`postgres` owns the named database volume. `migrate` runs `alembic upgrade
head` as a one-shot prerequisite. `scheduler` runs the long-lived scheduler and
has a semantic health command every five minutes. `api` runs Uvicorn and has a
health check. `web` receives the release SHA as a build argument. Caddy is the
only public entry point. Services use `restart: unless-stopped` and dependency
health/completion gates. Local Compose binds PostgreSQL 5433, API 8000 and web
3000 to loopback. Production commands must include
`docker compose --env-file .env -f deploy/oracle/compose.yaml ...`.

Backend environment contract:

- Required: `DATABASE_URL`.
- Auth: `ACE_AUTH`, `SETUP_TOKEN`, `SESSION_DAYS`,
  `REQUIRE_LOGIN_EMAIL_CODE` and `WEB_BASE_URL`.
- Owner Google sign-in: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and
  `GOOGLE_REDIRECT_URI`.
- Gmail: separate `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`,
  `GMAIL_REDIRECT_URI`, `GMAIL_TOKEN_KEY` and
  `GMAIL_AUTO_OUTCOMES_ALLOWED`.
- Alerts: `RESEND_API_KEY`, `MAIL_FROM`, `ALERT_EMAIL` and `PUBLIC_BASE_URL`.
- Discovery/rendering: `MAX_ALERT_POSTING_AGE_DAYS` default 10,
  `ALERT_ON_UNKNOWN_POSTING_AGE` default false, `DISPLAY_TIMEZONE` default
  `America/Los_Angeles`, and deployment profile `ACE_TARGET_PROFILE` default
  `early-career` in the Oracle template.
- Operations: `API_DOCS`, `ACE_DOMAIN`, database name/user/password and optional
  `OCI_BACKUP_BUCKET` with `ACE_BACKUP_MAX_REMOTE_BYTES`, currently 15 GiB in
  the template.
- Frontend runtime: `API_ORIGIN` points Next.js to FastAPI. It must be supplied
  at runtime, not assumed to have been baked into the build.

Secrets stay only in the private server `.env` with restrictive permissions.
Never copy them into this knowledge file. `deploy/oracle/backup.sh`, its systemd
service/timer, release preparation, independent-discovery comparison, parity
query and disabled legacy-replica tools are operational assets. The existence
of the replica script does not authorize re-enabling replication.

### Operational scripts and verification surface

Important backend commands are intentionally explicit:

- `run_scheduler.py` and `scheduler_health.py` operate and assess discovery.
- `source_health.py`, `probe_coverage.py`, `coverage_benchmark.py`,
  `discovery_inventory.py`, `discovery_parity.py`, `discover_sources.py` and
  `discover_boards.py` measure reachability and coverage.
- `gate_dry_run.py` and `rejection_audit.py` measure eligibility changes before
  activation.
- `backfill_job_evaluations.py`, `backfill_decode_descriptions.py`,
  `backfill_resume_studio.py` and `repair_applied_date_drift.py` are controlled
  data repairs/backfills, not routine startup hooks.
- `data_inventory.py`, persistence smoke scripts and source snapshot smoke
  scripts verify database behavior without printing private content.
- `time_pages.py` times requests read-only in-process without a login session.
  Its Analytics entry still calls the former `/api/dashboard`; update that
  diagnostic entry to the new `/api/analytics` reads before using its Analytics
  timing as evidence for the redesigned page. Other page timings remain useful.
- `create_owner.py` and `set_owner_email.py` mutate owner identity and require
  deliberate use against the intended database.
- `import_petition_reports.py` accepts only reviewed official evidence.
- `sync_gmail.py` performs a one-shot inbox sync; no production timer is
  implied.
- `legacy_replica.py` is historical. It stays inactive during independent
  comparison.

Backend tests cover every adapter family, adapter contracts, eligibility and
candidate profiles, hashing/persistence, scheduler timing and refusals,
discovery/coverage/parity, Pull telemetry, matching/scoring, application marks
and prior applications, auth and Google, Gmail reconciliation, petition data,
Resume Studio, migrations and API behavior. Frontend Playwright suites cover
auth, account/profile, navigation, responsive V2 visuals, jobs, marks,
applications, keyboard behavior, Studio, Combined Intelligence and real
extension fixtures. Extension rule and memory suites run directly in Node.

The normal validation ladder is:

```bash
.venv/bin/python -m pytest backend/tests -q
node extension/test-rules.js
node extension/test-memory.js
node --check extension/content.js
python scripts/no_user_facing_dashes.py
cd web
npm run typecheck
npm run lint
npm run build
npx playwright test
```

Choose focused tests while iterating, then expand in proportion to risk. Record
the exact command, result, fixture type and environment. A skipped live test is
not a pass. A local fictional browser fixture is not a production employer-form
verification.

### Change checklist for future chats

Before changing a subsystem, a future chat should answer all of these from this
file and the current code:

1. Which durable table, API route, page, extension message or scheduler worker
   owns the behavior?
2. Is the fact code-local, historically verified in production, or currently
   unverified?
3. Which owner safety invariant could the change affect: data preservation,
   no-submit, no-motivation capture, single-owner auth, source respect,
   independent schedulers or design fidelity?
4. Does the change require a migration, backfill, deployment, scheduler action,
   external OAuth consent or destructive operation that needs explicit owner
   approval?
5. Which focused regression reproduces the real failure shape, and which wider
   suites must still pass?
6. How will production be verified read-only after release without exposing
   private content?

Update this same file whenever an architecture contract, deployment truth,
schema head, production verification, owner decision or major remaining risk
changes. Do not create a competing continuity file.

## Repositories and runtime state

The legacy checkout is `/home/ubuntu/Documents/ace` on branch `main`. Its
Docker stack and database are preserved. As audited on 2026-10-16, before the
later independent-comparison decision:

- PostgreSQL 16 is healthy and published locally on port 5433.
- The legacy web service is available on port 8000.
- The scheduler is healthy and continues to poll.
- The database is at Alembic revision 0040.

The new checkout is `/home/ubuntu/Documents/ace-next` on branch
`wine-rose-platform`. It contains the approved Next.js interface, all existing
backend logic, Resume Studio, owner authentication, extension pairing, the
Pulls-first workspace and the Oracle deployment kit.

Do not rebuild or migrate the legacy stack during ordinary development. The
current owner decision is that both legacy and Oracle schedulers keep running,
each against its own PostgreSQL database, so their discovery results can be
compared. The databases are independent writers and their numeric IDs have
diverged. Keep the old cross-database replica cron disabled. Do not merge rows,
restart replication, or stop either scheduler without a new explicit owner
decision and a reconciliation plan.

## Historical production data inventory, 2026-10-16

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
extension tokens can read answers and work or education history plus manage
approved Answer Memory. They cannot access jobs, applications, resumes, owner
profile or other private API families.

Password sign-in supports an optional second email step. The Oracle template
requires it, but the actual production `/api/auth/status` check on 2026-10-25
reported `email_verification: false` and `reset_by_email: false`; production
therefore accepts the password under Continue with email without an emailed
code, and email recovery is unavailable. Never infer actual configuration from
the deployment template. When verification is enabled, ACE verifies the password,
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

#### Existing Google Console project and client, owner-confirmed 2026-10-25

The owner already has a Google Cloud project named `acee`. Their Console
screenshot shows an enabled Web application OAuth client named `acee prod`
(referred to conversationally as Ace Pro), created on 2026-10-19. Do not tell
the owner to recreate this project or replace/delete the existing sign-in client.
Its screenshot-confirmed configuration is:

- Authorized JavaScript origin: `https://ace.opik.net`.
- Authorized redirect URI: `https://ace.opik.net/api/auth/google/callback`.
- Legacy authorized redirect URI:
  `https://ace.161-153-89-170.sslip.io/api/auth/google/callback`.
- An enabled client secret exists; its value is masked in the Console and
  belongs only in private server configuration. Neither secret values nor the
  owner's Console screenshot belong in this public repository.

Those callbacks are for Google sign-in. The screenshot does not show the Gmail
callback `https://ace.opik.net/api/inbox/google/callback`, and does not establish
that Gmail API, the read-only scope, test-user access or server settings are
configured. A production presence-only check during Gmail setup guidance found
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` and `GMAIL_TOKEN_KEY` absent, with the
Gmail callback not configured; setup readiness was false and global automatic
outcomes were disabled. No credential values were printed or configuration
changed.

Continue Gmail setup inside the existing `acee` project. A dedicated Gmail Web
OAuth client there keeps `GMAIL_*` credentials independent of the existing
`GOOGLE_*` sign-in configuration. Preserve the current sign-in client and its
callbacks, and do not change the project's publishing status merely to follow
a generic testing tutorial. Gmail consent is a separate owner action even when
the same Google Cloud project is used. No Gmail scope/configuration change is
authorized by documenting these facts.

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
expected recovery behavior. In that historical replication mode, API replacement
required verifying that a subsequent log entry said
`ACE legacy replica synchronized through ...` and that the cursor advanced.
This is not an instruction to run replication now: the owner subsequently chose
independent discovery. Keep the replica disabled and never edit its cursor
forward by hand.

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
2. On the VM, confirm `/opt/ace` has no conflicting tracked changes. Untracked
   `private-backups/` is expected. Record current commit, API/web image IDs,
   scheduler/PostgreSQL/Caddy container IDs, schema and private aggregate
   inventory. Do not print credentials or private rows.
3. Take a fresh private consistent backup. Verify gzip integrity and PostgreSQL
   archive listing before activation. Keep previous API/web image IDs available
   for rollback. A list check is not a restore drill; do not claim one occurred.
4. Fetch and fast-forward to the exact approved SHA, preserving newer shared
   branch work. Set `ACE_BUILD_SHA` to that full SHA before image construction.
5. Build affected images. `deploy/oracle/prepare-release.sh` builds `migrate`,
   `api` and `web` without changing containers. For a schema-free API/web
   release, a direct `docker compose --env-file .env -f
   deploy/oracle/compose.yaml build api web` also prepares only what is needed.
6. For a schema-free API/web release, activate only those services with
   `docker compose --env-file .env -f deploy/oracle/compose.yaml up -d
   --no-build --no-deps --wait --wait-timeout 180 api web`. Website-only changes
   activate only `web`. `--no-deps` prevents triggering the existing migrate
   prerequisite. Do not include scheduler, migrate, PostgreSQL or Caddy merely
   because they appear in Compose dependencies. A migration needs separate
   explicit approval and the rehearsal procedure above.
7. Verify API/web are healthy, running images match the prepared IDs, public
   `/healthz` and `X-Ace-Frontend-Commit` match the approved SHA, schema is
   unchanged for a schema-free release, and scheduler/PostgreSQL/Caddy container
   IDs are unchanged. If activation fails, restore the recorded previous
   API/web image tags and prior build SHA, then recreate only API/web; never
   restore production data as an automatic application rollback.
8. Compare private aggregate inventories for protected state. Discovery can
   continue adding jobs/Pulls during a release, so those totals need not match.
   Run read-only data invariants and public auth/static-asset checks. Do not
   use mutation tests or an actual owner's browser session as fictional data.
9. Record exact evidence and unverified areas here. Do not claim that container
   health proves signed-in visuals, Gmail sync, official evidence availability
   or legacy scheduler freshness. Keep both schedulers running independently
   and the cross-database replica disabled; do not operate them to validate a
   website release. Monitoring checks may be read-only.

The Analytics release followed the schema-free path. Its protected inventory
comparison checked row counts for `job_marks`, `external_applications`,
`application_answers`, `resumes`, `users`, `resume_documents`, `career_facts`
and `resume_versions`, plus the applied-mark count. Those matched before/after.
This establishes aggregate preservation, not a full row-content hash audit.
The 919 application total is a dated snapshot, not a fixed expected total for
future releases. The Oracle scheduler was healthy and kept its container ID;
legacy health and fresh source-write parity were not rechecked in this release.

Release-script lessons from this deployment:

- When sending `bash -s` over SSH, a child `docker compose exec -T` can consume
  the script's remaining stdin. Give non-input commands `< /dev/null`; reserve
  stdin explicitly for a Python/SQL script or dump stream. A zero SSH exit code
  alone does not prove all planned commands ran. Verify expected artifacts and
  the public release SHA.
- Under `set -o pipefail`, `gzip -dc dump.gz | pg_restore --list` can exit 141
  because listing closes input before gzip finishes. First run `gzip -t` over
  the entire file. Then use Bash process substitution for archive listing,
  check the listing command succeeds and its output is nonempty, and only then
  rename the private `.partial` backup to its completed name. Do not ignore
  integrity errors or treat a partial file's existence as a verified backup.
- The ordinary backup script has retention cleanup. This release used a new
  private dump without pruning existing backups. No scheduler operation,
  cleanup, production restore or migration accompanied the deployment.
- Production data smoke checks used `SET default_transaction_read_only = on`
  on every diagnostic connection, without application startup hooks. The
  existing in-process `time_pages.py` pattern allowed a process-local auth
  override to exercise the route without creating a session or changing live
  auth configuration. Public private endpoints still returned 401. This is not
  verification of the owner's real signed-in browser.

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
failure if one occurs. Do not force-push. The one exception so far was an
owner-approved `--force-with-lease` during the 2026-10-25 reconciliation, which
dropped nothing. Do not merge this branch to `main`
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

### 2026-10-25, two Pulls and sidebar elements removed

- At the owner's request: the "Company first. Relevant role second." note
  above the Pulls figures, and the "Discovery engine online" line at the
  foot of the sidebar, with their styles. The top bar's live status still
  says when a source last answered.
  Released website-only; `/healthz` reported `922640f` by 2026-10-25T23:58Z.

### 2026-10-25, approved Analytics production release and continuity

- Implemented the exact four-tab Pixel-Lock module compositions in the existing
  Wine and Rose/Inter shell, added the read-only `/api/analytics` projection,
  exact Applications drilldowns, conservative evidence handling, reviewed local
  icons and the Pulls historical calendar above its original cards.
- Preserved the two newer performance commits by rebasing onto `4f41949`.
  Runtime release `340b175251a8040f3eedad9553c3f6f965657698` was pushed and
  deployed after the owner's explicit request. Documentation release record
  `8e604e7` was pushed afterward and does not require another deployment.
- A new 437 MB private backup passed gzip and archive checks. Matching API/web
  images became healthy at 23:41Z. PostgreSQL, Caddy and scheduler kept their
  container IDs; schema stayed `0050`; no migration, Gmail permission change,
  extension publication, retention cleanup or destructive operation occurred.
- Read-only production verification matched 919 unique applications to
  existing totals, checked four date ranges, disjoint cohorts, deduplication
  and drilldowns, and confirmed no-store. Eight protected table counts and
  applied-mark counts matched. Public health/header SHA, 11 logo hashes,
  private API 401s and four sign-in redirects passed. Public health was checked
  again at 23:52Z. No signed-in production browser review is claimed.
- Passed 89 initial focused backend tests, 45 fictional Playwright tests and
  final drilldown/mobile checks; after integration, 112 backend tests,
  TypeScript, lint, build and zero-hit dash scan passed. Browser runs remain
  suspended on this laptop pending cooling repairs. Screenshots, comparisons,
  logs and the 39-file implementation list remain Git-ignored locally.
- Recorded actual remaining gaps: zero production Gmail connections and
  petition reports, missing submitted-resume/channel attribution and complete
  observation coverage, unverified mailbox sync and owner visual acceptance.
  Unknowns remain visible; no source or effectiveness claims were invented.
- Consolidated the complete Analytics contract and file map into this file,
  corrected stale live SHA/branch/schema/auth descriptions, distinguished dated
  history from current facts, and documented safe schema-free releases, SSH
  stdin handling, backup-list SIGPIPE handling and read-only diagnostics.

### 2026-10-25, second speed round

- Released with owner approval at 2026-10-25T22:29Z: `/healthz` reported
  `269cb32fde277e49d31bc78fc821e403bdc8c4b3`; backup service ran first;
  migrate, api and web were recreated and healthy; scheduler untouched.
  `time_pages.py` afterwards, in ms (before in brackets): `/api/stats` 89
  (216), `/api/jobs` 99 (97), page 2 slowest 89 (216), `/api/intelligence`
  401 (2,542), `/api/coverage` 963 (3,365, the first read after a restart
  computes the snapshot), `/api/dashboard` 83 (68), `/api/facets` 138 (146),
  `/api/system` 139 (79, measured right after the API restart). That run
  still timed Applications' old requests and the badge's one-row page; the
  script now times what the pages ask for. The image's copy of the script
  updates with the next release; until then pipe it from a checkout.
- Production timings from `backend/scripts/time_pages.py` led to: two-pass
  job totals, list pages that fetch only what they show, a count-only jobs
  route for the new-since badge, a 6.4x faster exact skill extractor, a
  passing-first Career Dashboard query, JSONB containment plus a background
  snapshot for Coverage's sponsorship list, and no prefetch for job links or
  sign-out. Details under Speed and responsiveness.
- Checks: 1,252 backend tests (new: totals per filter, count-only route,
  external start date, skill extractor proofs, dashboard skills, snapshot,
  sponsorship list), TypeScript, ESLint, dash scan, production build, and
  signed-in fetches of every changed page on fictional data. The browser
  suite was not rerun: the laptop shut down a third time under it.

### 2026-10-25, speed, search history and search box

- Released with owner approval: `https://ace.opik.net/healthz` and the
  `X-Ace-Frontend-Commit` header reported
  `46d8738e29334ea228d6767858f3fd294a9b9dee` from 2026-10-25T21:22Z, API
  ok, signed-out pages answering in about 0.23 s. The owner ran the
  one-line release (backup service, prepare-release, `up` of postgres,
  migrate, api, web and caddy; scheduler untouched). Their output showed
  migrate, api and web recreated and healthy, and `alembic_version`
  `0050`: migration 0050 (Answer Memory) is applied in production.
- JIT off for app database connections and one fewer stats query; list
  pages fetch in parallel; every workspace route has a loading screen;
  same-route clicks dim the page. Details in the working notes above.
- No saved suggestions in any non-sign-in field; search box without the
  "/" chip and with a single focus ring.
- Checks: 1,229 backend tests, TypeScript, ESLint, dash scan, production
  build, a slow-API feedback probe, and the full Playwright suite at one
  worker on fictional data: 174 of 175 passed. The failure was the "/"
  shortcut test pressing the key right after load while the CPU was
  throttled at 93 to 98 C; it then passed 8 runs in a row. Production
  timing is not yet measured after release.
- The laptop shut down twice (12:58 and 14:03) while Playwright started
  four Chrome workers next to the servers; each boot log simply stops.
  `x86_pkg_temp` read 92 C three minutes after boot and 98 C with one
  worker. See the local testing recipes.

### 2026-10-25, agent working notes

- Added "Working notes for agents": owner working style, the no-AI commit
  rule, production access through owner-run one-line SSH, the website-only
  release line, the open Google sign-in sequence issue and its guarded fix,
  the shared Git layout, local test recipes and the typography contract.
- Updated the current state to `386bed9`, manifest 1.28.0, the retired
  pre-rebase clone and its safety copies, and the 22-test extension suite.

### 2026-10-25, V5.1 theme sync and Close

- The card follows the computer's Day or Night setting, live, through
  `prefers-color-scheme`. The header toggle picks the other theme and holds it;
  toggling back to the computer's own theme returns to following it. Stored as
  `aceStudioThemeMode`; the old `aceStudioTheme` value is ignored.
- A Close button (outline X) sits after Minimize in the card header and after
  Expand in the dock. It uses the existing dismiss path: the card stays closed
  on that page, including while the owner types, and returns on a new page,
  a new form step or the toolbar's Fill. Close never submits or advances.
- The Form detected pill stays on one line and the dock text ellipsizes, so
  the extra control changes no layout. Compact card height is 354px.
- Checks: 258 rule cases, the memory safety cases and 22 Chrome extension
  tests passed, including the new `extension-focus-theme-close.spec.ts`.
  Manifest 1.28.0. Local fixtures only; reload the unpacked extension to use it.

### 2026-10-25, reconciliation and V5.1 typography

- Combined the remote typography line with the V5.1 line on GitHub: the rebased
  V5.1 commits, the local continuity commit and this consolidated document are
  all on `wine-rose-platform`. Nothing from either line was dropped.
- Applied the website typography to the V5.1 card: packaged Inter instead of an
  uninstalled "Inter" fallback, the wordmark weight and tracking, an 11.5px
  floor, website weights and tabular numbers. Type properties only; the 318px
  width, drag, dock, Review and motivation exclusion are unchanged.
- Checks: 258 rule cases, the memory safety cases and 19 Chrome extension tests
  (including the seven V5.1 tests) passed. Served over HTTP with the packaged
  font, the card rendered `ace-inter` in Day and Night without page errors. The
  compact card is 355px tall in Inter, against 347px in the approved reference.
- The shared local repository holds a broken Codex checkpoint ref that makes
  `git fetch` fail with "bad object"; pushing still works. Fetch into a separate
  clone, or remove that one dangling ref with the owner's approval.
- Pasting a multi-line block that starts with `ssh` loses the following lines
  during login. Run a remote release as one `ssh host '...'` command.

### 2026-10-25, standalone continuity consolidation

- Made this file the single standalone platform handoff for new chats. The
  topic documents remain optional historical archives rather than required
  startup reading.
- Added a code-verified implementation map covering repository boundaries,
  backend modules, polling transactions, auth and HTTP boundaries, every API
  family, all durable tables, migrations 0001 through 0050, every current page
  route, client state ownership, Combined Intelligence, Gmail safeguards,
  extension modules and storage, Compose topology, environment settings,
  operational scripts, test surfaces and a future-change checklist.
- Reconciled the V2 baseline with current Career Dashboard and Inbox
  Intelligence routes while preserving Pulls as the authenticated home, and
  corrected the extension token description to include approved Answer Memory
  operations.
- Consolidated product vocabulary, the gate, discovery lifecycle, persistence,
  coverage, matching, applications, API domains, the complete website contract,
  Pulls metrics, Focus Mode V5.1, Answer Memory, Resume Studio, privacy,
  testing, operational doctrine, historical safeguards and known limitations.
- Corrected the stale lower-section instruction to stop one scheduler. The
  current owner decision is two independent discovery systems, separate
  databases and no cross-database replication.
- Recorded local documentation HEAD `a1e59ff` and the three-ahead,
  three-behind branch divergence that must be reconciled before any push.

### 2026-10-25, continuity and Focus Mode V5.1

- Recorded the V4 Answer Memory code and additive migration 0050, the locally
  implemented V5.1 extension, and the final visual and Workday listing fix.
- Distinguished local Chrome fixture results from live employer-form and
  production API verification. The V4 production migration and Memory API
  remain unverified in this record despite the owner's deployment approval.
- Recorded the other agent's three typography commits on the tracked remote
  branch so future work can reconcile them with the two local V5.1 commits.

### 2026-10-24, typography release recorded on the remote branch

- Commit `8d84141` records a website-only Inter typography release at frontend
  commit `61debd6`. Its recorded checks covered `/healthz`, the served font,
  sign-in routing, public Day and Night rendering, console output and forbidden
  dashes. That release did not recreate API, migration, scheduler, PostgreSQL or
  Caddy. Its extension typography work is on the remote branch and is not yet
  reconciled into this local V5.1 branch.

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
