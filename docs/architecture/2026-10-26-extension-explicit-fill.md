# Explicit Fill and Workday control correction, 2026-10-26

Extension version: **1.29.1**. The owner reported missing work dates, dropdowns
appearing under the label “Yes Required”, and unwanted filling/Review changes
while typing. They explicitly requested filling only when clicking Fill.

## Behavior

- Page loading, focus, hover, ordinary typing and late saved-data responses
  never start a fill or change the selected question. Legacy `aceAutoKnown`
  preferences cannot restore the old behavior. Manual minimize and drag stay.
- Fill all known answers, toolbar Fill and Alt+A initiate filling. A first
  toolbar injection waits for its requested data; ordinary initialization does
  not. An explicit editor Fill answer can still apply equivalent routine
  answers in the same requested pass. Existing employer values remain intact.
- Associated Workday question text precedes selected-control aria labels.
  Yes/No Required and other selected-state-only labels cannot become prompts.
  The question container counts actual button/combobox controls so one prompt
  cannot swallow neighboring dropdowns. Older Memory records remain stored.
- Explicitly saved profile facts are kept distinct: authorization, current
  sponsorship, future sponsorship and adult status are not interchangeable.
  A now-or-future negative requires both explicit negative facts; either
  explicit positive supports Yes. Unknown, foreign-scope, negated and legal
  declaration questions stay manual. Protected choices are not learned.
- Workday segmented month/year inputs receive their own numeric components;
  required markers on From/To labels cannot hide date direction. Locations
  come from the corresponding job. Exact employer identity is preferred.
  Wording variants require meaningful matching employer tokens, a matching
  long description prefix and exactly one saved job. An ambiguous entry is
  left blank rather than using the block index for a named employer.
- Standalone checkbox answers display Yes or No, including a committed
  unchecked choice. A known historical current-job No is complete without
  ticking the box. History values cannot become global reusable answers.
- The collapsed question chooser exposes every question, and progress counts
  only fields on the current step. Owner drafts, corrections, Undo and native/
  supported custom adapters remain. ACE never submits or marks Applied.

A read-only production check confirmed private work-history date completeness.
No names, personal descriptions, answer values, dates or screenshots were saved
in the public repository; no private records were changed.

## Checks

- 75 fictional Node DOM contracts passed, including passive behavior despite
  old preferences, late data arrival, exact Yes/No separation, toolbar intent,
  current-job No, segmented dates, locations and employer-identity ambiguity.
- All 258 matcher cases and Memory safety cases passed.
- JS syntax, TypeScript, lint, the merged-source production build and forbidden-dash/diff checks passed.
- All 39 extension Playwright fixtures were collected only. No Chrome launch,
  employer submission or owner browser verification was performed because
  the documented laptop cooling restriction remains.
- Node fixture assertions use boolean identity checks where appropriate to
  avoid serializing an entire linked DOM graph on an assertion failure.

## Delivery

The unpacked extension uses local files. Reload ACE at `chrome://extensions`,
then refresh existing employer tabs. That activates **1.29.1**. Updating the
website alone cannot replace scripts already injected into a browser tab.
This correction needs no backend, schema, Gmail permission, scheduler or
website container change. Existing production website fixes are preserved.

Files: `extension/content.js`, `extension/fields.js`, `extension/manifest.json`,
`extension/popup.js`, `extension/README.md`,
`web/tests/extension-review.test.mjs`,
`web/tests/e2e/extension-question-review.spec.ts`, `ACE_NEXT_KNOWLEDGE.md`,
`docs/HANDOFF.md`, `docs/knowledge/06-extension-autofill.md` and this report.
