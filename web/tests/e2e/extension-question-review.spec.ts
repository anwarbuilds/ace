import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

const extensionRoot = path.resolve(process.cwd(), '../extension');
const question = 'If you worked for Silverpine Labs, was it as an associate, an intern, or a contractor/temporary?';
const choices = ['Associate', 'Contractor', 'Intern', 'I have never worked for/at Silverpine Labs in any capacity.'];
const base = '<label for="name">Full name</label><input id="name" value="Example Applicant"><label for="email">Email</label><input id="email" value="applicant@example.test"><label for="phone">Phone</label><input id="phone" value="5550100100"><label for="role">Current role</label><input id="role" value="Engineer"><label for="resume">Resume</label><input type="file" id="resume">';
async function load(page: Page, body: string, memory: Array<Record<string, unknown>> = [], autoKnown = false, autoLearn = false, work: Array<Record<string, unknown>> = []) {
  await page.goto('data:text/html,<html><body></body></html>');
  await page.setContent(`<form>${base}${body}<button type="submit">Submit application</button></form>`);
  await page.evaluate(({ memory, autoKnown, autoLearn, work }) => {
    const w = window as typeof window & { chrome: unknown; __saved: Array<Record<string, unknown>>; __memory: Array<Record<string, unknown>>; __submits: number };
    w.__saved = []; w.__memory = memory; w.__submits = 0;
    document.querySelector('form')!.addEventListener('submit', event => { event.preventDefault(); w.__submits++; });
    w.chrome = { storage: { local: { get: (defaults: Record<string, unknown>, reply: (data: unknown) => void) => reply({ ...defaults, aceAutoKnown: autoKnown, aceAutoLearnRoutine: autoLearn }), set() {}, remove() {} } }, runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (value: string) => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message: { type: string; item: Record<string, unknown> }, reply: (data: unknown) => void) {
        if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memory') reply({ ok: true, items: w.__memory });
        else if (message.type === 'memorySave') { const entry = { ...message.item, id: w.__memory.length + 1, revision: 1, reuse_policy: 'reusable' }; w.__saved.push(message.item); w.__memory.push(entry); reply({ ok: true, item: entry }); }
        else reply({ ok: true, items: [], work, education: [] });
      } } };
  }, { memory, autoKnown, autoLearn, work });
  for (const file of ['fields.js', 'memory.js', 'content.js']) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator('.ace-root .ace-panel');
  await panel.getByRole('button', { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  return panel;
}

test('quick fill selects all known native choices once and preserves manual answers and missing options', async ({ page }) => {
  const memory = [{ id: 1, revision: 1, concept: 'q:preferred development environment', question: 'Preferred development environment', answer: 'Linux', answer_type: 'choice', reuse_policy: 'reusable' }];
  const body = ['first', 'second', 'manual', 'unavailable'].map(id => `<label for="${id}">Preferred development environment</label><select id="${id}"><option value="">Select one</option>${id === 'unavailable' ? '<option value="other">Other</option>' : '<option value="linux">Linux</option><option value="mac">macOS</option>'}</select>`).join('');
  const panel = await load(page, body, memory);
  await page.locator('#manual').selectOption('mac');
  await panel.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await expect(page.locator('#first')).toHaveValue('linux'); await expect(page.locator('#second')).toHaveValue('linux');
  await expect(page.locator('#manual')).toHaveValue('mac'); await expect(page.locator('#unavailable')).toHaveValue('');
  await expect(panel.locator('#studio-reuse')).toHaveCount(0);
  await panel.getByRole('button', { name: 'Back to fill', exact: true }).click();
  await expect(panel.locator('.focus-compact-actions button')).toHaveCount(1);
  await panel.getByRole('button', { name: 'Undo fill', exact: true }).click();
  await expect(page.locator('#first')).toHaveValue(''); await expect(page.locator('#second')).toHaveValue('');
  await expect(page.locator('#manual')).toHaveValue('mac');
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('one routine answer fills equivalent questions without another save or approval step', async ({ page }) => {
  const panel = await load(page, '<label for="first">Describe your experience writing integration tests</label><textarea id="first"></textarea><label for="second">Please tell us about your experience writing integration tests.</label><textarea id="second"></textarea><label for="different">Describe your experience writing unit tests</label><textarea id="different"></textarea>');
  await panel.getByRole('textbox', { name: 'Your answer' }).fill('Fictional testing experience');
  await panel.getByRole('button', { name: 'Fill answer', exact: true }).click();
  await expect(page.locator('#first')).toHaveValue('Fictional testing experience');
  await expect(page.locator('#second')).toHaveValue('Fictional testing experience');
  await expect(page.locator('#different')).toHaveValue('');
  await expect(panel.locator('#studio-reuse')).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('Workday checkbox choices show the full question and fill once after approval', async ({ page }) => {
  const panel = await load(page, `<div data-automation-id="formField-employment"><label id="prompt">${question}</label><div role="group" aria-labelledby="prompt">${choices.map((label, at) => `<div><input type="checkbox" id="choice-${at}" name="unique-${at}"><label for="choice-${at}">${label}</label></div>`).join('')}</div></div>`);
  await panel.getByRole('button', { name: /If you worked/ }).click();
  await expect(panel.locator('.studio-question')).toHaveText(question);
  for (const choice of choices) await expect(panel.getByRole('checkbox', { name: choice, exact: true })).toBeVisible();
  await panel.getByRole('checkbox', { name: choices[3], exact: true }).check();
  await expect(page.locator('#choice-3')).not.toBeChecked();
  await panel.getByRole('button', { name: 'Switch to Night theme' }).click();
  await expect(panel.getByRole('checkbox', { name: choices[3], exact: true })).toBeChecked();
  await panel.getByRole('button', { name: 'Fill answer' }).click();
  await expect(page.locator('#choice-3')).toBeChecked();
  for (let at = 0; at < 3; at++) await expect(page.locator(`#choice-${at}`)).not.toBeChecked();
  await expect(panel.locator('.studio-question').filter({ hasText: question })).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('ACE loads lazy dropdown choices without requiring an employer-page answer', async ({ page }) => {
  const panel = await load(page, '<label for="channel">Which recruiting channel introduced this role?</label><button id="channel" type="button" aria-haspopup="listbox" aria-controls="choices">Select One</button>');
  await page.evaluate(() => {
    const trigger = document.getElementById('channel')!;
    trigger.addEventListener('click', () => {
      if (document.getElementById('choices')) return;
      setTimeout(() => {
        const menu = document.createElement('div'); menu.id = 'choices'; menu.setAttribute('role', 'listbox');
        for (const text of ['Careers website', 'Friend referral']) {
          const option = document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = text;
          option.addEventListener('click', () => { trigger.textContent = text; menu.remove(); }); menu.append(option);
        }
        document.body.append(menu);
      }, 140);
    });
    trigger.addEventListener('keydown', event => { if (event.key === 'Escape') document.getElementById('choices')?.remove(); });
  });
  await panel.getByRole('button', { name: /Which recruiting channel/ }).click();
  await panel.getByRole('button', { name: 'Load employer options' }).click();
  await expect(panel.getByRole('combobox', { name: 'Exact employer options' })).toBeVisible();
  await expect(page.locator('#choices')).toHaveCount(0);
  await panel.getByRole('combobox', { name: 'Exact employer options' }).selectOption('Friend referral');
  await expect(page.locator('#channel')).toHaveText('Select One');
  await panel.getByRole('button', { name: 'Fill answer' }).click();
  await expect(page.locator('#channel')).toHaveText('Friend referral');
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('native option codes remain drafts until approval and reverted writes are not saved', async ({ page }) => {
  const panel = await load(page, '<label for="channel">How did you hear about this role?</label><select id="channel"><option value="">Select One</option><option value="ref-92">Friend referral</option><option value="site-17">Careers website</option></select>');
  await panel.getByRole('button', { name: /How did you hear/ }).click();
  await panel.getByRole('combobox', { name: 'Exact employer options' }).selectOption('ref-92');
  await expect(page.locator('#channel')).toHaveValue('');
  await page.locator('#channel').evaluate(field => {
    field.addEventListener('change', () => setTimeout(() => { (field as HTMLSelectElement).value = ''; }, 10));
  });
  await panel.getByRole('button', { name: 'Fill answer' }).click();
  await expect(panel.getByText('The employer field did not accept this answer. Review it on the form.')).toBeVisible();
  await expect(page.locator('#channel')).toHaveValue('');
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('a pre-existing form answer is confirmed once without another employer write and reused later', async ({ page }) => {
  const answer = 'I test API boundaries with isolated fixtures and deterministic assertions.';
  const panel = await load(page, `<label for="testing">Describe your experience writing integration tests</label><textarea id="testing">${answer}</textarea>`);
  await panel.getByRole('button', { name: /Describe your experience/ }).click();
  await expect(panel.getByText('Answer detected on form', { exact: true })).toBeVisible();
  await expect(panel.locator('.focus-detected')).toContainText(answer);
  await expect(panel.getByRole('textbox', { name: 'Your answer' })).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  await page.locator('#testing').evaluate(field => {
    field.addEventListener('input', () => field.setAttribute('data-extra-input', 'true'));
    field.addEventListener('change', () => field.setAttribute('data-extra-change', 'true'));
  });
  await panel.getByRole('button', { name: 'Use answer', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
  expect(await page.locator('#testing').getAttribute('data-extra-input')).toBeNull();
  expect(await page.locator('#testing').getAttribute('data-extra-change')).toBeNull();
  const memory = await page.evaluate(() => (window as typeof window & { __memory: Array<Record<string, unknown>> }).__memory);
  await load(page, '<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', memory, true);
  await expect(page.locator('#testing')).toHaveValue(answer);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('a manual custom dropdown answer is detected after Fill without a change event', async ({ page }) => {
  const panel = await load(page, '<label for="channel">Which application channel did you use?</label><button id="channel" type="button" aria-haspopup="listbox">Select One</button>');
  await panel.getByRole('button', { name: /^(Back to fill|Overview)$/, exact: true }).click();
  await panel.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await panel.getByRole('button', { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  await panel.getByRole('button', { name: /Which application channel/ }).click();
  await page.evaluate(() => {
    const trigger = document.getElementById('channel')!;
    trigger.addEventListener('click', () => {
      const option = document.createElement('button'); option.type = 'button'; option.setAttribute('role', 'option'); option.textContent = 'Friend referral';
      option.addEventListener('click', () => { trigger.textContent = 'Friend referral'; option.remove(); });
      document.body.append(option);
    });
  });
  await page.locator('#channel').click();
  await page.getByRole('option', { name: 'Friend referral' }).click();
  await expect(panel.getByText('Answer detected on form', { exact: true })).toBeVisible();
  await expect(panel.locator('.focus-detected')).toContainText('Friend referral');
  await expect(panel.getByRole('button', { name: 'Load employer options' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Use answer', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
});

test('Review mirrors a text input and textarea instead of making every answer multiline', async ({ page }) => {
  const panel = await load(page, '<label for="short">Additional short screening detail</label><input id="short" placeholder="Employer hint"><label for="long">Additional detailed screening response</label><textarea id="long"></textarea>');
  await panel.getByRole('button', { name: /Additional short screening/ }).click();
  await expect(panel.locator('input#studio-answer')).toBeVisible();
  await expect(panel.locator('textarea#studio-answer')).toHaveCount(0);
  await expect(panel.locator('#studio-answer')).toHaveAttribute('placeholder', 'Employer hint');
  await panel.locator('#studio-answer').fill('Fictional short answer');
  await panel.getByRole('button', { name: 'Fill answer' }).click();
  await expect(page.locator('#short')).toHaveValue('Fictional short answer');
  await panel.getByRole('button', { name: /Additional detailed screening/ }).click();
  await expect(panel.locator('textarea#studio-answer')).toBeVisible();
});

test('approval labels fit the full-width action row in Day, Night and narrow viewports', async ({ page }) => {
  const panel = await load(page, '<label for="detail">Additional screening detail</label><input id="detail">');
  await panel.getByRole('button', { name: /Additional screening detail/ }).click();
  await page.locator('#detail').fill('Fictional answer');
  const approve = panel.getByRole('button', { name: 'Use answer', exact: true });
  await expect(approve).toBeVisible();
  for (const width of [390, 195]) {
    await page.setViewportSize({ width, height: 900 });
    for (const colorScheme of ['light', 'dark'] as const) {
      await page.emulateMedia({ colorScheme });
      await expect(panel).toHaveClass(colorScheme === 'dark' ? /night/ : /focus-review/);
      const geometry = await panel.locator('.focus-review-actions').evaluate(actions => {
        const [primary, show, skip] = Array.from(actions.querySelectorAll('button'));
        const a = primary.getBoundingClientRect(), b = show.getBoundingClientRect(), c = skip.getBoundingClientRect();
        return { primaryWidth: a.width, availableWidth: actions.clientWidth, labelFits: primary.scrollWidth <= primary.clientWidth,
          secondaryBelow: b.top >= a.bottom, secondaryAligned: Math.abs(b.top - c.top) < 1 };
      });
      expect(geometry.primaryWidth).toBeGreaterThanOrEqual(geometry.availableWidth - 1);
      expect(geometry.labelFits).toBe(true); expect(geometry.secondaryBelow).toBe(true); expect(geometry.secondaryAligned).toBe(true);
    }
  }
});

test('a readonly wrapper combobox mirrors a dropdown and selects the actual employer option without typing', async ({ page }) => {
  const panel = await load(page, '<label id="detail-label">Additional screening detail</label><div id="detail-control" role="combobox" aria-labelledby="detail-label" aria-controls="detail-options"><input id="detail" readonly></div>');
  await page.evaluate(() => {
    const input = document.getElementById('detail') as HTMLInputElement;
    input.setAttribute('data-input-events', '0');
    input.addEventListener('input', () => input.setAttribute('data-input-events', String(Number(input.getAttribute('data-input-events')) + 1)));
    document.getElementById('detail-control')!.addEventListener('mousedown', () => {
      if (document.getElementById('detail-options')) return;
      const menu = document.createElement('div'); menu.id = 'detail-options'; menu.setAttribute('role', 'listbox');
      for (const text of ['Research', 'Engineering']) {
        const option = document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = text;
        option.addEventListener('click', () => { input.value = text; menu.remove(); }); menu.append(option);
      }
      document.body.append(menu);
    });
    input.addEventListener('keydown', event => { if (event.key === 'Escape') document.getElementById('detail-options')?.remove(); });
  });
  await panel.getByRole('button', { name: /Additional screening detail/ }).click();
  await expect(panel.getByRole('textbox', { name: 'Your answer' })).toHaveCount(0);
  await panel.getByRole('button', { name: 'Load employer options' }).click();
  const dropdown = panel.getByRole('combobox', { name: 'Exact employer options' });
  await dropdown.selectOption('Engineering');
  await expect(page.locator('#detail')).toHaveValue('');
  await panel.getByRole('button', { name: 'Fill answer' }).click();
  await expect(page.locator('#detail')).toHaveValue('Engineering');
  await expect(page.locator('#detail')).toHaveAttribute('data-input-events', '0');
});


test('routine employer answers save on leaving the field and auto-fill an equivalent future question', async ({ page }) => {
  const panel = await load(page, '<label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea>', [], false, true);
  await page.locator('#detail').fill('Fictional integration test experience');
  await page.waitForTimeout(450);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  await page.locator('#phone').focus();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
  await expect(panel.locator('.studio-question').filter({ hasText: 'integration tests' })).toHaveCount(0);
  const memory = await page.evaluate(() => (window as typeof window & { __memory: Array<Record<string, unknown>> }).__memory);
  const next = await load(page, '<label for="detail">Can you describe your experience writing integration tests?</label><textarea id="detail"></textarea>', memory, true, true);
  await expect(page.locator('#detail')).toHaveValue('');
  await next.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await expect(page.locator('#detail')).toHaveValue('Fictional integration test experience');
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('native choices save without approval while synthetic page events cannot teach Memory', async ({ page }) => {
  const panel = await load(page, '<label for="detail">Which interview format do you prefer?</label><select id="detail"><option value="">Select One</option><option value="remote-17">Remote</option></select><label for="testing">Describe your testing experience</label><textarea id="testing"></textarea>', [], false, true);
  // selectOption dispatches synthetic events. A real keyboard selection is
  // required here to cover the browser isTrusted gate.
  await page.locator('#detail').focus(); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __saved: Array<{answer: string}> }).__saved[0].answer)).toBe('Remote');
  await page.locator('#testing').evaluate(field => { (field as HTMLTextAreaElement).value = 'Page generated value'; field.dispatchEvent(new Event('input', { bubbles: true })); field.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
  await panel.getByRole('button', { name: 'Settings & activity', exact: true }).click();
  await panel.getByRole("button", { name: "Memory", exact: true }).click();
  await expect(panel.getByRole('switch', { name: 'Auto-save routine answers: On' })).toBeChecked();
  await panel.getByRole('switch', { name: 'Auto-save routine answers: On' }).click();
  await expect(panel.getByRole('switch', { name: 'Auto-save routine answers: Off' })).not.toBeChecked();
});


test('employer focus preserves the selected question and filling requires a click', async ({ page }) => {
  const memory = [{ id: 1, revision: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional saved testing experience', answer_type: 'text', reuse_policy: 'reusable' }];
  const panel = await load(page, Array.from({ length: 9 }, (_, at) => `<label for="detail-${at}">Fictional screening question ${at + 1}</label><textarea id="detail-${at}"></textarea>`).join(''), memory, true, true);
  await panel.getByRole('textbox', { name: 'Your answer' }).fill('Fictional unsent draft');
  await page.locator('#detail-8').click(); await expect(panel.locator('.studio-question')).toHaveText('Fictional screening question 1');
  await expect(panel.getByRole('textbox', { name: 'Your answer' })).toHaveValue('Fictional unsent draft');
  await panel.locator('.focus-question-picker summary').click();
  await panel.getByRole('button', { name: '9. Fictional screening question 9', exact: true }).click();
  await expect(panel.locator('.studio-question')).toHaveText('Fictional screening question 9');
  await panel.locator('.focus-question-picker summary').click();
  await panel.getByRole('button', { name: '1. Fictional screening question 1', exact: true }).click();
  await expect(panel.getByRole('textbox', { name: 'Your answer' })).toHaveValue('Fictional unsent draft');
  await page.evaluate(() => { const block = document.createElement('div'); block.innerHTML = '<label for="known">Could you describe your experience writing integration tests?</label><textarea id="known"></textarea>'; document.querySelector('form')!.append(block); });
  await page.locator('#known').click(); await expect(page.locator('#known')).toHaveValue('');
  await panel.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await expect(page.locator('#known')).toHaveValue('Fictional saved testing experience');
  await expect(page.locator('#detail-0')).toHaveValue('');
});

test('a direct protected custom dropdown choice completes without another approval and never enters Memory', async ({ page }) => {
  const panel = await load(page, '<label id="sponsor-label">Will you require visa sponsorship?</label><div id="sponsor" role="combobox" aria-labelledby="sponsor-label" aria-controls="sponsor-options" tabindex="0">Select One</div>', [], false, true);
  await page.evaluate(() => {
    const field = document.getElementById('sponsor')!;
    field.addEventListener('click', () => {
      if (document.getElementById('sponsor-options')) return;
      const menu = document.createElement('div'); menu.id = 'sponsor-options'; menu.setAttribute('role', 'listbox');
      const option = document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Yes';
      option.addEventListener('click', event => { event.stopPropagation(); field.textContent = 'Yes'; menu.remove(); }); menu.append(option); document.body.append(menu);
    });
  });
  await page.locator('#sponsor').click(); await page.getByRole('option', { name: 'Yes', exact: true }).click();
  await expect(panel.getByText('Answered on form', { exact: true })).toBeVisible();
  await expect(panel.getByText('Your choice is recorded for this application only.')).toBeVisible();
  await expect(panel.getByRole('button', { name: /Approve/ })).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});


test('Workday month and year sections fill from the matching saved job after one click', async ({ page }) => {
  const date = (id: string, label: string) => `<div><label>${label}*</label><div data-automation-id="dateInputWrapper"><input id="${id}-month" aria-label="${label}" data-automation-id="dateSectionMonth-input" maxlength="2" placeholder="MM"><input id="${id}-year" aria-label="${label}" data-automation-id="dateSectionYear-input" maxlength="4" placeholder="YYYY"></div></div>`;
  const panel = await load(page, `<section><label for="company">Company</label><input id="company" value="Fictional Workday Lab"><label for="current">I currently work here</label><input id="current" type="checkbox">${date('from', 'From')}${date('to', 'To')}</section>`, [], true, false, [{ employer: 'Fictional Workday Lab', is_current: false, start_month: 6, start_year: 2020, end_month: 8, end_year: 2023 }]);
  await expect(page.locator('#from-month')).toHaveValue('');
  await panel.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await expect(page.locator('#from-month')).toHaveValue('06'); await expect(page.locator('#from-year')).toHaveValue('2020');
  await expect(page.locator('#to-month')).toHaveValue('08'); await expect(page.locator('#to-year')).toHaveValue('2023');
  await expect(page.locator('#current')).not.toBeChecked();
});

test('legacy automatic preference cannot fill or open Review when the applicant edits the page', async ({ page }) => {
  const memory = [{ id: 1, revision: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional saved answer', answer_type: 'text', reuse_policy: 'reusable' }];
  const panel = await load(page, '<label for="known">Describe your experience writing integration tests</label><textarea id="known"></textarea><label for="manual">Additional screening detail</label><input id="manual">', memory, true, true);
  await panel.getByRole('button', { name: 'Back to fill', exact: true }).click();
  await page.locator('#known').focus(); await page.locator('#manual').fill('Applicant draft');
  await page.waitForTimeout(250); await expect(panel).toHaveClass(/focus-compact/); await expect(page.locator('#known')).toHaveValue('');
  await panel.getByRole('button', { name: 'Fill all known answers', exact: true }).click();
  await expect(page.locator('#known')).toHaveValue('Fictional saved answer'); await expect(page.locator('#manual')).toHaveValue('Applicant draft');
});
