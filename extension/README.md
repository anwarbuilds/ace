# ACE Focus Mode V5.1

Focus Mode runs inside the existing ACE Chrome extension. It fills supported fields and stops. You review the employer form and submit it yourself. Filling never marks an application Applied.

## Install or reload

1. Open `chrome://extensions` and turn on **Developer mode**.
2. If ACE is already installed, click **Reload** on its card. Otherwise choose **Load unpacked** and select `/home/ubuntu/Documents/ace-next/extension`.
3. Reload employer application tabs that were open before the extension reload. Chrome injects new content scripts on page load.
4. In the ACE toolbar popup, set the address to `https://ace.opik.net` for the cloud account, then pair it with a fresh code from the ACE Autofill Extension page. A local ACE instance uses `http://localhost:8000`.

Focus Mode uses the existing V4 Answer Memory API. No new database migration or pairing step is required for V5.1.

## Use Focus Mode

- Click **Fill all known answers**, or press **Alt+A**, to fill every empty supported field with a matching private saved answer. This includes native dropdowns, supported custom dropdowns, radio choices and saved work/education history. Existing employer answers remain intact. A missing or incompatible option stays unanswered.
- **Answer remaining questions** opens a shorter editor for the active question. ACE mirrors the employer's exact question and control: text box, textarea, date, dropdown, radios or checkboxes. **Choose another question** is collapsed by default. Opening, focusing, hovering or editing the employer form never changes ACE’s selected question or starts filling. Choose a question explicitly in ACE when needed.
- Answer directly on the employer form, or enter an answer in ACE and click **Fill answer**. There is no separate remember checkbox or save screen. After a verified routine answer entered in ACE, equivalent empty questions fill in the same pass. Supported choice controls select real employer options rather than typing an option label into an unrelated text box.
- Committed owner answers on the employer form leave the unanswered queue without another approval. Routine prefills do not add approval work and are never silently learned. With automatic learning enabled (the default), finished routine owner edits save privately for later equivalent questions. Text saves on leaving the field; choices save once committed. Protected prefills still need a per-application decision. Unsupported controls stay manual.
- Saving for future applications runs in the background. A save failure never makes a verified employer answer incomplete. The answer remains reusable on this form while its source control is unchanged; future-application saving has not succeeded until ACE confirms it. **Settings & activity** exposes retries, Undo and optional Memory management. Previously saved answers, corrections, pairing and revision checks remain in place. Automatic saving can still be turned off in Settings. Filling always requires your click or Alt+A; older automatic-filling preferences have no effect.
- Work dates, job locations and **I currently work here** use the matching saved job, including reordered employer blocks. Workday’s separate month/year inputs receive the correct numeric components; an unchecked current-job choice records No. These values are never learned as global From/To answers. Qualifications use actual saved facts. The explicit Fill action can use exact saved profile authorization, sponsorship or adult-status facts. Unknown age choices, authorization, consent and other protected decisions are never guessed or learned as routine reusable answers.
- Company-motivation prompts, including “Why this company?”, belong entirely on the employer form. ACE does not read, fill, review or remember those answers. Historical records remain stored but excluded from reuse.
- **Undo fill** is available on the main card. **Settings & activity** retains answer search/edit/delete and count-only activity. Answer values never enter diagnostics.
- Drag ACE from the six-dot grip or another non-interactive area across the full browser viewport. Embedded applications use the existing scoped outer-frame relay; form logic stays in the original frame. Touch/keyboard movement, saved position, double-click reset, Day/Night/system themes, manual minimize, expand and Close retain their existing behavior.
- Reload the unpacked extension and refresh employer tabs after an update. ACE never submits an employer application, advances its steps or marks it Applied after filling.

## Local checks

From the repository root:

```sh
node extension/test-rules.js
node extension/test-memory.js
cd web && npm run test:extension-dom && cd ..
node --check extension/content.js
```

The 75 DOM contract tests execute the actual content scripts with simulated layout, native activation and Chrome messaging. They do not verify real browser behavior. Run Chrome tests only after the documented laptop cooling problem is fixed. The Chrome interaction tests include `web/tests/e2e/extension-question-review.spec.ts`, `web/tests/e2e/extension-focus-v5.spec.ts` and `web/tests/e2e/extension-v4.spec.ts`.

## Release and rollback

Version **1.29.1** follows the owner’s explicit-fill workflow: no filling or Review navigation on page load, focus, hover, typing or late private-data responses. Toolbar Fill, the card button and Alt+A are explicit actions. Workday selected-state labels cannot replace actual questions; segmented dates and locations use their matched job. An unchecked standalone checkbox records No. It retains 1.29.0’s shorter editor and background private saving, 1.28.5’s full-viewport movement and optional routine learning. Source and fictional controls are tested locally; a real employer browser session has not been verified. No schema, Gmail, scheduler or website runtime change is required. Reload the unpacked extension and refresh employer tabs. To roll back, restore the previous extension files, reload and refresh tabs; keep private history and answer records.
