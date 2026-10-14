# The eligibility gate and role rules

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you change who passes (experience, location, contract, security, new grad, sponsorship, role families) or wonder why a posting was rejected or admitted.

## The gate is binary - PASS or REJECT

There was a `STRETCH` tier. It was removed 2026-09-05: the user wants
one list meaning "apply to this", not tiers to reason about. Three-year
roles became plain `PASS` because the user has 3.5 years.

## Unlabelled roles are included

A terse posting stating no experience bar and never saying "new grad" is
frequently open to one. Excluding them was tried and reversed on user
instruction. The early-career signal is kept for *ordering*, not
exclusion.

## Internships excluded (2026-09-06)

User is focused on full-time only. Controlled by `INCLUDE_INTERNSHIPS`
in `eligibility.py` - a flag, not deleted code, because search strategy
changes more often than code should. Removed 1,250 postings.

## Lane B is browse-only

Curated-feed postings carry no description, so requirement rules cannot
run. They appear on the website marked `UNVERIFIED` and sorted below
verified postings. Fetching the missing text is **impossible**, not
merely unimplemented: Tesla returns 403, and Apple and TikTok render
client-side with no structured data.

## The experience extractor was reading almost nothing (2026-09-07)

The user reported 5+ year roles showing as early career. Two separate
bugs, rules now v17.

**A whitelist of adjectives.** The pattern required one of a fixed set
of words between "years" and "experience", so "5+ years **backend**
software engineering experience", "7+ years **distributed systems**
experience" and "8+ years **in roles such as**" all matched nothing at
all, and those postings passed with no requirement recorded. Any few
words are now allowed. The company-bio cases it must not match are
tested: "Clay spent 18 years at Google", "transforming computing for
more than 25 years".

**A range's ceiling was ignored.** "2 to 10+ years" recorded a floor of
two, which is right for pass or reject, and then called the role early
career, which is not. A range reaching past
`MAX_REQUIRED_EXPERIENCE_YEARS` no longer counts as early career.

Removing the first bug changed real behaviour, so a test asserting a
"New Grad" title excuses "4+ years" was rewritten rather than patched:
it had only ever passed because the figure was invisible, and the
constant has always documented four or more as excluded.

Measured before shipping: 33 senior roles removed, 5 early-career
mislabels corrected, out of 778.

## Security roles are rejected on title (2026-09-07)

`SECURITY_TITLE_PATTERNS`, at the user's request. Deliberately broad:
a general engineering role on a security team is still a security team.
This does remove things like "Software Development Engineer, AWS
Compliance & Security", which is a judgement call the user made
explicitly. Hardware was already fully covered by
`HARDWARE_TITLE_PATTERNS`; nothing hardware-titled was passing.

## A Stripe job the user found by hand exposed the location gate (2026-09-08)

The user asked why a Stripe posting they had seen was not in ACE. ACE
had the job, had read it, and had rejected it: location "US", reason
"Location is outside US / Remote-US scope."

`US_LOCATION_MARKERS` held "usa" and "united states" and matched by
substring, so bare "US" reached none of them. Two shapes were missing
entirely.

**A bare US token.** "US", "US-Remote", "US-CA-Menlo Park". Matched on
token boundaries rather than as a substring, because "us" sits inside
Houston, Austin, Belarus, Cyprus and Mauritius, and a substring test
would have quietly admitted three countries.

**A city with no country.** Several large boards post one: 1,231 San
Francisco postings, 294 San Jose, 202 Sunnyvale, 145 Los Angeles were
all being thrown away. The list deliberately omits Cambridge,
Birmingham, Manchester, Richmond, Vancouver, London, Hamilton and
Waterloo, whose non-US reading is common in postings.

Compiled as one alternation. Sixty-four separate searches per call
made a full corpus re-evaluation exceed five minutes.

180 postings recovered with none newly rejected, and the queue went
from 592 to 772. The user found this by noticing one missing job,
which is worth remembering: the gate's false rejections are invisible
from inside ACE, and the only signal is someone spotting a job
elsewhere.

## A longer list is not a guarantee (2026-09-08)

Asked whether the location bug would recur, the honest answer was no,
and the proof was already in the data: after the first fix, "SF Office"
and "Emeryville HQ" were still being rejected. A curated list is never
finished, and the same bet had just failed once.

The problem is not the list, it is that **a false rejection is
invisible**. The queue looks healthy, nothing is logged, and the only
signal is the user noticing a job somewhere else that should have been
here. That is how a Stripe posting located "US" sat rejected for two
days.

`python -m backend.scripts.rejection_audit` prints the rejection
reasons in order and the location strings behind the ones that hinge on
a lookup table. It does not guess which are wrong; it makes the silence
readable. Anything in its location list that is plainly a US place is a
job being thrown away right now. It found the two above, and after
fixing them the list contains only Bangalore, Manchester, Bogota, Cape
Town, Stuttgart and Seoul.

The guarantee worth making is not "the rules are complete". It is "the
gap is now visible without waiting for the user to spot it".

## The experience range rule flipped twice (2026-09-08)

Worth recording as a decision rather than a conclusion, because it
moved in both directions and the second move undid the first.

It began by passing a wide range on its floor. It was changed to
reject on the ceiling, because the user reported a queue meaning "a
graduate can apply to this" full of postings wanting four or more
years. That change then threw away twenty-five software postings whose
floors were one or two years, including one titled "Software
Engineer I" and three Stripe roles reading "Minimum requirements 2-10+
years".

The two instructions are not in conflict once open-ended and bounded
are separated:

- **"3+ years"** sets a floor and takes whoever clears it, so a
  graduate competes with someone who has five. Rejected.
- **"2 to 10 years"** is a band a candidate with two is inside, and
  the employer wrote it under "Minimum requirements". Passed on its
  floor.

The ceiling still withholds the early-career label, because a range
reaching ten years is not a graduate posting even when a graduate may
apply. Labelling and eligibility are different questions and were
briefly conflated.

Found by auditing rejections rather than by waiting: software postings
rejected on experience where nothing in the text exceeded the bar.
That query is worth re-running after any change to the experience
rules.

## A structured "contract" flag was read and then thrown away (2026-09-09)

The user spotted recent Adzuna postings that were contracts, not
full-time. Adzuna's API reports `contract_type` directly -- unlike
almost every other signal ACE reads, this one is not inferred from
prose -- but the adapter read the field and nothing downstream ever
stored it. Two structural gaps had to be closed, not one:
`employment_type` had no column on `JobRecord`, so it was discarded at
the first persistence boundary; and once the column existed,
`compute_job_content_hash()` still didn't read it, so a poll that only
flipped a job's employment type from unknown to "contract" produced an
identical hash and never registered as a content change, so it never
re-evaluated. A rule (`CONTRACT_ROLE`) rejects any job whose
`employment_type` contains "contract"; a source that never states the
field at all is left alone rather than assumed full-time. Verified
live: two real postings (Vestwell, T-Mobile) stayed PASS until both
gaps were closed, and correctly flipped to REJECT once they were.

The same silent-drop shape existed a third time, in a script this fix
depends on: `backfill_job_evaluations.py` rebuilds `CanonicalJob` from
`JobRecord` for re-evaluation and had its own copy of the same
reconstruction, missing the same field. Left alone, running that
script would have quietly undone the fix above the next time someone
ran it. Fixed in the same pass. `CanonicalJob` is reconstructed from
`JobRecord` at three separate places in this codebase now
(`persistence/evaluations.py`, `scripts/backfill_job_evaluations.py`,
and the ingest path itself) with no shared helper enforcing that they
stay in sync -- a new eligibility-relevant field has to be added to
all three by hand, and nothing will complain if one is missed.

## New grad is a narrower question than early career (2026-09-11)

"also include a filter called new grad, early career and new grad are
important for me." ACE could only answer one of the two.
`is_early_career` is deliberately wide: junior, associate, entry level,
rotational and "Engineer I" all set it, and not one of them says new
grad. There was no way to ask the narrower question at all.

`is_new_grad` (migration 0028) is set by the gate from
`NEW_GRAD_TITLE_PATTERNS`, the subset of the early-career title
patterns that actually means "written for someone leaving university":
new grad, recent graduate, university graduate or hire, college grad,
campus, graduate programme, and a year followed by "grad". Live: 102
of 991, against 438 for Early career.

**Title only.** A description mentioning that new grads are welcome is
a weaker claim than a title announcing it, and this exists to be
trusted without opening the posting.

**Stored rather than matched in SQL at read time.** The alternative was
a second copy of the patterns as a Postgres regex, which is the drift
the company-tier work already learned to avoid, and which the SQLite
test database cannot run at all. One definition, in Python, beside the
rules that already read titles.

The `new_grad_first` sort now leads with the same flag, then
verification, then the wider early-career signal. A chip and a sort
both named "New grad" that selected and ordered different sets is
exactly the quiet disagreement the earlier entries already record fixing once.

`ELIGIBILITY_RULE_VERSION` bumped to `2026-09-11-v29` and the whole
corpus re-evaluated: 50,795 evaluations written, 0 left stale.

## Eightfold's country codes are also US state codes (2026-10-04)

Eightfold's standardized locations end in an ISO country code:
"Bengaluru, KA, IN". IN is also Indiana; CA, DE, ID, IL, CO and MO
collide the same way, and region codes too (TN: Tamil Nadu,
Tennessee). Four Qualcomm roles in India were in the queue as US jobs.
The adapter now writes the country out from `ISO_COUNTRY_NAMES`, joins a
posting's sites with "; " so two places do not run together, and
writes an unknown code as "City (XX)". The first draft wrote "outside
the United States (XX)" -- which the gate reads as the strongest US
signal there is. A test walks every entry of the table through the
gate, not a sample.

## Student roles by other names (2026-10-04)

"Part-Time Student" (John Deere, four titles), "Contract Student Worker"
(Zoox) and "Intership" (Microsoft, misspelt) were passing as full-time.
All three are now student roles beside "working student". Rule v36;
every active posting re-evaluated.

## Recent gate rules (2026-10-08 to 10-10)

- **Export control is not citizenship.** Only ITAR, an explicit U.S.
  person / citizenship demand, or access "without a licence" blocks.
  ServiceNow's licence paragraph rejected all its roles until gate v43.

- **"US" beside Canada is the US** (gate v50): "US / Canada", "Remote,
  Canada; Remote, US" were read as Canada. A remote "Americas" / "North
  America" role counts as open to the US (after the foreign-country
  check, so "Toronto, Canada (North America)" stays Canadian).

- **Data roles are off (v53)**: DATA_ENGINEERING and DATA_SCIENCE are
  classified (v51) but rejected as NON_TARGET_ROLE while
  `INCLUDE_NEW_GRAD_DATA_ROLES = False`. The user asked for new-grad data
  roles on 2026-10-09 and withdrew it the same day -- focus is software,
  ML and forward deployed engineering. With the flag on, only
  early-career postings below level II would pass.

- **Contract titles** (v50): contractor / freelance / temporary /
  fixed-term / AI trainer titles are CONTRACT_ROLE; "Smart Contract
  Engineer" is not. Contract-to-hire is rejected too -- the user asked
  for full-time only.

## Candidate profiles, SDE II, and two recall fixes (2026-10-14)

The owner has three years of experience. New grad roles stay the primary target (they sort first by default), and SDE II
is now wanted too. The gate's thresholds moved out of loose constants into a versioned `CandidateProfile`
(`eligibility.py`), chosen by `ACE_TARGET_PROFILE` at import, so the gate itself still reads no environment, clock or
network:

- `early-career` (default): unchanged thresholds. 4+ years rejected; open-ended "3+" rejected.
- `sde2`: identical except open-ended "3+" is admitted. 4+ or 5+, senior, staff, manager and L4/L5 stay rejected.

A decision records its profile's rule version, so switching re-evaluates stored decisions instead of mixing them.
`backend/scripts/gate_dry_run.py --profile sde2` lists, read-only, every job the switch would add or drop on the real
database; the owner reviews that list before switching.

Two recall fixes found while building the fixtures, shipped in v54 for both profiles:
- A bare "SDE II" (Amazon's short form) and "Software Dev Engineer" classified as OTHER, so every such role was
  rejected as non-target whatever its level. `roles.py` now reads `\bsde\b` as software engineering (`SDET` is not
  matched).
- `PREFERRED_CONTEXT_MARKERS` existed but was never used, so "3+ years preferred, 1+ years required" was rejected on the
  preferred figure. Experience figures in a clause that says preferred, nice to have, bonus or ideally now count as
  optional, like those under a "Preferred qualifications" heading.

After deploying v54, the stale-evaluation refresh re-evaluates the corpus (about 25 jobs a second). Tests:
`test_candidate_profiles.py` (the full matrix for both profiles), `test_gate_dry_run.py`.
