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
- **Review** stays open while you answer, approve, or skip. It shows the employer's exact options for native selects and supported choice controls. For a Workday-style listbox, open it once on the employer form so ACE can read the offered choices. An unsupported control stays on the employer form for manual completion.
- A choice made on the employer form appears in Review. A supported choice made in Review updates the employer control. **Approve & fill** confirms the answer. Safe, reusable answers can be saved to Answer Memory. Sensitive answers are for the current application only.
- Company-motivation prompts, including "Why this company?" and equivalent wording, belong entirely on the employer form. ACE does not fill, review, capture, or remember those answers. Historical records remain stored but are excluded from reuse.
- **Open memory & activity** opens the wider Workspace. Memory can be searched, edited, and deleted. Activity has **Undo** and field diagnostics. Answer values are not logged.
- Drag ACE from its six-dot grip or another non-interactive area. Arrow keys move it when the grip is focused. Double-click the grip to reset its position. The position is saved in Chrome. **Minimize ACE** creates a small dock; **Expand ACE** restores the card.
- New form questions are detected automatically. **Scan fields** is a manual fallback. The Day/Night control is in the card header. The existing answer bank, history, resume features, pairing, and site adapters remain in place.

## Local checks

From the repository root:

```sh
node extension/test-rules.js
node extension/test-memory.js
node --check extension/content.js
```

The Chrome interaction tests are `web/tests/e2e/extension-focus-v5.spec.ts` and `web/tests/e2e/extension-v4.spec.ts`.

## Release and rollback

This change is extension-only. It requires no schema migration. Keep a copy of the previous unpacked extension folder or use the previous Git commit, reload it from `chrome://extensions`, then reload employer tabs to roll back. Existing answers and application records remain on the ACE server. Do not remove the V4 Answer Memory table as part of a V5.1 rollback.
