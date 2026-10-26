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
- **Review** stays open while you answer, approve, or skip. Single-line employer inputs stay single-line, textareas stay multiline, and numeric/date controls preserve their native type and limits. It shows the employer's exact options for native selects and supported choice controls. Checkbox and radio groups show the full parent question and all original, untruncated options. For a Workday-style listbox, use **Load employer options** inside ACE to read its actual choices without answering on the employer page. An unsupported control stays on the employer form for manual completion.
- A choice made on the employer form appears in Review. A supported choice made in Review stays a draft until **Approve & fill** applies it and checks the actual employer state. You answer once. An employer edit supersedes an unapproved draft; a changed control or option set requires another review. Answers entered in ACE are saved after a verified fill. Multi-answer checkbox sets are used for the current application rather than flattened into a reusable answer. Safe, reusable answers can be saved to Answer Memory. Sensitive answers are for the current application only.
- Answer an unknown routine question directly on the employer form. With **Auto-save routine answers** on (the default), text saves when you leave the field and selections save after choosing. No separate approval is required. Only actual owner edits are learned, never untouched prefills, synthetic page events, or autocomplete search queries. Protected and multi-answer questions still require per-application review. Supported custom dropdowns require a real committed option selection; unsupported controls remain manual. Turning auto-save off restores **Approve answer** for direct answers.
- With **Auto-fill known** on, approved routine answers fill later equivalent questions through the existing paired Answer Memory API. Common changes such as “Describe your experience…” and “Please tell us about your experience…” can match; different subjects, numerical scope, negation, protected questions, or incompatible options stay separate. Auto-save and Auto-fill known are separate switches in Memory. Failed saves stay open with an explanation and **Save now** retry. Corrections update the matching Memory record with revision checking.
- Company-motivation prompts, including "Why this company?" and equivalent wording, belong entirely on the employer form. ACE does not fill, review, capture, or remember those answers. Historical records remain stored but are excluded from reuse.
- **Open memory & activity** opens the wider Workspace. Memory can be searched, edited, and deleted. Activity has **Undo** and field diagnostics. Answer values are not logged.
- Drag ACE from its six-dot grip or another non-interactive area across the full browser viewport. Embedded applications display the card on the outer page, so it can move beyond the form column; form controls still run in the original frame. If Chrome cannot reach the outer page, the local card remains usable inside the frame. Touch dragging uses the grip/header; the Review body still scrolls. Arrow keys move it when the grip is focused. Double-click the grip to reset its position. The position is saved in Chrome. **Minimize ACE** creates a small dock; **Expand ACE** restores the card. **Close ACE** (the X in the card header or the dock) hides ACE on that page; it returns on a new page or form step, or when you press Fill in the toolbar popup.
- New form questions are detected automatically. **Scan fields** is a manual fallback. ACE follows your computer's Day or Night setting. The Day/Night control in the card header picks the other theme; choosing your computer's theme again returns to following it. The existing answer bank, history, resume features, pairing, and site adapters remain in place.

## Local checks

From the repository root:

```sh
node extension/test-rules.js
node extension/test-memory.js
cd web && npm run test:extension-dom && cd ..
node --check extension/content.js
```

The 31 DOM contract tests execute the actual content scripts with simulated layout, native activation and Chrome messaging. They do not verify real browser behavior. Run Chrome tests only after the documented laptop cooling problem is fixed. The Chrome interaction tests include `web/tests/e2e/extension-question-review.spec.ts`, `web/tests/e2e/extension-focus-v5.spec.ts` and `web/tests/e2e/extension-v4.spec.ts`.

## Release and rollback

Version **1.28.5** moves embedded application cards into the outer viewport and captures the pointer immediately for reliable free movement. It retains the 1.28.4 changes, which add owner-requested automatic learning of finished routine employer answers and visible Memory switches. Protected answers and motivation exclusions remain. It retains the 1.28.3 control mirroring: single-line inputs, multiline textareas, numeric/date inputs, native suggestions, real dropdown choices, radios and checkboxes. Supported readonly/wrapper comboboxes load and select actual options. Approval has a full-width row above Show on form and Skip. Direct answer adoption and approved future reuse from 1.28.2 remain in place. This change is extension-only. It requires no schema migration. Keep a copy of the previous unpacked extension folder or use the previous Git commit, reload it from `chrome://extensions`, then reload employer tabs to roll back. Existing answers and application records remain on the ACE server. Do not remove the V4 Answer Memory table as part of a V5.1 rollback.
