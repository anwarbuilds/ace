# Alerts, email and sign-in history

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you touch alert emails, freshness or Resend, or you start the sign-in work (read the authentication entry first).

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

> **Status:** History. Sign-in returns in Phase 2 of the platform rebuild (HANDOFF.md section 9). Read this first: it records what went wrong, chiefly that the extension was locked out.

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
