# The Chrome extension and form filling

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you change the autofill matcher, the panel, the answer bank or anything that touches a live application form.

## Applying faster: the bank was empty and hidden (2026-09-07)

The user asked to cut the time spent retyping the same details. The
answer bank built for exactly that had **all 16 fields empty**, and
`answerToggle()` returned nothing when no field was filled. The one
feature that would save the most time was the one the interface never
mentioned until it was already in use.

Phase 1, in ACE itself:

**Fourteen more fields** (migration 0020), taken from what real forms
ask: split first and last name, postal address, pronouns, years of
experience, "how did you hear about us", and the four voluntary
disclosure questions. Those four never change and are pure repetition,
which makes them the most valuable rows in the bank. Only missing
labels are inserted, so nothing the user has typed is overwritten.

**The button is always shown**, dashed and prompting when empty. The
panel groups 30 fields into seven sections, from a constant in the
client rather than a schema column, so an answer the user adds
themselves still appears under Other.

Phase 2 is `extension/`, a Manifest V3 Chrome extension covering
Greenhouse, Ashby and Lever, which took 40 of the first 76
applications. It fills and stops: it never submits, and never
overwrites a field that already has a value.

## What real application forms taught the matcher (2026-09-07)

Every rule below was written blind, failed against a live form, and was
corrected. Testing against fixtures would have shipped all of them.

**Question text, not the name attribute.** Those are generated per
tenant and carry nothing.

**The first source that names a field wins, never the concatenation.**
Joining every label looked thorough and was wrong: the Greenhouse
container around the sponsorship question also holds the preceding
"legally authorized to work" question, so every sponsorship field
matched work authorisation.

**A field's own group is the smallest block holding one control.**
Taking the first label in any ancestor matched whichever question came
first in a shared container.

**A radio's own label is the option, not the question.** Ashby's "how
did you hear about us" has an option reading "LinkedIn", which matched
the LinkedIn profile rule, so a stored profile URL would have ticked a
referral-source box. The question comes from the group; the option text
only decides which choice to tick.

**A heading that wraps a control is an option.** Lever puts each choice
in its own label, so the group question read "he/him".

**Strip a block's own controls before reading it.** A select carries
every option in its text: Lever's gender label reads "gender select
male female decline to self-identify".

**Whole words, with an optional plural.** "ethnicity" contains "city",
and a substring test put a stored city into an ethnicity question.
Adding word boundaries then broke "pronouns" against the rule
"pronoun", so a trailing s is allowed and nothing else.

Result across three live forms: 42 of 54 distinct questions answered,
and every one of the 12 left alone is correct. File uploads wait on
storing resume bytes; the rest are company-specific questions, consent
boxes, or questions with no row in the bank, and all of those are the
user's to answer.

`extension/test-rules.js` pins 34 of these cases, half of them
questions that must stay empty.

## Filling a live form found four more bugs (2026-09-07)

Matching the right question is half the job. Running the extension
against a real Lever form, with the user's own answers, broke the other
half.

**"female" contains "male".** The option test was a substring both
ways, so a stored answer that is a substring of another option (as "male" is of "female") ticked both boxes in the gender group. The same trap as ethnicity and city, one layer down. Options now
compare whole words.

**A checkbox reports value "on" whether or not it is ticked.** The
"already has a value, leave it alone" guard read `field.value`, so
every unticked box counted as answered and ACE skipped whole groups.
Nineteen fields on one form were reported as already filled when none
of them were. Emptiness is `checked` for a box, and for a select it is
a placeholder option, not an empty value.

**A select showing "Select ..." is empty.** Its option carries a real
value, so the same guard skipped the disability question.

**An answer that matches no option said nothing at all.** The question
was known, the answer was there, and nothing happened, which reads as
handled. The badge now names them: "Your answer matched none of the
options for: Disability status." A stored answer worded "no disability" matches none of Lever's wordings, and refusing to guess on
an EEO question is right, so the user is told what to reword.

Result on that form: 12 fields filled, one group per question, undo
restores all 12.

## The badge gave up before the form arrived (2026-09-07)

The popup said "27 of 30 answers saved" and "this page is one ACE
fills", and no badge appeared on a Netflix form. Connected, covered,
and silent.

**One pass at load is not enough.** The startup check waited for the
first `input` to exist, and a Netflix application page carries
cookie-consent checkboxes in its markup from the start, so the check
passed instantly and the real form mounted seconds later against a
badge that had already removed itself. A debounced `MutationObserver`
now recomputes as the page changes, which also covers a multi-step form
where later steps mount as the user advances.

**A frame can run before `document.body`.** `document_idle` should
guarantee one, but the script runs in every frame, and the first
`appendChild` would throw and kill the extension silently.

**React drops the class ACE puts on a field.** The values survive, the
gold outline does not, so the user cannot see what was touched. It is
re-applied whenever the page settles.

Verified on the live Netflix form: 8 fields filled, values persisted
through React, outline visible, undo clears all 8.

**The harness lied twice before any of this was found.** Headless
Chrome does not run extension content scripts even with
`--load-extension`, so the files are injected directly. Injecting them
as one concatenated string is not the same as the manifest's two files:
the string threw at document-start, and because function declarations
hoist and `var` assignments do not, `aceQuestionFor` existed while
`ACE_RULES` was undefined. That looked exactly like a broken matcher.
Inject each file as its own script.

## A real form exposed a whole control type the extension had never met (2026-09-09)

The user sent screenshots of a Handshake application. It runs on
Ashby, already supported, and most of it already worked. Two things
did not, both found by driving the real page rather than guessing.

**A comma broke a phrase match.** "Will you now, or in the future,
require sponsorship for employment visa status?" reads as one
question, and the rule for it was written as the contiguous string
"in the future require". The real form's own punctuation put a comma
between "future" and "require", and a substring test does not see
through one. `aceNormalise` now turns `,`, `;` and `:` into spaces
before anything is matched, since any multi-word phrase in the rule
table was equally exposed and not just this one.

**Ashby has a second choice widget.** Every group so far was a real
`<input type=radio>` or `<checkbox>`. "Are you authorized to work
lawfully..." and the combined sponsorship question are neither: two
real `<button>` elements with `aria-pressed` and a `data-option`
attribute, plus a hidden, unfocusable checkbox that is not the thing
to click. `fillable()`, `groupMembers()`, `aceIsEmpty()` and `undo()`
all special-cased radio-versus-checkbox by `field.type`, which a
button has no meaningful value for, so each was rewritten against one
shared `aceIsChoiceControl()` predicate that also recognises
`button[data-option]`.

Undo needed its own check against the live control before trusting an
assumption: does clicking an already-selected Yes button toggle it
back off, or does Ashby's widget have no way back? Verified against
the real form -- it toggles -- so undo re-clicks the button it clicked
rather than trying to set a `.checked` property a button does not
have.

Two questions on the same form, "willing to relocate" and "willing to
work onsite", had no row in the bank at all. Added blank in migration
0022, the same treatment every earlier addition got: the questions are
predictable, the answers are the user's.

Verified against the live Handshake form, not a fixture: 14 of 18
fields filled, all three Yes/No button pairs correctly pressed and
correctly reversed by undo, the relocation radio group correctly
resolved among three options rather than two. The stub answers used
for that test never touched the real answer bank, confirmed by reading
it back afterward.

## A wrong autofill value, not a missing one (2026-09-09)

The user reported "How did you hear about us" filled in as "Search
Engine" on a real Applied Intuition form, when the stored answer is
"Job Portal". Confirmed live: this field is a controlled autocomplete
(`role="combobox"`), its real options rendered only once the listbox
opens, and none of its 23 real options -- AngelList, Conference,
LinkedIn, Search Engine, Other, and so on -- is "Job Portal". The
fallback path typed the raw text into the input anyway, and Ashby's
own widget silently defaulted to some option of its own on blur
rather than either rejecting it or leaving the field alone.

A wrong autofilled value is worse than every other failure mode this
extension has, because it looks handled: the field is not blank, the
badge said "filled", and nothing prompts a second look before
submitting. Every other mismatch this session left a field blank or
named it in "unmatched"; this one silently wrote something false.

The fix does not try to make the synchronous fill path smarter about
this widget -- it cannot be, since its options do not exist until it
is opened and that render is asynchronous, confirmed against the live
control: reading `[role=option]` in the same tick as the click that
opens it finds nothing. Autocomplete fields are now excluded from the
generic text path entirely and handled by a separate async pass after
the rest of the form fills: open, wait for the listbox, click a
matching option, or close it and leave the field untouched if nothing
matches. Preview cannot open the listbox before the user has consented
to anything changing, so a combobox with a stored answer is shown
honestly as "value (if listed)" rather than a promise.

Verified against the real bug: "Job Portal" now stays blank and is
named under "Reword these in ACE" rather than becoming "Search
Engine". Verified the repaired path too, not just the safe failure: a
stored answer of "LinkedIn" opens the listbox, finds the real option,
clicks it, and undo correctly clears it back to blank.

## The extension test harness had never tested the extension (2026-09-10)

The user sent a screenshot of a live JazzHR application with ACE's
popup saying it had not loaded, and said the extension was not working.
Two separate faults, and the second is the one to remember.

**A content script only injects while a page is loading.** A tab that
was already open when the extension was reloaded has none, whatever the
manifest says, and the popup's advice -- reload the page -- was a poor
answer to that. The popup now injects on demand: `chrome.scripting`
with the `activeTab` grant that opening the popup already gives, a
"Fill this page" button, and a `wake` message that runs ACE whether or
not the page passed the heuristic, because a user clicking Fill is a
better signal than any heuristic. `content.js` sets a flag on `window`
and returns early if it is already there, so injecting over a script
the manifest already placed is harmless.

**Every test so far had eval'd the scripts with a mocked `chrome`.**
That validates the matching logic and cannot catch a manifest,
permission or messaging fault -- exactly the class this turn was about.
Trying to load the real unpacked extension in headless Chrome failed:
recent builds disable `--load-extension` unless
`--disable-features=DisableLoadExtensionCommandLineSwitch` is passed,
and even then it did not attach here. So this remains untested end to
end, and that gap is worth naming rather than papering over.

What the honest fixture did find, once it stopped mocking the page's
own markup, were three real bugs on a form whose labels are not
associated with their inputs -- which is JazzHR, and common:

- The fallback to the `name` attribute yields `first_name`,
  `last_name`, `start_date`. `aceNormalise` left underscores alone, so
  none of them matched a rule phrase written with spaces. Now split;
  hyphens still stay, or "e-mail" stops reaching the email rule.
- `postal` bare did not match "postal code".
- **"No answer" was treated as an answer.** It is JazzHR's default for
  every dropdown, so ACE reported the relocation and felony questions
  as already filled and skipped them. Added to the placeholder list,
  along with "select one" and "n/a" -- but deliberately not "none",
  which a person can actually mean.

Before: 5 of 12 fields. After: 12 of 12.

## The host list was the reason nothing autofilled (2026-09-10)

Mid-way through building the repeating work-history section, the user
sent a screenshot of ACE's own popup on a live application saying
**"ACE does not fill this site."** That was the real blocker, and it
had nothing to do with matching.

The manifest named the boards ACE ran on. Measured against the real
applied history, **a substantial minority of applications went through
19 hosts it did not cover** -- stripe.com, careers.roblox.com, www.ixl.com, nuro.ai,
www.esri.com, and a different `*.oraclecloud.com` subdomain for each
Oracle tenant. Most companies self-host their own board, so the list
was a game with no last move: every fix covers one employer.

So the extension runs on `http://*/*` and `https://*/*` and decides per
page. Counting boxes is not enough on a page that could be anything, so
`looksLikeApplication()` also requires that ACE recognise at least two
of the questions -- which costs nothing, because naming a question needs
neither the network nor any stored answer. Nothing is fetched until
that passes, so the script loading everywhere does not mean reaching
for localhost everywhere. A form built after load still counts: a page
that is not one yet is watched rather than given up on.

The popup now asks the page instead of guessing from the host, and
reports how many questions ACE recognises there. A page where the
content script never loaded does not reply at all, which is the one
case the host list genuinely could describe.

## Repeating blocks: the Nth job into the Nth block (2026-09-10)

Forms ask work history as one block repeated -- employer, title, a
Yes/No for whether it is current, four date dropdowns, a description,
then a Remove link and another identical block underneath. The answer
bank could not hold it, and the reason is structural rather than a
missing rule: the bank is one value per question, so a form's second
block asks the same questions as the first and would get the same
answer back.

`history_entries` (migration 0026) holds them as a list, most recent
first, which is the order every one of these forms uses. Work and study
share the table because they share a shape; the columns are named for
the job case and reused for the degree case, a small dishonesty in the
names bought for one set of date handling and one extension code path.
Dates are a month and a year, not a date -- that is what the dropdowns
ask for, and a real date would mean inventing a day nobody typed.

The extension finds blocks by anchoring on the employer box: one per
block, present in every block, and the thing the block is about. A
block is the smallest ancestor holding that box and no other. Every
other history field is then assigned to whichever block contains it,
and the entries are handed out by position.

Three bugs, each worth keeping:

**"Current Employer" contains "employer".** First-match role detection
read the Yes/No beside the dates as another employer box, so every
radio became its own block and the form came out as four blocks of one
field each. Fixed by scoring on matched phrase length, the same fix the
answer rules already needed.

**Climbing the ancestors to tell a start date from an end date finds
nothing.** On a real block the four dropdowns and both headings are
siblings, so every ancestor holds "Start Date" and "End Date" together
and therefore names neither. Fixed by reading backwards through the
block in document order, which is how a person reads it: the nearest
heading above a dropdown is the one that names it.

**`aceHeadingIn` took the first heading in a block, not the nearest
above.** That was right only while a block held one question. On a
repeating block the "Current Employer" group read its question as
"Employer", the label of the box higher up the same block. Fixed to
take the nearest preceding heading, and to accept real headings as
candidates -- a form writes "Current Employer" as an h4, not as a
label, because it names a group rather than one input.

Verified end-to-end in real Chrome against a two-block form: block one
took the current role with its start date and no end date, block two
took the earlier job with May 2021 to December 2024. The Dell form was
re-checked afterwards, because the heading change is shared code.

## The bank was a pile of text boxes, and that was the wrong shape (2026-09-09)

The matcher rebuild left one thing untouched and the user went
straight to it: every question in the bank, including the ones a form
only ever asks as Yes/No or as a dropdown, was answered by typing into
a text box. The advice that came with it -- fill in thirteen boxes with
the word "No", and hand-write `LinkedIn | Job Board | Job Portal` so
the matcher has synonyms to try -- is what they rejected, and they were
right to.

Two jobs were on the user that are not theirs.

The first is obvious in hindsight: a question with two possible answers
should be two buttons, and a question with a known set of answers
should be that set. Typing "No" is data entry, not a decision.

The second is the one that mattered. A typed answer has to match
wording ACE has never seen. A stored "Job Portal" matches nothing on a
Dell form offering "Job Board (e.g., LinkedIn, Indeed, Glassdoor)", and
nothing at all on one offering only "Indeed". Asking the user to
enumerate the synonyms put the burden exactly backwards: knowing that a
job board and a job portal are the same thing is ACE's job.

So `backend/app/answers/catalogue.py` now declares what each question
is -- boolean, choice or free text -- and, for the choices, the
wordings a real form might print for each option. The answers page
draws a toggle, a list or a text box accordingly, and the label stops
being editable for anything ACE ships, because the label is the key the
extension's rules resolve to and renaming it would break the match
silently, on some future application. `/api/answers` sends the shape
and the aliases for whatever is stored, so the extension recognises the
concept under the form's own name. The user picks once and never a
wording.

Free text stays free text. A name is not a choice.

Verified end-to-end against a form built to Dell's markup: a stored
"Job board" fills "Job Board (e.g., LinkedIn, Indeed, Glassdoor)", and
an answer stored as one wording (say "Male") fills a form whose option reads "Man". Both of those
were blank before. The one gap found while verifying is worth keeping
in mind -- the preview had its own copy of the select path and did not
get the aliases, so it reported "matches no option" for a field the
fill would then have filled anyway. A preview that disagrees with the
fill is worse than either being wrong alone, because it is the thing
the user is trusting.

## One real Dell form answered the matcher's whole design (2026-09-09)

The user said the extension was "not at all good" for real
applications, and sent a Dell application as evidence: twenty-two
questions, all of them standard, none of them unusual. Measured
against it, the matcher recognised **four** and mis-routed **five**.

The mis-routings were the serious half, and each had the same shape.
"Is the role you are applying for located in the United States?"
matched the rule for a postal **state**, because "state" sits inside
"States". So did the trade-embargo question and the state-government
question. "Are you a recent graduate (less than 3 years since you
completed your most recent **degree**)?" matched the degree rule. A
free-text answer being offered to a Yes/No question is the same class
of bug as the combobox that wrote "Search Engine" over "Job Portal":
the field stops looking unanswered, so nothing prompts a second look.

Three changes, and it is worth being clear which one did the work:

**The shape of the answer is now checked against the shape of the
control.** A group whose every option is an unambiguous yes or no
cannot hold "Masters in Computer Science", so a rule whose answer is
free text is refused there outright. This alone killed four of the
five mis-routings, and it needs no per-question tuning: it is a fact
about the control, read off the page.

**The longest matched phrase wins, not the first rule in the list.**
Ordering was load-bearing and silently fragile -- a broad rule listed
first swallowed every narrow question beneath it. Ties still keep list
order, so the existing arrangement of narrow-above-broad still holds.

**Buttons that declare themselves a choice are now found.** Ashby's
Yes/No pair is marked with `data-option`, and matching only that meant
ACE could not see a single one of Dell's twenty-two questions: Oracle's
Candidate Experience marks the same shape with `aria-pressed` instead.
Every button is now considered and filtered on the attributes that
declare a choice, which a submit button never carries.

The taxonomy also grew from roughly thirty questions to sixty, and
migration 0024 adds the twenty-six answers behind them, seeded blank.
Worth noting what the commercial tools do here: Simplify and JobRight
deliberately leave sponsorship, work authorisation and EEO to the user,
because their answers differ per person. ACE has one user whose answers
do not change, so it can answer exactly the questions they skip -- which
makes the polarity the entire job. "Are you authorised to work" and "do
you need sponsorship" are both Yes for a candidate who needs sponsorship, and they are not the same
question.

Verified twice: 21 of the 22 answered correctly with none wrong as a
pure rule check, then end-to-end in real Chrome against a form built to
Dell's markup, where all twelve applicable fields filled, "WA" reached
the state box and none of the three questions naming the United States.
The one left blank is honest -- a stored "Job Portal" matches no option
on a form offering "Job Board (e.g., LinkedIn, Indeed, Glassdoor)".
Rather than teach it that portal means board, a bank answer may now
hold alternatives separated by `|`, tried in turn; the refusal to
choose between two equally good options is unchanged.

## The fill panel sat on top of the real Submit button (2026-09-09)

Reported directly: on a CareerPuck form, ACE's own panel was pinned
over the page's Submit button, and there was no way to get it out of
the way to click through. Two separate bugs, both in `content.js`/
`content.css`:

The panel was anchored `bottom:18px`, the one corner of the page a
form's own primary action is almost always in too. Moved to
`top:18px` -- a location a Submit control essentially never occupies.

Worse, the panel's close button did not actually close it. A
`MutationObserver` re-runs `refresh()` on any DOM change (this is how
ACE notices a client-routed page has changed), and `refresh()` always
called `showPreview()` again whenever no fill had happened yet,
regardless of why the panel had been removed. On a real form, typing
a single character is a DOM mutation, so the panel came back within
400ms of being closed -- closing it bought less than half a second.
Fixed with a `dismissed` flag set by the close button and checked
before `showPreview()` runs again. It has to reset on a genuine
navigation, or dismissing the panel on one posting would leave it
permanently off for every later posting visited in the same tab
without a full page reload (several boards route between postings
this way); `refresh()` now treats a `location.href` change as exactly
that reset point.

Verified live against an isolated headless Chrome with the real
`content.js`/`fields.js`/`content.css` loaded (not the user's browser):
the panel does not overlap a bottom-right Submit button after
repositioning; closing it survives repeated DOM mutations; a same-tab
`pushState` navigation correctly brings it back for the new page.

## A filled box that still submitted as empty (2026-09-11)

The user reported three things about the extension: it fills
inaccurately, it leaves a brown background on what it filled, and some
forms still say a field is required when the answer is visibly in it.
Two had a cause; the third needs a form to look at.

**"Required" on a filled field.** `setNatively` wrote through the
prototype setter and fired `input` and `change`, which is what makes
React see a real edit. What it never did was focus or blur. Formik and
React Hook Form mark a field touched, and run its validator, on blur
and not before, so a box ACE filled correctly was never revalidated
and the error raised against the empty field stayed up through submit.
It now focuses before writing (`preventScroll`, or a long form scrolls
to each field in turn) and blurs after.

Also rewinds React's value tracker first. React records the last value
it saw on the node and discards an `input` event that still agrees
with that record, so filling a value React already held was a no-op.
Rarer than the blur case, and cheap to make impossible.

**The brown background** was `.ace-filled`: a permanent 2px `#c9a227`
ring, gold being ACE's signal colour and also almost exactly what a
form uses to flag a problem. Every correctly filled field wore a
warning. It is now purple, and clears itself 3.5 seconds after the
fill: the marker exists to show what ACE just touched, the panel
already lists all of it, and there is nothing for a ring to keep
saying afterwards. `paint()` re-applies the class after a re-render,
so it now checks the faded set rather than resurrecting it.

**The gap this closed.** `extension/test-rules.js` tests which
question a field *is*, and nothing tested what happens once ACE
answers one. `backend/tests/browser/test_extension.py` loads the real
`fields.js` and `content.js` into real Chrome against a form carrying
a React-style tracker. content.js is one IIFE, so it now ends with a
`window.__aceInternals` seam; a content script has its own isolated
world, so that is invisible to the page.

**Headless Chrome fires no focus or blur events**, because the
document itself is never focused, while moving `document.activeElement`
correctly. The first version of the focus test failed against working
code for that reason. It now records `activeElement` inside the
`input` listener, which does fire, and checks the field is no longer
active once the call returns.

Still open: "not working accurately" is not yet reproducible, and
guessing at matcher rules is exactly what the earlier entries record going wrong
before. It needs the site and the fields it got wrong. Worth ruling
out first that the extension was never reloaded (an open item for the user), since
an unpacked extension keeps running the old build until it is.

## The panel was unreadable, and the marker was unwanted (2026-09-11)

The user sent two screenshots of a live OpenAI form on Ashby. Three
things wrong, all visible in the pictures.

**The panel's own text was drawn on top of itself.** Title over
subtitle, every listed field over the one above it, none of it
readable. The panel was a plain `div` under `document.body` with
`content.css` injected beside it, so the employer's stylesheet reached
straight into ACE's markup; Ashby flattens line heights and the panel
collapsed. Hardening the CSS does not settle this, because the next
board resets something else.

It now mounts in a **shadow root**. Nothing the page declares crosses
the boundary in either direction, so ACE cannot be restyled by a form
and cannot leak onto one. `content.css` is gone: the stylesheet is a
string in `content.js` and goes inside the shadow root, which also
removes the `insertCSS` call from the popup and the `css` entry from
the manifest. Two consequences worth knowing:

- An event crossing a shadow boundary is **retargeted to the host**,
  so a document-level `closest("[data-ace]")` finds nothing. The click
  handler is bound to the shadow root instead.
- The host node carries `all:initial` and is 0x0, so it is the one
  thing the page can see and there is nothing on it to style.

**The fill marker is gone entirely, at the user's request.** It had
been a permanent gold outline, then a purple one that cleared itself
after 3.5 seconds. The user's comparison was a browser's own autofill:
"it happened seamless and accurate with no highlighters". They are
right that a marker on a form about to be sent to an employer is ACE
announcing itself for no benefit, since the panel already lists every
field it touched. `markFilled`, `paint()` and the `.ace-filled` rules
are all removed; a test pins all three, because removing one and
leaving the others is how a marker comes back.

**"Filled 0 fields, 7 already had a value"** on a form ACE had in fact
just filled correctly. `runFill` sets `lastResult` only after the
combobox pass, and that pass takes seconds: it opens each autocomplete
and waits up to 1500ms for options. Meanwhile the plain fills mutate
the page, the MutationObserver fires, `refresh()` sees no `lastResult`
and redraws the **preview, Fill button and all**, over the "Filling..."
panel. Clicking it ran a second pass that found its own work already
done and reported it as nothing to do.

A `filling` flag now holds from the first line of `runFill` until
either exit path, and `refresh()` returns early while it is set. Not
covered by a test: reproducing it needs a live combobox and the
observer's 400ms debounce, and a test that fakes both would pin the
fake rather than the race.

## The panel now says which build it is (2026-09-11)

A bug was reported twice from screenshots of a build that had already
been fixed. Both times the panel looked exactly as it had before the
fix, because a content script only injects while a page is loading:
reloading the extension leaves every already-open tab running the
previous one, and nothing on screen distinguished them.

The manifest version is now printed in the panel header, quietly, at
the right. It costs ten pixels and it answers "is this the build I
think it is" from any screenshot without asking the user to check
anything. Version is read from `chrome.runtime.getManifest()` rather
than written twice.

**Reloading the extension is not enough. The tab has to be reloaded
too**, or ACE's own popup used, whose Fill button injects on demand.

## A whole DoorDash form filled nothing, and why (2026-09-11)

The user filled twelve dropdowns by hand and sent before-and-after
screenshots. Diagnosed against the **live** page in headless Chrome
with the real `fields.js` and `content.js` and the user's real answer
bank, rather than reasoned about: every conclusion below was measured.

**The matcher was never the problem.** Against the real DOM it
resolved work authorisation, both sponsorship questions, gender,
ethnicity, disability and more, and correctly returned nothing for the
company-specific ones. The failure was entirely in the combobox
mechanics, which is not where the complaint pointed.

**`comboboxOptions()` read any listbox on the page.** It was
`document.querySelector("[role=listbox]")` -- the first one in the
document, whatever it belonged to. Greenhouse's form keeps a phone
country-code list of **244 options** permanently mounted, so every
question on the form was answered against a list of countries,
matched nothing, and was left blank.

Blank was the lucky outcome. A stored country of "United States Of
America" against an option reading "United States +1" is the kind of
near-match `aceChooseOption` accepts, and the click would have landed
inside the phone widget: a wrong answer on a form about to be sent to
an employer, which is the one thing this extension exists not to do.

The lookup is now scoped to the field: `aria-controls` or `aria-owns`
first, then a climb bounded to five ancestors that stops at `<body>`,
at a `<form>`, and at any subtree holding a second combobox. All three
bounds are pinned by tests; without the depth bound the climb reaches
`<body>` and finds the stranger again, which is how the first version
of the fix was caught.

**The menu never opened.** `.click()` on the input dispatches a click
and no mousedown, and react-select -- which is what Greenhouse renders
-- opens on mousedown. Measured: `aria-expanded` stayed `false` after
`.click()`, after a dispatched ArrowDown, and even after a real
trusted CDP click. A full `pointerdown, mousedown, mouseup, click`
sequence on the control, plus ArrowDown as the ARIA fallback, opens
it: `aria-expanded` true, and the scoped lookup then returns
`Yes | No` instead of 244 countries. The existing toggle-button path
is tried first and untouched, because that is what Ashby needs.

**"telephone calls" swallowed a consent question.** DoorDash asks
whether you want SMS and WhatsApp updates and explains that otherwise
"we will only communicate with you via email and/or telephone calls".
The phone rule matched on the word buried in the explanation, so ACE
would have typed a phone number into a yes/no. Guarded.

Measured on the live form, before and after: nothing filled, then
**work authorisation, sponsorship now, sponsorship in future, gender
and disability status** all correct.

**Still not filled, and honestly so.** Country, city, university and
degree are type-to-search comboboxes whose options load only once
something is typed, which ACE does not yet do. Ethnicity has an answer
stored but its options did not open in the probe. Sexual orientation
and transgender have no answer saved (open items for the user). None of these are guessed
at, and the panel names every one.

## An application is several pages, and ACE saw one (2026-09-11)

The user, on a Workday form: "if there are multiple pages it's loading
only once, when I go to the next page even if data is there it's not
filling."

`refresh()` cleared `lastResult` only when `location.href` changed.
Workday's application is a wizard that swaps the whole step without
touching the URL, so after the first page was filled every later step
returned early: the panel never came back and nothing was filled
again. Invisible on any single-page form, which is every form that had
ever been tested.

A step change is now detected from the fields themselves. ACE holds
the nodes it filled, and a step that has been replaced has taken all
of them out of the document. That evidence is narrow on purpose: a
conditional question appearing in answer to something ACE just filled
leaves those nodes connected, so the result panel stays up instead of
being replaced by a fresh preview the moment it reports. With nothing
filled there are no nodes to ask, so a signature of the questions on
screen is compared instead.

`lastFill` is cleared at the same time. Undo cannot apply to fields
that are no longer in the document, and keeping them would make the
step check answer about a page that is gone.

## Forms behind a login cannot be read from outside (2026-09-11)

The DoorDash fix was measured against the live page. Workday, Oracle
and the rest put the form behind an account, and creating one on an
employer's recruiting system to read their markup is not a thing to
do. So that diagnosis is unavailable, and guessing at markup is what
The earlier entries already record going wrong repeatedly.

The panel therefore carries **"Copy what ACE sees"**: every question
found, the widget shape, whether the field already had a value, which
bank entry it matched, and for a combobox the options it can actually
read. The user pastes that and it is the whole diagnosis, with no
developer tools.

It deliberately carries no answer values, only the matched label and
what the page itself offered. The text is going somewhere else by
definition, and the bank holds a home address and demographic answers.

## A dial code is not part of the country's name (2026-09-11)

MongoDB's own careers form, not the Greenhouse one behind it. ACE
reported Country and City under "reword these in ACE", which means it
found the questions and read their options and simply could not match
the answer. The form then blocked on "Select a country", and rejected
the phone number it had filled along with it.

The widget is a phone country picker, and its options print the dial
code beside the name: "United States +1". `acePhraseIn` asks whether
one phrase sits inside the other, and with the code attached neither
direction holds against a stored "United States Of America".

`aceChooseOption` now retries containment against options with
`+<digits>` stripped, and **only** against options the stripping
actually changed, so a form carrying no dial codes cannot reach that
branch and cannot gain a match it would not otherwise have had. Where
more than one survives, the closest wins rather than the first: that
list holds "United States" and "United States Minor Outlying Islands"
together, and a first-match rule picks between them by accident.

Four cases pinned, two of which fail without the change. One of the
four carries no dial code at all and must stay unmatched, because the
risk in loosening an option matcher is never the case you are looking
at.

**Not verified against the live form.** MongoDB's careers page renders
its application late enough that a headless load sees only the site's
search box, so unlike DoorDash this was worked from the screenshot and
the reported symptom. The option text is inferred from the widget
showing "+1". Confirm with "Copy what ACE sees" before treating it as
settled.

## Filling the country emptied the phone (2026-09-11)

A Jump Trading form, and a regression caused by the fix two entries
above. Phone read **"+1"** and nothing else.

Comboboxes are filled in a second pass, because each one has to be
opened and waited on. So `plan()` wrote the phone number, and
`fillComboboxes()` then chose the country beside it -- which it could
only do at all because the dial-code matching had just been added --
and the phone widget reset the number box to its country prefix. ACE's
own two passes were fighting each other, and the second won.

`restoreClobbered()` runs after the combobox pass and puts back any
value ACE wrote that is no longer there. It walks **ACE's own record**,
not the form, so a field ACE never filled is never touched.

The hard part is telling a clobbering from a reformatting. A phone box
that renders "+1 206 555 0100" as "(206) 555-0100" has kept the number,
and rewriting that would be a fight with the page that never settles.
The comparison is on letters and digits alone, and when one side
contains the other and is at least five characters long it counts as
the same content. Five, because the value this exists for came back
holding a single "1".

The restore is deliberately blunt about anything else in the box: it
runs once, seconds after the fill, in the gap the combobox pass
occupies, and in that window a changed value is a widget rather than a
person. Nothing runs again afterwards, so a later edit by the user
stands.

**The test had to be rewritten before it was worth anything.** The
first version reimplemented the comparison in the test and asserted
against its own copy, which is the trap this file already names: it
pins the fake, not the code. It now pushes a real record through the
real function via the seam. Confirmed to fail with the restore
disabled -- and the first attempt at that mutation silently matched
nothing and "passed", which is its own reminder to check the mutation
took.

## The work-history dates were never fillable (2026-09-13)

Title, company, location and description filled on every block; the two
required date boxes and the "I currently work here" tick never did. Two
unrelated causes.

**A combined date box had no role.** `ACE_HISTORY_ROLES` knew
`startMonth`, `startYear`, `endMonth` and `endYear`, which is what a form
looks like when it splits the date into two dropdowns. The form in front
of the user has one box labelled **From** with an `MM/YYYY` placeholder,
and nothing matched it. `startDate` and `endDate` now do, sitting below
the split rules so longest-match still resolves "from month" to
`startMonth`. Bare "from" and "to" are only safe as rules because these
apply **inside an established history block**; in `ACE_RULES` they would
swallow half the form.

The format is read from the box rather than chosen: forms disagree
between `MM/YYYY`, `MM/DD/YYYY` and `YYYY-MM`, and the placeholder is
where they say which. An unrecognised hint falls back to `MM/YYYY`.

A current role returns **no** end date. Writing one would be a lie about
the entry, and the "currently work here" box is what carries that fact.

**A lone checkbox was being asked to choose.** A checkbox reaches the
choice path, which matches the stored answer against the option text of
its group. For a single checkbox that text is the statement it asserts,
"I currently work here", which no affirmative answer will ever match, so
it was reported as "your answer matched no option" and left clear on
every block. A single checkbox carries no choice: it **is** the answer,
and `aceIntent` decides it.

It stays clear on "No", and the asymmetry is the point: a missed tick is
a box the user notices and clicks, while a wrong tick tells an employer
they still work somewhere they left in 2024.

17 new cases, 6 of them confirmed to fail against the bug first.

## The phone widget needed answering in the right order (2026-09-17)

Extends the 2026-09-11 entry above, from a live form. Two symptoms, one
cause: Phone came out reading **"+2065550100"** with the dial code
eaten, and after the user picked the country by hand it read **"+1"**.

The country box beside the number was never filled at all, because
"country code" is ruled out of the country rule. That is right for a
bare text box, which wants "+1" and not a country name, and wrong for a
dropdown, whose options read "United States +1" -- which
`aceChooseOption` has stripped dial codes for since MongoDB's form. The
rule now splits on the shape of the control: a rule may declare
`needs: ACE_CHOICE` and be refused against anything that offers no
options, and an autocomplete reports as a choice for the same reason a
`<select>` does.

Answering it is not sufficient. `restoreClobbered()` covers a widget
that *resets* the number, and still does. It cannot cover one that
*reformats* it: the restore writes the number back, the widget eats the
code again on the next input event, and the check runs once. So the
phone country is now settled in a pass **before** the plain fields
rather than the one after, which is also simply the order a person
fills it in.

Third: a number box holding nothing but a dial code now reads as empty.
The widget writes "+1" there itself the moment a country is chosen, and
counting that as an answer made ACE skip the phone field and report it
already filled -- the user looking at a Phone containing "+1" beneath a
panel claiming success. Same idea `aceIsEmpty` already encodes for a
`<select>` showing "Select ...".

**Two tests, because one of them proves nothing on its own.** The reset
case passes with the old ordering too, since restore catches it. Only
the reformat case fails without the reordering -- and it fails
reproducing the reported value exactly, `+2060000000` against the
user's `+2065550100`, which is what confirmed the diagnosis rather than
merely being consistent with it.


## Pairing (1.21.0, 2026-10-14)

ace now asks who is calling, so the extension carries its own token
(see 07, "Owner sign-in with extension pairing"). Popup, Connection: a
pairing code from ace Settings, Pair, and Unpair. The service worker
adds `Authorization: Bearer` to every read and reports a 401 as
`unpaired`, which both the popup and the in-page panel turn into the
remedy. Only the extension's own pages may pair or unpair, never a
content script. An `https://` address (the cloud deployment) asks
Chrome for that origin when it is saved (`optional_host_permissions`).
Backward compatible: against an ace without sign-in it behaves as 1.20.
Host permission is now any localhost port (`http://localhost/*`; a
pattern without a port matches every port), so a second API on 8001 for
testing a branch can be paired too. Verified in Chromium on 8000 and 8001.

## The panel and popup take the website's typography (2026-10-24)

The website moved to the approved Refined typography (05). For one look across ace, the Apply Studio panel and the
toolbar popup now use the same face and scale.

- The panel asked for "Inter" (Apply Studio rules) or "Geist" (the older rules), but neither was packaged, so it showed
  whatever system face the computer had. Inter 4.1 now ships in `extension/fonts/` with its OFL licence.
- A shadow root cannot declare `@font-face`, so `loadPanelFont()` adds the face to the page's document with the FontFace
  API, under the name `ace-inter`, only when a panel opens; pages without a panel never see it. The file is listed in
  `web_accessible_resources`. If a page refuses it, the panel keeps the system face and works the same.
- Sizes are px tokens on `.ace-panel` mirroring `globals.css`: rem inside a content script would follow the employer
  page's root size. The popup is an extension page, so it uses a plain `@font-face` with a relative URL.
- The uppercase eyebrow became sentence case by removing `text-transform`; the text was already sentence case.

Checks: `test-rules.js`, `test-memory.js` and the `web/tests/e2e/extension-*.spec.ts` tests pass. Those tests stub
`chrome.runtime.getURL`, so they cover the fallback path; serving the extension folder over HTTP showed the face loading
in Day and Night with no page errors.

## Focus Mode V5.1 keeps employer motivation on the employer form (2026-10-24)

The V4 full-height panel used a generic textarea for every unknown question. That made a dropdown require the applicant to choose once on the employer form and type the answer again in ACE. It also pulled company-motivation prompts into Review, where ACE had no business storing a response.

The existing content script now renders the approved compact Wine and Rose Focus card, a persistent Review state, optional Workspace and a minimized dock. The shadow-root panel remains part of the original MV3 extension and keeps its answer bank, pairing, history and form adapters. Dragging works from the six-dot grip and non-interactive card surfaces; position is normalized to the viewport and stored in Chrome. The same approved answer is never interpreted as employer submission.

`aceMemory.isEmployerMotivation()` classifies question labels before the form scanner can read input values. Scan, Fill, diagnostics, Review and progress all share `fillable()`, which excludes these fields. Historical Memory rows are filtered in the extension without deleting them. The classifier has cases for employer-specific variants and counterexamples for ordinary technical `why` questions.

Review mirrors native select and choice options exactly. If a Workday-style listbox exposes its actual options when the applicant opens it, ACE mirrors those choices and verifies that the employer control accepted the selection. Inaccessible custom controls remain on the employer form. Approved reusable answers use the existing V4 API; protected questions are per-application only. Review stays open after approval and Skip; skipped questions show `Review paused`, not a false completion.

The extension-only upgrade requires no schema migration. Browser fixtures cover Day and Night, narrow widths, drag, dock, dropdown synchronization, motivation exclusion, dynamic questions, Memory and the no-submit invariant. The older V4 browser regression was updated for the approved interface while retaining its behavioral checks. No production deployment or extension publication was performed in this implementation step.

## Focus Mode V5.1 visual correction and Workday listing guard (2026-10-25)

The initial Focus implementation retained a V4-style compact overview with different spacing, status counters and plain Scan fields text. It looked unlike the approved V5.1 card. The compact card now uses the reference's short control statement, ready-to-review status block, check and scan icons, two equal action buttons, exact 318px width, 16px outer radius, theme colors, header and footer geometry. Review inherits the same reference typography, spacing, border treatment and three-button action row. These changes stay inside the existing shadow-root panel.

A Workday Search For Jobs route previously could satisfy the generic form heuristic because its filters resembled application questions. Workday pages outside `/apply/` now remain quiet, and navigating back to a listing within a Workday SPA removes an open ACE Review card. The explicit toolbar Wake path remains available. A browser fixture verifies listing, explicit Wake, application and listing transitions. The 7-test Chrome extension suite passes; the matcher and memory safety checks also pass. No extension publication or production change was made.

## Continuity and release boundary (2026-10-25)

The local Focus Mode V5.1 branch is at `cb7bb5e`, with the previous V4 Answer Memory API and migration 0050 code at `2e7c1dc`. The owner approved deployment of that V4 backend migration, but this branch has no post-release verification of the production revision or live Memory API. Do not assume Memory is available in production until checked read-only. The tracked remote branch separately contains approved Inter typography for the extension at `61debd6`; its three typography commits must be reconciled with the two local V5.1 commits before publication. The updated root `ACE_NEXT_KNOWLEDGE.md` is the cross-session state source.
