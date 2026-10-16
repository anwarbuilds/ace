# ACE Wine and Rose verified baseline and gap matrix

Verified on 2026-10-15 against the current `wine-rose-platform` branch and the locked V2 reference. The reference was extracted from `design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT.zip`; its prompt matches `design/CODEX_IMPLEMENTATION_PROMPT.md` byte for byte. All 12 reference screens were captured at 1440 by 900 in Night and Day before implementation.

## Verified system baseline

| Area | Verified behavior | Risk and required change |
| --- | --- | --- |
| Next.js | Next.js 16.3.8, React 19.2.8, App Router, real routes, server reads with `no-store`, browser mutations through the same-origin API proxy | Preserve route and data boundaries. Replace the anthracite visual tokens and shell with the locked Wine and Rose system. |
| Authentication | Owner-only Argon2id passwords, database sessions, HttpOnly session cookie, CSRF header, throttling, reset flow, safe return URL, protected private APIs | Preserve security code. Refactor only the public and authentication presentation. Google and Microsoft remain truthful unavailable states until configured. |
| Extension | Pairing creates a scoped bearer token that can only read answers and work or education history. The extension never submits | Preserve pairing routes, scopes, answer editor, and extension behavior. Restyle the real extension page. |
| Pulls | `/api/pulls` reports backend-derived 15-minute windows. It separates distinct successful sources, attempts, postings observed, new postings, qualifying arrivals, failures, and partial historical telemetry | Keep the API contract. Add the application total card and match the V2 composition without inventing health or counts. |
| Job marks | Rows and job detail update optimistically through `PUT /api/marks/{id}` and revert the row on failure | Coordinate the application total with the same optimistic transaction, prevent repeated writes, and refresh other tabs. |
| Application totals | `/api/dashboard` counts marked jobs plus external application history. `/api/marks` counts marked jobs only. The sidebar uses `/api/marks`, while Applications and Analytics use `/api/dashboard` | Add one explicit total across both stores to `/api/marks`. Use it in the sidebar, top bar, Pulls, Applications, Analytics, and Settings. Preserve the stored-posting and external split. |
| Theme | Night, Day, and System are stored in a cookie and applied before first paint | Replace old anthracite values with the exact V2 Wine and Rose tokens. Keep System as an existing useful preference. |
| Text guard | Runtime MutationObserver and Playwright visible-text and drawn-bar checks exist | Add a static user-facing source scanner that excludes fixtures, tests, comments, and the guard patterns themselves. Expand rendered coverage to public pages, all 12 routes, and dynamic states in both themes. |
| Tests | Backend auth and mark tests, Next.js Playwright tests, production build, and 185 extension matcher cases exist | Add total consistency, first mark, duplicate click, clear, status promotion, reload, failed rollback, external history, filters, focus refresh, and screenshot coverage. |

The final legacy `main` change after the branch point was audited and carried forward on 2026-10-15. Resume activation
now bounds synchronous scoring to active qualifying and marked jobs. The affected tests pass, and the full backend
suite reports 1,173 passing tests.

## Route gap matrix

| Route | Real feature status | Visual gap | Primary files |
| --- | --- | --- | --- |
| `/` | Public and private-data safe | Current page is a small information card. Build the V2 cinematic hero, complete A, light trails, Pulls preview, journey cards, and public footer | `web/src/app/page.tsx`, public components, `globals.css` |
| `/login` | Real owner login, first-owner setup, reset, safe redirects | Replace the prior auth composition with V2 split layout and wording while keeping the dialogs and real forms | `AuthSignInExperience.tsx`, auth components, `globals.css` |
| `/signed-out` | Protected success state and real logout flow | Match V2 lock card and split artwork exactly | `SignedOutCard.tsx`, `ThemeAwareAuthLayout.tsx`, `globals.css` |
| `/app/pulls` | Real authoritative Pulls API and expandable jobs | Restyle metrics, timeline, right rail, and add shared real application total | Pulls page and components, shared count component, `globals.css` |
| `/app/opportunities` | Real search, filters, sorting, paging, marks, job detail | Apply V2 table and filter language without removing richer filters or evidence | job list components, `globals.css` |
| `/app/applications` | Real marked jobs, external history, statuses, notes, CSV | Current heading count excludes external rows. Use the shared authoritative total and V2 pipeline cards | `JobListPage.tsx`, count component, backend marks aggregate |
| `/app/analytics` | Real application and discovery analytics | Use V2 metric and chart styling. Shared application total must update immediately | analytics page, count component, `globals.css` |
| `/app/resume-studio` | Real document, facts, checker, history, and skills routes | Apply the shared V2 shell and card system while preserving all real subroutes | studio pages and components, `globals.css` |
| `/app/extension` | Real pairing and answer-bank workflow | Apply V2 page hierarchy and card treatment | extension page and pairing component, `globals.css` |
| `/app/archive` | Real reviewed and dismissed records with reversible controls | Apply V2 list styling and page hierarchy | job list components, `globals.css` |
| `/app/coverage` | Real source reach, health, gaps, and add-source action | Apply V2 page hierarchy and cards to the full existing content | coverage page, `globals.css` |
| `/app/settings` | Real theme, sessions, extension tokens, resume, health, and exports | Replace old theme description and apply V2 sections and controls | settings components, `globals.css` |

## Implementation phases

1. Install exact Wine and Rose tokens, reusable artwork, wordmark, controls, and shell geometry.
2. Build the public home, sign-in, signed-out, and responsive compositions against the V2 reference.
3. Restyle the authenticated shell and all 9 private reference routes while retaining every existing data feature and secondary route.
4. Add the authoritative combined application total and coordinated optimistic updates with rollback and cross-tab refresh.
5. Add the static text scanner, expand Playwright route and dynamic-state coverage, capture 24 product screenshots, compare them with the 24 reference captures, and correct visible drift.
6. Run TypeScript, lint, build, affected backend tests, authentication tests, full Playwright, extension tests, and dash guards. No deployment is part of this work.
