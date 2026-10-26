# Historical handoff state, archived 2026-10-26

These dated observations were moved unchanged out of the handoff to keep it
short. They are historical evidence, not current operating instructions.
Use `ACE_NEXT_KNOWLEDGE.md` for current local and verified production state.

**2026-10-26 question-following update:** Local 1.28.6 follows clicked/focused
employer questions, fills equivalent known routine answers on focus and records
committed owner answers as Answered on form without duplicate approval. Protected
choices remain per-application; prefills still need one confirmation and ACE
editor drafts still need the explicit fill action. Inputless ARIA dropdowns,
completion invalidation, Memory failure handling and Undo are covered. 58 DOM
contracts, 258 matcher cases, Memory checks, TypeScript, lint, syntax and dash
checks pass. 35 Playwright cases collect only due to cooling. Reload 1.28.6 and
refresh employer tabs; no deployment or publication occurred.

**2026-10-26 drag update:** Local 1.28.5 lifts an embedded form's floating card
into the outer viewport through a tab/frame/document-scoped extension relay.
Form logic stays in the source frame; stale actions are rejected and an
unavailable outer receiver leaves the local card usable. Pointer capture starts
immediately; touch, keyboard, saved position and existing controls remain.
49 DOM contracts, 258 matcher cases, Memory checks, TypeScript, lint, syntax
and dash checks pass. 33 Playwright cases collect only due to cooling. Reload
the extension and refresh employer tabs. No deployment or publication occurred.

**2026-10-26 extension update:** Local 1.28.4 adds owner-authorized automatic
saving of finished routine employer-form answers without per-question approval.
Memory exposes separate Auto-save routine answers and Auto-fill known switches.
Trusted edits, settled readback, protected/motivation exclusions, revision checks
and no-submit remain. 43 DOM contracts, 258 matcher cases, Memory checks,
TypeScript, lint, syntax and dash scan pass. 32 Playwright cases collect only;
browser runs remain suspended for laptop cooling. Reload the unpacked extension
and refresh employer tabs. No production deployment/publication was performed.
See `ACE_NEXT_KNOWLEDGE.md` for the complete current state and limitations.

**2026-10-25 continuity check:** `ACE_NEXT_KNOWLEDGE.md` now distinguishes the local V5.1 extension at `cb7bb5e` from the last independently verified API/database release at `11a7fd4` and the separately recorded website typography release at `61debd6`. The V4 migration 0050 and live Memory API status were not verified in this session. The local branch has two V5.1 commits absent from `origin/wine-rose-platform`; the tracked remote has three typography commits absent locally. Reconcile both lines before pushing or releasing. A root `AGENTS.md` and the root `CLAUDE.md` direct future agents to the continuity file.

**2026-10-24 extension update:** ACE Focus Mode V5.1 is implemented locally in the existing MV3 extension on `wine-rose-platform`. The panel is a compact floating card with Review, Workspace, a minimized dock, free dragging, persisted position, Day/Night themes, native and supported listbox option mirroring, and persistent Review completion. Employer-motivation questions are excluded from scan, fill, Review, Memory reuse and progress; older records are retained on the server. This update requires no database migration and has not been deployed or published. See `extension/README.md` and `web/tests/e2e/extension-focus-v5.spec.ts` for usage and browser verification.

**2026-10-25 speed, second round:** production timings (`backend/scripts/time_pages.py`) showed `/api/stats` 216 ms, Career Dashboard 2.5 s and Coverage 3.4 s; totals now take two passes, list pages fetch only what they show, skill extraction is 6.4x faster with identical results, Coverage's sponsorship list is a background snapshot, and job links no longer prefetch. Production is at migration 0050.

**2026-10-25 speed:** PostgreSQL JIT cost about 0.5 s per queue query; app connections now turn it off, every workspace route has a loading screen, same-route clicks dim the page, and no text field outside sign-in keeps browser history. See `ACE_NEXT_KNOWLEDGE.md`, Speed and responsiveness.

**2026-10-25 theme sync and Close:** the V5.1 card follows the computer's Day or Night setting until the owner picks one (`aceStudioThemeMode`), and has a Close X in the header and dock that reuses the existing dismiss path. 22 Chrome extension tests pass. Reload the unpacked extension to use it.

**2026-10-25 visual correction:** The Focus compact and Review card now use the approved V5.1 geometry, colors, typography, borders and icons. A Workday Search For Jobs route is excluded even when its filters resemble application questions, including after SPA navigation. The local extension regression suite has 7 passing Chrome tests. Reload the unpacked extension and refresh employer tabs to see these local changes; no deployment or publication was performed.

The current production migration record is `ACE_NEXT_KNOWLEDGE.md`. Read it
before any database copy, Oracle deployment, Google OAuth setup or scheduler
cutover. It records the aggregate live inventory, staged migration, rollback,
backup and owner input requirements.

- **Typography refresh (2026-10-24, on `wine-rose-platform`):** the approved Refined typography only: self-hosted
  Inter (SIL OFL), one token scale in `web/src/app/globals.css`, sentence case labels, tabular numbers, colour emoji
  fallbacks. Layout, colours and text unchanged; evidence method in `docs/knowledge/05`. The extension panel and popup
  use the same face and scale (`docs/knowledge/06`). Live on https://ace.opik.net since 2026-10-24 (frontend commit
  `61debd6`, web container only). Chrome shows the extension change once its folder is updated and reloaded.
- **Live** on the user's machine via `compose.yaml`: postgres (host port 5433),
  migrate, scheduler, web (port 8000, FastAPI serving the old UI at `/`). Built
  from the tree at commit 4f516ef. The user's machine is the only deployment.
- About 2,090 enabled sources (about 2,050 polled), about 1,250 qualifying active
  jobs, roughly 600 applications tracked, a 66 row answer bank. The scheduler
  polls continuously (five minute cycles; Google every 30 minutes) and alerts
  are one email per closed 15 minute pull.
- Tests on `wine-rose-platform`: 1,191 backend tests (hermetic SQLite), 89 Next.js Playwright tests against fictional demo
  data, and 185 extension matcher cases. The retired single-file UI suite was removed; extension DOM tests remain.
- Done this week: own-site readers for Atlassian, EA, Apple, Shopify, AMD, SIG,
  Booking.com, Groq, Google, Meta, Intuit, Arm, Synopsys and about 25 more
  boards; gate v46 to v53; the full anthracite redesign (web, extension, email),
  night and day, then a step darker; em dash guards and the drawn dash scan.
- 2026-10-12: a posting the user applied to that an employer lists again (new id, no mark) now shows
  "Applied before, Oct 4" on its row, job page, group header, desktop notification and alert email. Derived on
  read in `applications/prior.py`, never stored, and compares requisition numbers so two open listings that differ are
  called possibly separate openings; see `docs/knowledge/04`.
- **2026-10-14, branch `next-app` (cloud session, demo data only):**
  - Resume scoring fixed: the scheduler now scores, after every cycle, active PASS jobs with no current score for the
    active resume (new, changed since scoring, or from an older algorithm), at most 2,000 per cycle. The API returns
    `match_state` (scored, pending, no_description, insufficient, no_resume) so no page says "n/a" or "could not read"
    for a job that simply was not scored yet. Not yet run on the live database: after pulling, rebuild and watch the
    scheduler log for `jobs_scored count=`.
  - `backend/scripts/seed_demo.py` builds a fictional demo database (SQLite or empty PostgreSQL); `db/session.py`
    branches on dialect. Demo tiers apply only with `ACE_DEMO_COMPANIES=1`.
  - The Next.js app in `web/` works against FastAPI: every page of the old UI under the new names (section 9), URL-held
    filters, sort and numbered pages, palette with role search, marks with undo, dash guards. Old UI still at `/`.
  - CI added (`.github/workflows/ci.yml`): unit, extension, web build, both browser suites on demo data.
  - Baseline, gap matrix, decisions and open questions: `docs/architecture/2026-10-14-baseline-and-plan.md`.
  - Overview at `/app`, Saved star removed (data kept), new grad first by default, `/api/system` health and
    `/api/export.json`; candidate profiles (`ACE_TARGET_PROFILE`, sde2 off until the owner approves a dry run).
  - **Sign-in (Phase 2):** owner-only, argon2id, DB sessions, CSRF, throttling, extension pairing (extension
    1.21.0), rollback `ACE_AUTH=disabled` (local peers only). Migration 0038. Demo owner `demo@ace.example` /
    `ace demo password` exists only in generated demo databases. Details: `docs/knowledge/07`. On the live database
    the owner runs `create_owner` once and pairs the extension; until then the API answers 401 (or set
    `ACE_AUTH=disabled` for a local rollback).
  - **Approved auth surface (2026-10-15, branch `auth-approved-design`):** `/login` now uses the locked Day and
    Night cinematic design with live DOM controls and the existing owner session flow. Email opens the real sign-in
    form. Google and Microsoft remain honest unavailable states because no OIDC backend exists. `/logout` revokes
    the server session before sending the browser to the exact `/signed-out` success screen. `/` is a public
    informational page, with public `/terms` and `/privacy`; private `/app/*` routes and extension token scopes are
    unchanged. Canonical capture command: `cd web && API_ORIGIN=http://127.0.0.1:18000 npm start`, then
    `WEB_URL=http://127.0.0.1:3000 CHROMIUM_PATH=/usr/bin/google-chrome node scripts/capture-auth-screenshots.mjs`.
  - **Approved Wine and Rose platform (2026-10-15, branch `wine-rose-platform`):** all public, auth and workspace
    routes use the locked V2 Night and Day design. The home and auth views render the complete angular A as live
    DOM artwork. Pulls remains the post-login home. Application totals now come from the backend's combined posting
    and external application history, update optimistically across the shell, synchronize across tabs, persist after
    refresh and roll back on save failure. `scripts/no_user_facing_dashes.py` scans production sources. Visual evidence
    is kept locally under ignored `artifacts/wine-rose/`; implementation baseline and decisions are in
    `docs/architecture/2026-10-15-wine-rose-baseline.md`.
  - **Legacy backend parity (2026-10-15):** the one commit added to `main` after the branches diverged was carried
    forward. Resume activation now scores only active qualifying and marked jobs instead of the entire historical
    corpus. This preserves visible scores while avoiding the 45 minute live upload observed on the legacy system.
  - **Production bridge (2026-10-16):** optional owner-only Google OIDC is wired to the existing owner and cannot
    create an account; migration 0041 stores Google's stable subject. An idempotent bridge copies legacy resume
    history into Resume Studio without changing the matcher's active resume or triggering a rescore. Aggregate-only
    inventory tooling and a single-VM Oracle Compose, Caddy and backup kit are in `deploy/oracle/`. The live legacy
    scheduler and database were not changed. See `ACE_NEXT_KNOWLEDGE.md` for the required rehearsal and cutover.
  - **Email verification (2026-10-16):** production password sign-in now verifies an eight-character email code
    before creating a session. Forgot password sends a separate code before accepting a replacement password. Both
    code types expire after 10 minutes, are hashed, single use and throttled. Oracle sets
    `REQUIRE_LOGIN_EMAIL_CODE=true`, which fails closed if Resend cannot deliver. Google OIDC continues to use its
    verified email claim and does not add a second ACE email step.
  - **Account creation in the browser:** the first visit to `/login` (or the old UI) offers "Create your account"
    while no owner exists; refused afterwards; from a public address it needs `SETUP_TOKEN`. The web app listens on
    127.0.0.1 because Next's rewrites do not forward the browser's address.
  - **Resume Studio foundation:** documents kept as uploaded, a career knowledge base with suggested, verified,
    needs clarification and retired facts and an audit trail, versions with a primary one feeding the job list, and a
    deterministic ATS checker with evidence quotes, unknowns and history. Migration 0039. `docs/knowledge/09`.
  - **Website layout:** top navigation and a department strip instead of the sidebar, whole-page scrolling with a
    footer, browse groups at `/app/browse/<slug>`, a shop-front home, company directory and pages. `docs/knowledge/05`.
  - **Pulls is home** (`/app`), focused navigation, a Dashboard page, no command palette, `/api/sessions` from about
    144 queries to 8. `docs/knowledge/05`.
  - **Pulls-first shell (2026-10-15)**, after the owner's approved prototype: sidebar in three groups, top bar with
    live, delayed or stalled, `/app/pulls` as home, `/app/analytics` (was Dashboard), `/app/extension` (pairing), a
    phone bottom bar. `/api/pulls` serves 15 minute windows with an honest metric contract; migration 0040 adds
    attempts and failures per window (older windows say not recorded). Deep links survive sign-in. Details:
    `docs/knowledge/05`. The web app forwards `/api/*` at runtime (`web/src/app/api/[...path]/route.ts`), so a build
    no longer bakes in API_ORIGIN.
  - **Pulls-first completion (2026-10-15):** the sidebar now collapses and remembers the choice; Analytics has URL
    backed 14, 30 and 90 day trend ranges plus a discovery role-family filter. The obsolete Browse and Companies
    pages redirect to Opportunities and their code is gone. FastAPI `/` redirects to Next.js and the legacy HTML was
    removed. Compose now has separate `api` and `web` services on local ports 8000 and 3000. Geist is bundled from
    the installed Next package, so production builds do not contact Google Fonts.
  - Hazard: the live compose (built from `main`) cannot migrate a database already upgraded by `next-app` (alembic
    cannot locate 0037 or 0038). Do not rebuild the live stack from `main` against a database `next-app` migrated;
    merge first.
- Alerts are composed but **not delivered**: `RESEND_API_KEY` is not set, so each
  pull logs `mail_not_configured`. Only the user can add the key.
- `README.md` now reflects the Next.js runtime and current test counts. Live source and posting totals remain the
  last recorded production figures until the approved deployment verification.
- User side, not yours: add `RESEND_API_KEY`; reload the extension at
  `chrome://extensions` (1.20.0, it never reloads itself); a private cleanup
  item the prompt mentions.

## Earlier automatic-logo handoff, archived 2026-10-26

**2026-10-26 automatic employer logos:** Review branch
`company-logo-consistency-20261026`, draft PR #1, now handles future employers
automatically through `/api/company-logo`. The 59 bundled icons/71 aliases are
an optional fast path. Exact registered sources provide employer branding;
no guessed domains, ATS favicon substitutions or external history disclosure.
A bounded, private asset cache and image decoder serve small PNGs while initial
fallbacks stay visible. Auth, application state, polling and scheduler are
unchanged; no migration or deployment. Shopify outside the bundle passed a
real public discovery and authenticated local proxy check against fictional
data. See `docs/architecture/2026-10-26-company-identity.md` for validation,
limits and changed files. Browser screenshots remain pending due to cooling.
