# Testing ACE

Use Python 3.12 and Node.js 22. Install `backend/requirements.txt` and run `npm ci` in `web/`. See the [README](../../README.md#local-setup) for isolated demo setup and the [CI workflow](../../.github/workflows/ci.yml) for the full hosted sequence.

## Fast checks

From the repository root:

```bash
.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/browser
node extension/test-rules.js
node extension/test-memory.js
node --check extension/content.js
python3 scripts/no_user_facing_dashes.py
cd web
npm run test:extension-dom
npm run test:company-logos
npm run test:inbox
node --test tests/analytics-calculations.test.mjs
npx next typegen
npm run typecheck
npm run lint -- src tests
npm run build
```

Choose focused backend files during implementation. A fresh checkout needs `next typegen` before TypeScript can resolve generated route types. A passing local test does not establish production behavior.

## Browser suites

Use only a newly seeded fictional database. These suites mutate marks and other records. Never set their URLs or database configuration to production or the retained legacy database.

The main workflow installs Python dependencies plus `websocket-client`, starts the fictional API on port 8000, then runs:

```bash
ACE_BROWSER_TEST_URL=http://127.0.0.1:8000 \
  .venv/bin/python -m pytest backend/tests/browser -q -rs
```

These Python tests exercise extension mechanics on fictional pages. They are retained after local legacy retirement. They are not an instruction to restart the old UI or legacy stack.

For the Next.js suites, install Playwright's browser dependencies on suitable hardware, build the website, and start it with `API_ORIGIN=http://127.0.0.1:8000` on port 3000. The default [Playwright configuration](../../web/playwright.config.ts) uses that website. The focused Inbox/Analytics specs require `backend.scripts.seed_analytics_demo`, which uses `/tmp/ace-analytics-fictional.db`. Other app specs use `backend.scripts.seed_demo`. Follow CI's fixture transitions rather than mixing the two databases.

```bash
cd web
npx playwright install --with-deps chromium
npx playwright test tests/e2e/inbox-review.spec.ts tests/e2e/analytics-redesign.spec.ts
```

The dedicated [Inbox workflow](../../.github/workflows/inbox-intelligence-review.yml) retains focused hosted verification. Existing assertions and failure visibility must remain intact. Do not skip tests or weaken expectations to conceal baseline failures.

## Owner laptop restriction

Do not run Chrome here until cooling is repaired. Earlier single-worker runs still caused shutdowns. Run heavy nonbrowser commands sequentially, at low priority and pinned to one CPU; Node DOM checks use a 256 MB heap. Hosted browser results and production HTTP/source checks are separate evidence.

## CI interpretation

Read the current run's jobs and failed test names. The pre-consolidation PR #19 full run passed backend/web but had 22 extension-browser failures, with later app-browser steps skipped; the dedicated Inbox run passed. Compare exact failures to that baseline and report any additional failure. Green arithmetic, source hashes and health checks do not certify semantic email accuracy, complete source/mailbox observation or signed-in production visuals.
