# Alerts, email and sign-in history

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you touch alert emails, freshness or Resend, or you start the sign-in work (read the authentication entry first).

## Gmail connected, quota failure during initial import (2026-10-25)

The owner configured the separate Gmail OAuth client and read-only grant.
Production's generic `Gmail read could not be completed` was reproduced by a
read-only diagnostic as HTTP 403 `rateLimitExceeded` on message 261, after
smaller reads succeeded. Token refresh and access worked; creating another
client or reconnecting does not fix this quota response. No email content,
tokens or owner screenshots are retained here.

Implemented remediation: bounded exponential retries for explicit Google
quota/temporary failures, respect Retry-After, skip already-imported message
detail reads and deleted messages, retain authorization state on temporary
failure and return a clear 429 instead of a generic connection failure.
Ordinary permission refusals are never retried. Tests use fictional responses
and isolated databases; the final focused set passed 112 tests with clean
whitespace and zero-hit dash checks. With explicit owner approval, API-only
release `dde926f` became healthy on 2026-10-25 at 20:01 Pacific. A fresh private
backup was verified; protected counts matched and other container IDs were
unchanged. No migration, scheduler operation, permission expansion or
automatic-outcome enablement occurred. Post-release Gmail reads and Analytics
totals/cohorts/drilldowns passed read-only. The owner still needs Resume sync and
completion of the historical preview/review; no full mailbox import or outcome
confirmation was performed during this release. See the root continuity file
for exact evidence and backup location.

## Baseline suppression was removed, then replaced by freshness

The first design suppressed all alerts on a source's first poll. That
meant a company discovered today with a great job posted yesterday would
never surface. Replaced with a freshness policy: a *baseline* `NEW` job
must also be recently posted; a later `NEW` job is always alertable
because it demonstrably appeared after a prior snapshot. A source is
baseline exactly once, so the caution costs one poll per company, ever.

## Email removed entirely (2026-09-06)

> **Status:** Superseded 2026-09-14: one alert email per closed pull was added back (see 'Job alerts, one email per pull' in this file). The old digest subsystem and the notification_outbox table stay dead.

ACE originally sent digest emails. The user monitors the web application
instead, so the whole notification subsystem was deleted: outbox,
digests, SMTP, delivery worker, ~4,000 lines of code and tests.
**The `notification_outbox` and `notification_digests` tables still
exist in the database** - code is gone, tables were left in place rather
than dropping delivery history. Drop them with a migration if wanted.

## Authentication was built, then removed (2026-09-13 to 09-14)

> **Status:** History. Superseded by "Owner sign-in with extension pairing (2026-10-14)" below, which shipped the extension token with it.

Built for a deployment that had not happened, and reverted the next day
because it made the platform worse in the meantime: the Chrome
extension was 401'd and stopped filling forms, and every use of the app
began with a login nobody else could reach anyway.

Removed as one revert of `c9455ba`, `6f4344e` and `c8bf8e9`, with
migrations 0030 and 0029 downgraded **first**, while the files still
existed to run them. The working tree came back byte-identical to
`70e8a2a`. No data was lost: dropping `owner_id` removed an annotation,
not the 288 marks, 58 answers, 47 external applications or 2 resumes it
annotated.

**The work is unreferenced, not gone.** Those three commits hold a
session layer, owner scoping, account management and a password-reset
flow, and apply cleanly if deployment happens. What is worth carrying
forward, because it will be rediscovered otherwise:

- **Deployment still requires auth.** The limitations table are
  unchanged on this. A public URL reaches an answer bank holding a home
  address, phone number, and gender, race, veteran and disability
  answers, plus 7 write endpoints.
- **Making the marks join fail closed found two real bugs immediately.**
  `set_mark` wrote rows with no owner, so a newly saved job returned
  200 and then never appeared again; `get_job` built its own unscoped
  `JobFilters` inside `queries.py`, so a job opened from a link showed
  no mark. Both would have been silent under a fail-open design, and
  would have been leaks rather than bugs once a second account existed.
- **Open registration needs more than scoping.** `job_marks` is keyed
  on `job_id` alone and `external_applications` is unique on
  `match_key` alone, so two people cannot both mark the same job or
  apply to the same role. Multi-user means re-keying both.
- **The browser suite drives the real app**, so auth broke all of it.
  Signing in from the harness is the right fix rather than running the
  app with the wall down. A login answers 303 with `Set-Cookie` on
  *that* response, so an opener that follows the redirect never sees
  the cookie.
- **CSS tokens are `--surface-2`, `--border-strong`, `--text`.**
  Inventing names produces declarations the browser silently discards;
  the account inputs rendered as invisible boxes.

The extension token, production compose and off-box backups remain
unbuilt, and remain the real blockers for deployment.

---

## Job alerts, one email per pull (2026-09-14)

Email was deleted on 2026-09-06 because the web application was the
only surface being watched. It is back, and the reason is different
rather than forgotten: alerts exist so an application can be started
from a phone, away from the laptop. A web page you have to be sitting
in front of cannot do that.

It is deliberately not the old system. No outbox, no digests, no
delivery worker, no retry schedule. One HTTPS call when a pull
finishes, and a timestamp saying it happened. Roughly 300 lines against
the 4,000 that were removed.

**A pull is the unit, because the user asked for it in those words:**
"for every pull there are certain amount of jobs coming, so all pull
jobs should come at once." That maps exactly onto `poll_sessions`,
which is already a fifteen-minute clock bucket and already how the
interface groups arrivals.

The alternatives were measured before being rejected. Per job: 3-20
emails on an ordinary day, and 140 and 185 on the two days new sources
were registered. Per scheduler cycle: a cycle runs every few seconds.

**A bucket is only alerted once it has closed.** A bucket still being
written to is a pull still arriving, and half a pull is not worth an
email.

**`notified_at` is a timestamp, not a boolean**, so "sent at 08:14" and
"never sent" are distinguishable. The migration backfills every
existing row as sent, because deploying this must not email a backlog
of 293 historical pulls. A pull older than twelve hours is marked
without sending, so a scheduler stopped for a week does not mail every
quarter hour it missed.

**A pull is consumed whether or not delivery succeeded.** The
alternative is a retry queue, and a pull that could not be delivered
once is stale by the time a retry lands. The jobs are in the queue
regardless: that is the durable surface, and an alert is a nudge.

**The alert sender is injected**, like `cycle_recorder` before it, so
`runtime.py` keeps no database import and a mail provider being down
cannot stop ACE polling.

Links point at the employer's own posting, per the standing invariant.
Tapping one on a phone has to land on the application form, which is
the entire point.

## An email client is not a browser (2026-09-14)

The alert was designed to be read in Gmail, on a phone and on a
desktop, which is a harder target than a web page and fails in ways a
browser never shows you.

**Gmail discards `<head>` and the `<body>` tag's attributes**, keeping
only the children. A design whose background lives on `<body>` renders
as light text on Gmail's white page. Verified by simulating the strip
and rendering the result, rather than assuming: the canvas is on the
outermost table, and `bgcolor` attributes sit beside every CSS
background because Outlook honours the attribute where it ignores the
property.

**Outlook renders through Word**, which ignores padding on an anchor,
so a styled `<a>` collapses into bare text. The Apply control is a
table cell with a `bgcolor`, which is the shape that survives
everywhere.

**No viewport meta meant a phone laid the mail out at 980px** and
zoomed out. Found by rendering at 390px. An alert unreadable on a phone
has failed at its only job, since applying from a phone is the reason
it exists.

**A preheader decides the inbox preview.** Without one a client scrapes
the first text in the body, so every alert previewed as "A C E". It now
names the first three roles.

**A test passed against the bug it described.** The first version
asserted the canvas colour appeared somewhere after the body tag, and
the preheader mentions that colour as its *text* colour, so removing
the background entirely left the test green. Only the mutation run
caught it. Asserting on `bgcolor="..."` or `background:...`
specifically is what actually pins the behaviour.

## Alert delivery (checked 2026-10-09)

- **Alert emails are not being delivered (checked 2026-10-09)**:
  ALERT_EMAIL is set but RESEND_API_KEY is not, so every pull logs
  `mail_not_configured` and is marked notified without a send. The old
  notification_outbox table is dead by design (email subsystem removed
  2026-09-06; alerts are now one Resend call per closed 15-minute pull).
  Only the user can add the key -- never ask for it in the conversation.


## Owner sign-in with extension pairing (2026-10-14)

Phase 2 of the rebuild, on `next-app`. Built so that the September
failure (the extension locked out) cannot recur: the extension token
shipped in the same change, and a rollback switch exists.

**Shape.** `backend/app/auth/`: `crypto.py` (argon2id via argon2-cffi,
RFC 9106 defaults; tokens are 256 random bits stored as SHA-256),
`service.py` (pure rules over a session and an explicit `now`),
`guard.py` (`require_auth`, installed as an app-wide FastAPI dependency
so a new route is private unless listed in `guard.PUBLIC`). HTTP in
`backend/app/api/routers/auth.py`. Migration 0038 adds `users`,
`auth_sessions`, `api_tokens`, `auth_codes`, `login_attempts`; purely
additive. Owner from `python -m backend.scripts.create_owner EMAIL`
(hidden prompt; `--reset` changes the password and signs browsers out).

**Decisions.**
- Cookie `ace_session` (HttpOnly, SameSite=Lax, Secure on HTTPS or
  behind a local proxy saying https) plus `ace_csrf` (readable) and the
  header `X-CSRF-Token` on every unsafe method, checked against a hash
  stored per session. Login, reset and pairing require
  `application/json`, which a cross-site form cannot send.
- Throttling is stored, not in memory: 5 failures per address or 20
  per IP in 15 minutes; 10 pairing guesses per IP. A forwarded address
  is believed only from a local proxy, and only its last hop.
- The extension token (`ace_ext_...`) may only GET `/api/answers`,
  `/api/history/{work,education}` and `/api/auth/status`. Pairing is a
  one-time 8 character code (no look-alike letters), 10 minutes, made in
  Settings by a password session, never by a token.
- `ACE_AUTH=disabled` answers only loopback and RFC 1918 or ULA peers,
  with every `X-Forwarded-For` hop also local. Python's `is_private`
  was not used: it also counts documentation ranges such as
  203.0.113.0/24, which a test caught.
- No `owner_id` columns yet. Single owner, enforced at the auth layer
  (a non-owner role is refused with 403). Multi-user needs re-keying
  `job_marks` and `external_applications` anyway (see above), so it
  belongs in the Phase 6 design, not here.
- Password sign-in uses a one-time email code whenever `RESEND_API_KEY`
  is set. Oracle also sets `REQUIRE_LOGIN_EMAIL_CODE=true`, so cloud
  password sign-in fails closed if delivery is unavailable. The code is
  eight characters, stored only as a hash, single use, valid for 10
  minutes and protected by database-backed send and guessing limits.
- Reset by email only when `RESEND_API_KEY` is set; otherwise no reset
  code is created. Reset codes have the same hashing, expiration and
  single-use rules. A successful reset revokes all browser sessions.
- Google OIDC validates Google's verified email and therefore does not
  add a second ACE email-code step.

**Lessons.**
- The Playwright `request` fixture does not share the browser context's
  cookies; it needs its own sign-in or every API check reads 401.
- A popup opened as a tab has `sender.tab` set, so "no tab" was the wrong
  test for "message from our own page". The extension now compares
  `sender.url` with `chrome.runtime.getURL("")`.
- SQLAlchemy bulk `delete` with the default `synchronize_session`
  evaluates the WHERE in Python over loaded rows; on SQLite's naive
  timestamps against an aware cutoff that raises. Pass
  `synchronize_session=False` for housekeeping deletes.
- "--reset" in UI text reads as a dash in Geist. UI copy names the
  command without flags.

## Approved authentication presentation (2026-10-15)

The secure owner session, CSRF checks, throttling, reset flow and extension pairing above remain unchanged. The public
home, sign-in and signed-out routes now use the approved Wine and Rose V2 presentation in Night and Day themes. Email
opens the real owner sign-in dialog. Google and Microsoft show honest unavailable dialogs because the backend has no
OIDC providers. Signing out revokes the server session before rendering the signed-out success screen.

## Approved authentication surface (2026-10-15)

The owner approved a separate cinematic Day and Night surface for authentication.
It changes presentation and routing around the existing owner-only security model;
it does not create another identity system.

- `/login` renders live text, buttons and accessible forms over decorative auth
  artwork. The Email control opens the existing password form and preserves safe
  deep-link return behavior.
- Google and Microsoft controls are part of the approved composition, but no OIDC
  implementation or provider configuration exists. They state that fact and offer
  Email. They never simulate a successful login or create an owner.
- `Create account` opens the existing first-owner bootstrap only when no owner
  exists and setup is allowed. Once an owner exists, it explains that this is a
  private one-owner workspace.
- `/logout` performs the authenticated POST first. Only after the API confirms
  revocation does the browser reach `/signed-out`. The signed-out route is public
  and is a success state, not a pre-logout confirmation.
- `/` is now a small public informational route so the signed-out secondary action
  has a real public destination. `/terms` and `/privacy` are public as well.
- The extension pairing token, its narrow read-only scope and immediate revocation
  behavior are unchanged and covered by the browser and extension tests.

The visual reference kit remains local under ignored `design/`; no private data or
reference screenshots are committed. Production auth artwork lives in
`web/public/auth/` and contains decoration only, with no baked-in copy or controls.

**Verified for this surface.** The 51 backend authentication tests, all 80
Next.js Playwright tests, the 185-case extension rules test, lint, TypeScript
and the production build pass. The browser suite covers anonymous API refusal,
CSRF, safe return paths, session logout, provider unavailable states and
extension pairing plus revocation.
