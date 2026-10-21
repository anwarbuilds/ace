# Coverage, discovery and company readers

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: a company or role was missed, you add a company or reader, or you judge whether a site may be read at all.

## Apple is deliberately not adapted

> **Status:** Superseded 2026-10-09: Apple is now read by the `apple` adapter from its server-rendered search pages, within robots.txt. The reasoning about bot protection on its JSON API still stands, and that API is still not used.

Its API answers automated requests with bot-protection responses (436,
then a redirect). Working around an access control was rejected as an
approach. Apple is covered through the curated feed instead.

## FAANG coverage, investigated (2026-09-06)

> **Status:** Partly superseded 2026-10-09: Google and Meta are now read within their robots.txt, Apple too, and Microsoft through Eightfold (see the recent-sources entries in this file). Tesla and LinkedIn stay unreachable.

One of the four is adaptable. Each verdict was measured, not assumed.

| Employer | Verdict |
| --- | --- |
| **Netflix** | **Adapted.** Eightfold ATS with an open JSON route. 504 postings, full descriptions on a per-posting detail call. |
| Google | Not adaptable. `careers.google.com/api/v3` returns 404; the jobs page is 1.25 MB of client-rendered HTML with no JSON-LD on search or detail pages. Same category as Apple and TikTok. |
| Meta | Not adaptable without defeating protections. The GraphQL route needs a POST with session tokens; the page is client-rendered and its `ld+json` carries no JobPosting. Not bypassed, per the Apple precedent. |
| Microsoft | Blocked by Microsoft's own TLS misconfiguration. `gcsservices.careers.microsoft.com` presents a certificate valid only for `*.azureedge.net`, so the hostname does not match. Disabling verification would expose every ACE request to interception, so it is refused. May fix itself on their side; worth re-checking. |

The adapter is written against **Eightfold**, not Netflix, because
Eightfold is multi-tenant. Other tenants were probed: Chegg and Micron
return 403, so Netflix is the only open one today, but adding another is
a catalog row rather than a module.

Eightfold cannot use conditional HTTP: the search response embeds
per-request session fields, so the body differs even when the postings
do not. It is a predicated-detail source like Workday, since descriptions
live behind a second call. On Netflix that is 79 detail requests instead
of 501.

**Numeric career levels are now a seniority signal** (rule v16). Netflix
writes seniority only in the title ("Software Engineer 4", "Engineer
(L5)"), and 66 of its 67 initially-qualifying postings never state years
of experience at all, so the experience rules could not see them. Level
4 and above is senior; 1 to 3 stay early career. Both forms are
anchored deliberately: a bare `L[4-9]` would also match "L4 autonomous
driving" and "L7 load balancer", where the number is a domain term, and
a bare trailing digit would read "Engineer, 8 to 12 months" as level 8.
Measured against the corpus before shipping: 85 of 31,323 active titles
matched and none were passing, so no queue entry was lost. Netflix went
from 67 apparent matches to 2 real ones.

**`refresh_stale_evaluations` now exists and is called.**
`iter_stale_job_ids` described staleness precisely and had no caller, so
a rule change only landed as each source happened to be re-polled, and
jobs from a quiet source kept decisions made under retired rules.

---

## Coverage, not correctness, was the first complaint (2026-09-07)

The user opened a Netflix form and got nothing. Netflix runs on
Eightfold, which was not in the manifest, so the content script never
loaded. The matcher handles it fine once there: 9 of 14, every miss
correct.

Hosts now include Eightfold, SmartRecruiters, Workday, Amazon and
Rippling alongside the three verified ones. The popup also says which
of the two problems it is, because "nothing to autofill" on an
uncovered site looks exactly like a broken extension.

Headless Chrome does not run extension content scripts even with
`--load-extension`, so end-to-end checks inject the same files with a
stubbed `chrome.runtime.sendMessage` instead. That covers everything
except Chrome's own injection.

## Coverage is 20%, and the 64% was selection bias (2026-09-07)

Asked how ACE could miss a job found on LinkedIn, the answer was that
Current's board was never registered. Asked what coverage could reach,
95% was quoted. Both the 64% baseline and the 95% target were wrong,
and the user was right to demand proof.

**The 64% was measured against companies already applied to**, and
they applied to those companies largely because ACE had shown them.
Testing a system on its own output.

**The honest measure is recall against a source ACE has never seen.**
Three new-grad lists maintained by other people, never used for
seeding: `speedyapply/2026-SWE-College-Jobs`, `vanshb03/New-Grad-2026`,
`jobright-ai/2025-SWE-New-Grad`. ACE reaches 29%, 17% and 20% of their
companies. **Overall recall: 20%.**

**Nor is 95% reachable.** Sampling 45 of the 493 missed companies, a
name-guess prober found boards for 42%. Compounded that is roughly
55%, not 95%. The companies that stayed missing say why: Comcast,
ASML, GE Aerospace, TIAA, Morningstar, Boston Dynamics. Large
non-tech-native employers on iCIMS, Taleo or SuccessFactors, each
needing its own adapter.

**One hit in that sample was wrong**: "applied materials" matched an
Ashby board named "applied", almost certainly Applied Intuition. The
`current` versus `current81` trap in reverse. Any discovery step needs
a verification pass confirming the board belongs to the company before
registering it, or ACE silently subscribes to the wrong employer.

The benchmark now lives at
`python -m backend.scripts.coverage_benchmark`. Adding any held-out
list to the seed feeds destroys the measurement, because ACE would
then be tested on its own inputs.

Read it as directional. The lists are themselves incomplete and skew
toward companies that hire graduates publicly. What it is good for is
movement: run it, change discovery, run it again.

## Discovery moved recall from 20% to 33% (2026-09-07)

With the benchmark in place the claim became testable, so the fix could
be measured rather than argued about. 129 boards to 241, recall 20% to
33%, one command apart.

**Verification is the whole design.** A guess that hits the wrong
company is worse than a miss: it fills the queue with another
employer's jobs under a name the user recognises. Three checks, in
descending strength.

1. **The board's own metadata.** Greenhouse publishes
   `/v1/boards/<token>` with the employer's name. Written by the
   employer, so it is real evidence.
2. **The board page title.** Ashby and Lever publish no metadata but
   both title the page "Ramp Jobs", "Wealthfront". This recovered
   roughly a third of the boards strict verification had been dropping.
3. **The employer's own words in a posting.** Last resort, weakest,
   finds fewer boards rather than wrong ones.

**A URL built from the guess is not evidence.** The first version
checked a Greenhouse job's `absolute_url`, which is
`boards.greenhouse.io/<token>/...`. Since the token came from the
company name, the check proved only that the guess was consistent with
itself, and it "verified" Current against the wrong board.

**Some cases are genuinely unresolvable.** Greenhouse boards `current`
and `current81` both declare themselves "Current" and belong to
different companies. No automated check separates them, which is why
`discover_boards` writes nothing without `--apply`.

**The tail polls daily.** 113 new boards at 86400 seconds. Every board
on the five-minute cycle is neither possible nor polite once there are
hundreds.

Verified rate is 23%, against 42% for unverified guessing. The
difference is boards ACE declined to claim. That is the intended
trade.

## Two faults found while checking discovery worked (2026-09-07)

**A registered board is invisible until the scheduler restarts.** The
catalog is read once at startup, so 112 boards sat unpolled with no
error anywhere: the scheduler was busy and healthy, just working from
the list it had loaded before they existed. `docker compose restart
scheduler` after `discover_boards --apply`, and 25 of them polled
within a minute. Worth making the catalog reload on its own; until
then it is a manual step.

**The benchmark counted a board ACE already polls as a miss.** ACE
registered Anduril as "Anduril"; a held-out list writes "Anduril
Industries". `normalise_company` stripped "technologies" and "labs"
but not "industries", so the two never met. `company_keys` now returns
the name with generic trailing words removed as well as in full, and
only trailing words, so "Apple" still never matches "Apple Bank".

The correction moved recall 33% to 34%, which says the original 20%
baseline was close to right rather than an artifact.

## An aggregator source, deliberately narrow (2026-09-09) - REMOVED 2026-09-10

> Superseded. Adzuna was removed the next day; see "The aggregator only ever linked to itself" below. Kept because the reasoning about wide-versus-deep coverage still stands and the next aggregator proposal should have to answer it.

The user asked whether ACE could reach deeper, the way a product like
JobRight does. JobRight itself is not a source: its jobs page is a
client-rendered SPA with no structured data and its real listings sit
behind a login, the same category as Apple, Google and Meta. What is
real and reachable is Adzuna, a job-search aggregator with a public
API, added as `SourceType.ADZUNA` with the user's own free-tier
credentials in `.env`.

**This is the wide, shallow net the coverage plan called for**, not a
replacement for polling boards directly. Two things keep it that way.

**Query terms stay narrow.** "software engineer" alone returned close
to six thousand results in a three-day window on this key, almost all
of it mid-career noise the gate would page through and reject one
expensive request at a time. Six specific phrasings ("new grad
software engineer", "associate software engineer", and similar) keep
the raw volume in the low hundreds, which a live poll confirmed: 156
results, 11 passed the gate. Every one of the 11 was a company ACE had
never had a source for -- Boeing, Morgan Stanley, T-Mobile, Accenture,
Cadence Systems, Lennar Homes.

**A result whose company ACE already watches directly is dropped.**
Adzuna's listing has a worse link than the native one: a 500-character
truncated description with no per-posting detail call to complete it
(unlike Greenhouse or Eightfold), and an application link that goes
through Adzuna's own apply page rather than straight to the employer.
Verified live: the same key returned a Scale AI posting, and it was
correctly dropped, since ACE already has Scale AI's own Greenhouse
board. The exclusion check needs a database read, which is why it
lives in the dispatcher wrapper rather than the adapter itself --
every other adapter in this codebase is a pure HTTP client with no
database access, and this one only breaks that pattern for the one
piece of logic that genuinely needs it. Company names are matched with
the same `company_keys()` normalisation the coverage benchmark uses,
so "Anduril" and "Anduril Industries" are recognised as the same
company here too.

The truncated description is a real, permanent limitation of the free
tier, not a bug to chase: a posting whose requirements sit past 500
characters lands in the gate's "no figure stated" bucket, the same
conservative treatment already given to any posting ACE could not read
at all. Title-based signals are unaffected, since titles are never
truncated.

Recall moved 33% to 35% on the first poll. Queue 806 to 817.

## Making the gap visible, and cheap to close (2026-09-10)

The user asked how to stop the Cursor kind of miss recurring, and the
honest answer had two halves that needed different things built.

**A Coverage page, because the gap was invisible.** ACE could not say
what it was blind to, so a missing company was only ever discovered by
clicking a job ACE never had. `/api/coverage` compares the curated list
against every board ACE polls and every company it holds an active
posting from, and the page shows the number and names every company it
cannot reach. 255 of 411 at the time of writing, 156 named on the page.

**An add box on the same page, because a number you cannot act on is
half a feature.** Paste a job link, a careers page, or a bare company
name; ACE works out which board it is, verifies it, registers it, and
the count updates. Three input shapes all resolve to the same board:

    https://cursor.com/careers/software-engineer-new-grad-2027
    https://jobs.ashbyhq.com/cursor/d0e5b41d-...
    Cursor

**The enabling change was in the scheduler, and it was the part that
would have made the feature useless.** The registry was a snapshot
taken at startup, so a company added from the page would have sat
unpolled until someone restarted the container -- looking, from the
outside, exactly like a bug. `SchedulerRuntime` now takes an optional
reloader and re-reads the source list between cycles. A source it
already knows keeps its next-due time, so a reload never causes a burst
of re-polling, and a failing reload is logged and ignored rather than
taking the scheduler down. Verified live: added Contentful from the
page and the log said `scheduler_sources_reloaded added=1 removed=0
total=448` without anyone touching the container.

Failure is reported honestly rather than hidden. Glean, Addepar and
Archer Aviation all come back with "no board ACE can read was found
there -- it may be self-hosted, on Workday, or behind a page that
builds itself in the browser", which is true and tells the user what
kind of problem it is.

Worth recording one false alarm from the audit that followed. `ashby/
astera` looked like the Aurora mistake repeating -- the curated list
says "Astera Labs", the semiconductor company, and that board belongs
to Astera Institute, a research nonprofit. It is not a mistake: the
board was found by `board_probe` and is correctly registered as "astera
institute". Astera Labs is genuinely still unreached, and says so on
the Coverage page. A systematic check of all 189 curated and hand-added
registrations against each board's own declared name found **zero**
mismatches, so Aurora remains the only one.

## Reading the board address off the company's own page (2026-09-10)

The user asked how to stop the Cursor kind of miss recurring. Part of
the answer was already written and never called: `careers_page_token`
reads the board token a company embeds in its own careers page, which
is exactly how Cursor was found by hand. It had tests and no callers.

Wired in as a fallback behind name-guessing, it registered **22 more
boards**, and the value is visible in the tokens themselves -- none of
these is derivable from the company name:

    Sourcegraph  -> greenhouse/sourcegraph91
    Grafana Labs -> greenhouse/grafanalabs
    Recursion    -> greenhouse/recursionpharmaceuticals
    XTX Markets  -> greenhouse/xtxmarketstechnologies
    Captions     -> ashby/mirage
    Headspace    -> greenhouse/hs
    GRAIL        -> lever/grailbio

**Reading is not trusting, and that had to be built in.** Mistral's
careers page links `jobs.ashbyhq.com/mistral`, which returns 404 with a
real User-Agent. A route that registered what it read would have
subscribed ACE to a dead board under a name the user recognises. So
anything found this way goes through the same `board_belongs_to`
verification as a guessed token, and Mistral is correctly rejected.
Two tests pin both directions.

## A wrong board did get registered, and the audit is why it was caught (2026-09-10)

Worth recording against the earlier claim that verification makes a
name list safe. It mostly does. It did not here.

"Aurora" was on the curated list meaning Aurora Innovation, the
self-driving company. Probing found `lever/aurora-dev`, a board
declaring itself "Aurora Labs" -- a Web3 company. Verification passed
because "Aurora" is contained in "Aurora Labs". Two generic postings
would have entered the queue under a name the user trusts.

Caught by auditing every registration whose company name was a single
short word, not by the verification. Removed, and thirteen ambiguous
names in the list were rewritten to say what they mean: Aurora
Innovation, Bolt Financial, Circle Internet Financial, Gemini Trust,
Column Bank, Unit Finance, Lambda Labs, Magic.dev, Mem Labs, Sana Labs,
Clay Labs, Arc Technologies, Omni Analytics.

The lesson is narrow and worth keeping: **verification is a floor, not
a substitute for naming the company precisely.** A short generic name
will pass a containment check against a different employer, and the
failure is invisible afterwards because the queue simply shows a
company the user recognises.

## The 154 unreachable companies were mostly ACE's own doing (2026-09-10)

Coverage reported **154 of 411** curated companies as out of reach, with
the standing explanation that they self-host, sit on Workday, or build
their careers page in the browser. Auditing them one at a time found
that explanation was mostly wrong. **ACE is now at 283 of 411**, with
24 new boards registered and 2,280 postings flowing that were not
before.

**Discovery only probed three of the nine ATSs ACE can already read.**
The adapters for Workday, SmartRecruiters and Eightfold have existed
for months. `board_endpoints` listed Greenhouse, Ashby and Lever. So
Canva (263 postings), Freshworks (144), Wise (427), Cadence (591),
Zendesk (89) and Boston Dynamics (79) were all invisible to a system
that could have read every one of them. SmartRecruiters is now guessed
like the others -- and verifies better than any of them, because every
posting carries `company.name` written by the employer. Workday cannot
be guessed at all (the data-centre number is not derivable: Zendesk is
wd1, BigCommerce wd12, NVIDIA wd5) so it is only ever read off a
careers page.

**Three smaller bugs, each costing real companies.**
- Calm's board declares itself "Calm.com". The check compared for
  exact equality against "Calm", so it was refused -- and refused
  *early*, because a board naming somebody else must not be rescued by
  weaker evidence. The refusal rule was right; the comparison was
  wrong.
- Zendesk's careers page is larger than the 200KB `_fetch_text` read.
  The Workday link sat past the cut. The company looked unreachable
  and the reason was a buffer size.
- Guessing `<name>.com` and reading whatever answered put "Adept" on
  Omron's robotics division and "Beta Technologies" on an unrelated
  software firm. Those pages were then searched for a board to
  subscribe the user to. Nothing bad reached the database because the
  board is verified afterwards -- but the failure that check cannot
  catch is the wrong page linking a board that passes anyway, which is
  exactly how ACE came to poll Aurora Labs.

**The audit is the part worth keeping.** The sweep proposed 26 boards
and four of them were wrong, all four having passed every automated
check:
- `ashby/astera` is the **Astera Institute**, a research foundation,
  not Astera Labs the semiconductor company. `normalise_company` drops
  "Labs", so "Astera Labs" reduced to "astera" and the foundation's
  "ABOUT ASTERA" matched. The Aurora failure again, one tier down.
  Posting prose is now held to the whole name, suffixes included.
- `smartrecruiters/glean` is **Glean AI**, an expense-management
  fintech, not Glean the enterprise search company. Two real companies,
  the same name, and **no rule separates them.** Recorded in
  `NAMESAKE_BOARDS` instead, which is what a human confirmation is
  for.
- `smartrecruiters/uber` holds one posting, "Test UAT".
  `smartrecruiters/bigcommerce` holds "Rene's Test Job" and "Test Job
  2". Both declare the right employer. Subscribing would have made the
  coverage page report a company as reached while ACE saw nothing
  real -- the number lying, which is the one thing that page exists to
  stop.

Fixing the first and third did not just reject those boards: the search
continued and found the **right** ones. Astera Labs resolved to
`greenhouse/asteralabs` (164 postings, "NASDAQ: ALAB"), BigCommerce to
their real Workday tenant (36). A guard that only rejects is worth less
than one that keeps looking.

**worldlabs.com is a parked domain for sale**, titled "WORLDLABS.COM |
Strategic-Grade domain names...". That title contains the company name,
so it read as a positive identification -- and because finding a
company's site ends the search, it cost the real World Labs at
worldlabs.ai, whose careers page links an Ashby board in plain HTML.

**The gap is now a queue, not a wall.** `source_probes` (migration
0027) keeps why each company is unreachable, and the Coverage page
groups by it. Of the 128 that remain: **94** publish no board ACE
recognises (genuinely JS-rendered -- Zoom, Shopify, Wiz, Retool, dbt
Labs all fetch their jobs at runtime, and nothing is in the HTML or the
first-level JS), **18** have no website answering for the name, **10**
hire through an ATS ACE has no adapter for (iCIMS x3, Phenom,
SuccessFactors, Rippling, BambooHR, Teamtailor), **5** have a readable
board with nothing posted today, and **1** was refused for naming a
different company. Those are five different pieces of work, and three
of them are now countable rather than open-ended.

`python -m backend.scripts.probe_coverage --apply` re-runs the whole
thing in about four minutes.

## 411 names, and ACE stopped renting its recall (2026-09-10)

The user's framing settled the design: **ACE should be the reliable
platform, and the community trackers are a hint, not a dependency.**

The curated list went from 82 names to **411**, covering the tiers this
user actually targets: AI labs and tooling, developer infrastructure,
data platforms, observability, security, product companies, fintech,
quant and prop trading, health and bio software, aerospace, defence,
autonomy, robotics and semiconductors.

One probing run against that list registered **150 new boards**, taking
sources from 275 to **425**. Postings went 43,098 to 56,951 and the
queue 883 to **967**. Of the 411 curated names ACE now reaches **249
(60%)**, against 30 before any of this started.

The registrations are trustworthy because every one carries its own
evidence: 77 "board declares itself", 73 "board page titled", 4
"company named in posting". Not one was accepted on a guessed slug
alone. That matters more as the list grows -- at 411 names nobody is
going to eyeball each result, so the verification has to be the thing
that holds.

The scheduler took the jump without complaint: 425 of 425 polled, none
failed. Curated boards poll every fifteen minutes rather than the daily
tail, which is affordable because Ashby and Greenhouse answer 304 on an
unchanged board.

**What is still missing, and why it is a different problem.** 162 of
the 411 do not resolve, and the reason is not that ACE cannot read
their boards -- it is that their board token cannot be derived from
their name. Weights & Biases is `wandb`. Others self-host, sit on
Workday under an opaque tenant, or use a slug nobody would guess.

`careers_page_token` in probing.py already solves exactly this: it
reads the token a company's own careers page embeds, which is how
Cursor was found by hand in the first place. **It is fully written,
tested, and called from nowhere in production.** Wiring it in as a
fallback, given a careers URL per stubborn company, is the obvious next
increment and would take a good share of those 162.

## The bottleneck was names, not machinery (2026-09-10)

Following the Cursor miss, the question was what to do about coverage
generally. The answer turned on one measurement, and it is worth
recording because it inverted the obvious assumption.

`find_board("Cursor")` resolves the board in one call, with 128 jobs
behind it and verification that the board really is Cursor's. The
prober was never the problem. Neither were the adapters. **ACE simply
did not have the name.**

Measured properly: of 82 well-known employers in this user's tier, ACE
reached 30. Of the 52 it did not, **32 were reachable by name probing
alone** -- Coinbase, Reddit, Ramp, Cohere, Robinhood, Perplexity, Brex,
Block, Zoox, Lucid and more, around 3,400 postings sitting behind
boards ACE already knew how to read.

So the fix was not new machinery. `backend/app/coverage/companies.py`
holds the list ACE owns, `discover_boards` probes it before the
trackers' names, and a curated hit is registered as `curated_list` on a
fifteen-minute interval rather than the daily tail -- a company the user
chose is not the tail. Registering the 32 took one run: 3,263 postings
stored, 50 of them through the gate, queue 833 to 883.

Two things worth keeping.

**Verification is what makes a name list safe.** Each registration
carries its own evidence -- "board declares itself 'Gusto, Inc.'",
"board page titled 'Supabase'", "company named in posting
descriptionPlain". Without that, a guessed slug would subscribe ACE to
another employer's jobs under a name the user recognises, which is far
harder to notice than a gap. 28 of 60 names resolved to nothing and
were left alone, which is the correct outcome rather than a failure.

**Some names cannot be guessed.** "Weights & Biases" does not resolve
because their slug is `wandb`, and no token guess derived from the name
reaches it. Those stay on the list and are retried, since the
careers-page route finds tokens the name route cannot, and a company
that self-hosts today may move onto a supported board tomorrow.

The remaining honest limit: the curated list is still a list, and a
company nobody puts on it stays invisible. What changed is who owns it.

## A company ACE had simply never heard of (2026-09-10)

The user sent a Cursor posting and asked why ACE had not found it. The
answer was not a gate rule, a parser or a bug: **Cursor was not one of
the 242 registered sources**, so ACE had never looked.

It runs on Ashby, an adapter ACE has supported from the start, under
the account `cursor`. Registering it took one row and immediately
brought in 128 postings, 23 of which pass the gate, including the one
the user sent.

Two things worth keeping.

**The registry is a snapshot taken at startup.** `run_scheduler` calls
`load_source_registry(session)` once before `run_forever`, so a source
inserted into `job_sources` afterwards is invisible until the scheduler
restarts. Adding a source is therefore two steps, and the second is
easy to forget: the row was there, the board was reachable, and nothing
polled it for several minutes while it looked like a bug.

**Discovery is entirely downstream of three community lists.** The
coverage benchmark and `discover_boards` both read
`HELD_OUT_LISTS` -- speedyapply/2026-SWE-College-Jobs,
vanshb03/New-Grad-2026 and jobright-ai/2025-SWE-New-Grad. Checked
directly: none of the three mentions Cursor or Anysphere even once.
So ACE could not have found it by any automated path. Board-probing
finds boards for companies it already has names for; it does not
discover names.

That is the shape of the remaining coverage gap, and it is worth being
precise about it: ACE's recall is bounded by whoever maintains those
three README files. A company they do not list, ACE cannot see. The
fix is not a better probe, it is a wider set of name sources -- and
until then, a posting the user finds by hand is a legitimate way for a
company to enter the system, which is what `discovery_source='manual'`
now records.

## The aggregator only ever linked to itself (2026-09-10)

The user reported that Adzuna's jobs were all contracts and that it
never gave the real job link, and said to remove the source if that was
true. Both claims checked out, and the second is the one that decided
it.

**Every one of the 242 stored Adzuna rows pointed at
`adzuna.com/details/...` or `adzuna.com/land/ad/...`, and not one at
the employer.** That is not a defect in the adapter; it is all the
Adzuna API returns. `redirect_url` is their click-tracking link, and
there is no field carrying the employer's own posting. So the source
could not be fixed, only kept or dropped.

Keeping it would have contradicted the thing ACE is for. A posting
whose link goes to an aggregator's landing page has to be searched for
again by hand, which is the work ACE exists to remove. Worse, the
stored URL carried the API key as a `utm_source` parameter on all 242
rows, so it would have travelled into the exported spreadsheet the
moment one was applied to.

The contract claim was true but smaller: 15 explicitly contract, 211
not stating a type at all. What settled it was the yield -- of 179
active rows only 10 passed the gate, and most of those were staffing
and consulting firms whose
postings are not the employer's either. The two genuinely good ones
were large employers ACE already reaches through their own
boards.

Removed completely: adapter, dispatcher fetcher, `SourceType.ADZUNA`,
the config fields, the credentials out of `.env`, and the 242 rows.
Two details worth keeping:

**The order mattered.** The registered `job_sources` row had to be
deleted *before* the scheduler restarted. A source row whose
`SourceType` no longer exists in the code is exactly what crashed the
scheduler for an hour once already, and `restart: unless-stopped` turns
that into a crash loop that reads as "restarting".

**Two rows had applications recorded against them**, from a list ACE
had produced. Deleting the jobs would have taken the marks
with them, so both were first copied into `external_applications` --
which is precisely the table for an application with no stored posting
behind it. History intact, misleading rows gone.

`employment_type` and the `CONTRACT_ROLE` rule stay. No source
populates them now, but the field is honest about that (None means the
source did not say) and removing it would rewrite the content hash of
43,000 rows to delete something correct that costs nothing.

## Reaching a company through a feed is what stopped ACE reaching it (2026-09-17)

The user found a Two Sigma campus software engineering post in Houston
and asked why ACE did not have it. The adapter was the second half of
the answer. The first half was that **the company had never been probed
at all**.

Coverage asked which curated companies ACE could already reach, and
`reachable_keys` answered "every company ACE polls **or holds jobs
from**". Five Two Sigma roles had arrived through the curated feed, so
the company counted as reached and was dropped from the probe list. Its
own board was never looked for.

That failure compounds in the wrong direction: the more a feed lists,
the less ACE looks. It is also permanent, because nothing ever revisits
the decision.

The measurement is worse than the single case. **549 companies are
known to ACE only through a multi-employer feed, and not one had ever
appeared in a single probe. 114 of them already produce roles that pass
the gate.** For Two Sigma the ratio was 5 roles seen against 55 on its
own board.

A job from `simplify` or `ripplematch` now proves only that the feed
listed it, which is all it ever proved. A job from the company's own
board still counts, and so does a registered source with no jobs yet,
or the fix would collapse into "never reachable" -- both directions are
pinned. 146 curated companies became due for probing.

**Avature**, the board Two Sigma actually runs, is the first adapter
here keyed on a URL rather than a tenant slug. Avature portals are
served from the employer's own domain, with the tenant visible only in
the sitemap reference in `robots.txt`, so there is no slug to key on.
No apply-link exception is needed, unlike RippleMatch: it is the
company's own board whatever domain it answers on. `OpenRoles` pages
ten at a time and repeats its last page rather than returning an empty
one, so the walk stops on "no new identifier" -- stopping only on an
empty page would never stop.

The general lesson, and the reason this is written down rather than
just fixed: **an aggregator is a floor, never a ceiling.** Anything
that treats "we have something from X" as "we have X" will quietly cap
coverage at whatever the aggregator chose to publish, and the symptom
is a missing job rather than an error.

## A board that stops answering is a company ACE stopped reading (2026-10-04)

Found while checking the restart: Postman's Greenhouse board had been
404 for seventeen days, Stytch's empty for fifteen, and Amplitude, Wayve
and Iterable had moved to Ashby (Puzzle renamed its Ashby board). The
scheduler logged a failure each poll and carried on. Their old postings
stayed active, so Coverage counted all of them as reached.

Every six hours, on a background thread, the scheduler now re-diagnoses
sources with no success for a day (or three of their intervals). Moved:
register the new board, retire the old, close its leftover postings.
Not found: leave it polling and list it under "Stopped answering" on
Coverage. The first run moved Amplitude, Iterable and Wayve -- 47 stale
postings closed, and Wayve's new board had 63 roles, five passing -- and
listed Postman, Stytch and Puzzle.

The lesson: **a log line is not monitoring.** A failure that repeats
every poll for weeks is a coverage gap, and it has to surface somewhere
a person looks.

## The source audit: what came from where, and what ACE could not see (2026-10-05)

The user asked for a strict audit and for ACE to rely on companies' own
sources rather than on aggregators. Measured on the live database:

- **31% of passing roles came only from feeds.** 372 of 1,191; 297 of
  them at 114 companies ACE did not read directly. 364 of the 372 had
  passed *unread*: the feed has no description, so clearance,
  citizenship, sponsorship and experience rules never ran.
- **Read at the employer, most of them should not have passed.** For the
  85 feed postings whose employer page publishes a schema.org
  JobPosting, 50 were rejections: 43 security clearance, 18 citizenship,
  8 experience. This was the clearance noise the user kept reporting.
- **Readers capped what they read, and closed the rest.** Amazon read the
  newest 2,500 US postings within 45 days -- its new-grad postings stay
  open for months ("Software Development Engineer - 2026 (US)" was
  posted in February), so they were never seen, and everything past the
  cap was marked closed while open. Workday's search returns at most
  2,000 and reports 2,000 as the total: NVIDIA has 2,679.
- **59 boards that had produced passing roles were polled once a day**,
  among them Amazon, Clera (73), Nuro, Neuralink, Twitch, Discord,
  Plaid.
- **The biggest direct gap was ByteDance/TikTok** -- 139 passing roles
  through Simplify only; ACE's "ByteDance" source was a two-posting
  SmartRecruiters board. Then fifteen employers on Oracle Recruiting
  Cloud (American Express, JPMorgan, Oracle, BNY, Dell, Honeywell,
  Fortinet, Cummins, ...).
- **Three sources were staffing agencies**, not employers: Jobsbridge
  (45 passing reposts, "5 (+) years", "GC/Citizen only"), People Culture
  Talent, 9to9 Software Solutions.

What changed:

- **Feed postings are judged on the employer's page**
  (`verification/employer_page.py`). Before the gate runs, a Simplify
  posting's own page is read -- robots.txt honoured, only titles that
  could pass, 150 new pages per poll, each page at most weekly -- and
  its JobPosting description is what the gate reads, the feed's own
  sentences after it. Readings live in `employer_page_readings`
  (migration 0033) so the next feed poll cannot restore the placeholder.
  An unreadable page leaves the posting as it was: silence is not
  rejection. Pages that render in the browser (Oracle, Workable, JazzHR,
  BambooHR, Rippling) publish no JobPosting and are not read yet.
- **ByteDance and TikTok read directly** (`adapters/bytedance.py`): both
  sites are fronts for one public "supplier" API. 4,291 + 1,417
  postings, about thirty requests a poll; 175 + 75 pass, against 106 +
  33 through the feed. "Third-party associate" postings are staffing
  placements and are written as contract roles.
- **Oracle Recruiting Cloud read directly**
  (`adapters/oracle_recruiting.py`), account `{host}/{siteNumber}`.
  Descriptions come from a per-posting detail call, fetched only for
  titles that could pass and cached in the same reading store. American
  Express alone: 425 postings, 14 passing -- its 2027 campus Software
  and AI Engineer roles.
- **Amazon reads three categories whole** -- software development,
  machine learning science, systems/QA/security -- with no horizon:
  2,568 postings, 15 s. A category that does not finish raises rather
  than return part of itself.
- **Workday tenants past 2,000 are read in slices** of a facet that
  partitions them (job family first); NVIDIA 2,679, Abbott 2,590. One
  that cannot be split (Accenture 42,255; Target 13,967) is read in part
  and marked so: `FetchedSourceSnapshot.complete=False` reaches
  `process_snapshot(close_missing=False)`, and nothing is closed for
  being absent from part of a board.
- **Productive boards are polled at their registration cadence**
  (`coverage/cadence.py`, in the six-hourly maintenance): a board that
  has ever produced a passing role is never polled daily. Promotion
  only. A shorter interval takes effect from the last poll, not after
  the slot already booked.
- **Gate (v37)**: "5 (+) years" is a minimum; "GC/Citizen", "USC/GC" are
  citizenship requirements -- unless work permits follow ("Only
  GC/Citizen, OPT, EAD, H4" admits OPT).
- **Data, not code**: Jobsbridge, People Culture Talent and 9to9
  disabled and their postings closed; TikTok, ByteDance and the fifteen
  Oracle tenants registered by hand (`discovery_source="source_audit"`).

- **Feed copies hidden by link too** (0034): 183 feed rows pointed at a
  posting a direct row already held, under a reworded title.
- **Hashing an instant, not text**: Greenhouse's "-04:00" times made
  27,950 evaluations look permanently stale to every re-evaluation.

After, on the live database: 1,431 passing roles, 1,108 from the
employers' own boards (was 819 of 1,191); feed-only roles at companies
with no direct source 109 (was 297); productive boards polled daily 0
(was 59). The queue itself: 1,230 roles, 1,108 direct. Still open: 264
feed rows not yet checked at the employer (150 a feed update), pages
that publish no JobPosting (Workable, JazzHR, BambooHR, Rippling),
Accenture and Target read in part, and the laptop's nightly dark hours.

The lesson: **a feed is evidence that a role exists, never of what it
requires.** Anything judged on a feed's word alone will pass exactly the
roles the user is trying to filter out.

## Chewy: the board was in ACE's own records, and nothing read it (2026-10-06)

The user found Chewy's "Software Engineer I" (R30985, Bellevue), posted
the day before, that ACE had never seen. Causes, all fixed:

1. **Feed links were never turned into sources automatically.** Two Chewy
   postings had passed through Simplify, both linking to its Workday
   board, but registering boards from feed links was a command nobody
   had run since early September. The scheduler's maintenance (now every
   30 minutes) collects every board named in today's listings and in
   every feed posting ever stored, reads each once, and registers the
   unknown ones -- all boards whose postings could pass, every run;
   forty others a run. Backlog found: **1,197 boards** (556 Workday, 203
   Ashby, 198 Greenhouse, 89 SmartRecruiters, 77 Oracle, 74 Lever).
   Each is saved as soon as it is read, so a restart loses nothing.
2. **Workday's second address form was unknown**:
   `wd5.myworkdaysite.com/recruiting/{tenant}/{site}`. Now recognised in
   links, careers pages and diagnosis.
3. **The probe stopped at Chewy's careers front end (Phenom)** and never
   followed the page's own job-search link, where every apply button
   names the Workday board. Diagnosis had its own copy of the careers
   walk; both now share `page_board_ref`.
4. **The feed dropped postings on "readable" boards** whether or not ACE
   read them. Now only when the board is registered and enabled.

Staffing agencies arrive with feed links: the first run registered nine
(Atria, Infojini, DellFor, Saxon Global, SA Technologies, Testing Xperts,
Miracle Software Systems, Proximate, Jobs for Humanity), all on
SmartRecruiters. `staffing_reason` rejects agency names, contract
templates ("Duration:", "Rate:", "Client: Direct Client") in a fifth of
described postings, and agency-style names on SmartRecruiters; a
rejected board is recorded switched off with the reason. Size alone was
tried and turned away Bosch and Western Digital -- it counts only when
nothing is described. Feed copies from switched-off agencies are hidden.

New Workday and Oracle boards start hourly (556 Workday boards at 15
minutes would hit the edge NVIDIA and Salesforce share); a passing role
promotes a board to 15 minutes (Eightfold to an hour).

Also this day: Workable boards read directly (65 employers; Avalore's
"SECRET clearance" postings had passed unread); level-II titles judged
by the years they ask instead of rejected as senior (250 roles, none
asking 4+ years; v38); "Mgr" read as manager (v39); desktop alerts from
the open portal; and the Coverage page's own daily audit -- "Caught
late" and "Known only through a feed".

**Indeed, LinkedIn, ZipRecruiter, Glassdoor cannot be sources.** Indeed's
robots.txt allows only the first page of a search; `/viewjob`, deeper
pages and `/rss` are disallowed, and its terms forbid automated
collection. LinkedIn and ZipRecruiter disallow everything. They copy
employers' ATS postings anyway, later; reading the ATS is the way to be
first. The legitimate route to them is the user's own job-alert emails,
which needs the user's mailbox consent -- proposed, not built.

---

## Recent sources, readers and sweeps (2026-10-08 to 10-10)

- **IBM is read from its site search, not careers.ibm.com.** The careers
  site is Avature behind an AWS WAF JavaScript challenge (202, empty body,
  `x-amzn-waf-action: challenge`); never try to get round it.
  `www-api.ibm.com/search/api/v2` (appId careers, scope careers2) is what
  ibm.com/careers/search uses: size ≤ 100, `_source` must be exactly the
  page's field list, no custom aggs. Source type `ibm`, account
  `careers.ibm.com` (2026-10-08).

- **Run `discover_boards` on named companies** with its `probe_company`
  and `register` functions (scratch script); dry-run first and skip
  matches whose only evidence is "company named in posting description".

- **Own-site readers added 2026-10-08/09** (all respect robots.txt):
  - Atlassian (`atlassian`): one JSON list with whole descriptions, ETag.
  - EA (`avature`, account `https://jobs.ea.com/en_US/careers/SearchJobs`):
    the Avature reader takes a listing page as the account, steps by the
    portal's own page size (20 here), reads every location from the
    posting page ("MultipleDataSetFields"), and fetches descriptions
    only for titles the gate could pass.
  - Apple (`apple`, account `jobs.apple.com`): server-rendered search
    pages with `__staticRouterHydrationData`; the team filter must keep
    literal `+` separators (an encoded `%2B` silently drops the filter
    to all 4,440 US rows). Detail URLs use the row `id`
    ("200683887-0836"); the bare number 301s. The `/api/v1/...` JSON
    API wants a CSRF token -- not used. First full read ~15 minutes;
    later polls reuse stored descriptions (`_stored_descriptions`).
  - Shopify (`shopify`): `/careers` carries every posting as React
    Router turbo-stream data (`adapters/turbo_stream.py`); posting pages
    resolve by the id after `_`, whatever the slug. robots.txt disallows
    `/careers/search?*` and `/careers/portal/*`.
  - AMD, SIG (`jibe`, account = where job pages live:
    `careers.amd.com/careers-home`, `careers.sig.com`): iCIMS Jibe
    `/api/jobs`, 100 a page, robots crawl-delay 5 s, page-1 ETag 304s.
  - Groq (`gem`, account `groq`): `api.gem.com/job_board/v0/<board>/job_posts/`.
  - Zoom: Workday `zoom/Zoom` on `zoom.wd5.myworkdayjobs.com`.

- **Target companies with no direct source (2026-10-09 sweep)**: the
  stock prober guesses only name-shaped tokens, and every company
  reached through a feed was never probed at all. A wider guess list
  (suffixes inc/hq/1/98/labs..., known renames) plus a scan of each
  careers page for ATS links found and registered: Box (boxinc), Navan
  (tripactions), Zipline (flyzipline), Stoke Space, Varda (was disabled
  by a false staffing match), Vannevar Labs, Addepar (addepar1),
  Couchbase (couchbaseinc), Teleport (ashby goteleport), Timescale (ashby
  tigerdata, renamed Tiger Data), DigitalOcean (digitalocean98), Chroma
  (ashby trychroma), Patronus AI (patronusaiinc), Planet Labs, Ro (lever
  ro), SambaNova (sambanovasystems), Archer (archer56), AQR (aqr), Fly.io
  (lever fly), Jasper (ashby "Jasper AI"), Capella Space, Stainless
  (ashby stainlessapi), Retool/Bilt/Chef Robotics (gem), Millennium
  (classic eightfold at career.mlp.com, domain mlp.com -- the PCSX
  search 403s), Booking.com (jibe jobs.booking.com/booking).
  Renames already covered: Grammarly is Superhuman (ashby "Superhuman
  Platform Inc"), Intercom is "Fin" (greenhouse intercom).
  Not readable or not allowed: Indeed, Revolut, Adept (403), Equinix
  (202 challenge), Tempus, Shift4 (429 on careers page), Arm and Synopsys
  (Radancy sites, robots disallow /search-jobs/), Joby (iCIMS classic),
  Vespa (BambooHR), Aqua Security (Comeet), Rudderstack (Rippling ATS) --
  no reader for the last four. "indeed1" on Greenhouse is a staffing
  board, not Indeed; ashby "rain" is a stablecoin company, not Rain AI.

- **Google, Meta, Intuit, Arm, Synopsys (2026-10-09)**, all within
  robots.txt:
  - Google (`google`): robots.txt disallows only `results?page=` and
    `results?*&page=`, so the first page of any search is allowed and
    carries the whole posting for 20 results (AF_initDataCallback
    `ds:1`; row fields 0 id, 1 title, 3 responsibilities, 4 quals, 7
    company, 9 places, 10 about, 12 created, 14 updated). Three US
    searches sorted by date: EARLY (all), MID "software engineer", MID
    "machine learning". Posting URLs resolve by id whatever the slug.
  - Meta and Radancy sites (`jobposting_sitemap`, account = host): Meta's
    robots.txt names `/jobsearch/sitemap.xml` (~1,100
    `/profile/job_details/<id>/`, all lastmod within the week so it
    cannot narrow reads); Radancy `/sitemap.xml` lists
    `/job/<city>/<slug>/<org>/<id>`. Pages carry JobPosting JSON-LD,
    stored in employer_page_readings under `<url>#jobposting`.
  - Level III: Google's "Software Engineer III" is L4 asking two years;
    the numeral alone no longer means senior -- judged by stated years,
    senior when none (gate v52).

- **Still unreachable (2026-10-09)**: Tesla (Akamai 403, even robots.txt),
  Citadel (career-sitemap.xml readable, every role page 403 from
  Cloudflare), Citadel Securities (403), D. E. Shaw (sitemap lists ~78
  roles by slug, page content loads from disallowed `/recruit/`),
  LinkedIn (`User-agent: * Disallow: /`).

## A Greenhouse posted date can predate the listing by days (2026-10-21)

Asked whether ace missed a DoorDash new grad role (greenhouse `doordashusa`, job 8163709). Its `posted_at` (Greenhouse
`first_published`) was Sep 4, ace first saw it on Sep 10, and ace had been reading the board since Sep 5, which looked
like six days late. It was not: that week ace caught every new DoorDash posting within minutes, the read at 17:33 UTC on
Sep 10 did not contain it and the read at 17:55 did. Greenhouse keeps `first_published` when a post is relisted (a Shift
Lead first published in 2022 reappeared the same day), so it went public, or back up, on Sep 10. To judge lateness,
compare `first_seen_at` with the board's neighbouring arrivals (the reads just before), never with `posted_at`. The
caught-late audit is unaffected: it measures against the feed's first sighting.
