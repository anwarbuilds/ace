# ACE Next knowledge

Last updated: 2026-11-05 Pacific (chat 2 checkpoint). Chat 1 main CI verified green and owner confirmed real-job add. Chat 2 built locally on its main-based branch; acceptance and hosted CI pending, nothing new live.

**This is ACE's global memory. It loads in every chat, so it holds only current state, rules and an index.** The complete dated history, word for word, is in `docs/archive/ACE_NEXT_KNOWLEDGE-history.md` (about 130,000 tokens).

- **Reading the history.** Never load it whole. When a task touches an older decision or incident, find the section through the index at the end of this file or with `grep -n`, and read only that part.
- **What wins.** The owner's newest instruction, then this file. For implementation facts, trust the code and the running system over any record. Older records are evidence, not tasks. Never replay completed releases or operators.
- **Keeping it small.** Update current state in place instead of adding dated narratives. Full release proof goes in that release's private artifact folder, with a short note here. Keep this file under about 12,000 tokens: move anything you retire to the end of the archive word for word and add it to the index. Never rewrite existing archive text.

## Requirements programme and working method, 2026-11-04 Pacific

> **Start here for new work.** Read section 13 of the requirements file, beginning with "Latest state to pick up" in 13.5. It says exactly what is done, what to do first and where the code lives. Running state is in the next section.

The owner's goal: ACE finds every eligible role as soon as it is posted, with the employer's own link, and becomes the strongest tool for this search without rebuilding the architecture. A long research chat produced a master requirements file and interface designs. All new work follows them.

**Where things are**

- Requirements: `docs/requirements/2026-11-04-ace-requirements.md` (137 requirements, version 6). **A new chat starts at its section 13** (method, chat plan, P0 in simple words, tracker, reader and code facts, chat log) and reads only what its items need. It is the only requirements document: overwrite it in place, with no copies or archives. **It stays out of Git by owner decision**, because it describes the owner's search profile and this repo is public; `.git/info/exclude` blocks it. It exists only in this checkout, so the owner keeps a private copy.
- Designs: private canvas https://claude.ai/artifact/7jxkV16W8A34SPLzmka4fX, 17 boards with fictional data; its top row is what chat 1 built, and the older boards need rewriting in plain words before they are shown. Generator copy and rebuild notes: ignored `artifacts/ace-design-20261104/README.md`.
- Evidence: ignored `artifacts/platform-research-20261103/` holds the read-only scripts and results, and ignored `artifacts/requirements-chat-1-20261105/` holds the release scripts, read-only audits and the quick CI helper. Measured figures stay in the requirements file and out of public documents.

**How every chat works (owner's method)**

1. Read section 13, the chat's row in section 8.9 and only its items' rows.
2. Explain each item in very simple words with a small example, one item and one question at a time, never a list of decisions together. The owner confirms or changes it before any code.
3. Say which items have an interface part and show the design. The owner decides what changes. An item and its interface are built together in the same chat; no interface is built before its design is approved.
4. Build on one branch per chat from current `main`, with fictional fixtures. One chat runs at a time unless the owner asks otherwise.
5. An item closes only with its acceptance evidence. Merge, deployment, migration, scheduler change and each source registration batch need the owner's approval for that operation.
6. **Before every chat ends or runs low on room:** update the tracker and chat log in section 13, this file, `docs/HANDOFF.md` and the relevant `docs/knowledge/` topic, then give the owner the prompt for the next chat. The owner requires that each new chat has all prior knowledge.

**Plan.** P0 is 37 items in eleven proposed chats (section 13.2). **Chat 1 is done and live**: ARCH-01 and ARCH-02 are standing rules; OPS-01 is verified on `main` run 42150028596 (47, 59 and 206 browser cases, none skipped); DIS-14 is verified; DIS-15 is owner-verified; FRS-05 awaits the host sweep. PR #29 merged as `caf1e12`, PR #30 as `1363103`. **Chat 2 (DIS-16):** owner approved board/employer separation and planned Pear VC switch-off after impact review, not the live write. Local `requirements-chat-2-company-identity-20261105`, based on main `1363103`, has identity checks, unverified portfolio leads and exact petition guards. No screen or migration. 229 affected tests pass; full local backend stalled and was interrupted. Snapshot acceptance passes; live read-only new-code dry run and six-board preview passed; hosted CI pending. Hosted CI pending; nothing pushed or live. Earlier branch-command refusal was not retried; later read-only status showed the branch exists. Continue chat 2, not chat 3. P1 and later get planned when P0 is done.

**Owner decisions, 2026-11-05.** Plain words everywhere, with every page saying what it is (the first Coverage design was jargon to the owner). Show exactly what a chat will build, not the whole vision. Pasting a job gets an answer on screen; email and phone stay with alert work.

**Owner decisions, 2026-11-04.** Full-time roles only. Breadth first: finding and adding companies moved up into P0. $5 a month approved for LLM use. Phone push is design only for now. All alert work goes last, even though production email alerts are currently off. Add to the existing interface with no new sidebar items and no fifth Analytics tab. Registrations are approved batch by batch.

**Open with the owner** (sections 10 and 13.5 of the requirements file), one at a time: Pear VC exact live switch-off approval, after impact review; SmartRecruiters' robots file (it says `Disallow: /` to all but LinkedIn's bot, and ACE reads 155 boards through that API), Workday's site terms, borderline role families, the DOL LCA file for DIS-10, whether to use FreeHire's UKG links as pointers, labelling time, tailoring and options.

## Current running state

Last verified 2026-11-06T00:33Z through public HTTP, container identity and read-only audits. No release has been checked in a signed-in production browser by the agent; the owner is the only one who has seen these pages signed in. Check again before claiming anything is running.

| Surface | Current |
| --- | --- |
| Website | https://ace.opik.net |
| Web | `1a08549550b765f40acc047dd0a82f684c3af58a`, PR #29 |
| API | `1a08549550b765f40acc047dd0a82f684c3af58a`, Inbox parser 15 |
| Scheduler | `1a08549550b765f40acc047dd0a82f684c3af58a`, gate `2026-10-29-v56`, 8 workers, lead ledger on, `HOST_POLICY_ENFORCE` off |
| Schema | `0051` |
| Extension | Source 1.31.6, unpacked from `extension/`, never published to the Web Store; owner reload pending |
| Production checkout | `/opt/ace`, Compose project `oracle`, stays at `8ec89cd` with the intended Caddyfile edit; images come from an override, never from this checkout |
| Source | `main` in `anwarbuilds/ace`, public (live commit merged as `caf1e12`); local standalone clone at `/home/ubuntu/Documents/ace-next` |

- Services now run one commit, and only the web reports its build. Source pushes do not deploy. Images were built from an isolated exact-commit archive: `ace-chat1-backend:1a08549` (migrate, API, scheduler) and `ace-chat1-web:1a08549`.
- Latest proof and rollback: `/opt/ace/private-backups/chat1-release-20261105T2137Z/`, images `oracle-api:before-chat1-20261105T2137Z`, `oracle-scheduler:before-chat1-20261105T2137Z`, `oracle-web:before-chat1-20261105T2137Z`, guarded rollback in section 13.5 of the requirements file, owner-local `artifacts/requirements-chat-1-20261105/`. Migration 0051 is additive and stays through a rollback. Never restore old SQL as an image rollback.
- **Never run `docker compose up` for a service without the release override.** Compose has no image names, so it would start stale `oracle-*:latest` images. Live images: `ace-chat1-backend:1a08549` (migrate, API, scheduler), `ace-chat1-web:1a08549`. The same goes for any scheduler recreate to change a setting.
- Caddy: since 2026-11-03 it serves HTTP/1.1 and HTTP/2 with `Alt-Svc: clear`, after a QUIC error in Chrome. The edited file is bind-mounted: preserve its content (SHA256 `0445b6da406ffb6cb860f5b7a05ca8c30757c47fe9633db7dddb911f591bff15`) and inode through any checkout or release. Older source holds the pre-repair file. Proof: `artifacts/site-reachability-20261103/REVIEW.md`.
- Gmail: the API runs one monitor with a PostgreSQL lease about every 180 seconds (`GMAIL_BACKGROUND_SYNC_ENABLED`). `GMAIL_HISTORICAL_RECHECKS_ENABLED` stays false. The parser-7 operator stays stopped: never restart it. The connection was seen going from ready to error around 2026-11-01; recheck it (INB-02).
- Alerts: production email alerts are off, with the alert address and mail key unset on the scheduler. Deferred to the end by owner decision.
- CI: full sequence passing (backend, web, 47 extension, 59 Inbox and Analytics, 206 other browser cases, none skipped). Each browser step stops the next, so any failure is new, not a baseline. Lessons on flaky tests: the topic. Before changing a failing test, check it against the newest owner decision (`docs/knowledge/08-operations-and-testing.md`).
- Backups: private, on the VM, unencrypted, no offsite copy yet (OPS-02).
- Legacy: retired. Recovery material stays until the owner decides: volume `ace_ace_postgres_data`, recovery images, `/home/ubuntu/ace-private-backups/consolidation-20261030T170532Z/`, public tag `legacy-main-final`, private local `recovery-20261030/*` tags (never push all tags). Do not restart legacy services, comparison or replication.
- Open extension issues: on some Workday tenants the disability checkboxes stay unanswered and the self-identification Date shows digits while Workday reports it required; waiting for the owner's Copy field diagnostics paste. SmartRecruiters one-click forms in shadow roots are unsupported (APP-02). ACE cannot attach files.
- Coverage: three tabs at `/app/coverage` (Scoreboard, Leads, Sources). Scheduler maintenance keeps `employer_leads` and `host_policies` current in small budgets and never registers a board; first sweep runs for about 3 days. A refused host keeps polling until the owner decides (`HOST_POLICY_ENFORCE`). SmartRecruiters' API is the known refused host, with 155 boards.
- Open source issue: Pear VC's shared Ashby board was registered under the firm's name. Owner decision pending; the check gets fixed with a fictional regression (DIS-16).

## Rules

- ACE fills only after an explicit action, never submits an employer form, never advances it, and never marks Applied after filling. The owner reviews and submits.
- Employer-motivation answers ("Why this company?") stay entirely on the employer form: not suggested, filled, captured, counted, remembered or reused.
- Reuse only genuinely equivalent answers. Never infer a narrow sensitive answer from a broad one. Authorization, sponsorship, citizenship and legal questions stay conservative.
- Preserve backend, extension, authentication, discovery, application history, owner decisions, Gmail evidence, resumes and Undo. Rebuild nothing that works.
- Production data comes from the real backend. Fixtures are fictional. Never ship demo counts, names or scores.
- This repo is public. No names, contact details, application history, answers, mail, resumes, screenshots, dumps, tokens or credentials in Git, logs or issues. Actual owner totals stay in private artifacts.
- Respect robots and refusals. A 401, 403, 405, 429 or bot challenge is an answer: back off, and never get around it with proxies, other addresses, fingerprints or signed-in sessions.
- No user-facing em dashes or en dash punctuation. Run `python3 scripts/no_user_facing_dashes.py`.
- Deployment, publication, migration, scheduler change, source registration and destructive data work each need the owner's explicit approval for that operation. An approval does not carry over.
- Commit with the owner's configured identity. No co-author trailers and no mention of any AI in commits or PRs. Commit or push only when asked, and branch first on `main`.
- Do not claim a local test is production verification. Report failures and limits plainly. Never call classification or coverage perfect or complete without evidence.
- No destructive Git (reset, clean, force push) over owner work. Fetch before editing or pushing.

**Working with the owner.** Very simple words, with a small example, one item and one question at a time, never a list of decisions together. Lead with the result in a few plain sentences and keep replies short. The owner judges interface work by looking, so show Day and Night. "Push" means commit and push; "live" means https://ace.opik.net through an approved release. Say which one a change needs.

## Product contracts

**Website.** Next.js 16.4.2 App Router (read `web/AGENTS.md` and `web/node_modules/next/dist/docs/` before web code). Approved Wine and Rose V2: Night is deep wine and black, Day is rose wine and bright white, Inter, lowercase `ace` wordmark, tokens in `web/src/app/globals.css`, nothing under 11.5 px, sentence case, tabular numbers, company before role. Pulls is the landing page. Sidebar: Pulls, Opportunities, Applications, Analytics, Inbox Intelligence; Resume Studio, Autofill Extension, Archive; Coverage, Settings, Sign out. Reference kits are under `design/` (locally ignored). Marking Applied updates every count at once, persists, rolls back on failure and never double counts.

**Analytics.** Four tabs only: Overview, Outcomes, Role and resume, Companies. `/api/analytics` reads effective Inbox meaning and application history in one READ ONLY, REPEATABLE READ snapshot, with no counters or second ledger. Refresh lives once in the persistent app layout (`AnalyticsRefresh`), never inside the server subtree it refreshes; quiet no-store checks every 120 seconds while visible; a failed read keeps the mounted selection's last verified output. Headlines: Interview invitations and Online assessments count effective invitation emails by receipt date and open exact email records; Meaningful replies uses `positive`. Application stages count eligible identities separately, and recognized email never invents a stage or a match. Unanswered means pending, never rejected. Later rejection keeps earlier stages. Email scope starts July 1, 2026 Pacific (`2026-07-01T07:00:00Z`), separate from submission cohorts. Week arrows use Monday-to-Sunday Pacific weeks from already loaded daily data. Owner removals stay removed: the metrics disclosure and application CSV controls everywhere, and lower sections past Overview's and Outcomes' four cards. Desktop Overview, Outcomes and Role and resume fill the workspace with 28 px gutters. Submitted resume, channel and response-effectiveness rates stay "not recorded" or unavailable until evidence exists. Petitions and LCAs are not hires or a promise of sponsorship. Source contract: `docs/analytics/metric-sources.md`.

**Inbox.** Gmail is read-only, with its own OAuth client, separate from Google sign-in. Email meaning, application identity and permission to change status are three separate decisions. Clear rejections with one exact application are recorded automatically with Undo; a clear rejection with a reliably identified employer but no safe role is company evidence, with no status change. Positive outcomes need the opt-in, a live message, an exact job ID and an authenticated employer. Owner choices, Undo and all audit events are protected. Active Inbox scope starts July 1, 2026 Pacific; older mail stays stored for audit. Same-parser agreement, zero review items and arithmetic checks do not prove recall; population accuracy is unmeasured. No bulk historical replay without separate approval.

**Extension.** Manifest V3, approved Focus Mode V5.1 card (`design/ace-focus-v5.1/`): compact, draggable across the full viewport, dock, Close, and a theme that follows the website's Day, Night or System choice. Fill runs only from Fill, toolbar Fill or Alt+A; opening, hovering, focusing, typing and late responses stay passive. Finished owner answers save under the `learned` Memory policy, except motivation, signatures, passwords, history-owned fields, date sections and native multi-selects. Reuse goes exact fact, then answer-bank rule, then topic similarity with equal negation, timeframe, numbers and country. Work history dates belong to their matched entry. After a change, Reload at `chrome://extensions` and refresh employer tabs. Details: `docs/knowledge/06-extension-autofill.md`.

**Eligibility gate.** Deterministic and versioned, PASS or REJECT, never reading clock or network. Passes US full-time software, ML and forward deployed roles at 0 to 3 years. Rejects open-ended 3+ and above, senior and management titles, internships, contract work, infrastructure, platform, cloud, DevOps, SRE and mobile families (but "Software Engineer, Infrastructure" stays), data roles, explicit no-sponsorship, ITAR and citizenship requirements. Silence is unknown, not rejection. Every change needs a version bump, tests, a corpus dry run (`backend/scripts/gate_dry_run.py`) and a stale-row backfill. Details: `docs/knowledge/01-gate-and-roles.md`.

**Coverage.** Each tab says in plain words what it is. Adding by hand always answers on screen, keeps a lead whatever happens, and asks robots first; a board switched off earlier stays off. Lead checks only record: a board that qualifies waits for the owner. Details: `docs/knowledge/03-coverage-and-discovery.md`, `05-web-ui.md`.

**Discovery.** One adapter per platform. Job identity is (source, source_account, external_id); numeric IDs are internal. Only a complete snapshot can close jobs; a partial, empty, refused or non-authoritative read never does (`close_missing=False`). Conditional HTTP, bounded jittered retries, refusal backoff up to six hours, restarts resume persisted schedules. Eight workers; maintenance every 30 minutes. New boards go through `scripts/register_network_boards.py`, a dry run by default: it reads each board once and adds it only if it reads, is not an agency or shared board, and has a US software or ML role. A board with a passing role polls every 15 minutes, others hourly. Workable refuses the VM with 429s. The employer's own posting is the apply link; RippleMatch is the one exception. Details: `docs/knowledge/02-sources-and-scheduler.md`, `03-coverage-and-discovery.md`.

**Applications.** Identity is `job:<id>` from applied marks plus `external:<id>` records; separate applications are never fuzzy-merged. Marked pages ignore gate and active filters so history never vanishes. No spreadsheet import UI. "Applied before" is read-time evidence and never copies a mark.

**Company logos.** `CompanyLogo` and `CompanyIdentity` on every structured company surface: 85 reviewed bundled assets with provenance, then the owner-only `/api/company-logo` route using only verified sources. Never guess a domain, borrow a parent's mark or fabricate a logo; missing evidence shows initials.

**Resume Studio.** Deterministic, no generative AI yet. Facts are separate from wording and only verified facts count. The ATS checker reports an "Estimated ace compatibility score", never an employer's score. Tailoring and export are not built.

**Authentication.** One owner, no registration. Argon2id, hashed sessions, CSRF on mutations, email codes when mail is configured. Google sign-in binds the owner's subject. The Google Cloud project `acee` holds separate Web clients for sign-in and Gmail; credentials live only in the server's private `.env`. Extension tokens are least privilege and revocable.

## Release procedure

Prepare and test first, and get approval for the exact SHA and operation. If the agent's permission check refuses a production step, stop and offer the owner the exact command; never work around it. A release with a migration adds a real restore drill into a throwaway container with no network (about 4 minutes), a schema-only rehearsal including a downgrade, and runs `compose run --rm --no-deps migrate` before the services; the scripts that did this are in ignored `artifacts/requirements-chat-1-20261105/release/`, and section 13.5 of the requirements file explains them. For a schema-free release:

1. Inspect what is running: commits, images, container IDs, schema, private inventory.
2. Take a fresh private backup in `/opt/ace/private-backups/<name>-<UTC stamp>/` (directory 700, dump 600). Check gzip, archive catalog and full expansion. This is not a restore drill. No pruning.
3. Tag each prior image `oracle-<service>:before-<name>-<stamp>` and write a guarded rollback that replaces only that service.
4. Build the exact source with its SHA embedded, then activate only what changed: `docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build --no-deps --wait --wait-timeout 180 <service>`. Always pass `--env-file .env`. Never run `down`, remove volumes or recreate unrelated services. A migration or scheduler change needs its own approval.
5. Verify public `/healthz` and `X-Ace-Frontend-Commit`, served asset hashes, anonymous auth boundaries, installed read-only audits, protected row hashes (HMAC snapshots across 19 tables before and after), unrelated container IDs, private configuration hashes and inodes, schema and logs.
6. Record the outcome here in a few lines and the proof privately. Separate source and HTTP checks from signed-in browser checks.

Access: `ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170`, checkout `/opt/ace`. Never print `.env` or expanded Compose configuration. The agent's permission check can refuse production reads until the owner approves in that chat.

Lessons: a scheduler has no `--wait`, because its health check first runs after five minutes, so wait for `ace_scheduler_ready` in its log. In SSH `bash -s`, give non-input `docker compose exec` calls `</dev/null` or they swallow the remaining script. With `pipefail`, `gzip -dc | pg_restore --list` can exit 141, so run `gzip -t` first and use process substitution. Start long VM builds with `nohup` and poll a log. Use umask 022 for checkouts and 077 for private files. Health alone once missed unreadable new assets, so check hashes through public HTTPS.

## Local work and testing

- Browser tests run on hosted CI only. Full CI runs on a pull request in about 15 minutes, and a push cancels it. `artifacts/requirements-chat-1-20261105/ci-quick/quick_push.sh <commit>` runs chosen specs and takes Day and Night screenshots in about four minutes on a throwaway branch; delete it afterwards. Do not launch Chrome on this laptop: it has shut down under load, and the cooling restriction stands.
- Run heavy commands one at a time with `nice -n 15 taskset -c 0`. Node DOM tests: `--max-old-space-size=256`. TypeScript: 768 MB.
- Backend: pyenv 3.12.12 with `PYTHONPATH=.venv/lib/python3.12/site-packages`, because the `.venv` python symlink fails importing `_ctypes`. Fictional fixtures only. Starlette TestClient can stall in a restricted sandbox.
- Checks: `node extension/test-rules.js`, `node extension/test-memory.js`, `npm run test:extension-dom`, `npm run test:inbox`, `npm run typecheck`, `npm run lint`, `npm run build` (in `web/`), `git diff --check`, the dash scan. `npx next typegen` generates route types in a fresh checkout.
- Demo: `.venv/bin/python -m backend.scripts.seed_demo --database-url sqlite:///ace-demo.db`, then run the API with `ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db` and the web with `API_ORIGIN` pointing at it. Never seed production.
- Scratch directories do not survive a chat. Keep durable private work under the ignored `artifacts/` folder.

## Where to find things

- Topics, each read only when relevant: `docs/knowledge/README.md`. Current handoff: `docs/HANDOFF.md`. Testing runbook: `docs/operations/testing.md`. Deployment: `deploy/oracle/README.md`. Consolidation and recovery: `docs/operations/platform-consolidation-2026-10-30.md`.
- Code layout, every API route, every table and the migration ledger: "Code-verified implementation map" in the archive, indexed below. Product vocabulary and historical safeguards: "Standalone platform specification". Check both against the code before relying on them.

## Index of the archive

Every section of `docs/archive/ACE_NEXT_KNOWLEDGE-history.md`, newest first, with its first line. These are records from their dates: headings such as "START HERE" or "OPEN WORK" are historical, not tasks.

| Line | Section |
| ---: | --- |
| 6 | Assessment invitation headline LIVE, 2026-11-03 Pacific |
| 41 | Extension 1.31.5 follow-up, 2026-11-03 Pacific |
| 53 | Extension 1.31.4: Workday questions and ACE theme, 2026-11-03 Pacific |
| 87 | QUIC transport repair LIVE, 2026-11-03 Pacific |
| 110 | Outcomes and Role and resume workspace spacing LIVE, 2026-11-01 Pacific |
| 157 | Outcomes reference and global UI removal LIVE, 2026-11-01 Pacific |
| 215 | Analytics charts and immediate weekly navigation LIVE, 2026-11-01 Pacific |
| 292 | Analytics Overview workspace follow-up LIVE, 2026-11-01 Pacific |
| 355 | Analytics Overview weekly navigation LIVE, 2026-10-31 Pacific |
| 433 | Next-chat continuation checkpoint, 2026-10-31 Pacific |
| 608 | Interview invitation headline correction LIVE, 2026-10-31 Pacific |
| 679 | Inbox-to-Analytics synchronization LIVE, 2026-10-30 Pacific |
| 752 | Inbox-to-Analytics synchronization review, 2026-10-30 Pacific |
| 861 | Current platform consolidation completed, 2026-10-30 Pacific |
| 960 | Historical continuity records |
| 978 | Current Inbox contract and continuation, 2026-10-30 Pacific |
| 1054 | Source inventory and startup coverage gaps, 2026-10-30 |
| 1098 | Gate v56 and city startup networks LIVE, 2026-10-29 18:18 Pacific |
| 1149 | Inbox parser 14 corrective release LIVE, 2026-10-29 Pacific |
| 1204 | Inbox parser 15 LIVE; correction complete and PR #19 merged, 2026-10-30 Pacific |
| 1331 | Historical accuracy dispute, parser 13, superseded by parser 14 above |
| 1347 | Scheduler capacity release LIVE, 2026-10-29 16:54 Pacific |
| 1375 | Startup talent networks and gate v55 LIVE, 2026-10-29 16:04 Pacific |
| 1493 | Company-aware Inbox Intelligence LIVE, 2026-10-28 21:22 Pacific |
| 1614 | Continuous Inbox Intelligence LIVE, 2026-10-28 16:29 Pacific |
| 1695 | Extension 1.31.3 and learned-answer API LIVE, 2026-10-28 Pacific |
| 1805 | Inbox backlog correction LIVE with explicitly scoped cleanup, 2026-10-28 Pacific |
| 1913 | Inbox Intelligence LIVE, owner-approved and verified, 2026-10-28 Pacific |
| 2035 | Pre-deployment Inbox candidate assessment, superseded by the LIVE record above |
| 2120 | Analytics dashboard LIVE, owner-approved and verified 2026-10-27 Pacific |
| 2274 | Analytics screenshot/data rebuild ready for review, 2026-10-27 Pacific |
| 2350 | Analytics refresh fix LIVE, owner-approved and verified 2026-10-27T21:13Z |
| 2480 | Analytics refresh correction ready for web-only approval, 2026-10-27T20:27Z |
| 2587 | Approved job-mail release LIVE, verified 2026-10-27T19:27Z |
| 2669 | Job-mail triage completed locally, 2026-10-27 11:31 Pacific |
| 2807 | START HERE: job-related Inbox triage continuation, 2026-10-27 11:06 Pacific (18:06Z) |
| 3108 | Historical live release checkpoint, 2026-10-27T16:30Z |
| 3174 | Final live verification, 2026-10-27T16:01Z |
| 3221 | Approved activation, 2026-10-27T14:24Z |
| 3260 | Continuation checkpoint for new chats, 2026-10-26 |
| 3419 | 2026-10-26: Contextual answer adoption, API live, extension 1.30.0 |
| 3584 | OPEN WORK for the next chat: a reliable Inbox (measured 2026-10-26 evening) |
| 3937 | 2026-10-26: Pulls employer logos and automatic provider recovery |
| 3983 | 2026-10-26: Platform-wide logo coverage follow-up |
| 4032 | 2026-10-26: Missing Hive and Vizient logos, tenant metadata correction |
| 4071 | 2026-10-26: Explicit filling and Workday corrections, extension 1.29.1 |
| 4117 | 2026-10-26: Inbox clarity, Rejected companies and Workday matching deployed |
| 4214 | 2026-10-26: Logos and quick fill deployed |
| 4242 | 2026-10-26: Simplified extension quick fill, local 1.29.0 |
| 4283 | Instructions for a new Codex chat |
| 4359 | Non-negotiable owner requirements |
| 4399 | Working notes for agents (learned 2026-10-24 to 2026-10-25) |
| 4692 | Current working state on 2026-10-25 |
| 5517 | Historical core live state on 2026-10-24 |
| 5733 | Historical live state on 2026-10-22 |
| 5796 | Product objective |
| 5808 | Standalone platform specification |
| 6415 | Code-verified implementation map |
| 7170 | Repositories and runtime state |
| 7194 | Historical production data inventory, 2026-10-16 |
| 7222 | Architecture |
| 7255 | Data ownership and compatibility |
| 7289 | Authentication |
| 7387 | Owner identity and real Resume Studio documents |
| 7421 | Applications and counters |
| 7432 | Local commands |
| 7491 | Safe migration procedure |
| 7680 | Oracle Free Tier operation |
| 7701 | Deferred post-launch retention plan |
| 7777 | Git and GitHub |
| 7792 | Outstanding owner decisions and monitoring |
| 7833 | Change log |
