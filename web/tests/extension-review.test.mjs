/* DOM contract tests execute the real content scripts without launching Chrome.
   Layout, native control activation and Chrome messaging are simulated explicitly.
   Playwright fixtures separately cover browser event/default-action behavior. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
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

function fixture(body, config = {}) {
  const { window } = parseHTML(`<html><head><title>Engineer | Fictional employer</title></head><body><form>${base}${body}<button type="submit">Submit application</button></form></body></html>`);
  delete window.__aceLoaded;
  const { document, HTMLElement, HTMLInputElement, HTMLSelectElement, HTMLOptionElement } = window;
  const timers = new Set();
  const saved = [];
  const memoryStore = config.memoryStore || [];
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
  Object.defineProperty(HTMLOptionElement.prototype, 'value', { get() { return this.getAttribute('value') ?? this.textContent; }, set(value) { this.setAttribute('value', value); }, configurable: true });
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
    innerWidth: 1440, innerHeight: 900, console, crypto: webcrypto, TextEncoder,
    setTimeout(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; },
    clearTimeout(id) { clearTimeout(id); timers.delete(id); },
    MutationObserver: config.observeDOM ? window.MutationObserver : class { observe() {} disconnect() {} },
    chrome: { ...(config.autoKnown || config.autoLearn !== undefined ? { storage: { local: {
      get(defaults, reply) { reply({ ...defaults, aceAutoKnown: !!config.autoKnown, aceAutoLearnRoutine: !!config.autoLearn }); }, set() {}, remove() {},
    } } } : {}), runtime: { lastError: null, onMessage: { addListener() {} }, getURL: value => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message, reply) {
        if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memory') reply({ ok: true, items: memoryStore });
        else if (message.type === 'memorySave') {
          saved.push(message.item);
          if (config.failSave) { reply({ ok: false, error: "unavailable" }); return; }
          const existing = memoryStore.find(entry => entry.concept === message.item.concept);
          const entry = { ...message.item, id: existing?.id || memoryStore.length + 1, revision: (existing?.revision || 0) + 1, reuse_policy: 'reusable' };
          if (existing) Object.assign(existing, entry); else memoryStore.push(entry);
          reply({ ok: true, item: entry });
        }
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

test('typed employer answer needs only approval, then fills an equivalent question on a later application', async t => {
  const memoryStore = [];
  const first = fixture('<label for="testing">Describe your experience writing integration tests</label><textarea id="testing"></textarea>', { memoryStore }); t.after(first.dispose);
  first.review('Describe your experience');
  const field = first.document.getElementById('testing');
  let writes = 0;
  const descriptor = Object.getOwnPropertyDescriptor(first.window.HTMLTextAreaElement.prototype, 'value');
  Object.defineProperty(field, 'value', { get() { return descriptor.get.call(this); }, set(value) { writes++; descriptor.set.call(this, value); } });
  field.value = 'I test API boundaries with isolated fixtures and deterministic assertions.';
  field.dispatchEvent(new first.window.Event('input', { bubbles: true }));
  await until(() => first.panel().textContent.includes('Answer detected on form'), 'typed form answers must appear without blur or retyping');
  assert.ok(first.panel().querySelector('.focus-detected').textContent.includes(field.value));
  assert.equal(first.panel().querySelector('#studio-answer'), null, 'detected answers need approval, not another editor');
  assert.equal(first.panel().querySelector('[data-ace^="approve:"]').textContent, 'Approve answer');
  assert.equal(first.saved.length, 0, 'observing a typed answer never saves it');
  first.click(first.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => first.saved.length === 1, 'explicit approval saves the detected answer');
  assert.equal(writes, 1, 'approval must not fill the employer field a second time');
  const answer = field.value;
  first.dispose();
  const later = fixture('<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', { memoryStore, autoKnown: true }); t.after(later.dispose);
  await until(() => later.document.getElementById('testing').value === answer, 'approved equivalent answers must auto-fill on a later application');
  assert.equal(later.saved.length, 0);
  assert.equal(later.submissions(), 0);
});

test('manual native selection is approved without another change and reuses visible text across different option codes', async t => {
  const memoryStore = [];
  const first = fixture('<label for="channel">Which application channel did you use?</label><select id="channel"><option value="">Select one</option><option value="ref-1">Friend referral</option><option value="site-2">Careers website</option></select>', { memoryStore }); t.after(first.dispose);
  first.review('Which application channel');
  let changes = 0;
  const field = first.document.getElementById('channel'); field.addEventListener('change', () => changes++);
  field.value = 'ref-1'; field.dispatchEvent(new first.window.Event('change', { bubbles: true }));
  await until(() => first.panel().textContent.includes('Answer detected on form'), 'native selections must be detected');
  assert.ok(first.panel().querySelector('.focus-detected').textContent.includes('Friend referral'));
  assert.ok(!first.panel().querySelector('.focus-detected').textContent.includes('ref-1'));
  first.click(first.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => first.saved.length === 1, 'approval saves the option text');
  assert.equal(changes, 1); assert.equal(first.saved[0].answer, 'Friend referral'); first.dispose();
  const later = fixture('<label for="channel">Which application channel did you use?</label><select id="channel"><option value="">Select one</option><option value="new-site">Careers website</option><option value="new-ref">Friend referral</option></select>', { memoryStore, autoKnown: true }); t.after(later.dispose);
  await until(() => later.document.getElementById('channel').value === 'new-ref', 'reuse matches a real option rather than copying an old code');
});

test('custom dropdown selection without change events is detected after Fill and approved without another option click', async t => {
  const f = fixture('<label for="channel">Which application channel did you use?</label><button id="channel" type="button" aria-haspopup="listbox">Select One</button>', { observeDOM: true }); t.after(f.dispose);
  f.click('fill'); await sleep(150); f.review('Which application channel');
  const trigger = f.document.getElementById('channel'); let optionClicks = 0;
  trigger.addEventListener('click', () => {
    const box = f.document.createElement('div'); box.setAttribute('role', 'listbox');
    const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Friend referral';
    option.addEventListener('click', () => { optionClicks++; trigger.textContent = option.textContent; box.remove(); });
    box.append(option); f.document.body.append(box);
  });
  trigger.click(); f.document.querySelector('[role=option]').click();
  await until(() => f.panel().textContent.includes('Answer detected on form'), 'custom label mutations must update Review even after Fill');
  assert.equal(f.panel().querySelector('[data-ace^="read-options:"]'), null, 'an existing answer does not require loading options again');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approve the custom selection');
  assert.equal(optionClicks, 1);
  assert.equal(f.saved[0].answer, 'Friend referral');
});

test('direct protected answers need per-application approval and never enter future memory', async t => {
  const memoryStore = [];
  const first = fixture('<label for="authorization">Are you authorized to work in the U.S.?</label><select id="authorization"><option value="">Select one</option><option>Yes</option><option>No</option></select>', { memoryStore }); t.after(first.dispose);
  first.review('Are you authorized');
  const field = first.document.getElementById('authorization'); field.value = 'Yes'; field.dispatchEvent(new first.window.Event('change', { bubbles: true }));
  await until(() => first.panel().textContent.includes('Answer detected on form'), 'protected manual answers can be confirmed for this form');
  first.click(first.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  assert.equal(memoryStore.length, 0); assert.equal(first.saved.length, 0); first.dispose();
  const later = fixture('<label for="authorization">Are you authorized to work in the U.S.?</label><select id="authorization"><option value="">Select one</option><option>Yes</option><option>No</option></select>', { memoryStore, autoKnown: true }); t.after(later.dispose);
  await sleep(200); assert.equal(later.document.getElementById('authorization').value, '');
});

test('typing a motivation answer does not read or capture it', async t => {
  const f = fixture('<label for="motivation">Why do you want to work at Silverpine Labs?</label><textarea id="motivation"></textarea>'); t.after(f.dispose);
  const field = f.document.getElementById('motivation');
  Object.defineProperty(field, 'value', { get() { assert.fail('motivation values must never be read'); } });
  field.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  field.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  await sleep(220); f.click('tab:review');
  assert.ok(!f.panel().textContent.includes('Why do you want to work')); assert.equal(f.saved.length, 0);
});

test('a manually corrected legacy memory answer updates the existing record rather than creating ambiguous duplicates', async t => {
  const memoryStore = [{ id: 7, revision: 1, concept: 'q:describe your experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional old answer', answer_type: 'text', reuse_policy: 'reusable' }];
  const f = fixture('<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', { memoryStore }); t.after(f.dispose);
  const field = f.document.getElementById('testing'); field.value = 'Fictional corrected testing experience';
  field.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  await sleep(220); f.review('Please tell us about');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approve the updated form answer');
  assert.equal(memoryStore.length, 1); assert.equal(memoryStore[0].id, 7);
  assert.equal(memoryStore[0].answer, 'Fictional corrected testing experience');
});

test('an answer typed without approval is not learned on a later application', async t => {
  const memoryStore = [];
  const first = fixture('<label for="testing">Describe your experience writing integration tests</label><textarea id="testing"></textarea>', { memoryStore }); t.after(first.dispose);
  const field = first.document.getElementById('testing'); field.value = 'An unapproved fictional answer'; field.dispatchEvent(new first.window.Event('input', { bubbles: true }));
  await sleep(220); assert.equal(first.saved.length, 0); first.dispose();
  const later = fixture('<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', { memoryStore, autoKnown: true }); t.after(later.dispose);
  await sleep(200); assert.equal(later.document.getElementById('testing').value, ''); assert.equal(memoryStore.length, 0);
});

test('credential and search inputs never enter employer-answer learning', async t => {
  const f = fixture('<label for="password">Create an employer account password</label><input type="password" id="password"><label for="search">Search jobs</label><input type="search" id="search">'); t.after(f.dispose);
  const password = f.document.getElementById('password');
  Object.defineProperty(password, 'value', { get() { assert.fail('passwords must never be captured'); } });
  password.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  f.document.getElementById('search').dispatchEvent(new f.window.Event('input', { bubbles: true }));
  await sleep(220); f.click('tab:review');
  assert.ok(!f.panel().textContent.includes('Create an employer account password'));
  assert.ok(!f.panel().textContent.includes('Search jobs')); assert.equal(f.saved.length, 0);
});

test('a detected answer can be edited in ACE without changing the form until approval', async t => {
  const f = fixture('<label for="channel">Which application channel did you use?</label><select id="channel"><option value="">Select one</option><option value="site">Careers website</option><option value="ref">Friend referral</option></select>'); t.after(f.dispose);
  f.review('Which application channel');
  const field = f.document.getElementById('channel'); field.value = 'site'; field.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  await until(() => f.panel().textContent.includes('Answer detected on form'), 'detect the existing employer answer');
  f.click(f.panel().querySelector('[data-ace^="edit-answer:"]').getAttribute('data-ace'));
  const editor = f.panel().querySelector('#studio-answer'); assert.equal(editor.value, 'site');
  editor.value = 'ref'; editor.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(field.value, 'site');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approve and remember the corrected selection');
  assert.equal(field.value, 'ref'); assert.equal(f.saved[0].answer, 'Friend referral');
});

test('custom choice buttons that change only aria state are adopted for approval', async t => {
  const f = fixture('<div role="radiogroup" aria-label="Which interview format do you prefer?"><button type="button" aria-pressed="false" id="remote-format">Remote video</button><button type="button" aria-pressed="false" id="onsite-format">On site</button></div>'); t.after(f.dispose);
  for (const button of f.document.querySelectorAll('[aria-pressed]')) button.addEventListener('click', () => {
    f.document.querySelectorAll('[aria-pressed]').forEach(option => option.setAttribute('aria-pressed', String(option === button)));
  });
  f.review('Which interview format'); f.document.getElementById('onsite-format').click();
  await until(() => f.panel().textContent.includes('Answer detected on form'), 'aria-only custom choices must be detected');
  assert.ok(f.panel().querySelector('.focus-detected').textContent.includes('On site'));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approval remembers the exact custom choice');
  assert.equal(f.saved[0].answer, 'On site'); assert.equal(f.submissions(), 0);
});

test('approval never saves a detected answer that changed after ACE displayed it', async t => {
  const f = fixture('<label for="testing">Describe your experience writing integration tests</label><textarea id="testing"></textarea>'); t.after(f.dispose);
  f.review('Describe your experience');
  const field = f.document.getElementById('testing'); field.value = 'First fictional answer'; field.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  await until(() => f.panel().textContent.includes('Answer detected on form'), 'display the answer awaiting approval');
  field.value = 'A changed fictional answer'; // A framework update without an input event.
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  assert.equal(f.saved.length, 0);
  assert.ok(f.panel().textContent.includes('employer answer changed'));
  assert.ok(f.panel().querySelector('.focus-detected').textContent.includes('A changed fictional answer'));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approve the newly displayed answer');
  assert.equal(f.saved[0].answer, 'A changed fictional answer');
});

test('Review mirrors single-line, multiline, numeric and date fields with their real control types', t => {
  for (const type of ['text', 'email', 'tel', 'url', 'number', 'date', 'month', 'time']) {
    const f = fixture(`<label for="detail">Additional screening detail</label><input id="detail" type="${type}" placeholder="Employer hint" min="1" max="40" step="1">`); t.after(f.dispose);
    f.review('Additional screening detail');
    const editor = f.panel().querySelector('#studio-answer');
    assert.equal(editor.tagName, 'INPUT', type); assert.equal(editor.type, type);
    assert.equal(editor.getAttribute('placeholder'), 'Employer hint');
    assert.equal(editor.getAttribute('min'), '1'); assert.equal(editor.getAttribute('max'), '40');
    f.dispose();
  }
  const f = fixture('<label for="detail">Additional screening detail</label><textarea id="detail"></textarea>'); t.after(f.dispose);
  f.review('Additional screening detail'); assert.equal(f.panel().querySelector('#studio-answer').tagName, 'TEXTAREA');
});

test('a mirrored single-line editor keeps its draft through theme changes and fills only on approval', async t => {
  const f = fixture('<label for="detail">Additional screening detail</label><input id="detail" type="text">'); t.after(f.dispose);
  f.review('Additional screening detail');
  const editor = f.panel().querySelector('#studio-answer'); editor.value = 'Fictional screening response'; editor.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  f.click('theme'); assert.equal(f.panel().querySelector('#studio-answer').value, 'Fictional screening response');
  assert.equal(f.document.getElementById('detail').value, '');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'single-line approval must fill the original input');
  assert.equal(f.document.getElementById('detail').value, 'Fictional screening response');
});

test('a native datalist stays a text input with its actual suggestions', t => {
  const f = fixture('<label for="detail">Additional screening detail</label><input id="detail" list="suggestions"><datalist id="suggestions"><option value="Option A">First suggestion</option><option value="Option B">Second suggestion</option></datalist>'); t.after(f.dispose);
  f.review('Additional screening detail');
  assert.equal(f.panel().querySelector('#studio-answer').tagName, 'INPUT');
  assert.equal(f.panel().querySelector('#studio-answer').getAttribute('list'), 'studio-answer-options');
  assert.deepEqual(Array.from(f.panel().querySelectorAll('#studio-answer-options option'), option => option.value), ['Option A', 'Option B']);
});

test('wrapper comboboxes mirror actual dropdown choices and select an option without typing', async t => {
  const f = fixture('<label id="detail-label">Additional screening detail</label><div id="detail-control" role="combobox" aria-labelledby="detail-label" aria-controls="detail-options"><input id="detail" type="search" readonly value="Select One"></div>'); t.after(f.dispose);
  const scope = f.document.getElementById('detail-control'); const field = f.document.getElementById('detail'); field.readOnly = true;
  let typed = 0; let picked = 0;
  field.addEventListener('input', () => typed++);
  scope.addEventListener('mousedown', () => {
    if (f.document.getElementById('detail-options')) return;
    const menu = f.document.createElement('div'); menu.id = 'detail-options'; menu.setAttribute('role', 'listbox');
    for (const label of ['Research', 'Engineering']) {
      const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = label;
      option.addEventListener('click', () => { picked++; field.value = label; menu.remove(); }); menu.append(option);
    }
    f.document.body.append(menu);
  });
  scope.addEventListener('keydown', event => { if (event.key === 'Escape') f.document.getElementById('detail-options')?.remove(); });
  assert.equal(f.context.aceIsAutocomplete(field), true);
  f.review('Additional screening detail');
  assert.equal(f.panel().querySelector('textarea'), null, 'dropdowns never become free-text editors');
  f.click(f.panel().querySelector('[data-ace^="read-options:"]').getAttribute('data-ace'));
  await until(() => f.panel().querySelector('#studio-answer option[value="Engineering"]'), 'load the actual wrapper-owned list');
  const editor = f.panel().querySelector('#studio-answer'); assert.equal(editor.tagName, 'SELECT'); editor.value = 'Engineering'; editor.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  assert.equal(field.value, 'Select One');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'approval must select the real option');
  assert.equal(field.value, 'Engineering'); assert.equal(typed, 0); assert.equal(picked, 1);
});

test('aria-autocomplete inputs are choice controls even when role=combobox is absent', t => {
  const f = fixture('<label for="detail">Additional screening detail</label><input id="detail" aria-autocomplete="list">'); t.after(f.dispose);
  assert.equal(f.context.aceIsAutocomplete(f.document.getElementById('detail')), true);
  f.review('Additional screening detail');
  assert.equal(f.panel().querySelector('#studio-answer'), null);
  assert.ok(f.panel().querySelector('[data-ace^="read-options:"]'));
});

test('a combobox option click that does not commit an answer is not approved or remembered', async t => {
  const f = fixture('<label for="detail">Additional screening detail</label><div><input id="detail" role="combobox" aria-controls="detail-options"></div>'); t.after(f.dispose);
  const field = f.document.getElementById('detail');
  field.parentElement.addEventListener('mousedown', () => {
    if (f.document.getElementById('detail-options')) return;
    const menu = f.document.createElement('div'); menu.id = 'detail-options'; menu.setAttribute('role', 'listbox');
    const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Engineering'; menu.append(option); f.document.body.append(menu);
  });
  field.addEventListener('keydown', event => { if (event.key === 'Escape') f.document.getElementById('detail-options')?.remove(); });
  f.review('Additional screening detail'); f.click(f.panel().querySelector('[data-ace^="read-options:"]').getAttribute('data-ace'));
  await until(() => f.panel().querySelector('#studio-answer'), 'load actual choices');
  const editor = f.panel().querySelector('#studio-answer'); editor.value = 'Engineering'; editor.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.panel().textContent.includes('did not accept this answer'), 'a no-op option cannot be claimed as filled');
  assert.equal(field.value, ''); assert.equal(f.saved.length, 0);
});

test('custom selection displayed beside a cleared search input is verified and remembered', async t => {
  const f = fixture('<label for="detail">Additional screening detail</label><div><input id="detail" role="combobox" aria-controls="detail-options"></div>'); t.after(f.dispose);
  const field = f.document.getElementById('detail');
  field.parentElement.addEventListener('mousedown', () => {
    if (f.document.getElementById('detail-options')) return;
    const menu = f.document.createElement('div'); menu.id = 'detail-options'; menu.setAttribute('role', 'listbox');
    const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Engineering';
    option.addEventListener('click', () => {
      const value = f.document.createElement('span'); value.className = 'react-select__single-value'; value.textContent = 'Engineering'; field.parentElement.append(value); field.value = ''; menu.remove();
    });
    menu.append(option); f.document.body.append(menu);
  });
  field.addEventListener('keydown', event => { if (event.key === 'Escape') f.document.getElementById('detail-options')?.remove(); });
  f.review('Additional screening detail'); f.click(f.panel().querySelector('[data-ace^="read-options:"]').getAttribute('data-ace'));
  await until(() => f.panel().querySelector('#studio-answer'), 'load actual choices');
  const editor = f.panel().querySelector('#studio-answer'); editor.value = 'Engineering'; editor.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'the committed visible selection is the answer even when the search input clears');
  assert.equal(field.value, ''); assert.equal(f.saved[0].answer, 'Engineering');
});

// linkedom has no hardware events. These explicit trusted-event simulations
// exercise the real gate; the corresponding Playwright cases use browser input.
function ownerEvent(f, field, type) {
  const event = new f.window.Event(type, { bubbles: true });
  Object.defineProperty(event, 'isTrusted', { value: true });
  field.dispatchEvent(event);
}
const routine = '<label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea>';

test('finished routine employer answers save without approval and auto-fill equivalent future prompts', async t => {
  const memoryStore = [];
  const first = fixture(routine, { autoLearn: true, memoryStore }); t.after(first.dispose);
  const field = first.document.getElementById('detail'); field.value = 'Fictional integration test experience';
  ownerEvent(first, field, 'input');
  await sleep(450); assert.equal(first.saved.length, 0, 'typing is not a finished answer');
  ownerEvent(first, field, 'focusout');
  await until(() => memoryStore.length === 1, 'leaving the field should remember the answer');
  assert.equal(first.saved[0].answer, field.value);
  first.click('tab:review'); assert.ok(!first.panel().querySelector('.studio-question')?.textContent.includes('integration tests'), first.panel().textContent.slice(-2500));
  const next = fixture('<label for="next">Can you describe your experience writing integration tests?</label><textarea id="next"></textarea>', { autoKnown: true, autoLearn: true, memoryStore }); t.after(next.dispose);
  await until(() => next.document.getElementById('next').value === field.value, 'equivalent future prompt auto-fills');
  assert.equal(next.saved.length, 0, 'ACE filling is never learned as owner input');
  assert.equal(first.submissions() + next.submissions(), 0);
});

test('synthetic events and untouched prefills never auto-learn', async t => {
  const f = fixture(routine, { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Synthetic page value';
  field.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  field.dispatchEvent(new f.window.Event('change', { bubbles: true }));
  ownerEvent(f, field, 'focusout');
  await sleep(500); assert.equal(f.saved.length, 0);
});

test('native selections save visible employer labels once and update corrections in place', async t => {
  const memoryStore = [];
  const f = fixture('<label for="detail">Which interview format do you prefer?</label><select id="detail"><option value="">Select One</option><option value="remote-7">Remote</option><option value="office-9">On site</option></select>', { autoLearn: true, memoryStore }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'remote-7'; ownerEvent(f, field, 'change'); ownerEvent(f, field, 'focusout');
  await until(() => f.saved.length === 1, 'native choice saves without approval'); assert.equal(f.saved[0].answer, 'Remote');
  ownerEvent(f, field, 'change'); await sleep(450); assert.equal(f.saved.length, 1, 'same answer does not create another revision');
  field.value = 'office-9'; ownerEvent(f, field, 'change');
  await until(() => f.saved.length === 2, 'correction saves'); assert.equal(memoryStore.length, 1);
  assert.equal(f.saved[1].expected_revision, 1); assert.equal(memoryStore[0].answer, 'On site');
});

test('new typing cancels an unfinished scheduled save', async t => {
  const f = fixture(routine, { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'First draft'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  field.value = 'Still editing'; ownerEvent(f, field, 'input'); await sleep(450); assert.equal(f.saved.length, 0);
  ownerEvent(f, field, 'focusout'); await until(() => f.saved.length === 1, 'final value is saved'); assert.equal(f.saved[0].answer, 'Still editing');
});

test('Memory switch cancels pending auto-save and preserves manual approval', async t => {
  const f = fixture(routine, { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Fictional final answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  f.click('workspace'); f.click('tab:memory');
  assert.equal(f.panel().querySelector('[data-ace=auto-learn]').getAttribute('aria-checked'), 'true'); f.click('auto-learn');
  await sleep(450); assert.equal(f.saved.length, 0);
  f.review('Describe your experience'); assert.equal(f.panel().querySelector('[data-ace^="approve:"]').textContent, 'Approve answer');
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'explicit approval still saves with auto-learning disabled');
});

test('protected, motivation and multi-answer controls never auto-save', async t => {
  const f = fixture('<label for="sponsor">Do you require sponsorship?</label><input id="sponsor"><label for="company">Have you previously worked for Silverpine?</label><input id="company"><label for="why">Why this company?</label><textarea id="why"></textarea><fieldset><legend>Which interview formats do you prefer?</legend><input type="checkbox" id="remote"><label for="remote">Remote</label></fieldset>', { autoLearn: true }); t.after(f.dispose);
  for (const id of ['sponsor', 'company', 'remote']) {
    const field = f.document.getElementById(id); field.value = 'Fictional answer'; field.checked = true; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'change'); ownerEvent(f, field, 'focusout');
  }
  const why = f.document.getElementById('why'); let reads = 0; Object.defineProperty(why, 'value', { get() { reads++; return 'Excluded'; } });
  ownerEvent(f, why, 'input'); ownerEvent(f, why, 'change'); ownerEvent(f, why, 'focusout');
  await sleep(500); assert.equal(f.saved.length, 0); assert.equal(reads, 0);
});

test('failed auto-save stays visible and can be retried without approving', async t => {
  const config = { autoLearn: true, failSave: true }; const f = fixture(routine, config); t.after(f.dispose);
  f.review('Describe your experience'); const field = f.document.getElementById('detail'); field.value = 'Fictional final answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  await until(() => f.panel().textContent.includes('Not saved yet.'), 'failure remains honest');
  assert.ok(f.panel().textContent.includes('Save now')); config.failSave = false;
  f.click(f.panel().querySelector('[data-ace^="learn-now:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 2 && !f.panel().querySelector('.studio-question')?.textContent.includes('integration tests'), 'retry saves without approval'); assert.equal(f.saved.length, 2);
});

test('long question keys fit the existing API and remain reusable', async t => {
  const question = 'Describe your experience ' + 'building fictional integration fixtures '.repeat(7);
  const memoryStore = []; const f = fixture(`<label for="detail">${question}</label><textarea id="detail"></textarea>`, { autoLearn: true, memoryStore }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Fictional technical answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  await until(() => f.saved.length === 1, 'long question can save'); assert.match(f.saved[0].concept, /^q:sha256:[a-f0-9]{64}$/);
  const next = fixture(`<label for="detail">${question}</label><textarea id="detail"></textarea>`, { autoKnown: true, autoLearn: true, memoryStore }); t.after(next.dispose);
  await until(() => next.document.getElementById('detail').value === field.value, 'hashed key still matches full question');
});

test('custom dropdown learns only a committed choice from its associated menu', async t => {
  const f = fixture('<label for="detail">Which interview format do you prefer?</label><div><input id="detail" role="combobox" aria-controls="formats"></div><div role="listbox" id="unrelated"><div role="option">Unrelated</div></div>', { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail');
  field.addEventListener('click', () => {
    if (f.document.getElementById('formats')) return;
    const box = f.document.createElement('div'); box.id = 'formats'; box.setAttribute('role', 'listbox');
    const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Remote'; option.addEventListener('click', () => { setTimeout(() => { field.value = 'Remote'; box.remove(); }, 0); }); box.append(option); f.document.body.append(box);
  });
  ownerEvent(f, field, 'click'); field.value = 'Rem'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  ownerEvent(f, f.document.querySelector('#unrelated [role=option]'), 'click'); await sleep(450); assert.equal(f.saved.length, 0);
  ownerEvent(f, f.document.querySelector('#formats [role=option]'), 'click');
  await until(() => f.saved.length === 1, 'real associated choice should save'); assert.equal(f.saved[0].answer, 'Remote'); assert.equal(f.submissions(), 0);
});

test('custom option clicks that leave a query uncommitted do not learn', async t => {
  const f = fixture('<label for="detail">Which interview format do you prefer?</label><div><input id="detail" role="combobox" aria-controls="formats"></div><div role="listbox" id="formats"><div role="option">Remote</div></div>', { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); ownerEvent(f, field, 'click'); field.value = 'Remote'; ownerEvent(f, field, 'input');
  ownerEvent(f, f.document.querySelector('#formats [role=option]'), 'click'); await sleep(500); assert.equal(f.saved.length, 0);
});


test('auto-learning preserves a non-equivalent answer with the same broad legacy concept', async t => {
  const memoryStore = [{ id: 1, concept: 'python_api_experience', question: 'Describe your current Python API experience', answer: 'Fictional current answer', answer_type: 'text', reuse_policy: 'reusable', revision: 1 }];
  const f = fixture('<label for="detail">Describe your previous Python API experience</label><textarea id="detail"></textarea>', { autoLearn: true, memoryStore }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Fictional previous answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  await until(() => f.saved.length === 1, 'qualified answer should save independently');
  assert.equal(memoryStore.length, 2); assert.equal(memoryStore[0].answer, 'Fictional current answer'); assert.notEqual(f.saved[0].concept, memoryStore[0].concept);
});


test('native radio and aria-only choice buttons save the actual chosen answer automatically', async t => {
  for (const buttons of [false, true]) {
    const choices = buttons ? '<button type="button" role="radio" aria-checked="false" id="remote">Remote</button><button type="button" role="radio" aria-checked="false" id="office">On site</button>' : '<input id="remote" type="radio" name="format"><label for="remote">Remote</label><input id="office" type="radio" name="format"><label for="office">On site</label>';
    const f = fixture(`<fieldset><legend>Which interview format do you prefer?</legend>${choices}</fieldset>`, { autoLearn: true }); t.after(f.dispose);
    const field = f.document.getElementById('office');
    if (buttons) { field.addEventListener('click', () => field.setAttribute('aria-checked', 'true')); ownerEvent(f, field, 'click'); }
    else { field.checked = true; ownerEvent(f, field, 'change'); }
    await until(() => f.saved.length === 1, 'actual radio choice should save'); assert.equal(f.saved[0].answer, 'On site'); assert.equal(f.submissions(), 0);
    f.dispose();
  }
});
