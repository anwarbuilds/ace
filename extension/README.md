# ACE Autofill

Fills the fields every application form asks for, from the answer bank
in your local ACE instance. It fills and stops: nothing here submits a
form, and nothing overwrites a box that already has something in it.

Covers Greenhouse, Ashby and Lever, which between them took 40 of the
first 76 applications recorded in ACE.

## Install

1. Open `chrome://extensions`
2. Turn on **Developer mode**, top right
3. **Load unpacked**, and choose this `extension` folder
4. Fill your answers in ACE first, under Answers. An empty bank fills
   nothing.

If ACE runs somewhere other than `http://localhost:8000`, set the
address from the toolbar icon.

## How it works

A badge appears at the bottom right of a supported form saying how many
fields it can fill. Click **Fill**. It reports what it filled, what it
left alone because there was already a value, and which questions it had
no answer for, so you know exactly what is left to do by hand. **Undo**
puts everything back.

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
