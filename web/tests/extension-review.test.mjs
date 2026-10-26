/* DOM contract tests execute the real content scripts without launching Chrome.
   Layout, native control activation and Chrome messaging are simulated explicitly.
   Playwright fixtures separately cover browser event/default-action behavior. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { test } from 'node:test';
import { parseHTML } from 'linkedom';

const extension = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../extension');
const prompt = 'If you worked for Silverpine Labs, was it as an associate, an intern, or a contractor/temporary?';
const options = ['Associate', 'Contractor', 'Intern', 'I have never worked for/at Silverpine Labs in any capacity.'];
const grouped = `<div data-automation-id="formField-employment"><label id="employment-prompt">${prompt}</label><div role="group" aria-labelledby="employment-prompt">${options.map((label, at) => `<div><input type="checkbox" id="option-${at}" name="unique-${at}"><label for="option-${at}">${label}</label></div>`).join('')}</div></div>`;
const base = `<label for="name">Full name</label><input id="name" value="Example Applicant"><label for="email">Email</label><input id="email" value="applicant@example.test"><label for="phone">Phone</label><input id="phone" value="5550100100"><label for="role">Current role</label><input id="role" value="Engineer"><label for="resume">Resume</label><input id="resume" type="file">`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, message) {
  for (let i = 0; i < 75; i++) { if (check()) return; await sleep(25); }
  assert.fail(message);
}

function fixture(body) {
  const { window } = parseHTML(`<html><head><title>Engineer | Fictional employer</title></head><body><form>${base}${body}<button type="submit">Submit application</button></form></body></html>`);
  delete window.__aceLoaded;
  const { document, HTMLElement, HTMLInputElement, HTMLSelectElement, HTMLOptionElement } = window;
  const timers = new Set();
  const saved = [];
  let submissions = 0;
  let active = document.body;
  Object.defineProperty(document, 'activeElement', { get: () => active });
  Object.defineProperty(HTMLElement.prototype, 'offsetParent', { get() { return this.hidden ? null : document.body; }, configurable: true });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { get() { return 318; }, configurable: true });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { get() { return 500; }, configurable: true });
  HTMLElement.prototype.getClientRects = function () { return this.closest('[hidden]') ? [] : [{}]; };
  // The DOM shim tracks document.activeElement when a control receives focus.
  // eslint-disable-next-line @typescript-eslint/no-this-alias
  HTMLElement.prototype.focus = function () { active = this; };
  HTMLElement.prototype.blur = function () { active = document.body; };
  HTMLElement.prototype.scrollIntoView = function () {};
  Object.defineProperty(HTMLInputElement.prototype, 'checked', {
    get() { return this.hasAttribute('checked'); }, set(value) { this.toggleAttribute('checked', Boolean(value)); }, configurable: true,
  });
  HTMLInputElement.prototype.click = function () {
    if (this.disabled) return;
    if (this.type === 'radio') document.querySelectorAll('input[type=radio]').forEach(input => { if (input.name === this.name) input.checked = false; });
    if (this.type === 'checkbox') this.checked = !this.checked;
    if (this.type === 'radio') this.checked = true;
    this.dispatchEvent(new window.Event('click', { bubbles: true, cancelable: true }));
    this.dispatchEvent(new window.Event('change', { bubbles: true }));
  };
  Object.defineProperty(HTMLOptionElement.prototype, 'selected', { get() { return this.hasAttribute('selected'); }, set(value) { this.toggleAttribute('selected', Boolean(value)); }, configurable: true });
  Object.defineProperty(HTMLSelectElement.prototype, 'multiple', { get() { return this.hasAttribute('multiple'); }, configurable: true });
  Object.defineProperty(HTMLSelectElement.prototype, 'selectedOptions', { get() { const selected = Array.from(this.options).filter(option => option.selected); return selected.length || this.multiple ? selected : Array.from(this.options).slice(0, 1); }, configurable: true });
  Object.defineProperty(HTMLSelectElement.prototype, 'selectedIndex', { get() { return Array.from(this.options).indexOf(this.selectedOptions[0]); }, configurable: true });
  Object.defineProperty(HTMLSelectElement.prototype, 'value', { get() { return this.selectedOptions[0]?.value || ''; }, set(value) { Array.from(this.options).forEach(option => { option.selected = option.value === value; }); }, configurable: true });
  window.Node.DOCUMENT_POSITION_FOLLOWING = 4;
  class DOMEvent extends window.Event { constructor(type, init = {}) { super(type, init); Object.assign(this, init); } }
  const context = vm.createContext({ window, document, Node: window.Node, HTMLElement, HTMLInputElement,
    HTMLSelectElement, HTMLTextAreaElement: window.HTMLTextAreaElement, Event: window.Event, MouseEvent: DOMEvent, KeyboardEvent: DOMEvent,
    location: { href: 'https://fixture.example/apply', hostname: 'fixture.example', pathname: '/apply' },
    CSS: { escape: value => String(value).replace(/[^a-zA-Z0-9_-]/g, character => `\\${character}`) },
    innerWidth: 1440, innerHeight: 900, console,
    setTimeout(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; },
    clearTimeout(id) { clearTimeout(id); timers.delete(id); },
    MutationObserver: class { observe() {} disconnect() {} },
    chrome: { runtime: { lastError: null, onMessage: { addListener() {} }, getURL: value => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message, reply) {
        if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memorySave') { saved.push(message.item); reply({ ok: true, item: { ...message.item, id: saved.length, revision: 1 } }); }
        else reply({ ok: true, items: [], work: [], education: [] });
      } } },
  });
  document.querySelector('form').addEventListener('submit', event => { event.preventDefault(); submissions++; });
  for (const file of ['fields.js', 'memory.js', 'content.js']) vm.runInContext(fs.readFileSync(path.join(extension, file), 'utf8'), context, { filename: file });
  const panel = () => document.querySelector('.ace-root')?.shadowRoot?.querySelector('.ace-panel');
  function click(action) { const button = panel()?.querySelector(`[data-ace="${action}"]`); assert.ok(button, `Missing action ${action}`); button.click(); }
  function review(question) {
    click('tab:review');
    const button = Array.from(panel().querySelectorAll('[data-ace^="question:"]')).find(button => button.textContent.includes(question));
    assert.ok(button, `Missing review prompt ${question}`); button.click();
  }
  return { window, document, context, panel, click, review, saved, submissions: () => submissions,
    dispose() { timers.forEach(clearTimeout); } };
}

test('parent prompt and all uniquely named checkbox choices remain one exact question', async t => {
  const f = fixture(grouped); t.after(f.dispose);
  f.review('If you worked');
  assert.equal(f.panel().querySelector('.studio-question').textContent, prompt);
  assert.deepEqual(Array.from(f.panel().querySelectorAll('#studio-answer label span'), node => node.textContent), options);
  assert.equal(f.panel().querySelectorAll('#studio-answer input[type=checkbox]').length, 4);
  assert.equal(f.context.aceChoiceMembers(f.document.querySelector('#option-3')).length, 4);
  assert.equal(f.context.aceQuestionFor(f.document.querySelector('#option-3')), f.context.aceNormalise(prompt));
  const last = f.panel().querySelector('[data-choice="3"]'); last.checked = true;
  last.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(f.document.querySelector('#option-3').checked, false, 'answer stays a draft until approval');
  f.click('theme');
  assert.equal(f.panel().querySelector('[data-choice="3"]').checked, true, 'draft survives rerender');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.document.querySelector('#option-3').checked, 'approval must fill the employer choice');
  await until(() => !f.panel().textContent.includes(prompt), 'verified answer must leave the open queue');
  assert.deepEqual(Array.from(f.document.querySelectorAll('input[type=checkbox]'), input => input.checked), [false, false, false, true]);
  assert.equal(f.saved.length, 0, 'employer-specific checkbox answer is not reusable');
  assert.equal(f.submissions(), 0);
  f.click('workspace'); f.click('tab:activity'); f.click('undo');
  assert.equal(f.document.querySelector('#option-3').checked, false, 'undo restores the previous choice state');
});

test('separate option labels cannot replace an unlabelled group prompt', t => {
  const f = fixture(grouped.replace(' role="group" aria-labelledby="employment-prompt"', '')); t.after(f.dispose);
  for (const input of f.document.querySelectorAll('input[type=checkbox]')) {
    assert.equal(f.context.aceQuestionLabelFor(input), prompt);
    assert.equal(f.context.aceChoiceMembers(input).length, 4);
  }
});

test('checkbox groups keep multiple selections and never merge a neighbouring question', async t => {
  const f = fixture(`${grouped}<fieldset><legend>Which analysis tools do you use?</legend><input type="checkbox" id="sql"><label for="sql">SQL</label><input type="checkbox" id="python"><label for="python">Python</label></fieldset>`); t.after(f.dispose);
  f.review('Which analysis tools');
  for (const input of f.panel().querySelectorAll('[data-choice]')) { input.checked = true; input.dispatchEvent(new f.window.Event('change', { bubbles: true })); }
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.document.querySelector('#sql').checked && f.document.querySelector('#python').checked, 'both checkbox answers must fill');
  assert.equal(f.document.querySelector('#option-0').checked, false);
  assert.equal(f.saved.length, 0, 'multi-answer sets are not flattened into single-answer Memory');
});

test('lazy employer options load from ACE without selecting, then approval commits the exact option', async t => {
  const f = fixture('<label for="source">Which recruiting channel introduced this role?</label><button id="source" type="button" aria-haspopup="listbox" aria-controls="source-options">Select One</button>'); t.after(f.dispose);
  const trigger = f.document.querySelector('#source');
  let clicks = 0;
  trigger.addEventListener('click', () => {
    if (f.document.getElementById('source-options')) return;
    const menu = f.document.createElement('div'); menu.id = 'source-options'; menu.setAttribute('role', 'listbox');
    for (const text of ['Careers website', 'Friend referral']) {
      const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = text;
      option.addEventListener('click', () => { trigger.textContent = text; clicks++; menu.remove(); }); menu.append(option);
    }
    f.document.body.append(menu);
  });
  trigger.addEventListener('keydown', event => { if (event.key === 'Escape') f.document.getElementById('source-options')?.remove(); });
  f.review('Which recruiting channel'); f.click(f.panel().querySelector('[data-ace^="read-options:"]').getAttribute('data-ace'));
  await until(() => f.panel().querySelector('#studio-answer option[value="Friend referral"]'), 'choices should load from ACE');
  assert.equal(trigger.textContent, 'Select One'); assert.equal(clicks, 0);
  assert.equal(f.document.getElementById('source-options'), null, 'option discovery closes the employer menu');
  const select = f.panel().querySelector('#studio-answer'); select.value = 'Friend referral'; select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(trigger.textContent, 'Select One');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'save only after the actual employer control accepts the choice');
  assert.equal(trigger.textContent, 'Friend referral'); assert.equal(clicks, 1);
  assert.equal(f.saved[0].answer, 'Friend referral'); assert.equal(f.submissions(), 0);
});

test('employer motivation remains outside Review and its answer is never read', t => {
  const f = fixture(`${grouped}<label for="motivation">Why do you want to work at Silverpine Labs?</label><textarea id="motivation"></textarea>`); t.after(f.dispose);
  const field = f.document.querySelector('#motivation');
  Object.defineProperty(field, 'value', { get() { assert.fail('ACE must not read this answer'); }, set() { assert.fail('ACE must not fill this answer'); } });
  f.review('If you worked'); f.click('tab:overview'); f.click('scan'); f.click('tab:review'); f.click('theme');
  assert.ok(!f.panel().textContent.includes('Why do you want to work'));
});

test('native opaque option values fill exactly after approval and save the visible answer', async t => {
  const f = fixture('<label for="channel">How did you hear about this role?</label><select id="channel"><option value="">Select one</option><option value="ref-92">Friend referral</option><option value="site-17">Careers website</option></select>'); t.after(f.dispose);
  f.review('How did you hear');
  const select = f.panel().querySelector('#studio-answer'); select.value = 'ref-92'; select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(f.document.querySelector('#channel').value, ''); assert.equal(f.saved.length, 0);
  f.click('theme');
  assert.equal(f.panel().querySelector('#studio-answer').value, 'ref-92');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'native choice should be filled and then saved');
  assert.equal(f.document.querySelector('#channel').value, 'ref-92');
  assert.equal(f.saved[0].answer, 'Friend referral');
});

test('native multiple select keeps the full approved set and undo restores the empty set', async t => {
  const f = fixture('<label for="tools">Which analysis tools have you used?</label><select id="tools" multiple><option value="sql">SQL</option><option value="py">Python</option><option value="r">R</option></select>'); t.after(f.dispose);
  f.review('Which analysis tools');
  const select = f.panel().querySelector('#studio-answer');
  Array.from(select.options).forEach(option => { option.selected = ['sql', 'py'].includes(option.value); });
  select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(f.document.querySelector('#tools').selectedOptions.length, 0);
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => !f.panel().textContent.includes('Which analysis tools'), 'the whole set must verify before leaving Review');
  assert.deepEqual(Array.from(f.document.querySelector('#tools').selectedOptions, option => option.value), ['sql', 'py']);
  assert.equal(f.saved.length, 0);
  f.click('workspace'); f.click('tab:activity'); f.click('undo');
  assert.equal(f.document.querySelector('#tools').selectedOptions.length, 0);
});

test('radio review keeps the parent prompt and fills only the approved radio', async t => {
  const f = fixture('<fieldset><legend>Which interview format do you prefer?</legend><input type="radio" name="format" id="remote"><label for="remote">Remote video</label><input type="radio" name="format" id="onsite"><label for="onsite">On site</label></fieldset>'); t.after(f.dispose);
  f.review('Which interview format');
  const radio = f.panel().querySelector('[data-choice="1"]'); radio.checked = true; radio.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(f.document.querySelector('#onsite').checked, false);
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approved radio should fill and verify');
  assert.equal(f.document.querySelector('#remote').checked, false); assert.equal(f.document.querySelector('#onsite').checked, true);
  assert.equal(f.saved[0].question, 'Which interview format do you prefer?'); assert.equal(f.saved[0].answer, 'On site');
});

test('a rejected employer write is never approved or saved to Memory', async t => {
  const f = fixture('<label for="channel">How did you hear about this role?</label><select id="channel"><option value="">Select one</option><option value="site">Careers website</option></select>'); t.after(f.dispose);
  f.document.querySelector('#channel').addEventListener('change', () => { setTimeout(() => { f.document.querySelector('#channel').value = ''; }, 10); });
  f.review('How did you hear');
  const select = f.panel().querySelector('#studio-answer'); select.value = 'site'; select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.panel().textContent.includes('did not accept this answer'), 'reverted selection must stay for review');
  assert.equal(f.saved.length, 0); assert.equal(f.document.querySelector('#channel').value, ''); assert.equal(f.submissions(), 0);
});

test('an employer change after drafting cannot be overwritten by a stale choice', t => {
  const f = fixture('<label for="channel">How did you hear about this role?</label><select id="channel"><option value="">Select one</option><option value="site">Careers website</option><option value="friend">Friend referral</option></select>'); t.after(f.dispose);
  f.review('How did you hear');
  const select = f.panel().querySelector('#studio-answer'); select.value = 'site'; select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  // Simulate a framework update without a change event.
  f.document.querySelector('#channel').value = 'friend';
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  assert.equal(f.document.querySelector('#channel').value, 'friend'); assert.equal(f.saved.length, 0);
  assert.ok(f.panel().textContent.includes('employer answer changed'));
});

test('a standalone checkbox uses its own full statement rather than the preceding field label', t => {
  const f = fixture('<div data-automation-id="formField-fluency"><input type="checkbox" id="fluent"><label for="fluent">I am fluent in this language.</label></div>'); t.after(f.dispose);
  assert.equal(f.context.aceQuestionLabelFor(f.document.querySelector('#fluent')), 'I am fluent in this language.');
});

test('protected authorization answers fill for this application and are not reusable', async t => {
  const f = fixture('<label for="authorization">Are you authorized to work in the U.S.?</label><select id="authorization"><option value="">Select one</option><option value="yes-code">Yes</option><option value="no-code">No</option></select>'); t.after(f.dispose);
  f.review('Are you authorized');
  const select = f.panel().querySelector('#studio-answer'); select.value = 'yes-code'; select.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(f.panel().querySelector('#studio-reuse'), null);
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => !f.panel().textContent.includes('Are you authorized'), 'protected approval must fill and verify');
  assert.equal(f.document.querySelector('#authorization').value, 'yes-code'); assert.equal(f.saved.length, 0);
});

test('an unlabelled radio option never becomes a profile question', t => {
  const f = fixture('<div><input type="radio" name="unknown" id="social"><label for="social">LinkedIn</label></div>'); t.after(f.dispose);
  f.document.querySelector('form').innerHTML = '<div><input type="radio" id="unlabelled-choice"><label for="unlabelled-choice">LinkedIn</label></div>';
  assert.equal(f.context.aceQuestionFor(f.document.querySelector('#unlabelled-choice')), '');
});
