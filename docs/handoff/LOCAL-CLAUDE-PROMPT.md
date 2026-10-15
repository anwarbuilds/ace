# Prompt for the local Claude Code session

Paste everything below the line into Claude Code, started in `~/Documents/ace-next` on branch `next-app`.

---

You are finishing the ace web app on this machine. Read, in order: `CLAUDE.md`, `docs/HANDOFF.md`,
`docs/knowledge/10-ui-rebuild-status.md`, `docs/knowledge/05-web-ui.md` (last three entries), `web/AGENTS.md`. The
approved design is `design/ace-pulls-first-demo.html` and the requirements are
`design/ACE-CODEX-PULLS-FIRST-IMPLEMENTATION-PROMPT.md`. Open the prototype in a browser and look at every page before
coding. Data in the prototype is fictional; never copy its numbers.

Goal: one interface, the Next.js app, looking like the prototype on every page, in Night and Day, desktop and phone.
The owner wants the old interface gone.

Rules you must keep (details in CLAUDE.md and HANDOFF section 2): the repo is public, so no personal data, secrets,
`.env`, database dumps or screenshots of real data in commits; no em dashes or dash-like bars anywhere the user sees;
the wordmark is lowercase "ace"; anthracite palette, never lighter; every text pair passes WCAG AA; never bypass
robots.txt, 403/429 or bot challenges; never ask for passwords or keys; no force-push, history rewrite, destructive
migration, deploy or spending without asking. Do not change the gate rules. Work in small commits on `next-app`.

Steps:

1. Setup and baseline. `git pull origin next-app`. Run `alembic upgrade head` against the local database (0038 to
   0040 are additive). Start the API on 127.0.0.1:8001 and `cd web && npm run dev` with
   `API_ORIGIN=http://127.0.0.1:8001`. Sign in. Take screenshots of every page and of the prototype's matching page,
   side by side, so the owner can see the gap. Run `.venv/bin/python -m pytest backend/tests -q
   --ignore=backend/tests/browser` and `cd web && npx playwright test` against demo data
   (`python -m backend.scripts.seed_demo`), never against the real database (the tests write marks).

2. Sign-in page. Restyle `/login` (sign in, first-run "Create your account", reset) to the prototype's look. Keep the
   server-side auth exactly as it is (argon2id, sessions, CSRF, throttling, `next` return). There is no public sign-up
   and must not be one.

3. Restyle the remaining pages to the prototype, one page per commit, keeping every feature listed in
   `docs/knowledge/10-ui-rebuild-status.md` under "What must not be lost":
   Opportunities (toolbar with searchbar and tabset, table panel, optional detail drawer), job page, Applications
   (funnel, family bars, search, status select, CSV), Resume Studio (knowledge base, versions, match panel), Archive,
   Coverage, Settings (Appearance, Security, Discovery), Answers, Skills. Reuse `components/page/PageParts.tsx`.
   After each page: screenshot Night and Day at 1440 and 390 wide, compare with the prototype, fix, then commit.

4. Remove what the owner no longer wants: the unlinked `/app/browse` and `/app/companies` routes and their components,
   unused CSS from the old top navigation, and the old single-file UI. For the old UI: make FastAPI `/` redirect to
   the web app (configurable `WEB_BASE_URL`), delete `backend/app/api/static/index.html` and its browser tests only
   after every Playwright test passes, and say in the commit how to roll back (`git revert`). Do not delete any
   database table or row.

5. Run it for daily use: add a `web` service to `compose.yaml` (Node, `npm run build && npm start`,
   `API_ORIGIN=http://web:8000` or the API service name, bound to 127.0.0.1:3000). Tell the owner the exact commands
   and wait for their go before rebuilding the live stack. The live stack is built from `main`; merge `next-app`
   first, or alembic will fail on 0037+.

6. Verify on the real data, read-only: Pulls windows after the scheduler restart show sources checked, answered,
   failed and attempts; older windows say not recorded; job counts in a window match its expanded list.

7. Before ending: update `docs/HANDOFF.md` section 3 and `docs/knowledge/10-ui-rebuild-status.md`, scan the diff for
   personal data, run both test suites, commit, push, and reply with screenshots and a short Completed, Next,
   Blockers list.

Later work, not part of this session unless the owner asks: Resume Studio tailoring and DOCX/PDF export, typed API
types, the Oracle Cloud free deployment, the SDE II dry run.
