import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

const extensionRoot = path.resolve(process.cwd(), '../extension');
const question = 'If you worked for Silverpine Labs, was it as an associate, an intern, or a contractor/temporary?';
const choices = ['Associate', 'Contractor', 'Intern', 'I have never worked for/at Silverpine Labs in any capacity.'];
const base = '<label for="name">Full name</label><input id="name" value="Example Applicant"><label for="email">Email</label><input id="email" value="applicant@example.test"><label for="phone">Phone</label><input id="phone" value="5550100100"><label for="role">Current role</label><input id="role" value="Engineer"><label for="resume">Resume</label><input type="file" id="resume">';
async function load(page: Page, body: string) {
  await page.goto('data:text/html,<html><body></body></html>');
  await page.setContent(`<form>${base}${body}<button type="submit">Submit application</button></form>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __saved: Array<Record<string, unknown>>; __submits: number };
    w.__saved = []; w.__submits = 0;
    document.querySelector('form')!.addEventListener('submit', event => { event.preventDefault(); w.__submits++; });
    w.chrome = { runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (value: string) => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message: { type: string; item: Record<string, unknown> }, reply: (data: unknown) => void) {
        if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memorySave') { w.__saved.push(message.item); reply({ ok: true, item: { ...message.item, id: w.__saved.length, revision: 1 } }); }
        else reply({ ok: true, items: [], work: [], education: [] });
      } } };
  });
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
