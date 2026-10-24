# ACE Apply Studio V4

Apply Studio runs inside the existing ACE Chrome extension. It fills application fields and stops. You review every field and submit the employer application yourself. Filling never marks a job Applied in ACE.

## Install or reload

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Choose **Load unpacked** and select `/home/ubuntu/Documents/ace-next/extension` if ACE is not installed yet. If it is already installed, click **Reload** on its card.
3. Reload any employer tabs that were open before the extension reload. Chrome injects the updated content script when a tab loads.
4. Open the ACE toolbar icon, set the ACE address to `https://ace.opik.net` if this browser uses the cloud instance, then pair it with a fresh code from ACE's Autofill Extension page. A local ACE instance uses `http://localhost:8000` instead.

The V4 Answer Memory API needs database migration `0050_extension_answer_memory` on the ACE server before approvals can be saved. Reloading the unpacked extension alone does not deploy that API or migration.

If the Memory tab says the server needs the V4 update, the extension has loaded but the selected ACE server has not. Check the ACE address in the toolbar popup. After the server update, use **Retry connection** in Memory. You do not need to reload the employer page for that retry.

## Using Apply Studio

- **Fill** applies known, approved answers to empty fields. It never overwrites a manual answer. **Alt+A** is the keyboard shortcut.
- The **Review** tab lists unknown questions, protected questions, and saved answers that do not match an employer's offered choices. Enter an answer and choose **Approve and fill**. A reusable answer is saved to Answer Memory immediately before it is applied. Sensitive and company-specific answers are used only on this form.
- The **Memory** tab shows approved reusable answers. You can search, edit, or delete them. A saved answer can match a carefully recognized equivalent question without reloading the employer page.
- The **Activity** tab records local fill actions and provides **Undo** and field diagnostics. Answer values are not logged there.
- The Day and Night themes can be switched from the panel header. The preference persists in Chrome.
- New form questions are detected as they appear. **Scan fields** refreshes the view manually.
- **Auto-fill known** can be turned off in Overview if you want Fill to be the only trigger. It affects only known answers and never submits.

The existing answer bank, work and education history, pairing, supported form controls, and application tracking remain separate. Work authorization, sponsorship, legal declarations, and company-specific questions stay in Review even when a broad or previous answer exists. If ACE cannot verify a dropdown choice, it leaves that field for review.

## Local checks

From the repository root, run `node extension/test-rules.js` and `node extension/test-memory.js`. The browser regression tests live in `web/tests/e2e/extension-*.spec.ts`.

## Release and rollback

Before a future deployment, take the normal PostgreSQL backup and verify that it can be restored. Apply migration `0050` before loading V4 in Chrome. The migration only creates `extension_answer_memory`; it does not alter the existing answer bank or application data.

If V4 needs to be rolled back, reload the previous unpacked extension version and restore the previous backend application while leaving the additive memory table in place. That preserves any answers approved during V4 use. If schema rollback is required, export `extension_answer_memory` first and then run `alembic downgrade 0049`; that downgrade drops only the V4 table and its saved answers. Do not run the downgrade against production without a verified backup and explicit authorization.
