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
- **Answer remaining questions** opens a shorter editor for the active question. ACE mirrors the employer's exact question and control: text box, textarea, date, dropdown, radios or checkboxes. **Choose another question** is collapsed by default. Clicking or focusing an employer question follows it; hovering previews without filling.
- Answer directly on the employer form, or enter an answer in ACE and click **Fill answer**. There is no separate remember checkbox or save screen. After a verified routine answer entered in ACE, equivalent empty questions fill in the same pass. Supported choice controls select real employer options rather than typing an option label into an unrelated text box.
- Committed owner answers on the employer form leave the unanswered queue without another approval. Routine prefills do not add approval work and are never silently learned. With automatic learning enabled (the default), finished routine owner edits save privately for later equivalent questions. Text saves on leaving the field; choices save once committed. Protected prefills still need a per-application decision. Unsupported controls stay manual.
- Saving for future applications runs in the background. A save failure never makes a verified employer answer incomplete. The answer remains reusable on this form while its source control is unchanged; future-application saving has not succeeded until ACE confirms it. **Settings & activity** exposes retries, Undo and optional Memory management. Previously saved answers, corrections, pairing and revision checks remain in place. Auto-save and Auto-fill known can still be turned off separately.
- Work dates and **I currently work here** use the matching saved job, including reordered employer blocks. These values are never learned as global From/To answers. Qualifications use actual saved facts. Unknown age choices, authorization, consent and other protected decisions are never guessed or learned as routine reusable answers.
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

The 65 DOM contract tests execute the actual content scripts with simulated layout, native activation and Chrome messaging. They do not verify real browser behavior. Run Chrome tests only after the documented laptop cooling problem is fixed. The Chrome interaction tests include `web/tests/e2e/extension-question-review.spec.ts`, `web/tests/e2e/extension-focus-v5.spec.ts` and `web/tests/e2e/extension-v4.spec.ts`.

## Release and rollback

Version **1.29.0** simplifies the main workflow around Fill all known answers, a short question editor and background private saving. It retains the 1.28.6 question-following behavior, 1.28.5 full-viewport movement and 1.28.4 owner-authorized routine learning. Repeated controls have distinct completion identities, custom history dropdowns use their saved job entry, and slow Memory requests no longer hold up profile/history filling. No backend, website or schema change is required. This local extension has not been published. To roll back, restore the previous extension folder or Git version, reload the extension and refresh employer tabs; keep the private answer/history records.
