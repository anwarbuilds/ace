# 10. UI rebuild status against the approved prototype

Written 2026-10-15 for the local session that finishes the interface. The approved design is the owner's prototype
`ace-pulls-first-demo.html`; the requirements are `ACE-CODEX-PULLS-FIRST-IMPLEMENTATION-PROMPT.md`. Both live only on
the owner's machine in `design/` (ignored by git). Verified on branch `next-app`, commit a82cb9a or later.

## What exists, page by page

| Route | State | Gap against the prototype |
| --- | --- | --- |
| Shell | Done: sidebar in three groups, top bar (crumb, Live/Delayed/Stalled, theme), phone bottom bar, `/app/more` | Collapse button for the sidebar; compare spacing pixel for pixel |
| `/login` | Works (owner sign-in, first-run account creation, reset) | Old card styling. Restyle to the prototype's anthracite look |
| `/app/pulls` | Done: hero, 4 KPIs, 15 minute timeline with filters and day paging, rail, expandable jobs with actions | Close; verify on live data |
| `/app/opportunities` | Ported old Queue table with tabs, sorts, filters, pages | Prototype: searchbar plus tabset toolbar, table in a rounded panel, job detail drawer. Restyle; keep every filter |
| `/app/jobs/[id]` | Ported old job page | Restyle to prototype drawer and panel look (can stay a page) |
| `/app/applications` | 4 KPIs plus the ported table, CSV export, history list | Prototype: funnel, family bars, searchbar, status select in a panel table |
| `/app/analytics` | Done on the new pattern (applications first, then discovery) | Date and role filters |
| `/app/resume-studio` | Ported studio (knowledge base, documents, checker, history) | Prototype layout: knowledge list left, versions, match panel with radial score |
| `/app/extension` | Done on the new pattern (pairing, steps) | Extension graphic as in the prototype |
| `/app/archive`, `/app/saved` | Ported table | Restyle like Opportunities |
| `/app/coverage` | Ported | Prototype KPIs and panels |
| `/app/settings` | Ported sections | Prototype: Appearance, Security, Discovery preferences as panels |
| `/app/answers`, `/app/insights/skills` | Ported | Restyle; keep reachable from Extension and Resume Studio |
| `/app/browse/*`, `/app/companies/*` | Unlinked leftovers | Delete |
| FastAPI `/` (old single-file UI) | Still served on :8000 | Owner asked (2026-10-15) to retire it: redirect `/` to the web app once the new pages are at parity |

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
