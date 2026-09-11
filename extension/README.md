# ACE Autofill

Fills the fields every application form asks for, from the answer bank
in your local ACE instance. It fills and stops: nothing here submits a
form, and nothing overwrites a box that already has something in it.

Runs on every site and decides per page, rather than from a list of
supported hosts. The list could not be made to hold: most companies
self-host their board and Oracle gives every tenant its own subdomain,
so a substantial share of one real user's applications went through 19
hosts a list did not name.

## Install

1. Open `chrome://extensions`
2. Turn on **Developer mode**, top right
3. **Load unpacked**, and choose this `extension` folder
4. Fill your answers in ACE first, under Answers. An empty bank fills
   nothing.

ACE itself has to be running, since the answers are read from it.

If ACE runs somewhere other than `http://localhost:8000`, set the
address from the toolbar icon.

## After changing anything in this folder

Open `chrome://extensions` and press **Reload** on the ACE card. An
unpacked extension keeps running the build Chrome last read, so
editing a file here changes nothing until it is reloaded.

A tab that was already open then still has no content script in it,
whatever the manifest says, because a content script only injects
while a page is loading. Either reload the tab, or press **Fill this
page** in the toolbar popup, which injects on demand.

## How it works

A panel appears at the **top right** of a form saying how many fields
it can fill, and listing them before it touches anything. Top right
rather than bottom right because a form's own Submit button is almost
always at the bottom, and a fixed panel over it blocks the one click
that matters most.

Click **Fill**, or press **Alt+A**. It reports what it filled, what it
left alone because there was already a value, and which questions it
had no answer for, so you know exactly what is left to do by hand.
**Undo** puts everything back.

Each field it fills carries a purple outline for a few seconds and
then clears. It is a marker for what just happened, not a status: the
panel is what lists everything it did. It is deliberately not gold,
because a permanent gold ring sat in the same colour range as a form's
own warnings and made correctly filled fields read as errors.

Matching is on the question text a person reads, not on the field's
`name` attribute, because those are generated and differ between
tenants. A question it cannot identify is left empty rather than
guessed at: a wrong answer in a form you are about to send an employer
is worse than a blank one.

## Adding a question it misses

Add a rule to `ACE_RULES` in `fields.js`. `answer` must be the exact
label of a row in your ACE answer bank. Narrower questions go above the
broader ones they would otherwise be swallowed by, which is why the
sponsorship rules are ordered the way they are.

Reload the extension from `chrome://extensions` afterwards.
