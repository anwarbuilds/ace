/* Cross-origin browser DOM fixture. Chrome messaging is simulated, while the
   real background router and both real content-script instances execute.
   This is not an installed MV3 or live employer verification. */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { expect, test, type Frame } from '@playwright/test';

const extension = path.resolve(process.cwd(), '../extension');
type Message = Record<string, unknown>;

test('embedded form card moves across the outer page and retains Review, fill, dock and Close', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const outer = 'https://outer.example.test/careers';
  const form = 'https://forms.example.test/apply';
  await page.route(outer, route => route.fulfill({ contentType: 'text/html', body: `<html><body style="margin:0"><section style="width:55%;height:1600px">Fictional job description</section><iframe title="Application" src="${form}" style="position:absolute;top:30px;right:20px;width:560px;height:820px;border:0"></iframe></body></html>` }));
  await page.route(form, route => route.fulfill({ contentType: 'text/html', body: '<html><head><title>Engineer | Fictional employer</title></head><body><form><label for="name">Full name</label><input id="name" value="Example Applicant"><label for="email">Email</label><input id="email" value="applicant@example.test"><label for="phone">Phone</label><input id="phone" value="5550100100"><label for="resume">Resume</label><input id="resume" type="file"><label for="detail">Describe your experience writing integration tests</label><textarea id="detail"></textarea><label for="why">Why this company?</label><textarea id="why">Excluded fictional motivation</textarea><button type="submit">Submit application</button></form></body></html>' }));

  let router: (message: Message, sender: Message, reply: (value: Message) => void) => void = () => {};
  const frames = new Map<number, Frame>();
  const runtime = { id: 'fixture-extension', lastError: null as null | { message: string }, onMessage: { addListener(listener: typeof router) { router = listener; } } };
  vm.runInNewContext(fs.readFileSync(path.join(extension, 'background.js'), 'utf8'), { chrome: { runtime, tabs: {
    sendMessage(_tab: number, message: Message, target: { frameId: number }, reply: (value: Message) => void) {
      const frame = frames.get(target.frameId);
      if (!frame) { reply({ ok: false }); return; }
      void frame.evaluate(message => new Promise<Message>(resolve => {
        const w = window as typeof window & { __aceListeners: Array<(message: Message, sender: Message, reply: (value: Message) => void) => void> };
        for (const listener of w.__aceListeners) listener(message, { id: 'fixture-extension' }, resolve);
      }), message).then(reply, () => reply({ ok: false }));
    },
  } } });
  await page.exposeBinding('__aceTransport', ({ frame }, message: Message) => new Promise<Message>(resolve => {
    const frameId = frame === page.mainFrame() ? 0 : 7;
    router(message, { id: runtime.id, tab: { id: 17 }, frameId, documentId: `document-${frameId}` }, resolve);
  }));
  await page.goto(outer);
  const child = page.frames().find(frame => frame.url() === form)!;
  expect(child).toBeTruthy(); frames.set(0, page.mainFrame()); frames.set(7, child);
  for (const frame of [page.mainFrame(), child]) {
    await frame.evaluate(() => {
      const w = window as typeof window & { chrome: unknown; __aceListeners: unknown[]; __aceTransport: (message: Message) => Promise<Message>; __saved: Message[]; __submits: number };
      w.__aceListeners = []; w.__saved = []; w.__submits = 0;
      document.querySelector('form')?.addEventListener('submit', event => { event.preventDefault(); w.__submits++; });
      w.chrome = { storage: { local: { get(defaults: Message, reply: (value: Message) => void) { reply({ ...defaults, aceAutoKnown: false, aceAutoLearnRoutine: false }); }, set() {}, remove() {} } }, runtime: {
        id: 'fixture-extension', lastError: null, onMessage: { addListener(listener: unknown) { w.__aceListeners.push(listener); } }, getURL: (value: string) => value, getManifest: () => ({ version: 'test' }),
        sendMessage(message: Message, reply: (value: Message) => void) {
          if (message.type === 'aceFocusRoute') { void w.__aceTransport(message).then(reply); return; }
          if (message.type === 'answers') reply({ ok: true, items: [{ label: 'Full name', value: 'Example Applicant' }, { label: 'Email', value: 'applicant@example.test' }, { label: 'Phone', value: '5550100100' }] });
          else if (message.type === 'memorySave') { w.__saved.push(message.item as Message); reply({ ok: true, item: { id: 1, revision: 1 } }); }
          else reply({ ok: true, items: [], work: [], education: [] });
        },
      } };
    });
    for (const file of ['fields.js', 'memory.js', 'content.js']) await frame.addScriptTag({ path: path.join(extension, file) });
  }
  await expect.poll(() => page.evaluate(() => Boolean((window as typeof window & { __aceInternals: { remotePanel(): HTMLElement | null } }).__aceInternals.remotePanel()))).toBe(true);
  const handle = (await page.evaluateHandle(() => (window as typeof window & { __aceInternals: { remotePanel(): HTMLElement | null } }).__aceInternals.remotePanel())).asElement()!;
  expect(await page.locator('.ace-remote-root').evaluate(host => host.shadowRoot)).toBeNull();
  await expect(child.locator('.ace-root')).toHaveCSS('visibility', 'hidden');
  const grip = (await handle.$('[data-focus-grip]'))!;
  const gripBox = (await grip.boundingBox())!;
  await page.mouse.move(gripBox.x + 5, gripBox.y + 5); await page.mouse.down();
  await page.mouse.move(100, 150, { steps: 10 }); await page.mouse.up();
  const cardBox = (await handle.boundingBox())!;
  const frameBox = (await page.locator('iframe').boundingBox())!;
  expect(cardBox.x + cardBox.width).toBeLessThan(frameBox.x);
  await (await handle.$('[data-ace="tab:review"]'))!.click();
  await expect.poll(() => handle.getAttribute('class')).toContain('focus-review');
  const editor = (await handle.$('#studio-answer'))!; await editor.fill('Fictional integration test answer');
  await expect(child.locator('#detail')).toHaveValue('');
  await (await handle.$('[data-ace^="approve:"]'))!.click();
  await expect(child.locator('#detail')).toHaveValue('Fictional integration test answer');
  await expect.poll(() => child.evaluate(() => (window as typeof window & { __saved: Message[] }).__saved.length)).toBe(1);
  expect((await handle.boundingBox())!.x).toBeLessThan(frameBox.x);
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect.poll(() => handle.getAttribute('class')).toContain('night');
  await page.setViewportSize({ width: 700, height: 750 });
  await expect.poll(async () => { const box = (await handle.boundingBox())!; return box.x >= 0 && box.x + box.width <= 700 && box.y >= 0 && box.y + box.height <= 750; }).toBe(true);
  await (await handle.$('[data-ace="minimize"]'))!.click(); await expect.poll(() => handle.getAttribute('class')).toContain('focus-dock');
  await (await handle.$('[data-ace="expand"]'))!.click(); await expect.poll(() => handle.getAttribute('class')).toContain('focus-review');
  await (await handle.$('[data-ace="close"]'))!.click(); await expect(page.locator('.ace-remote-root')).toHaveCount(0);
  expect(await child.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
  await expect(child.locator('#why')).toHaveValue('Excluded fictional motivation');
});
