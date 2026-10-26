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
  const { window } = parseHTML(`<html><head><title>Engineer | Fictional employer</title></head><body><form>${config.topOnly ? "" : base}${body}<button type="submit">Submit application</button></form></body></html>`);
  delete window.__aceLoaded;
  window.top = config.embedded ? {} : window;
  const { document, HTMLElement, HTMLInputElement, HTMLSelectElement, HTMLOptionElement } = window;
  const timers = new Set();
  const listeners = [];
  const saved = [];
  const memoryStore = config.memoryStore || [];
  let submissions = 0;
  let active = document.body;
  Object.defineProperty(document, 'activeElement', { get: () => active });
  Object.defineProperty(HTMLElement.prototype, 'offsetParent', { get() { return this.hidden ? null : document.body; }, configurable: true });
  Object.defineProperty(HTMLElement.prototype, 'offsetLeft', { get() { return parseFloat(this.style.left) || 0; }, configurable: true });
  Object.defineProperty(HTMLElement.prototype, 'offsetTop', { get() { return parseFloat(this.style.top) || 0; }, configurable: true });
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
    innerWidth: config.width || 1440, innerHeight: config.height || 900, console, crypto: webcrypto, TextEncoder,
    setTimeout(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; },
    clearTimeout(id) { clearTimeout(id); timers.delete(id); },
    MutationObserver: config.observeDOM ? window.MutationObserver : class { observe() {} disconnect() {} },
    chrome: { ...(config.autoKnown || config.autoLearn !== undefined ? { storage: { local: {
      get(defaults, reply) { reply({ ...defaults, aceAutoKnown: !!config.autoKnown, aceAutoLearnRoutine: !!config.autoLearn }); }, set() {}, remove() {},
    } } } : {}), runtime: { id: 'fixture-extension', lastError: null, onMessage: { addListener(listener) { listeners.push(listener); } }, getURL: value => value, getManifest: () => ({ version: 'test' }),
      sendMessage(message, reply) {
        if (config.onSend?.(message, reply)) return;
        if (message.type === 'aceFocusRoute') { reply({ ok: false }); return; }
        if (message.type === 'answers') reply({ ok: true, items: config.answerItems || [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }, { label: 'Current role', value: 'Engineer' }] });
        else if (message.type === 'memory') reply({ ok: true, items: memoryStore });
        else if (message.type === 'memorySave') {
          saved.push(message.item);
          if (config.failSave) { reply({ ok: false, error: "unavailable" }); return; }
          const existing = memoryStore.find(entry => entry.concept === message.item.concept);
          const entry = { ...message.item, id: existing?.id || memoryStore.length + 1, revision: (existing?.revision || 0) + 1, reuse_policy: 'reusable' };
          if (existing) Object.assign(existing, entry); else memoryStore.push(entry);
          reply({ ok: true, item: entry });
        }
        else if (message.type === 'history') reply({ ok: true, work: config.work || [], education: config.education || [] });
        else reply({ ok: true, items: [], work: [], education: [] });
      } } },
  });
  document.querySelector('form').addEventListener('submit', event => { event.preventDefault(); submissions++; });
  for (const file of ['fields.js', 'memory.js', 'content.js']) vm.runInContext(fs.readFileSync(path.join(extension, file), 'utf8'), context, { filename: file });
  const panel = () => document.querySelector('.ace-root')?.shadowRoot?.querySelector('.ace-panel');
  function click(action) { const button = panel()?.querySelector(`[data-ace="${action}"]`); assert.ok(button, `Missing action ${action}`); button.click(); }
  function review(question) {
    if (!panel().classList.contains('focus-review')) click('tab:review');
    const button = Array.from(panel().querySelectorAll('[data-ace^="question:"]')).find(button => button.textContent.includes(question));
    assert.ok(button, `Missing review prompt ${question}`); button.click();
  }
  return { window, document, context, internals: window.__aceInternals, panel, click, review, saved,
    deliver(message, sender = { id: 'fixture-extension' }) {
      let response;
      for (const listener of listeners) listener(message, sender, value => { response = value; });
      return response;
    }, submissions: () => submissions,
    dispose() { timers.forEach(clearTimeout); } };
}

test('quick fill has one main action and fills every matching native dropdown without changing existing answers', t => {
  const memoryStore = [{ id: 1, concept: 'q:preferred development environment', question: 'Preferred development environment', answer: 'Linux', answer_type: 'choice', reuse_policy: 'reusable' }];
  const f = fixture(['first', 'second', 'manual', 'unavailable'].map(id => `<label for="${id}">Preferred development environment</label><select id="${id}"><option value="">Select one</option>${id === 'unavailable' ? '<option value="other">Other</option>' : '<option value="linux">Linux</option><option value="mac">macOS</option>'}</select>`).join(''), { memoryStore }); t.after(f.dispose);
  assert.equal(f.panel().querySelector('[data-ace="fill"]').textContent, 'Fill all known answers');
  assert.equal(f.panel().querySelectorAll('.focus-compact-actions button').length, 1);
  assert.equal(Boolean(f.panel().querySelector('#studio-reuse')), false);
  f.document.getElementById('manual').value = 'mac'; f.click('fill');
  assert.equal(f.document.getElementById('first').value, 'linux');
  assert.equal(f.document.getElementById('second').value, 'linux');
  assert.equal(f.document.getElementById('manual').value, 'mac');
  assert.equal(f.document.getElementById('unavailable').value, '');
  assert.ok(f.panel().querySelector('[data-ace="tab:review"]').textContent.includes('(1)'), 'a repeated question with incompatible options stays visible');
  assert.equal(f.submissions(), 0); f.click('undo');
  assert.equal(f.document.getElementById('first').value, '');
  assert.equal(f.document.getElementById('second').value, '');
  assert.equal(f.document.getElementById('manual').value, 'mac');
});

test('one answer fills equivalent prompts immediately and a failed background save does not reopen them', async t => {
  const config = { failSave: true };
  const f = fixture('<label for="first">Describe your experience writing integration tests</label><textarea id="first"></textarea><label for="second">Please tell us about your experience writing integration tests.</label><textarea id="second"></textarea><label for="other">Describe your experience writing unit tests</label><textarea id="other"></textarea>', config); t.after(f.dispose);
  f.review('Describe your experience writing integration');
  assert.equal(Boolean(f.panel().querySelector('#studio-reuse')), false, 'no separate remember checkbox');
  const editor = f.panel().querySelector('#studio-answer'); editor.value = 'Fictional integration testing experience'; editor.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.document.getElementById('second').value === editor.value, 'one click fills equivalent prompts');
  assert.equal(f.document.getElementById('other').value, '');
  assert.ok(f.panel().textContent.includes('Saving for future applications failed'));
  assert.equal(f.panel().querySelector('.studio-question')?.textContent, 'Describe your experience writing unit tests');
  config.failSave = false; f.click('workspace');
  const retry = f.panel().querySelector('[data-ace^="retry-save:"]'); assert.ok(retry, 'retry lives in optional settings'); f.click(retry.getAttribute('data-ace'));
  await until(() => f.saved.length === 2 && !f.panel().querySelector('[data-ace^="retry-save:"]'), 'private save can retry without answering again');
  assert.equal(f.submissions(), 0);
});

test('saved profile fills before a delayed reusable-answer request completes', async t => {
  const f = fixture('<label for="fresh">Full name</label><input id="fresh">', { autoKnown: true,
    onSend(message) { return message.type === 'memory'; } }); t.after(f.dispose);
  f.click('fill');
  await until(() => f.document.getElementById('fresh').value === 'Example Applicant', 'slow Memory must not block known profile facts');
  assert.equal(f.submissions(), 0);
});

test('job-specific dates and current-job choices come from history, never a global From answer', async t => {
  const job = (id, employer) => `<section><h2>Work experience ${id}</h2><label for="employer-${id}">Company</label><input id="employer-${id}" value="${employer}"><label for="from-${id}">From</label><input id="from-${id}" type="month"><label for="current-${id}">I currently work here</label><input id="current-${id}" type="checkbox"></section>`;
  const f = fixture(job(1, 'Fictional Current Lab') + job(2, 'Fictional Previous Lab') + job(3, 'Unknown Fictional Lab'), {
    autoLearn: true, work: [{ employer: 'Fictional Previous Lab', start_month: 5, start_year: 2020, is_current: false }, { employer: 'Fictional Current Lab', start_month: 3, start_year: 2024, is_current: true }],
    memoryStore: [{ id: 1, concept: 'q:from', question: 'From', answer: '1999-01', answer_type: 'text', reuse_policy: 'reusable' }],
  }); t.after(f.dispose); f.click('fill');
  assert.equal(f.document.getElementById('from-1').value, '2024-03');
  assert.equal(f.document.getElementById('from-2').value, '2020-05');
  assert.equal(f.document.getElementById('from-3').value, '');
  assert.equal(f.document.getElementById('current-1').checked, true);
  assert.equal(f.document.getElementById('current-2').checked, false);
  const date = f.document.getElementById('from-1'); date.value = '2024-04'; ownerEvent(f, date, 'input'); ownerEvent(f, date, 'focusout'); await sleep(450);
  assert.equal(f.saved.length, 0, 'history dates must not become shared global answers');
});

test('one click chooses a real custom history dropdown even without a global answer for From', async t => {
  const f = fixture('<section><h2>Work experience</h2><label for="company">Company</label><input id="company" value="Fictional Lab"><label for="from">From</label><button type="button" id="from" aria-haspopup="listbox" aria-controls="dates">Select One</button></section>', { work: [{ employer: 'Fictional Lab', start_month: 3, start_year: 2024, is_current: true }] }); t.after(f.dispose);
  const field = f.document.getElementById('from'); let typed = 0;
  field.addEventListener('input', () => typed++);
  field.addEventListener('click', () => {
    if (f.document.getElementById('dates')) return;
    const menu = f.document.createElement('div'); menu.id = 'dates'; menu.setAttribute('role', 'listbox');
    for (const label of ['02/2024', '03/2024']) {
      const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = label;
      option.addEventListener('click', () => { field.textContent = label; menu.remove(); }); menu.append(option);
    }
    f.document.body.append(menu);
  });
  f.click('fill'); await until(() => field.textContent === '03/2024', 'the saved date must select its actual option');
  assert.equal(typed, 0); assert.equal(f.saved.length, 0); assert.equal(f.submissions(), 0);
});

test('qualification dropdowns use saved facts while unknown age choices remain unanswered', t => {
  const f = fixture('<label for="degree">Highest qualification</label><select id="degree"><option value="">Select one</option><option value="bs">Bachelor of Science</option><option value="ms">Master of Science</option></select><label for="age">Are you at least 18 years old?</label><select id="age"><option value="">Select one</option><option>Yes</option><option>No</option></select>', { answerItems: [{ label: 'Degree', value: 'Master of Science' }] }); t.after(f.dispose);
  f.click('fill'); assert.equal(f.document.getElementById('degree').value, 'ms'); assert.equal(f.document.getElementById('age').value, ''); assert.equal(f.submissions(), 0);
});

test('editing a saved answer replaces the immediate reuse copy while preserving existing employer text', async t => {
  const f = fixture('<label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea>'); t.after(f.dispose);
  f.review('Describe your experience'); const editor = f.panel().querySelector('#studio-answer'); editor.value = 'First fictional answer'; editor.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  f.click(f.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 1, 'first answer saves privately');
  f.click('workspace'); f.click('tab:memory'); f.click('edit:1');
  f.panel().querySelector('#studio-memory-edit').value = 'Corrected fictional answer'; f.click('save-edit:1');
  f.document.querySelector('form').insertAdjacentHTML('beforeend', '<label for="later">Please tell us about your experience writing integration tests.</label><textarea id="later"></textarea>');
  f.click('fill'); assert.equal(f.document.getElementById('later').value, 'Corrected fictional answer');
  assert.equal(f.document.getElementById('detail').value, 'First fictional answer');
  assert.equal(f.submissions(), 0);
});

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
  assert.equal(Boolean(f.panel().querySelector('#studio-reuse')), false);
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
  assert.equal(Boolean(first.panel().querySelector('#studio-answer')), false, 'detected answers need approval, not another editor');
  assert.equal(first.panel().querySelector('[data-ace^="approve:"]').textContent, 'Use answer');
  assert.equal(first.saved.length, 0, 'observing a typed answer never saves it');
  first.click(first.panel().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => first.saved.length === 1, 'explicit approval saves the detected answer');
  assert.equal(writes, 1, 'approval must not fill the employer field a second time');
  const answer = field.value;
  first.dispose();
  const later = fixture('<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', { memoryStore, autoKnown: true }); t.after(later.dispose); later.click('fill');
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
  const later = fixture('<label for="channel">Which application channel did you use?</label><select id="channel"><option value="">Select one</option><option value="new-site">Careers website</option><option value="new-ref">Friend referral</option></select>', { memoryStore, autoKnown: true }); t.after(later.dispose); later.click('fill');
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
  assert.equal(Boolean(f.panel().querySelector('[data-ace^="read-options:"]')), false, 'an existing answer does not require loading options again');
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
  const later = fixture('<label for="authorization">Are you authorized to work in the U.S.?</label><select id="authorization"><option value="">Select one</option><option>Yes</option><option>No</option></select>', { memoryStore, autoKnown: true }); t.after(later.dispose); later.click('fill');
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
  const later = fixture('<label for="testing">Please tell us about your experience writing integration tests.</label><textarea id="testing"></textarea>', { memoryStore, autoKnown: true }); t.after(later.dispose); later.click('fill');
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
  assert.equal(Boolean(f.panel().querySelector('textarea')), false, 'dropdowns never become free-text editors');
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
  assert.equal(Boolean(f.panel().querySelector('#studio-answer')), false);
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
  first.click('tab:review'); assert.equal(Boolean(first.panel().querySelector('[data-ace^="approve:"]')), false); assert.ok(first.panel().textContent.includes('Answered on form'));
  const next = fixture('<label for="next">Can you describe your experience writing integration tests?</label><textarea id="next"></textarea>', { autoKnown: true, autoLearn: true, memoryStore }); t.after(next.dispose); next.click('fill');
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

test('Memory switch cancels pending saving without asking for the completed form answer again', async t => {
  const f = fixture(routine, { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Fictional final answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  f.click('workspace'); f.click('tab:memory');
  assert.equal(f.panel().querySelector('[data-ace=auto-learn]').getAttribute('aria-checked'), 'true'); f.click('auto-learn');
  await sleep(450); assert.equal(f.saved.length, 0);
  f.click('tab:review');
  await until(() => f.panel().textContent.includes('Answered on form'), 'completed answer remains complete with learning disabled');
  assert.equal(Boolean(f.panel().querySelector('[data-ace^="approve:"]')), false);
  f.click(f.panel().querySelector('[data-ace^="edit-answer:"]').getAttribute('data-ace'));
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
  await until(() => f.panel().textContent.includes('Saving for next time failed.'), 'failure remains honest');
  assert.ok(f.panel().textContent.includes('Retry saving')); config.failSave = false;
  f.click(f.panel().querySelector('[data-ace^="retry-save:"]').getAttribute('data-ace'));
  await until(() => f.saved.length === 2 && !f.panel().textContent.includes('Saving for next time failed.'), 'retry saves without approval'); assert.equal(f.saved.length, 2);
});

test('long question keys fit the existing API and remain reusable', async t => {
  const question = 'Describe your experience ' + 'building fictional integration fixtures '.repeat(7);
  const memoryStore = []; const f = fixture(`<label for="detail">${question}</label><textarea id="detail"></textarea>`, { autoLearn: true, memoryStore }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Fictional technical answer'; ownerEvent(f, field, 'input'); ownerEvent(f, field, 'focusout');
  await until(() => f.saved.length === 1, 'long question can save'); assert.match(f.saved[0].concept, /^q:sha256:[a-f0-9]{64}$/);
  const next = fixture(`<label for="detail">${question}</label><textarea id="detail"></textarea>`, { autoKnown: true, autoLearn: true, memoryStore }); t.after(next.dispose); next.click('fill');
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


function framedFixture(body) {
  const endpoints = new Map(), routes = [];
  let route;
  const runtime = { id: 'fixture-extension', lastError: null, onMessage: { addListener(listener) { route = listener; } } };
  const background = vm.createContext({ chrome: { runtime, tabs: { sendMessage(tab, message, target, reply) {
    routes.push({ tab, message, target });
    reply(endpoints.get(target.frameId)?.deliver(message));
  } } } });
  vm.runInContext(fs.readFileSync(path.join(extension, 'background.js'), 'utf8'), background);
  function config(frame, extra) {
    return { autoLearn: false, ...extra, onSend(message, reply) {
      if (message.type !== 'aceFocusRoute') return false;
      route(message, { id: runtime.id, tab: { id: 17 }, frameId: frame, documentId: `fictional-document-${frame}` }, reply); return true;
    } };
  }
  const top = fixture('', config(0, { topOnly: true })); endpoints.set(0, top);
  const source = fixture(body, config(7, { embedded: true, width: 600, height: 700 })); endpoints.set(7, source);
  const remote = () => top.internals.remotePanel();
  return { top, source, remote, routes, route, endpoints,
    click(action) { const button = remote()?.querySelector(`[data-ace="${action}"]`); assert.ok(button, `Missing outer action ${action}`); button.click(); },
    dispose() { top.dispose(); source.dispose(); } };
}

test('embedded application card renders outside the form frame and drags across the outer viewport', async t => {
  const f = framedFixture(routine); t.after(f.dispose);
  await until(() => f.remote(), 'outer viewport should host the card');
  await until(() => f.source.document.querySelector('.ace-root').style.visibility === 'hidden', 'local card should hide after the outer receiver acknowledges');
  assert.equal(f.top.document.querySelector('.ace-remote-root').shadowRoot, null, 'outer page cannot inspect the mirrored Answer Memory DOM');
  const card = f.remote(); const grip = card.querySelector('[data-focus-grip]'); let captured = false;
  card.setPointerCapture = () => { captured = true; };
  function pointer(type, x, y) { const event = new f.top.window.Event(type, { bubbles: true, cancelable: true }); Object.assign(event, { button: 0, pointerId: 1, clientX: x, clientY: y, pointerType: 'mouse' }); grip.dispatchEvent(event); }
  pointer('pointerdown', 1200, 50); assert.equal(captured, true, 'capture begins before the pointer can leave the grip');
  pointer('pointermove', 100, 210); pointer('pointerup', 100, 210);
  assert.ok(parseFloat(card.style.left) < 100, 'card can move left of the embedded form column');
  assert.equal(parseFloat(card.style.top), 178);
  f.click('tab:review'); await until(() => f.remote()?.classList.contains('focus-review'), 'review stays connected after dragging');
  assert.ok(parseFloat(f.remote().style.left) < 100, 'source rerender keeps the outer drag position');
  assert.equal(f.top.panel(), undefined, 'outer page does not start a separate application controller');
  assert.equal(f.source.submissions(), 0);
});

test('outer Review edits, approval, Memory and undo operate only on the originating frame', async t => {
  const f = framedFixture(routine); t.after(f.dispose);
  await until(() => f.remote(), 'outer card should appear'); f.click('tab:review');
  await until(() => f.remote()?.querySelector('.focus-chips'), 'Review should appear');
  const priorEditor = f.remote().querySelector('#studio-answer');
  const chip = Array.from(f.remote().querySelectorAll('[data-ace^="question:"]')).find(button => button.textContent.includes('integration tests')); chip.click();
  await until(() => f.remote()?.querySelector('#studio-answer') !== priorEditor, 'source refresh arrives after question selection');
  await until(() => f.remote()?.querySelector('.studio-question')?.textContent.includes('integration tests'), 'right source question should appear');
  const editor = f.remote().querySelector('#studio-answer'); editor.value = 'Fictional answer entered in the outer card'; editor.dispatchEvent(new f.top.window.Event('input', { bubbles: true }));
  assert.equal(f.source.document.getElementById('detail').value, '', 'typing in ACE remains a draft');
  f.click(f.remote().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.source.saved.length === 1, 'source controller verifies filling and saves Memory');
  assert.equal(f.source.document.getElementById('detail').value, 'Fictional answer entered in the outer card');
  await until(() => !f.remote()?.querySelector('.studio-question')?.textContent.includes('integration tests'), 'outer card receives completion');
  f.click('workspace'); await until(() => f.remote()?.querySelector('[data-ace="tab:memory"]'), 'Settings navigation arrives'); f.click('tab:memory'); await until(() => f.remote()?.textContent.includes('Saved for reuse'), 'Memory remains functional');
  f.click('tab:activity'); await until(() => f.remote()?.textContent.includes('Undo last fill'), 'Activity remains functional'); f.click('undo');
  await until(() => f.source.document.getElementById('detail').value === '', 'Undo reaches the originating field');
  assert.equal(f.source.submissions() + f.top.submissions(), 0);
  assert.ok(f.routes.filter(route => route.message.op === 'event').every(route => route.target.frameId === 7 && route.target.documentId === 'fictional-document-7'));
});

test('outer native choices preserve opaque values and protected decisions remain application-only', async t => {
  const f = framedFixture('<label for="sponsor">Do you require sponsorship?</label><select id="sponsor"><option value="">Select One</option><option value="sponsor-19">Yes</option></select>'); t.after(f.dispose);
  await until(() => f.remote(), 'outer card appears'); f.click('tab:review');
  await until(() => f.remote()?.querySelector('.focus-chips'), 'Review appears');
  const priorEditor = f.remote().querySelector('#studio-answer');
  Array.from(f.remote().querySelectorAll('[data-ace^="question:"]')).find(button => button.textContent.includes('sponsorship')).click();
  await until(() => f.remote()?.querySelector('#studio-answer') !== priorEditor, 'source refresh arrives after question selection');
  await until(() => f.remote()?.querySelector('.studio-question')?.textContent.includes('sponsorship'), 'protected prompt appears');
  const select = f.remote().querySelector('#studio-answer'); select.value = 'sponsor-19'; select.dispatchEvent(new f.top.window.Event('change', { bubbles: true }));
  assert.equal(f.source.document.getElementById('sponsor').value, '');
  f.click(f.remote().querySelector('[data-ace^="approve:"]').getAttribute('data-ace'));
  await until(() => f.source.document.getElementById('sponsor').value === 'sponsor-19', 'exact original option is selected');
  assert.equal(f.source.saved.length, 0); assert.equal(f.source.submissions(), 0);
});

test('outer Close, popup Wake, dock and keyboard movement remain connected', async t => {
  const f = framedFixture(routine); t.after(f.dispose);
  await until(() => f.remote(), 'outer card appears'); f.click('minimize');
  await until(() => f.remote()?.classList.contains('focus-dock'), 'dock is outer-page-owned');
  const grip = f.remote().querySelector('[data-focus-grip]'); const before = parseFloat(f.remote().style.left);
  const event = new f.top.window.Event('keydown', { bubbles: true, cancelable: true }); Object.assign(event, { key: 'ArrowLeft' }); grip.dispatchEvent(event);
  assert.equal(parseFloat(f.remote().style.left), before - 10);
  f.click('close'); await until(() => !f.remote(), 'Close hides the outer card');
  assert.equal(Boolean(f.source.document.querySelector('.ace-root')), false);
  assert.equal(f.top.deliver({ type: 'wake' }).ok, true);
  await until(() => f.remote()?.classList.contains('focus-compact'), 'popup Wake reopens the same embedded application');
  assert.equal(f.top.panel(), undefined); assert.equal(f.source.submissions(), 0);
});

test('frame relay rejects foreign senders, wrong directions and stale review actions', async t => {
  const f = framedFixture(routine); t.after(f.dispose);
  await until(() => f.remote(), 'outer card appears');
  for (const sender of [{ id: 'other-extension', tab: { id: 17 }, frameId: 0 }, { id: 'fixture-extension', frameId: 0 }, { id: 'fixture-extension', tab: { id: 17 }, frameId: 7 }]) {
    let reply; const count = f.routes.length;
    f.route({ type: 'aceFocusRoute', op: 'event', sourceFrame: 7 }, sender, value => { reply = value; });
    assert.equal(reply.ok, false); assert.equal(f.routes.length, count);
  }
  const snapshot = f.routes.find(route => route.message.op === 'render').message;
  f.click('tab:review'); await until(() => f.remote()?.classList.contains('focus-review'), 'new revision appears');
  assert.equal(f.source.deliver({ ...snapshot, op: 'event', event: 'click', action: 'fill', control: 0 }).ok, false);
  assert.equal(f.source.document.getElementById('detail').value, '');
  assert.equal(f.source.deliver({ ...snapshot, session: 'wrong-session', op: 'event', event: 'wake' }).ok, false);
});

test('motivation values never enter frame relay snapshots and missing outer receivers retain a usable local card', async t => {
  const f = framedFixture('<label for="why">Why this company?</label><textarea id="why">Private fictional motivation excluded from ACE</textarea>'); t.after(f.dispose);
  await until(() => f.remote(), 'outer card appears');
  assert.ok(f.routes.filter(route => route.message.op === 'render').every(route => !JSON.stringify(route.message).includes('Private fictional motivation')));
  const fallback = fixture(routine, { embedded: true }); t.after(fallback.dispose);
  await sleep(100); assert.ok(fallback.panel()); assert.notEqual(fallback.document.querySelector('.ace-root').style.visibility, 'hidden');
});

test('employer focus does not change the chosen ACE prompt or disturb an editor draft', async t => {
  const f = fixture(Array.from({ length: 9 }, (_, at) => `<label for="detail-${at}">Fictional screening question ${at + 1}</label><textarea id="detail-${at}"></textarea>`).join(''), { autoLearn: false }); t.after(f.dispose);
  f.review('Fictional screening question 1');
  const editor = f.panel().querySelector('#studio-answer'); editor.value = 'Fictional draft retained in ACE'; editor.dispatchEvent(new f.window.Event('input', { bubbles: true }));
  ownerEvent(f, f.document.getElementById('detail-8'), 'pointerdown'); await sleep(180);
  assert.equal(f.panel().querySelector('.studio-question').textContent, 'Fictional screening question 1');
  assert.equal(f.panel().querySelector('#studio-answer').value, 'Fictional draft retained in ACE');
  f.review('Fictional screening question 9'); assert.equal(f.panel().querySelector('.studio-question').textContent, 'Fictional screening question 9');
  f.review('Fictional screening question 1'); assert.equal(f.panel().querySelector('#studio-answer').value, 'Fictional draft retained in ACE');
  assert.equal(f.document.getElementById('detail-0').value, '');
});

test('a committed protected employer selection finishes locally without a second approval or Memory save', async t => {
  const f = fixture('<label for="sponsor">Will you require visa sponsorship?</label><select id="sponsor"><option value="">Select One</option><option value="yes-9">Yes</option><option value="no-3">No</option></select>', { autoLearn: true }); t.after(f.dispose);
  f.click('tab:review');
  const field = f.document.getElementById('sponsor'); ownerEvent(f, field, 'focusin'); field.value = 'yes-9'; ownerEvent(f, field, 'change');
  await until(() => f.panel().textContent.includes('Answered on form'), 'actual applicant selection is the per-form decision');
  assert.ok(f.panel().textContent.includes('this application only')); assert.equal(Boolean(f.panel().querySelector('[data-ace^="approve:"]')), false); assert.equal(Boolean(f.panel().querySelector('#studio-answer')), false);
  await sleep(400); assert.equal(f.saved.length, 0);
  field.dispatchEvent(new f.window.Event('change', { bubbles: true })); await sleep(220);
  assert.ok(f.panel().textContent.includes('Answered on form'), 'unchanged synthetic events cannot reopen a completed question');
  field.value = ''; f.click('theme');
  assert.ok(!f.panel().textContent.includes('Answered on form'), 'clearing the real answer invalidates completion'); assert.ok(f.panel().querySelector('#studio-answer'));
  assert.equal(f.submissions(), 0);
});

test('protected prefills stay visible for confirmation rather than being silently approved by focus', async t => {
  const f = fixture('<label for="sponsor">Will you require visa sponsorship?</label><select id="sponsor"><option value="">Select One</option><option value="yes-9" selected>Yes</option></select>', { autoLearn: true }); t.after(f.dispose);
  f.click('tab:review');
  const field = f.document.getElementById('sponsor'); ownerEvent(f, field, 'focusin');
  await until(() => f.panel().querySelector('.focus-detected'), 'existing answer is shown without re-entry');
  assert.ok(f.panel().querySelector('.focus-detected').textContent.includes('Yes'));
  assert.equal(f.panel().querySelector('[data-ace^="approve:"]').textContent, 'Use answer'); assert.equal(f.saved.length, 0);
});

test('inputless ARIA comboboxes expose their actual selected label and committed protected choice', async t => {
  const f = fixture('<label id="sponsor-label">Will you require visa sponsorship?</label><div id="sponsor" role="combobox" aria-labelledby="sponsor-label" aria-controls="sponsor-options" tabindex="0">Select One</div>', { autoLearn: true }); t.after(f.dispose);
  const field = f.document.getElementById('sponsor'); f.click('tab:review');
  field.addEventListener('click', event => { if (event.target !== field) return; setTimeout(() => {
    if (f.document.getElementById('sponsor-options')) return;
    const menu = f.document.createElement('div'); menu.id = 'sponsor-options'; menu.setAttribute('role', 'listbox');
    const option = f.document.createElement('div'); option.setAttribute('role', 'option'); option.textContent = 'Yes';
    option.addEventListener('click', () => setTimeout(() => { field.textContent = 'Yes'; menu.remove(); }, 0)); menu.append(option); field.append(menu);
  }, 0); });
  ownerEvent(f, field, 'focusin');
  await until(() => f.panel().querySelector('[data-ace^="read-options:"]'), 'declared inputless dropdown stays a choice control');
  ownerEvent(f, field, 'click'); await until(() => f.document.querySelector('#sponsor-options [role=option]'), 'real menu opens');
  ownerEvent(f, f.document.querySelector('#sponsor-options [role=option]'), 'click');
  await until(() => f.panel().textContent.includes('Answered on form'), 'committed custom choice is acknowledged without re-entering');
  assert.ok(f.panel().textContent.includes('Yes')); assert.equal(f.saved.length, 0); assert.equal(f.submissions(), 0);
});

test('known answers wait for an explicit Fill and focus never reverses Undo', async t => {
  const memoryStore = [{ id: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional remembered test experience', answer_type: 'text', reuse_policy: 'reusable', revision: 1 }];
  const f = fixture('', { autoKnown: true, autoLearn: true, memoryStore }); t.after(f.dispose); await sleep(150);
  const label = f.document.createElement('label'); label.setAttribute('for', 'new-question'); label.textContent = 'Could you describe your experience writing integration tests?';
  const field = f.document.createElement('textarea'); field.id = 'new-question'; f.document.querySelector('form').append(label, field);
  field.focus(); ownerEvent(f, field, 'focusin');
  await sleep(200); assert.equal(field.value, ''); assert.ok(f.panel().classList.contains('focus-compact'));
  f.click('fill'); await until(() => field.value === memoryStore[0].answer, 'explicit Fill uses the known answer');
  assert.equal(f.saved.length, 0, 'ACE does not relearn its own write');
  assert.ok(f.document.activeElement === field, 'manual Fill keeps the current employer focus');
  f.click('workspace'); f.click('tab:activity'); f.click('undo'); assert.equal(field.value, '');
  ownerEvent(f, field, 'focusin'); await sleep(200); assert.equal(field.value, '', 'focusing does not reverse an explicit Undo'); assert.equal(f.submissions(), 0);
});

test('hover and synthetic focus leave the selected question alone and never infer sensitive answers', async t => {
  const memoryStore = [{ id: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional remembered answer', answer_type: 'text', reuse_policy: 'reusable', revision: 1 }];
  const f = fixture('', { autoKnown: true, autoLearn: true, memoryStore }); t.after(f.dispose); await sleep(150);
  const container = f.document.createElement('div'); container.innerHTML = '<label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea><label for="sponsor">Will you require visa sponsorship?</label><input id="sponsor"><label for="why">Why this company?</label><textarea id="why"></textarea>'; f.document.querySelector('form').append(container);
  const field = f.document.getElementById('detail'); field.dispatchEvent(new f.window.Event('focusin', { bubbles: true })); await sleep(150); assert.equal(field.value, '');
  f.click('tab:review'); const selected = f.panel().querySelector('.studio-question').textContent; ownerEvent(f, field, 'pointerover'); await sleep(180); assert.equal(field.value, ''); assert.equal(f.panel().querySelector('.studio-question').textContent, selected);
  ownerEvent(f, f.document.getElementById('sponsor'), 'focusin'); await sleep(180); assert.equal(f.document.getElementById('sponsor').value, '');
  const why = f.document.getElementById('why'); let reads = 0; Object.defineProperty(why, 'value', { get() { reads++; return 'Excluded'; } });
  ownerEvent(f, why, 'focusin'); ownerEvent(f, why, 'pointerover'); await sleep(180); assert.equal(reads, 0); assert.ok(!f.panel().textContent.includes('Why this company'));
});

test('pointed known native choices reject employer reversion instead of claiming completion', async t => {
  const memoryStore = [{ id: 1, concept: 'q:which interview format do you prefer', question: 'Which interview format do you prefer?', answer: 'Remote', answer_type: 'choice', reuse_policy: 'reusable', revision: 1 }];
  const f = fixture('', { autoKnown: true, autoLearn: false, memoryStore }); t.after(f.dispose); await sleep(150);
  const container = f.document.createElement('div'); container.innerHTML = '<label for="format">Which interview format do you prefer?</label><select id="format"><option value="">Select One</option><option value="remote-19">Remote</option></select>'; f.document.querySelector('form').append(container);
  const field = f.document.getElementById('format'); field.addEventListener('change', () => setTimeout(() => { field.value = ''; }, 10));
  ownerEvent(f, field, 'focusin'); await sleep(150); assert.equal(field.value, ''); f.click('fill'); await sleep(150); f.click('theme'); assert.equal(field.value, ''); assert.ok(!f.panel().textContent.includes('Answered on form')); assert.equal(f.saved.length, 0);
});

test('employer edits stay passive through the outer card and finish without duplicate approval', async t => {
  const f = framedFixture('<label for="sponsor">Will you require visa sponsorship?</label><select id="sponsor"><option value="">Select One</option><option value="yes-7">Yes</option></select>' + routine); t.after(f.dispose);
  await until(() => f.remote(), 'outer card appears');
  const sponsor = f.source.document.getElementById('sponsor'); ownerEvent(f.source, sponsor, 'focusin'); sponsor.value = 'yes-7'; ownerEvent(f.source, sponsor, 'change');
  await sleep(250); assert.ok(f.remote().classList.contains('focus-compact'), 'typing does not open Review');
  f.click('tab:review'); await until(() => f.remote()?.querySelector('.studio-question')?.textContent.includes('integration tests'), 'only unanswered questions need input');
  assert.equal(sponsor.value, 'yes-7'); assert.equal(f.source.saved.length, 0); assert.equal(f.source.submissions(), 0);
});


test('pointed choice autofill never clicks a submit button even if it declares choice semantics', async t => {
  const memoryStore = [{ id: 1, concept: 'q:are you available for a remote interview', question: 'Are you available for a remote interview?', answer: 'Yes', answer_type: 'yesno', reuse_policy: 'reusable', revision: 1 }];
  const f = fixture('', { autoKnown: true, autoLearn: false, memoryStore }); t.after(f.dispose); await sleep(150);
  const group = f.document.createElement('div'); group.setAttribute('role', 'radiogroup'); group.setAttribute('aria-label', 'Are you available for a remote interview?');
  group.innerHTML = '<button id="no" type="button" aria-pressed="false">No</button><button id="bad-choice" type="submit" aria-pressed="false">Yes</button>'; f.document.querySelector('form').append(group);
  let attempts = 0; f.document.getElementById('bad-choice').addEventListener('click', () => { attempts++; });
  ownerEvent(f, f.document.getElementById('no'), 'focusin'); await sleep(250);
  assert.equal(attempts, 0); assert.equal(f.saved.length, 0); assert.equal(f.submissions(), 0);
});

test('legacy auto-fill preferences cannot write or open Review on load, focus, hover or typing', async t => {
  const memoryStore = [{ id: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Fictional saved answer', answer_type: 'text', reuse_policy: 'reusable' }];
  const f = fixture('<label for="known">Describe your experience writing integration tests</label><textarea id="known"></textarea><label for="manual">Additional screening detail</label><input id="manual">', { autoKnown: true, autoLearn: true, memoryStore }); t.after(f.dispose);
  await sleep(200); const known = f.document.getElementById('known'), manual = f.document.getElementById('manual');
  for (const type of ['focusin', 'pointerdown', 'pointerover']) ownerEvent(f, known, type);
  manual.value = 'Applicant is typing'; ownerEvent(f, manual, 'input');
  await sleep(250); assert.equal(known.value, ''); assert.equal(manual.value, 'Applicant is typing');
  assert.ok(f.panel().classList.contains('focus-compact')); assert.equal(Boolean(f.panel().querySelector('#studio-answer')), false);
  f.click('minimize'); ownerEvent(f, known, 'focusin'); await sleep(150); assert.ok(f.panel().classList.contains('focus-dock'));
  f.click('expand'); f.click('fill'); assert.equal(known.value, memoryStore[0].answer); assert.equal(manual.value, 'Applicant is typing'); assert.equal(f.submissions(), 0);
});

test('selected Yes Required state never replaces the actual Workday question or spreads a saved Yes', t => {
  const body = '<div data-automation-id="formField-auth"><label id="auth-label">Are you legally authorized to work in the US?</label><button type="button" id="auth" aria-haspopup="listbox" aria-label="Yes Required" aria-labelledby="auth-label auth">Yes</button></div><div data-automation-id="formField-relative"><label id="relative-label">Do you have relatives currently employed at Fictional Labs?</label><button type="button" id="relative" aria-haspopup="listbox" aria-label="No Required" aria-labelledby="relative-label relative">No</button></div><div><button type="button" id="unnamed" aria-haspopup="listbox" aria-label="Yes Required">Yes</button></div>';
  const f = fixture(body, { memoryStore: [{ id: 1, concept: 'q:yes required', question: 'Yes Required', answer: 'Yes', answer_type: 'choice', reuse_policy: 'reusable' }] }); t.after(f.dispose);
  assert.equal(f.context.aceQuestionFor(f.document.getElementById('auth')), 'are you legally authorized to work in the us?');
  assert.equal(f.context.aceQuestionFor(f.document.getElementById('relative')), 'do you have relatives currently employed at fictional labs?');
  const missing = f.document.getElementById('unnamed'); missing.removeAttribute('id');
  assert.equal(f.context.aceQuestionFor(missing), '', 'selected-value text cannot become a reusable question');
  f.click('fill'); assert.equal(f.document.getElementById('relative').textContent, 'No'); assert.equal(f.saved.length, 0); assert.equal(f.submissions(), 0);
});

test('explicit Fill uses each exact saved authorization or sponsorship fact rather than a shared Yes', async t => {
  const f = fixture('<label for="auth">Are you legally authorized to work in the US?</label><select id="auth"><option value="">Select One</option><option>Yes</option><option>No</option></select><label for="future">Do you now or in the future require sponsorship for employment visa status?</label><select id="future"><option value="">Select One</option><option>Yes</option><option>No</option></select><label for="relative">Do you have relatives currently employed at Fictional Labs?</label><select id="relative"><option value="">Select One</option><option>Yes</option><option>No</option></select><label for="foreign">Are you authorized to work in Canada?</label><select id="foreign"><option value="">Select One</option><option>Yes</option><option>No</option></select>', { autoKnown: true, answerItems: [{ label: 'Work authorisation', value: 'Yes' }, { label: 'Need sponsorship now', value: 'No' }, { label: 'Need sponsorship in future', value: 'No' }] }); t.after(f.dispose);
  await sleep(100); assert.equal(f.document.getElementById('auth').value, '');
  f.click('fill'); assert.equal(f.document.getElementById('auth').value, 'Yes'); assert.equal(f.document.getElementById('future').value, 'No');
  assert.equal(f.document.getElementById('relative').value, ''); assert.equal(f.document.getElementById('foreign').value, ''); assert.equal(f.saved.length, 0);
});

test('Workday sectioned month/year controls receive their own job dates and correct current flags', t => {
  const date = (prefix, label) => `<div data-automation-id="formField-${prefix}"><label>${label}*</label><div data-automation-id="dateInputWrapper"><input id="${prefix}-month" aria-label="${label}" data-automation-id="dateSectionMonth-input" placeholder="MM" maxlength="2"><span>/</span><input id="${prefix}-year" aria-label="${label}" data-automation-id="dateSectionYear-input" placeholder="YYYY" maxlength="4"></div></div>`;
  const block = (id, company, end) => `<section><h2>Work Experience ${id}</h2><label for="company-${id}">Company</label><input id="company-${id}" value="${company}"><label for="current-${id}">I currently work here</label><input id="current-${id}" type="checkbox">${date(`start-${id}`, 'From')}${end ? date(`end-${id}`, 'To') : ''}</section>`;
  const f = fixture(block(1, 'Fictional Current Lab', false) + block(2, 'Fictional Previous Lab', true), { work: [{ employer: 'Fictional Previous Lab', is_current: false, start_month: 6, start_year: 2020, end_month: 8, end_year: 2023 }, { employer: 'Fictional Current Lab', is_current: true, start_month: 9, start_year: 2024 }] }); t.after(f.dispose);
  f.click('fill');
  assert.equal(f.document.getElementById('start-1-month').value, '09'); assert.equal(f.document.getElementById('start-1-year').value, '2024');
  assert.equal(f.document.getElementById('start-2-month').value, '06'); assert.equal(f.document.getElementById('start-2-year').value, '2020');
  assert.equal(f.document.getElementById('end-2-month').value, '08'); assert.equal(f.document.getElementById('end-2-year').value, '2023');
  assert.equal(f.document.getElementById('current-1').checked, true); assert.equal(f.document.getElementById('current-2').checked, false);
});

test('resume employer wording variants need independent description evidence and a unique saved job', t => {
  const description = 'Built isolated fictional integration fixtures with deterministic assertions, explicit dependency boundaries and stable application state across every test scenario.';
  const work = [{ employer: 'Fictional Research Group University', job_title: 'Research Assistant', description, start_month: 4, start_year: 2024, is_current: true }];
  const body = `<section><label for="company">Company</label><input id="company" value="University Fictional Research Group"><label for="title">Job Title</label><input id="title" value="Research Assistant"><label for="date">From</label><input id="date" type="month"><label for="description">Role Description</label><textarea id="description">${description}</textarea></section>`;
  const f = fixture(body, { work }); t.after(f.dispose); f.click('fill'); assert.equal(f.document.getElementById('date').value, '2024-04');
  const ambiguous = fixture(body, { work: [work[0], { ...work[0], start_year: 2022 }] }); t.after(ambiguous.dispose); ambiguous.click('fill'); assert.equal(ambiguous.document.getElementById('date').value, '');
  const different = fixture(body.replace(description, 'A different fictional description without corroborating evidence.'), { work }); t.after(different.dispose); different.click('fill'); assert.equal(different.document.getElementById('date').value, '');
});

test('the toolbar Fill request fills immediately while ordinary page initialization stays passive', t => {
  const f = fixture('<label for="fresh">Full name</label><input id="fresh">', { autoKnown: true }); t.after(f.dispose);
  assert.equal(f.document.getElementById('fresh').value, '');
  assert.equal(f.deliver({ type: 'wake' }).ok, true);
  assert.equal(f.document.getElementById('fresh').value, 'Example Applicant'); assert.equal(f.submissions(), 0);
});

test('a late saved-answer response cannot begin filling after the applicant starts typing', async t => {
  let respond;
  const f = fixture('<label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea>', { autoKnown: true, onSend(message, reply) { if (message.type === 'memory') { respond = reply; return true; } return false; } }); t.after(f.dispose);
  const field = f.document.getElementById('detail'); field.value = 'Applicant draft'; ownerEvent(f, field, 'input');
  respond({ ok: true, items: [{ id: 1, concept: 'q:experience writing integration tests', question: 'Describe your experience writing integration tests', answer: 'Saved fictional answer', answer_type: 'text', reuse_policy: 'reusable' }] });
  await sleep(200); assert.equal(field.value, 'Applicant draft'); assert.ok(f.panel().classList.contains('focus-compact'));
  field.value = ''; f.click('fill'); assert.equal(field.value, 'Saved fictional answer');
});

test('now-or-future sponsorship never turns an incomplete negative fact into a blanket No', t => {
  const body = '<label for="combined">Do you now or in the future require visa sponsorship?</label><select id="combined"><option value="">Select One</option><option>Yes</option><option>No</option></select>';
  for (const [present, future, expected] of [['Yes', 'No', 'Yes'], ['No', 'No', 'No'], ['', 'No', ''], ['', 'Yes', 'Yes']]) {
    const f = fixture(body, { answerItems: [{ label: 'Need sponsorship now', value: present }, { label: 'Need sponsorship in future', value: future }] }); t.after(f.dispose);
    f.click('fill'); assert.equal(f.document.getElementById('combined').value, expected); assert.equal(f.saved.length, 0); f.dispose();
  }
});

test('history locations use the saved job rather than the global contact location', t => {
  const f = fixture('<section><label for="company">Company</label><input id="company" value="Fictional Remote Lab"><label for="where">Location</label><input id="where"></section>', { work: [{ employer: 'Fictional Remote Lab', location: 'Fictional Work City', is_current: false }], answerItems: [{ label: 'Location', value: 'Fictional Home City' }] }); t.after(f.dispose);
  f.click('fill'); assert.equal(f.document.getElementById('where').value, 'Fictional Work City');
});

test('an unchecked current-job choice is a completed No rather than an inferred Yes', async t => {
  const f = fixture('<label for="current">I currently work here</label><input id="current" type="checkbox">', { autoLearn: true }); t.after(f.dispose);
  f.review('I currently work here'); const field = f.document.getElementById('current');
  field.checked = true; ownerEvent(f, field, 'change'); await sleep(100);
  field.checked = false; ownerEvent(f, field, 'change'); await until(() => f.panel().textContent.includes('Answered on form') && f.panel().querySelector('.focus-question p')?.textContent === 'No', 'the explicit No leaves the queue');
  assert.equal(f.panel().querySelector('.focus-question p').textContent, 'No');
  assert.equal(f.saved.length, 0); assert.equal(field.checked, false);
});
