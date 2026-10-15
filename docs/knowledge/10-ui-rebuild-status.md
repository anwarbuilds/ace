# 10. UI rebuild status against the approved prototype

Written 2026-10-15 for the local session that finished the interface. The approved design is the owner's prototype
`ace-pulls-first-demo.html`; the requirements are `ACE-CODEX-PULLS-FIRST-IMPLEMENTATION-PROMPT.md`. Both live only on
the owner's machine in `design/` (ignored by git). Verified on branch `next-app`, commit a82cb9a or later.

## What exists, page by page

| Route | State | Gap against the prototype |
| --- | --- | --- |
| Shell | Done: three navigation groups, persistent collapse state, top bar, phone bottom bar, `/app/more` | None found in Night, Day, desktop or phone review |
| `/login` | Done: owner sign-in, first-run account creation and reset in the anthracite card | None found |
| `/app/pulls` | Done: hero, 4 KPIs, honest 15 minute windows, filters, day paging, rail and durable job actions | Live-data verification remains an owner-machine step |
| `/app/opportunities`, `/app/jobs/[id]` | Done: local search, tabs, ordered sorts, full filters, table, paging and dedicated details | The detail URL preserves return context |
| `/app/applications` | Done: KPIs, search and filters, durable status controls, CSV and unmatched history | Status changes remain on the detail page |
| `/app/analytics` | Done: applications first, discovery and resume fit, date-range and discovery-family filters | None found |
| `/app/resume-studio` | Done for the shipped foundation: overview, knowledge, documents, ATS checker and history | Tailoring and DOCX/PDF export are later scope |
| `/app/extension` | Done: status, pairing, revocation, setup and answer-bank path | None found |
| `/app/archive`, `/app/saved` | Done on the Opportunities table pattern | Saved remains secondary and is not in navigation |
| `/app/coverage`, `/app/settings` | Done: working source coverage, appearance, security and discovery controls | None found |
| `/app/answers`, `/app/insights/skills` | Done and reachable from Extension and Resume Studio | None found |
| `/app/browse/*`, `/app/companies/*` | Removed; old links redirect to Opportunities | No data was deleted |
| FastAPI `/` | Redirects to the canonical Next.js Pulls page | The legacy HTML and its UI-only tests were removed |

## What must not be lost
Marks (saved, reviewed, dismissed, applied with status and note), external applications, CSV export, the answer bank
and history the extension reads, extension pairing tokens, the gate rules, job identity and first-seen times.
Retiring the old UI deletes a page, never data.

## How the pieces fit
- Shared page parts: `web/src/components/page/PageParts.tsx` (PageHero, Kpi, Bars, DayColumns).
- Shell: `web/src/components/shell/{Sidebar,Topbar,nav,NavIcon,liveState}.tsx|ts`.
- Styles: `web/src/app/globals.css`, the blocks after "Pulls-first shell"; tokens at the top (Night and Day).
- New-style pages wrap content in `<div className="pg">` inside `ScrollArea`; ported pages use `.head` and `.page`.
- The browser calls `/api/*` on the web origin; `web/src/app/api/[...path]/route.ts` forwards it to API_ORIGIN at
  runtime. Nothing is baked into a build.
- Compose now runs separate `api` and `web` services. The app is on `127.0.0.1:3000`; FastAPI remains available on
  `127.0.0.1:8000` for health and local operations.
