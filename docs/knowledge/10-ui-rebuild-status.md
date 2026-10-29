# 10. UI rebuild status against the approved prototype

Written 2026-10-15 for the local session that finished the interface. The approved design is the owner's prototype
`ace-pulls-first-demo.html`; the requirements are `ACE-CODEX-PULLS-FIRST-IMPLEMENTATION-PROMPT.md`. Both live only on
the owner's machine in `design/` (ignored by git). Verified on branch `next-app`, commit a82cb9a or later.


## Inbox accuracy correction in progress — 2026-10-29 Pacific

Inbox parser 13 remains deployed (frontend `e64c547`; the newer startup-network
API release preserves that Inbox implementation). The owner disputed the semantic
accuracy of acknowledgements, offers and an interview after reviewing the live UI. The release is not accepted as accurate.
Source, health, preservation and arithmetic projection checks do not establish
semantic accuracy; agreement between a saved label and the same parser's fresh
reading is not independent validation.

The confirmed active email scope is July 1, 2026 onward, using the owner's
America/Los_Angeles calendar. Older Gmail evidence must remain preserved for
audit/Undo, while the active Inbox and email progress metrics use that scope.
Correction and representative regression work are in progress. No new historical
rewrite or deployment is implied by this checkpoint. Resume Studio is outside
scope. The stopped parser-7 runner and global historical rechecks remain off.

## Live Inbox/Analytics update, 2026-10-28 21:22 Pacific

The approved Wine and Rose V2 website now runs API/frontend `873ee080`, parser
12/schema 0050. Inbox records confirmed company rejections without a role picker,
retains Undo, and exposes assessment/test and interview/screen filters. Analytics
shows company email evidence separately from exact application outcomes, using
receipt-date scope and explicit exclusion of unknown role families. No unrelated
page, shell design, application register or extension 1.31.3 was replaced by this
feature.

Hosted Day/Night company and Undo behavior passes within 40 focused browser
cases; live source/auth/assets and private real-mail routes are separately
verified. Historical processing was separately authorized and completed with
preservation checks; only its explicit exact-target outcome plan changed
application statuses. Full CI remains red from the canonical extension browser
stub missing `chrome.runtime.id`; this does not certify broader browser coverage
or population classification accuracy. Read the first root knowledge section
for the complete live release, verified backup, rollback and private evidence
boundaries. The older page-by-page snapshot below remains historical.


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
