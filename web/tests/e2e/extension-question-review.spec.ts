import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

const extensionRoot = path.resolve(process.cwd(), '../extension');
const question = 'If you worked for Silverpine Labs, was it as an associate, an intern, or a contractor/temporary?';
const choices = ['Associate', 'Contractor', 'Intern', 'I have never worked for/at Silverpine Labs in any capacity.'];
const base = '<label for="name">Full name</label><input id="name" value="Example Applicant"><label for="email">Email</label><input id="email" value="applicant@example.test"><label for="phone">Phone</label><input id="phone" value="5550100100"><label for="role">Current role</label><input id="role" value="Engineer"><label for="resume">Resume</label><input type="file" id="resume">';
async function load(page: Page, body: string, memory: Array<Record<string, unknown>> = [], autoKnown = false) {
  await page.goto('data:text/html,<html><body></body></html>');
  await page.setContent(`<form>${base}${body}<button type="submit">Submit application</button></form>`);
  await page.evaluate(({ memory, autoKnown }) => {
    const w = window as typeof window & { chrome: unknown; __saved: Array<Record<string, unknown>>; __memory: Array<Record<string, unknown>>; __submits: number };
    w.__saved = []; w.__memory = memory; w.__submits = 0;
    document.querySelector('form')!.addEventListener('submit', event => { event.preventDefault(); w.__submits++; });
    w.chrome = { storage: { local: { get: (defaults: Record<string, unknown>, reply: (data: unknown) => void) => reply({ ...defaults, aceAutoKnown: autoKnown }), set() {}, remove() {} } }, runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (value: string) => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message: { type: string; item: Record<string, unknown> }, reply: (data: unknown) => void) {
        if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memory') reply({ ok: true, items: w.__memory });
        else if (message.type === 'memorySave') { const entry = { ...message.item, id: w.__memory.length + 1, revision: 1, reuse_policy: 'reusable' }; w.__saved.push(message.item); w.__memory.push(entry); reply({ ok: true, item: entry }); }
        else reply({ ok: true, items: [], work: [], education: [] });
      } } };
  }, { memory, autoKnown });
  for (const file of ['fields.js', 'memory.js', 'content.js']) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator('.ace-root .ace-panel');
  await panel.getByRole('button', { name: /^Review/ }).click();
  return panel;
}

test('Workday checkbox choices show the full question and fill once after approval', async ({ page }) => {
  const panel = await load(page, `<div data-automation-id="formField-employment"><label id="prompt">${question}</label><div role="group" aria-labelledby="prompt">${choices.map((label, at) => `<div><input type="checkbox" id="choice-${at}" name="unique-${at}"><label for="choice-${at}">${label}</label></div>`).join('')}</div></div>`);
  await panel.getByRole('button', { name: /If you worked/ }).click();
  await expect(panel.locator('.studio-question')).toHaveText(question);
  for (const choice of choices) await expect(panel.getByRole('checkbox', { name: choice, exact: true })).toBeVisible();
  await panel.getByRole('checkbox', { name: choices[3], exact: true }).check();
  await expect(page.locator('#choice-3')).not.toBeChecked();
  await panel.getByRole('button', { name: 'Switch to Night theme' }).click();
  await expect(panel.getByRole('checkbox', { name: choices[3], exact: true })).toBeChecked();
  await panel.getByRole('button', { name: 'Approve & fill' }).click();
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
  await panel.getByRole('button', { name: 'Approve & fill' }).click();
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
  await panel.getByRole('button', { name: 'Approve & fill' }).click();
  await expect(panel.getByText('The employer field did not accept this answer. Review it on the form.')).toBeVisible();
  await expect(page.locator('#channel')).toHaveValue('');
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test('a typed form answer needs approval only and auto-fills an equivalent question on the next application', async ({ page }) => {
  const panel = await load(page, '<label for="testing">Describe your experience writing integration tests</label><textarea id="testing"></textarea>');
  await panel.getByRole('button', { name: /Describe your experience/ }).click();
  const answer = 'I test API boundaries with isolated fixtures and deterministic assertions.';
  await page.locator('#testing').fill(answer);
  await expect(panel.getByText('Answer detected on form', { exact: true })).toBeVisible();
  await expect(panel.locator('.focus-detected')).toContainText(answer);
  await expect(panel.getByRole('textbox', { name: 'Your answer' })).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(0);
  await page.locator('#testing').evaluate(field => {
    field.addEventListener('input', () => field.setAttribute('data-extra-input', 'true'));
    field.addEventListener('change', () => field.setAttribute('data-extra-change', 'true'));
  });
  await panel.getByRole('button', { name: 'Approve answer', exact: true }).click();
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
  await panel.getByRole('button', { name: 'Overview', exact: true }).click();
  await panel.getByRole('button', { name: 'Fill', exact: true }).click();
  await panel.getByRole('button', { name: /^Review/ }).click();
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
  await panel.getByRole('button', { name: 'Approve answer', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __saved: unknown[] }).__saved.length)).toBe(1);
});

test('Review mirrors a text input and textarea instead of making every answer multiline', async ({ page }) => {
  const panel = await load(page, '<label for="short">Additional short screening detail</label><input id="short" placeholder="Employer hint"><label for="long">Additional detailed screening response</label><textarea id="long"></textarea>');
  await panel.getByRole('button', { name: /Additional short screening/ }).click();
  await expect(panel.locator('input#studio-answer')).toBeVisible();
  await expect(panel.locator('textarea#studio-answer')).toHaveCount(0);
  await expect(panel.locator('#studio-answer')).toHaveAttribute('placeholder', 'Employer hint');
  await panel.locator('#studio-answer').fill('Fictional short answer');
  await panel.getByRole('button', { name: 'Approve & fill' }).click();
  await expect(page.locator('#short')).toHaveValue('Fictional short answer');
  await panel.getByRole('button', { name: /Additional detailed screening/ }).click();
  await expect(panel.locator('textarea#studio-answer')).toBeVisible();
});

test('approval labels fit the full-width action row in Day, Night and narrow viewports', async ({ page }) => {
  const panel = await load(page, '<label for="detail">Additional screening detail</label><input id="detail">');
  await panel.getByRole('button', { name: /Additional screening detail/ }).click();
  await page.locator('#detail').fill('Fictional answer');
  const approve = panel.getByRole('button', { name: 'Approve answer', exact: true });
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
  await panel.getByRole('button', { name: 'Approve & fill' }).click();
  await expect(page.locator('#detail')).toHaveValue('Engineering');
  await expect(page.locator('#detail')).toHaveAttribute('data-input-events', '0');
});
