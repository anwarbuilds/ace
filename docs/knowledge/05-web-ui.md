# The web interface: design, behaviour and its lessons

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you change the old single-file UI or build its Next.js replacement; it records what each screen is for and what went wrong.

## The interface is a triage instrument (2026-09-06)

Full design direction in the session record. The decisions that constrain
future UI work:

**Queue is the primary page.** Four primary destinations: Queue, Feed,
Resumes, Skills. Two secondary: Saved, Archive. A queue implies an end,
and 777 is finishable. Rejected: a Sessions page (a session is a grouping
of Feed, not a place), a Today page (755 of 777 jobs are "today", so it
would hold 97% of the queue), and an Applied page (an annotation, not a
destination, and building one starts the slide into an ATS).

**Split pane at 1024px and up**, 232 / 480 / flex. The scan-to-inspect
loop runs dozens of times per session, so it must cost zero navigation.
Below 1024px the detail becomes a full-screen push. Tablet behaves like
mobile, not desktop: two 380px panes serve neither.

**Unscored is a designed state, not an absence.** 358 of 777 actionable
jobs (46%) have no score because the posting was never readable. It gets
a dotted assay rail and the words "Not scored, description unavailable".
Rendering it as 0, a dash, or grey would read as "bad match", which is a
lie about what ACE knows.

**Session grouping lives in Feed, never on Queue.** Chronology fights
priority ordering, and most pulls qualify zero jobs, so a session-grouped
Queue would render as timestamps above empty space. Feed shows empty runs
deliberately: "21 found, none passed your filters" is proof of work.

**"New since last visit", not "today".** Freshness is currently useless
as a sort axis because re-polling stamps almost everything within 24
hours. The read line (a persistent hairline at the last-visit boundary)
only renders under a chronological sort, since under best-match sort new
arrivals are scattered and a single line would be meaningless.

**Gold is budgeted.** One gold fill per viewport. Gold text is permitted
for tier and active state. Never on secondary buttons, timestamps,
ordinary borders, status badges, or unknown states.

**No work authorization badge on rows.** Only 3 of 437 postings state
sponsorship, so the badge would print "Unknown" 99% of the time. It
appears only when a genuine restriction was detected.

**Em dashes are prohibited in the interface.** Permanent content rule.
Titles arriving from sources with one are normalized to a comma at
render time, since ACE does not control upstream text.

**Experience fit is stated on every row.** Three honest states: labelled
"Early career", an extracted ceiling ("3 yrs max"), or "Experience not
stated". The last must read as neutral, because unlabelled roles are
deliberately kept (see the decision above) and a blank or a warning
would misrepresent them. "Early career" is also a pinned filter chip in
the rail rather than an option inside the filter popover, since it is a
standing constraint rather than an occasional lens.

**The list pages on scroll, 60 rows at a time.** The first build capped
it at 100 with no way to load more, stranding 677 of 777 jobs. Client
code must never call `loadJobs` as a promise callback directly:
`then(loadJobs)` passes the resolved value as the `append` argument,
which silently takes the append branch and fetches nothing.

**JS reads breakpoints through `matchMedia`, never `window.innerWidth`.**
The split-pane check and the CSS must agree, and innerWidth is reported
as 0 in some environments, which silently disabled auto-selection.

**Marks are durable and server-side** (`job_marks`, migration 0015).
Saved, reviewed, dismissed and applied are the only job data ACE cannot
recompute: they are entered by hand, so they are authoritative and a
re-score must never touch them. `review_state` is one column rather than
two booleans because reviewed and dismissed both mean "handled" and a
row claiming both would have no correct rendering. Saved and Archive
filter in SQL, so they search all 777 jobs. The browser-local version
filtered whichever page happened to be loaded, so a job saved at
position 400 silently vanished.

There is no owner column. Adding authentication (item 8) means adding
one and scoping every mark query by it.

**Partial-match evidence is derived at read time**, not stored. The API
returns `related_evidence` pairs ("scalability, via distributed
systems") computed from the same graph the scorer used, so the
explanation cannot drift from the rules that produced the score.

**One load per navigation.** `goTo(page, view)` changes both and fetches
once. Calling `setPage` then `setView` fired two overlapping requests and
the older one could land last, leaving the list disagreeing with the
control above it (the "Highly matched" view showed 777 instead of 105).
Every non-append load carries a token and stale responses are dropped.

---

## Interface polish completed (2026-09-06)

The four items deferred from the combined UI pass:

**Match-change annotation.** A row shows "MEDIUM to HIGH" when a
re-score moved its tier, but only while the change is newer than the
last visit. `previous_score` (migration 0016) is captured before the
re-score deletes the old rows. Null means never scored before, which is
deliberately different from "did not move".

**Discovery runs nest their arrivals.** The feed shows each run's best
three, with "Show N more in Queue" beyond that, because runs have ranged
from 4 to nearly 900 jobs and one big run would otherwise bury a week.
Attached in one pass via `jobs_per_session`, not a request per run.

**Skills is filterable** by role family and by "roles I already fit".
One unfiltered list answered neither "what am I missing for ML roles"
nor "what am I missing where I already score well".

**The read line is reachable.** It only means anything in arrival order,
so the "N new since 5:04 PM" header is now a button that switches to
that order. This exposed a real bug: the count was computed over the
loaded rows, so the same visit read "19 new" under one sort and "60 new"
under another. It is now counted by the server over the whole queue.

---

## Old postings hide from the Queue, they are never deleted (2026-09-07)

The user asked to "delete jobs from dashboard that are 15 days older."
Offered the choice explicitly rather than guessing, because the two
readings are not close: hard-deleting rows would break Skills-gap
analysis and resume-match statistics (both read the full historical
set) and would make URL-based application-import matching fail for
anything already purged. The user chose the non-destructive reading.

`JobFilters.max_detected_age_days` hides postings ACE detected (
`first_seen_at`) more than N days ago from `/api/jobs` and `/api/stats`.
Deliberately keyed on detection time, not `posted_at`: most postings
have no trustworthy publish date at all, and a source misreporting one
must never hide something ACE only just found. `first_seen_at` is set
once, on first discovery, and never touched again by re-observation
(`repository.py` only updates `last_seen_at` on an existing record), so
the field genuinely ages rather than resetting on every poll.

Applied only to the Queue's view, and **off by default** (changed
2026-09-07 at the user's request: they would rather see the whole queue
and narrow it deliberately than have anything hidden without being
asked). The "Last 15 days" chip sits next to "Early career" in the
filter rail; one click turns it on. Saved, Archive, Feed, Resumes and
Skills are all unaffected, since the filter lives in `params()` gated on
`state.page==="queue"` rather than as a stored preference - nothing a
user saved or is tracking can be hidden by a housekeeping default.

Nothing is deleted. A hidden posting still exists, still counts in
Skills and Resume statistics, and is one click away in the Queue itself.

---

## Redesign: anthracite grey (2026-10-09/10)

Supersedes the purple-and-gold palette below; the table-first layout,
combined sorts, tiers and the job page as its own page all stand.

**Palette, as the user named it: anthracite grey.** Night is RAL 7016
itself (#293133 canvas, surfaces stepping lighter toward the reader);
Day is its light version, the same cool green-blue grey with anthracite
(#293133) as the ink. "Anthracite" alone was taken as near-black slate
first and corrected by the user: it is the grey. Every text pair was
contrast-checked on every surface (AA). Settings calls them Night, Day,
System.

**Red is budgeted** (it replaces gold in the old rule): the active nav
indicator, the one primary action on a screen (Open official posting,
Fill), a new-arrival badge. Green means match, as on a streaming title
card. Tiers are monochrome: big tech brightest.

**Wordmark: lowercase "ace", nothing else.** The user rejected a red "A"
tile, an all-caps ACE, a "Career engine" subtitle and a "Go at your own
pace" caption, one after another. Do not add a mark or caption back.

**No em dash on screen, ever.** `clean()` still normalises titles; a
MutationObserver (`undashTree`) rewrites any em dash or spaced en dash
in text nodes and in title/placeholder/aria-label attributes, including
popovers and the palette drawn outside render(). Textareas are exempt
(the user's own answers), and an unspaced en dash in a range ("2-4" with
an en dash) stays. Browser test `test_no_em_dash_reaches_the_screen`.

**The spreadsheet import is gone from the interface** (Upload sheet,
Import applications, the import dialog). The user applies only through
ACE, never outside it. The API endpoints remain; Export CSV stays.

**Components:** Geist / Geist Mono; company monogram tiles (`avatar()`,
hue derived from the name); the view tabs share one sliding pill
(`syncTabs()` replays the move after each innerHTML render); row actions
float in as a dock over the row's right end instead of holding a
column; cards light up under the pointer (`--mx/--my`); the match is a
ring on the job page and "43%" plus a hairline in the table; the
sidebar's "Search or jump to" opens the command palette. Nothing
animates on entry inside render(), because every action redraws the
page and the animation would replay.

**The extension matches**: panel (shadow-root CSS in `content.js`) and
popup use the same anthracite tokens, lowercase "ace" mark, one red
action, and follow the OS light/dark preference. Version 1.20.0, name
"ace autofill".

**Previewing:** run uvicorn from the repo on :8001 with `.env` loaded
(it reads the static file per request, so no image rebuild per edit),
and run the browser suites against it with
`ACE_BROWSER_TEST_URL=http://127.0.0.1:8001`.

## Redesign: purple and gold, table-first (2026-09-07)

> **Status:** Superseded 2026-10-09/10 by 'Redesign: anthracite grey' in 05-web-ui.md. The colours here are history; the reasoning for a table-first layout still applies.

The previous interface was a narrow 480px list beside a mostly empty
detail pane, in a warm cream palette the user described as an Anthropic
clone. Five changes, requested together.

**Palette is purple and gold** (Kolkata Knight Riders), not cream.
Purple carries structure and navigation; gold is reserved for the
signal: big-tech tier, HIGH match, the primary action. Every token was
contrast-checked against its own ground before any CSS was written, and
all 19 pairs passed AA on the first pass.

**Layout is a full-width table**, not a vertical list with dead space.
Company, role, location, experience, match, status, seen, actions.
Sortable headers double as the sort control.

**Job detail is its own page**, reached by clicking the role. Two
columns: match intelligence on the left, actions, application status and
provenance on the right. Escape or Back returns to where you came from,
which is tracked so Pulls returns to Pulls.

**Sorts combine.** `parse_sort` takes a comma-separated list, up to 3
keys, applied in order, with a numbered badge showing precedence. "New
grad first, then best match" was the specific request and is the
default. One sort at a time forced a false choice between two things
that matter at once.

**Employer tiers** (`intelligence/companies.py`). BIG_TECH gets a gold
rail, TOP_TIER purple, ESTABLISHED neutral, everything else unmarked.
62% of the queue classifies. Curated by hand rather than inferred:
headcount and funding are bad proxies for "good place to start", and a
derived signal would be confidently wrong in both directions.

Matching is exact on the lowercased name plus an alias table,
deliberately not fuzzy, because the same classification must be
reproducible in SQL for ordering as in Python for display. A
normalisation the database cannot perform would let a posting sort as
big tech while its badge said otherwise. A test asserts the two agree.

**Pulls replaces Feed**, grouped by day then by pull time, with each
pull's jobs nested beneath it in the same table. Empty pulls keep their
line.

## Filters exclude as well as include (2026-09-07)

`JobFilters.exclude_companies` removes companies from results and
stacks with every other filter. Kept separate from `companies` rather
than expressed as a negative there, because "only these" and
"everything except these" are different questions and the user often
wants both: every big-tech early-career role, except Amazon's 43.

Excluded companies render struck through in the danger colour rather
than as another selected chip, because a removal is not a selection.

`/api/stats` also had to learn `tier` and `exclude_company`. It already
accepted the other filters so the headline total would equal the rows on
screen, and the tier filter added earlier had quietly broken that: the
list said 62 while the header said 252. A count that disagrees with the
list reads as jobs being withheld.

---

## Turning a sort on makes it primary (2026-09-07)

Sorts were appended when enabled, so a user who toggled "Not applied
first" off and back on found it third, where it only broke ties, and
reported the feature as broken. It was doing exactly what it was told;
the instruction was the wrong one. Enabling a sort now puts it first,
the way clicking a column header does, and the oldest key is dropped
when the list would exceed three.

Apply mode was removed at the user's request: the friction was never
navigation, it was retyping the same answers, which is what the answer
bank addresses.

Removing it broke the page, because the regex that deleted the apply
mode functions ran from its section comment to the render comment and
swallowed the answer bank block sitting between them. Nothing caught
it: there are no tests over the single-file client, so `render()` threw
`answerToggle is not defined` and the app rendered nothing at all.
Check the page actually loads after deleting a block from it.

## Pulls was lying about what it listed (2026-09-07)

The page said "a pull that found nothing still appears, because that is
how you know it ran". A poll only writes a `poll_sessions` row when it
*discovers* something, so a check that found no new postings left no
trace, and the most recent check was routinely missing from a list
claiming to be a complete log. The user saw "updated 2m ago" with
nothing from the last hour and reasonably asked why.

The copy is corrected, and when the last poll is newer than the newest
recorded pull it is shown on its own row: "checked, no new postings".
That is the difference between "ACE is idle" and "ACE looked and there
was nothing", which is the only question the page exists to answer.

## The filter list showed 10 of 169 companies (2026-09-07)

Two bugs in one popover, both visible in a screenshot the user sent.

**Truncated.** `grp()` and the exclude group each did `.slice(0,10)`,
so 159 of the corpus's 169 companies could not be filtered on at all.
The fix is not a longer list: 169 entries in a 300px scroller is no
more usable. A search input at the top of the popover narrows every
group, the ten busiest stay as the default view, and each group ends
with "N more, type to find one" so the truncation is stated rather
than implied.

**Folded to lower case.** The same `grp()` applied
`.toLowerCase()` to every value. That is right for `SOFTWARE_ENGINEERING`
and `greenhouse`, and wrong for ByteDance, IXL Learning and DoorDash,
which is why the "only this company" list read `bytedance` while the
"hide a company" list beside it read `ByteDance`. Case folding is now a
per-group choice: companies are written the way their company writes
them, sources and families are folded.

Only the list is redrawn as the user types, so the caret stays put.

## Pulls could not act on its own rows (2026-09-07)

`jobById` scanned `state.items` only, but the Pulls page renders the
same `jobRow()` markup from `state.sessions[].jobs`. Saving or applying
from a Pulls row reported "That opportunity is no longer on screen"
while the row sat there in plain sight. Clicking the row body worked,
because `openJob` falls back to fetching the job it cannot find, which
is why the failure looked arbitrary. The lookup now covers every list
the user can act on, plus `detailJob` and `heldRow`.

## Filter counts were taken over the wrong corpus (2026-09-07)

The user said tapping a filter did not work. Every mechanism checked
out under real pointer events: the tier chips filtered correctly, and
taps on both company groups applied. The fault was that a tap could
land on nothing.

`build_facets` counted over the whole qualifying corpus, ignoring
whatever the user already had on. With the Big tech tier active the
Queue held 305 rows, and the menu still offered "Jobsbridge 69".
Jobsbridge is not big tech, so choosing it returned zero. A filter that
promises 69 and delivers an empty screen is indistinguishable from a
tap that did nothing.

Facet counts are now taken inside the active filters, so a number in
the menu is the number of rows choosing it will show: Big tech offers
18 companies summing to exactly 305.

The user's actual complaint turned out to be the second candidate: the
"161 more, type to find one" line. A count of what is hidden is not an
instruction, and set as a line of text it read as something to tap.
Their words were "it is like a text, no action to do on it". It is now
a button, "Show 161 more", that opens the group it counts. One group at
a time, because opening everything at once buries sources and families
under 169 companies. Search still works as the faster path.

**Each facet clears its own dimension.** Filtering to one company must
still list the others, or the menu is a dead end. Both company
dimensions clear together, since "only this" and "hide this" are drawn
from one list.

## CSS inserted with literal backslash-n (2026-09-08)

The user reported the Activity header reading "Last checkjust now" and
"In your queue593". The cause was not layout: a patch had written the
stylesheet rules joined by the two characters backslash and n rather
than a newline, so the file contained
`}\n.ctl-grp{`. CSS reads that as a selector beginning with an escape,
and every rule after the first in the block silently never applied.
Nothing errors, nothing logs, the page just renders unstyled.

Measured rather than eyeballed afterwards: the gap between a control
label and its first chip was 0px, and is now 6px. A browser test
asserts the computed gap, because the failure mode is invisible in a
screenshot review that is only looking for missing spaces.

When patching CSS through a Python string, check the file afterwards
for a literal `\n` before a selector.

## The activity log hid the wrong half (2026-09-08)

The first pass collapsed quiet checks into "9 other checks found
nothing new" and expanded every check that found something. The user
asked for the opposite and was right: a log that hides its quiet
entries cannot answer "was ACE running at 3am", and one that expands
every entry is a wall of rows.

Every check is now a row carrying its time, outcome and how many
postings it saw. Only checks that found something are clickable, and
their jobs appear on click.

## Two controls that earned nothing (2026-09-08)

"Last 15 days" was a filter the user had already asked to stop
defaulting on, and it survived as a chip nobody pressed. The `/` badge
in the search box advertised a keyboard shortcut and read as stray
punctuation inside the field. Both removed.

The bar is now three labelled rows rather than one run-on line, and
"Clear all" appears whenever anything is narrowing the list. It had
been rendered only when a filter chip existed, so a tier filter left
no single way back to the full queue.

## The activity log could not show that ACE was running (2026-09-08)

The header said the last check was a minute ago while the log's newest
entry was an hour old, and the two read as a contradiction. Both were
right: `record_discoveries` never creates an empty run, which is
correct for a run, so a check that found nothing left no trace.

`record_check` now records that ACE looked, whether or not it found
anything. The merge window makes it affordable: the scheduler
completes a cycle roughly every ten seconds, so a row per cycle would
be nine thousand rows a day, and extending one row instead leaves a
quiet stretch as a single entry whose span grows.

The log shows three outcomes rather than two. "Nothing new" means
postings were read and none qualified; "no new postings" means there
was nothing to read. Collapsing them hid whether ACE had looked.

## One log entry covered two and a half hours (2026-09-08)

The header said the last check was a minute ago and the log's newest
entry read "12:13 PM - 2:44 PM", which the user read as a check that
happened at lunchtime. Both were correct and the presentation was not.

Two changes. The latest activity leads, with the start shown as "since
12:13 PM" behind it. And an entry stops growing after an hour however
quiet things stay, because a log entry has to describe a period short
enough to mean something.

## Activity is logged in quarter-hour buckets (2026-09-08)

The user expected the log to show individual pulls with their own
timings and results. There is no natural "one pull" to log: the
scheduler completes a cycle every few seconds and polls whichever
sources are due, so a row per cycle is nine thousand a day.

Merging on idleness was the first attempt and produced one row
covering two and a half hours. Fixed clock buckets replace it. Every
fifteen minutes with any activity is exactly one row, always starting
on the quarter hour, so the log reads 2:45, 3:00, 3:15 and is at most
ninety-six rows a day. Two checks either side of a boundary are two
rows however close together they ran.

## The activity history stopped at a hard wall (2026-09-09)

The user asked where the complete history was; they could only see
today and yesterday. `/api/sessions` had no pagination at all -- a
flat `limit`, capped at 100 server-side, with nothing past that
reachable from the client. On a busy day, with checks now bucketed
every fifteen minutes, 100 rows is barely more than a single day, and
the page was silently discarding everything older than that rather
than saying so.

`list_discovery_runs` takes a `before` cursor now: pass the oldest
`started_at` already on screen and it returns the next page further
back, with no upper bound. A "Load older activity" control appears
until the server returns fewer than a full page, at which point it is
replaced by "End of recorded activity" -- an honest end, not a
truncation. Verified against the real corpus: repeated clicks reached
99 sessions before exhausting, each page strictly older than the last.

## The activity page had nothing in its own margin (2026-09-09)

Widened past a laptop screen, the log column left the rest of the page
blank. Filled with information that already existed but was locked
inside a CLI script (`source_health.py`) the user cannot run
themselves: a sidebar showing where the queue's jobs actually come
from, platform by platform, built from the same facets the Queue page
already loads rather than a second network call.

## A check that found jobs, expanding onto nothing (2026-09-10)

Surfaced by a browser test failing after the aggregator was removed,
which is the sort of catch that justifies having them: "expanding a
check showed no jobs".

The Pulls page decided whether a check was expandable from
`qualifying_discovered`, the count recorded at the time. That count is
history and cannot change. The postings it counted can: deleting a
whole source removed them, so a row still read "13 passed", stayed
clickable, and opened onto an empty list.

Split into two questions, because they are two. The badge still says
what the check found, because that did happen. Whether the row expands
now depends on whether anything is actually behind it.

Also worth recording what this says about the removal: deleting rows is
never only deleting rows. The applications on them were preserved
deliberately, but this second consequence -- a log entry counting
postings that no longer exist -- was not foreseen and was found by a
test rather than by a person.

## The one filter the user needed did not exist (2026-09-11)


The user's whole target is "early career, or anything asking three
years or less". They were using the **Early career** chip for it, and
it was quietly wrong for the job: it filters on `is_early_career`
alone, so of 986 qualifying postings it showed 385 and hid 52 that
state one to three years, including **every single one** of the 33
three-year roles. The exact band they asked for was the band the
control removed.

Asked whether the filter should then exclude the 549 postings that
state no experience requirement at all, the user rejected it, and was
right to: "if no experience is stated they might have early careers
also". That is the gate's own reasoning, and turning it into a hiding
filter at the read surface would have overruled a decision the earlier entries already
records.

So this is a **sort, not a filter**, and the distinction is the whole
point. The gate already refuses four years and up, so everything in
the queue is already applicable; the user does not need a smaller
list, they need their band first. `experience_fit_first` orders in
three levels:

| Level | Meaning |
| --- | --- |
| 0 | In band, description read |
| 1 | In band on the title alone, description unreadable |
| 2 | States no experience requirement |

Level 1 exists because 128 in-band postings are Lane B, where the only
evidence is a title reading "New Grad". That is real evidence and
beats silence, but it is weaker than a description ACE checked, so it
sits between the two. The ceiling is imported from
`MAX_REQUIRED_EXPERIENCE_YEARS` rather than written as 3, so the
ordering cannot drift into a second, quieter definition of what the
user can apply to.

Default sort is now `unapplied_first, experience_fit_first,
best_match`. Nothing is hidden, so the boundary is drawn instead: a
divider row reading "Below here, experience not stated, N more",
rendered only while that sort is active, since under any other order
the two kinds interleave and the line would fall in an arbitrary
place.

The **Early career** chip is kept but renamed **"Labelled early career
only"**, because a control whose whole effect is to hide the roles the
user just asked for must say so on its face.

## The numbered sort badges were read as decoration (2026-09-11)

"Not applied first" showed a `1` meaning it was the primary sort. The
user read the badges as ornament, could not tell what they encoded,
and reported that clicking "Not applied first" repeatedly still showed
applied jobs at the top.

Two separate causes, and only one was the badge.

**The badge.** `1`/`2`/`3` now read `1st`/`2nd`/`3rd`, the chips carry
`aria-pressed` and a title saying which state a click produces, and a
line underneath states the combination in words: "Showing the ones you
have not applied to first, then roles that fit your experience, then
best match." A "Reset to default" appears once the order is changed.
Keep "first" attached to the leading key: "A, B, then C first" reads
as though C led.

**The real bug.** Marking a row applied sets `state.pinned` and
`state.heldRow` so the row survives one load instead of vanishing to
the bottom. They were cleared **only on navigation**, so the row was
re-inserted at position one by `unshift` on *every* later load. Every
sort toggle, every filter change, every search redrew the queue with
an applied job pinned to the top. The sort had worked correctly all
along and was being overruled by the client after the fact.

The hold is now released in the load it was held for, which is what
its own comment always claimed. Both the released hold and the
spelled-out sort line are pinned by browser tests, each confirmed to
fail against the bug it describes before being kept.

## Renaming the chip broke it (2026-09-11)

"Early career" was renamed "Labelled early career only" earlier the
same day, so its narrowing would be stated on its face. The user's next
question was "where is early career filter thats the one i use more".
It was on screen. They could not find it.

A longer, more accurate name is not an improvement to a control someone
reaches for by recognition. The warning belonged in the behaviour, not
the label.

So the chip is **"Early career"** again, and it now filters on the same
`_experience_in_band()` the sort orders by: labelled early career, or
stating three years or less. Live, that is 437 rather than 386 -- the
51 postings it used to hide, including every three-year role, which was
the original complaint that started all of this. `early_career_only`
stays in the API for the stricter label-only question; nothing in the
interface asks it any more.

One definition, read by both the chip and the sort. A chip filtering to
a different set than the sort orders by would be worse than having
neither: the rows leading the list would disappear when the user
narrowed to them. A test pins that they agree.

**"Showing newest first first."** The sort sentence appended "first" to
the leading key, and two phrases already end in it ("newest first",
"oldest first"). Visible in the same screenshot, fixed by not
appending when it is already there.

## "Show 303 more" showed 300 (2026-09-17)

Found by a browser test failing on the RippleMatch commit, not by
looking. The company filter's expand path sliced to 300, so the three
alphabetically last companies never rendered -- the ones you would have
scrolled that far to find. The cap was 300 because `.pop-list` is
`max-height: 300px`; a pixel height had been copied in as an item
count. The list scrolls inside that fixed box, so its length was never
what needed bounding.

Latent for as long as the corpus was under 300 companies. Worth noting
as a shape: a limit that silently drops the tail is invisible until the
data crosses it, and the failure looks like whatever change crossed it.

## "31 postings seen" meant 31 new, out of about 63,000 checked (2026-10-05)

The user doubted ACE was searching enough: the Activity page showed 31
or 52 "postings seen" per quarter hour. Those were *new* postings. In
the 16:15 window ACE made 700 polls of 483 boards holding 63,517
postings; at 16:30, 481 boards and 69,182. Nothing on the page said so.
Each pull now records the distinct boards read during it and the
postings they held (0035; a "not modified" board counts its known
size), and the row reads "31 new · 483 boards, 63,517 postings checked".

Measured separately, the speed question: of 111 postings that appeared
both on an employer board ACE already read and later in Simplify, ACE
had 92 first, by a median of 5 hours. The 14 feed-first were Amazon
(the capped reader fixed that morning) and two Duolingo roles on a
daily board -- which is why every board on a one-request provider is
now polled every fifteen minutes whatever it has produced (71 moved;
the RippleMatch feed is the only daily source left).

## The Next.js app, under new names (2026-10-14)

Built in `web/` against the unchanged FastAPI API, in a cloud session on the fictional demo database. The old UI's CSS
is ported with its class names (`web/src/app/globals.css`), Tailwind loaded without its preflight so the approved
spacing does not move. Server components read FastAPI through `API_ORIGIN`; the browser calls `/api/*`, rewritten to
FastAPI. Filters, sort and page are URL parameters (`src/lib/listState.ts`), with numbered pages instead of infinite
scroll. Theme and time zone are cookies, so the server renders the right theme and dates with no flash; last visit is
worked out in `src/proxy.ts` before the page renders.

New names, by the owner's brief: Opportunities (Queue), Activity (Pulls), Applications (Applied), Resume Studio
(Resume), Skills under `/app/insights/skills`; tabs All opportunities, Strong matches, New since your last visit, Latest
discoveries. Old URLs redirect (307), and `/#job/<id>` links open the job page. Saved left the navigation at the
owner's request; its data, the star on rows and `/app/saved` remain.

Bugs the Playwright suite found before the user could:
- A Tailwind utility is named `ring`, the same as the score ring's class, and drew a square box around it.
- The scroll restorer reset the panel to the top during hydration, after the browser had scrolled to the pager, so a
  quick click on page 2 landed on empty space. It now restores only a remembered position, and resets only on a real
  route change.
- Every popover listened for Escape even while closed and stopped it, so Escape never left the job page.
- The palette kept the last search when reopened; it now mounts only while open.

Tests: `web/tests/e2e` (39: every route in both themes with the typed and drawn dash scans, URL state, pagination,
redirects, keyboard, palette, marks with undo, score wording). Screenshots: `web/scripts/screenshots.mjs`, demo data
only.

## A website, not a dashboard (2026-10-14)

The owner asked for the app to read as a multi-page website, "like Amazon, Flipkart or Netflix", not a dashboard.
What changed on `next-app`:

- **Top navigation** replaced the sidebar: Home, Opportunities, Companies, Applications, Resume Studio, Answers and a
  More menu (Discovery activity, Archive, Skills, Coverage); search, theme and settings on the right; a drawer under
  1024px. A department strip under it links every browse group.
- **The document scrolls.** The page body scrolls under a sticky header and ends in a footer with a site map. Table
  headers and asides stick below the header (`--site-h`). `ScrollArea` now saves and restores `window.scrollY` per
  URL, so returning from a job page still lands on the row.
- **Browse groups** (`web/src/lib/browse.ts`): strong matches, new today, new grad, big tech, top tier, machine
  learning, forward deployed, software engineering, remote. Each is a saved `/api/jobs` query with its own route,
  `/app/browse/<slug>`, with sort, tier filter and numbered pages in the URL, and breadcrumbs. Nothing is hidden that
  Opportunities shows.
- **Home** (`/app`) is a shop front: a featured top pick, then a row of cards per group, each leading to its page,
  then companies hiring, then applications and service health.
- **Companies**: `/api/companies` (open qualifying roles and applications per employer) feeds a directory at
  `/app/companies` and a page per company, `/app/companies/<name>`.

Lessons: a spaced hyphen ("Agent - Legal") reads as a dash; `clean()` now turns it into a comma and the dash scan
flags it, but the repost grouping must split on the raw title before cleaning or the vertical disappears.

## Pulls is home; focused navigation; speed (2026-10-15)

The owner's daily loop is: open Pulls every 15 minutes, open a new role, apply with the extension. So `/app` is now
Pulls (old `/app/activity` and `/app/pulls` redirect there). Navigation is Pulls, Opportunities, Applications,
Dashboard, Resume Studio, Answers, with Archive, Skills and Coverage under More. The command palette ("Search or jump
to", Ctrl K) and the department strip were removed on request; the browse and company routes still exist but are not
linked from the shell. New `/app/dashboard` (one call, `/api/dashboard`): open roles by company tier and role family
with how the resume scores across each (high, medium, minimal, not scored), best fits by company, applications by
status, roles found per day.

Speed: `/api/sessions` ran a full job listing per run, about 144 queries for a page of 30 runs (0.7 s on a 364 job
demo, seconds on the live corpus). It is now one grouped count, one ranked query (row_number per run, the listing's own
best_match tie-breaks) and one listing by id: 8 queries, identical output, pinned by a test. The shell layout no longer
fetches stats, coverage or external applications on every navigation, and `/app/loading.tsx` answers a click at once.
`next dev` compiles each route on first visit; for daily use run the production build (`npm run build && npm start`).

## Pulls-first shell after the approved prototype (2026-10-15)

Status: supersedes the top navigation of "A website, not a dashboard" and the `/app` home of the entry above.

The owner approved a prototype (`ace-pulls-first-demo.html`, kept outside the repo) and a directive. Implemented:

- **Shell**: a 244 px sidebar in three groups (Daily workspace: Pulls, Opportunities, Applications, Analytics; Career
  tools: Resume Studio, Autofill Extension, Archive; System: Coverage, Settings), a red bar on the active entry, the
  owner chip and the engine state at the bottom. Icons only below 900 px; below 650 px the sidebar goes and a bottom
  bar holds Pulls, Jobs, Applied, Analytics and More (`/app/more` lists every page). A sticky 64 px top bar holds the
  breadcrumb, the live pill and the theme switch. No palette, no Jump, no Ctrl K. Answers stay at `/app/answers`
  (selects Autofill Extension), Skills at `/app/insights/skills` (selects Resume Studio).
- **Routes**: `/` and `/app` redirect to `/app/pulls`; `/app/activity` to `/app/pulls`; `/app/dashboard` to
  `/app/analytics`. New `/app/extension` holds pairing (moved out of Settings, which links to it). An /app request
  while signed out now goes to `/login?next=<path>` (proxy.ts passes the path as `x-ace-path`), so deep links survive.
- **Pulls** (`/app/pulls`, one request to `/api/pulls`): live, delayed (no successful read for 15 minutes) or stalled
  (45) from `SourceState.last_success_at`, never from the page loading; four 24 hour KPIs; one card per 15 minute
  window for the chosen local day, quiet windows included, with the time range in the reader's zone; filters All
  activity, With opportunities, Quiet checks, and day paging; a window opens to its qualifying jobs (loaded on open
  from `/api/jobs?session_id=`) with details, official posting, applied and not relevant, all through the marks API.
- **Metric contract** (`backend/app/api/routers/pulls.py` docstring): sources enabled is configuration; sources
  checked is distinct boards attempted in the window; answered is distinct boards read successfully
  (`boards_checked`); failed is distinct boards with a failed or refused attempt (one that failed then succeeded counts
  in both); attempts counts every attempt; postings observed is what answered boards held (mostly seen before); new is
  first seen in the window; relevant is new and passing the gate when it arrived. Attempts and failures come from
  migration 0040 (three nullable columns on `poll_sessions`, filled by the scheduler from memory, never lowered);
  older windows show them as not recorded. The 24 hour "sources checked" KPI counts enabled sources whose last
  success is inside the span, because summing per window distinct counts would count a board once per window.

Lessons: the sidebar count for Opportunities used the queue total (204) while the list showed 203 under its default
filters, so it was removed rather than shown wrong. The prototype's dimmest grey (#889496) fails AA on small text over
the panel; `--text-muted` stands in.

## Analytics and Applications on the new page pattern; no build-time API address (2026-10-15)

- `/api/dashboard` gained `applied`: every application (marked jobs and external ones), by current status, role
  family (external ones as "No stored posting"), company and day, with heard back (screening, interviewing, offer,
  accepted, rejected), interviews and offers. ace keeps no status history, so the page says counts are by current
  status; No reply is never counted as rejected.
- Analytics leads with applications (KPIs, applied per day, status, family, companies), then discovery and resume
  fit. Applications shows four KPIs above the list. Ported pages (Opportunities, Archive, Coverage, Settings, Answers,
  Skills, Resume Studio) take the new header scale and gutter; their duplicate live chips are gone (the top bar has it).
- A local agent found `/login` showing "Not Found": an older build had baked `rewrites()` to :8000, where the old
  container has no `/api/auth`. Already fixed by the runtime proxy; `/healthz` now goes through a route handler too,
  so `.next/routes-manifest.json` holds no API address (checked with a build without API_ORIGIN). Sign-in forms now
  say "The sign-in service is not reachable" for a 404, 405 or 5xx instead of the raw status text.

## Pulls-first interface completed; legacy UI retired (2026-10-15)

The approved multi-route interface is now the only UI. The desktop sidebar collapses to icons and persists that
choice in local storage; below 900 px it uses the compact rail, and below 650 px the phone bar remains the navigation.
Analytics gained URL-backed 14, 30 and 90 day trend ranges and a role-family filter for discovery and resume-fit
data. Application totals stay all-history, which the filter copy says explicitly.

The unlinked Browse and Companies pages and components were removed. Their URLs issue temporary redirects to
Opportunities so old bookmarks do not break. FastAPI no longer serves `static/index.html`; `/` sends the browser to
`WEB_BASE_URL/app/pulls`. The command-palette CSS and the last keyboard-guard references were deleted as well.

Production builds use the Geist files already installed with Next through `next/font/local`. This avoids a Google
Fonts request during a build and keeps the rendered typography identical in disconnected containers.
