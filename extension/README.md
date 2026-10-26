# ACE Focus Mode V5.1

Focus Mode runs inside the existing ACE Chrome extension. It fills supported fields and stops. You review the employer form and submit it yourself. Filling never marks an application Applied.

## Install or reload

1. Open `chrome://extensions` and turn on **Developer mode**.
2. If ACE is already installed, click **Reload** on its card. Otherwise choose **Load unpacked** and select `/home/ubuntu/Documents/ace-next/extension`.
3. Reload employer application tabs that were open before the extension reload. Chrome injects new content scripts on page load.
4. In the ACE toolbar popup, set the address to `https://ace.opik.net` for the cloud account, then pair it with a fresh code from the ACE Autofill Extension page. A local ACE instance uses `http://localhost:8000`.

Focus Mode uses the existing V4 Answer Memory API. No new database migration or pairing step is required for V5.1.

## Use Focus Mode

- The compact assistant shows **Fill** and **Review**. **Fill** only writes approved answers into empty, supported fields. **Alt+A** also starts Fill.
- **Review** stays open while you answer, approve, or skip. It shows the employer's exact options for native selects and supported choice controls. Checkbox and radio groups show the full parent question and all original, untruncated options. For a Workday-style listbox, use **Load employer options** inside ACE to read its actual choices without answering on the employer page. An unsupported control stays on the employer form for manual completion.
- A choice made on the employer form appears in Review. A supported choice made in Review stays a draft until **Approve & fill** applies it and checks the actual employer state. You answer once. An employer edit supersedes an unapproved draft; a changed control or option set requires another review. Memory is saved only after a verified fill. Multi-answer checkbox sets are used for the current application rather than flattened into a reusable answer. Safe, reusable answers can be saved to Answer Memory. Sensitive answers are for the current application only.
- You can answer an unknown question directly on the employer form. ACE shows **Answer detected on form** and asks only for **Approve answer**. It does not write that answer again. Leave **Remember this approved answer** checked to save eligible routine answers. **Edit answer in ACE** is available if you want to correct one before approval.
- With **Auto-fill known** on, approved routine answers fill later equivalent questions through the existing paired Answer Memory API. Common changes such as “Describe your experience…” and “Please tell us about your experience…” can match; different subjects, numerical scope, negation, protected questions, or incompatible options stay separate. No learning happens before approval. Failed Memory saves stay open with an explanation.
- Company-motivation prompts, including "Why this company?" and equivalent wording, belong entirely on the employer form. ACE does not fill, review, capture, or remember those answers. Historical records remain stored but are excluded from reuse.
- **Open memory & activity** opens the wider Workspace. Memory can be searched, edited, and deleted. Activity has **Undo** and field diagnostics. Answer values are not logged.
- Drag ACE from its six-dot grip or another non-interactive area. Arrow keys move it when the grip is focused. Double-click the grip to reset its position. The position is saved in Chrome. **Minimize ACE** creates a small dock; **Expand ACE** restores the card. **Close ACE** (the X in the card header or the dock) hides ACE on that page; it returns on a new page or form step, or when you press Fill in the toolbar popup.
- New form questions are detected automatically. **Scan fields** is a manual fallback. ACE follows your computer's Day or Night setting. The Day/Night control in the card header picks the other theme; choosing your computer's theme again returns to following it. The existing answer bank, history, resume features, pairing, and site adapters remain in place.

## Local checks

From the repository root:

```sh
node extension/test-rules.js
node extension/test-memory.js
cd web && npm run test:extension-dom && cd ..
node --check extension/content.js
```

The 24 DOM contract tests execute the actual content scripts with simulated layout, native activation and Chrome messaging. They do not verify real browser behavior. Run Chrome tests only after the documented laptop cooling problem is fixed. The Chrome interaction tests include `web/tests/e2e/extension-question-review.spec.ts`, `web/tests/e2e/extension-focus-v5.spec.ts` and `web/tests/e2e/extension-v4.spec.ts`.

## Release and rollback

Version **1.28.2** adds direct employer-answer adoption, approval-only review and reuse of approved equivalent routine questions. It includes the 1.28.1 parent-question and choice-group repair. This change is extension-only. It requires no schema migration. Keep a copy of the previous unpacked extension folder or use the previous Git commit, reload it from `chrome://extensions`, then reload employer tabs to roll back. Existing answers and application records remain on the ACE server. Do not remove the V4 Answer Memory table as part of a V5.1 rollback.
