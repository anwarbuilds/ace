# ace web

The Next.js app for ace. It reads and writes through the FastAPI backend in `backend/`; it has no database of its own.
The app serves the private workspace plus the approved public authentication surface.

```
# from the repo root: a fictional demo database and the API on :8000
.venv/bin/python -m backend.scripts.seed_demo
ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db .venv/bin/uvicorn backend.app.api.main:app --port 8000

# here
npm ci
npm run dev                     # http://localhost:3000 (API_ORIGIN defaults to http://127.0.0.1:8000)
npx playwright test             # 80 browser tests; they write marks, so demo data only
npx next build                  # production build
node scripts/capture-auth-screenshots.mjs  # fixed-size auth reference captures
```

Map: routes in `src/app/app/`, URL state in `src/lib/listState.ts`, server reads in `src/lib/api.ts`, browser calls in
`src/lib/client.ts`, shell (sidebar, palette, toasts, dash guard) in `src/components/shell/`. Design tokens are the old
UI's, in `src/app/globals.css`. Read `AGENTS.md` before changing Next.js code.
