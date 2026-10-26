import path from "node:path";
import fs from "node:fs";
import { expect, test } from "@playwright/test";

const extensionRoot = path.resolve(process.cwd(), "../extension");
const captures = path.resolve(process.cwd(), "../artifacts/extension-v5.1");

test("Focus Mode V5.1 mirrors choices, protects motivation, stays open and never submits", async ({ page }) => {
  fs.mkdirSync(captures, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form id="application">
    <label for="name">Full name</label><input id="name">
    <label for="email">Email address</label><input id="email">
    <label for="tradeoff">Explain a distributed systems design tradeoff you faced</label><textarea id="tradeoff"></textarea>
    <label for="motivation">Why do you want to work at Cobalt Systems?</label><textarea id="motivation"></textarea>
    <label for="source">How did you hear about this position?</label><select id="source"><option value="">Select a source</option><option value="careers">Cobalt Systems website</option><option value="friend">Friend referral</option></select>
    <label for="sponsor">Will you now or later need visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select>
    <button id="submit" type="submit">Submit application</button>
  </form>`);
  await page.evaluate(() => {
    document.title = "Software Engineer | Cobalt Systems";
    const w = window as typeof window & { chrome: unknown; __memory: unknown[]; __storage: Record<string, unknown>; __submits: number; __applied: number };
    w.__memory = [{ id: 99, concept: "q:why do you want to work at cobalt systems", question: "Why do you want to work at Cobalt Systems?", answer: "Historical private motivation", answer_type: "text", reuse_policy: "reusable", revision: 1 }];
    w.__storage = { aceAutoKnown: false };
    w.__submits = 0;
    w.__applied = 0;
    document.querySelector("form")!.addEventListener("submit", event => { w.__submits++; event.preventDefault(); });
    HTMLFormElement.prototype.submit = function () { w.__submits++; };
    HTMLFormElement.prototype.requestSubmit = function () { w.__submits++; };
    document.getElementById("submit")!.addEventListener("click", () => { w.__submits++; });
    w.chrome = {
      storage: { local: {
        get: (defaults: Record<string, unknown>, callback: (value: unknown) => void) => callback({ ...defaults, ...w.__storage }),
        set: (values: Record<string, unknown>) => Object.assign(w.__storage, values),
        remove: (key: string) => { delete w.__storage[key]; },
      } },
      runtime: {
        lastError: null,
        onMessage: { addListener() {} },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "1.26.0" }),
        sendMessage: (message: { type: string; item?: Record<string, unknown>; id?: number }, callback: (reply: unknown) => void) => {
          if (/applied|applicationMark/i.test(message.type)) w.__applied++;
          if (message.type === "answers") callback({ ok: true, items: [
            { label: "Full name", value: "Example Applicant", aliases: [] },
            { label: "Email", value: "applicant@example.invalid", aliases: [] },
          ] });
          else if (message.type === "history") callback({ ok: true, work: [], education: [] });
          else if (message.type === "memory") callback({ ok: true, items: w.__memory });
          else if (message.type === "memorySave") {
            const entry = { ...message.item, id: w.__memory.length + 100, revision: 1, reuse_policy: "reusable" };
            w.__memory.push(entry); callback({ ok: true, item: entry });
          } else callback({ ok: false });
        },
      },
    };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await expect(panel).toHaveClass(/focus-compact/);
  await expect(panel.getByRole("button", { name: "Fill", exact: true })).toBeVisible();
  await expect(panel.locator(".focus-compact-title")).toHaveText("You're in control.");
  await expect(panel.locator(".focus-status")).toContainText("ACE never submits the employer form.");
  await expect(panel.getByRole("button", { name: "Scan fields" }).locator("svg path")).toHaveCount(1);
  await expect(panel).toHaveCSS("border-radius", "16px");
  await expect(panel).toHaveCSS("width", "318px");
  await panel.screenshot({ path: path.join(captures, "compact-day.png") });
  await page.locator("#motivation").fill("My own specific reason for applying.");
  await panel.getByRole("button", { name: "Fill", exact: true }).click();
  await expect(page.locator("#name")).toHaveValue("Example Applicant");
  await expect(page.locator("#motivation")).toHaveValue("My own specific reason for applying.");
  await panel.getByRole("button", { name: /Review/ }).click();
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await panel.getByRole("button", { name: "Overview" }).click();
  await page.mouse.move(0, 0);
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await panel.screenshot({ path: path.join(captures, "compact-night.png") });
  await panel.getByRole("button", { name: /Review/ }).click();
  await panel.getByRole("button", { name: "Switch to Day theme" }).click();
  await expect(panel).toHaveClass(/focus-review/);
  await expect(panel.getByText("3 open")).toBeVisible();
  await expect(panel.getByText(/Why do you want to work at Cobalt/)).toHaveCount(0);
  await expect(panel.getByText("Historical private motivation")).toHaveCount(0);
  await panel.screenshot({ path: path.join(captures, "review-day.png") });
  await panel.getByRole("textbox", { name: "Your answer" }).fill("I measured latency and chose a simpler consistency model.");
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await expect(panel.getByRole("textbox", { name: "Your answer" })).toHaveValue("I measured latency and chose a simpler consistency model.");
  await panel.screenshot({ path: path.join(captures, "review-question-night.png") });
  await panel.getByRole("button", { name: "Switch to Day theme" }).click();
  await panel.getByRole("button", { name: "Approve & fill" }).click();
  await expect(page.locator("#tradeoff")).toHaveValue("I measured latency and chose a simpler consistency model.");
  await expect(panel).toHaveClass(/focus-review/);
  await page.locator("#source").selectOption("friend");
  await expect(panel.locator(".focus-detected")).toContainText("Friend referral");
  await panel.getByRole("button", { name: "Edit answer in ACE" }).click();
  await expect(panel.getByRole("combobox", { name: "Exact employer options" })).toHaveValue("friend");
  await panel.getByRole("combobox", { name: "Exact employer options" }).selectOption("careers");
  await expect(page.locator("#source")).toHaveValue("friend");
  await panel.getByRole("button", { name: "Approve & fill" }).click();
  await expect(panel).toHaveClass(/focus-review/);
  await panel.getByRole("combobox", { name: "Exact employer options" }).selectOption("Yes");
  await expect(page.locator("#sponsor")).toHaveValue("");
  await panel.getByRole("button", { name: "Approve & fill" }).click();
  await expect(page.locator("#sponsor")).toHaveValue("Yes");
  await expect(panel.getByText("Review complete")).toBeVisible();
  await expect(panel).toHaveClass(/focus-review/);
  await expect(page.locator("#motivation")).toHaveValue("My own specific reason for applying.");
  await panel.screenshot({ path: path.join(captures, "review-complete-day.png") });
  await panel.getByRole("button", { name: "Memory & activity" }).click();
  await expect(panel.getByText("Historical private motivation")).toHaveCount(0);
  await panel.screenshot({ path: path.join(captures, "workspace-memory-day.png") });
  await panel.getByRole("button", { name: "Review", exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __memory: unknown[] }).__memory.length)).toBe(3);
  const stored = await page.evaluate(() => (window as typeof window & { __memory: Array<{ question: string; answer: string }> }).__memory);
  expect(stored.filter(item => /motivation|why do you want to work/i.test(item.question))).toHaveLength(1);
  expect(stored.some(item => item.answer === "My own specific reason for applying.")).toBe(false);
  expect(stored.some(item => item.answer === "Cobalt Systems website")).toBe(true);
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await panel.screenshot({ path: path.join(captures, "review-night.png") });
  await panel.getByRole("button", { name: "Overview" }).click();
  await panel.getByRole("button", { name: "Scan fields" }).click();
  await expect(page.locator("#motivation")).toHaveValue("My own specific reason for applying.");
  await panel.screenshot({ path: path.join(captures, "compact-night-after-review.png") });
  const before = await panel.boundingBox();
  const logo = panel.locator(".studio-logo");
  const logoBox = await logo.boundingBox();
  if (!before || !logoBox) throw new Error("ACE card unavailable for drag test");
  await page.mouse.move(logoBox.x + logoBox.width / 2, logoBox.y + logoBox.height / 2);
  await page.mouse.down(); await page.mouse.move(logoBox.x - 120, logoBox.y + 90, { steps: 8 }); await page.mouse.up();
  const after = await panel.boundingBox();
  expect(after).not.toBeNull();
  expect(Math.abs(after!.x - before.x)).toBeGreaterThan(50);
  await expect.poll(() => page.evaluate(() => Boolean((window as typeof window & { __storage: Record<string, unknown> }).__storage.aceFocusPosition))).toBe(true);
  const grip = panel.getByRole("button", { name: "Move ACE with pointer or arrow keys" });
  const gripBox = await grip.boundingBox();
  if (!gripBox) throw new Error("ACE drag grip unavailable");
  await page.mouse.move(gripBox.x + gripBox.width / 2, gripBox.y + gripBox.height / 2);
  await page.mouse.down(); await page.mouse.move(gripBox.x + 50, gripBox.y + 40, { steps: 6 }); await page.mouse.up();
  const afterGrip = await panel.boundingBox();
  expect(Math.abs(afterGrip!.y - after!.y)).toBeGreaterThan(15);
  await grip.focus(); await grip.press("ArrowLeft");
  const afterKey = await panel.boundingBox();
  expect(afterKey!.x).toBeLessThan(afterGrip!.x);
  await grip.dblclick();
  const reset = await panel.boundingBox();
  expect(reset!.y).toBeLessThan(afterKey!.y);
  await panel.getByRole("button", { name: "Minimize ACE" }).click();
  await expect(panel).toHaveClass(/focus-dock/);
  const dockBefore = await panel.boundingBox();
  const dockStatus = await panel.locator(".focus-dock-status").boundingBox();
  if (!dockBefore || !dockStatus) throw new Error("ACE dock unavailable for drag test");
  await page.mouse.move(dockStatus.x + dockStatus.width / 2, dockStatus.y + dockStatus.height / 2);
  await page.mouse.down(); await page.mouse.move(dockStatus.x - 40, dockStatus.y + 36, { steps: 6 }); await page.mouse.up();
  const dockAfter = await panel.boundingBox();
  expect(Math.abs(dockAfter!.x - dockBefore.x)).toBeGreaterThan(15);
  await panel.screenshot({ path: path.join(captures, "dock-night.png") });
  await panel.getByRole("button", { name: "Expand ACE" }).click();
  await expect(panel).toHaveClass(/focus-compact/);
  await panel.getByRole("button", { name: "Switch to Day theme" }).click();
  await panel.getByRole("button", { name: "Minimize ACE" }).click();
  await panel.screenshot({ path: path.join(captures, "dock-day.png") });
  await panel.getByRole("button", { name: "Expand ACE" }).click();
  await page.locator("form").evaluate(form => {
    const label = document.createElement("label"); label.htmlFor = "incident"; label.textContent = "Describe how you debug a production incident";
    const answer = document.createElement("textarea"); answer.id = "incident";
    form.append(label, answer);
  });
  await panel.getByRole("button", { name: /Review/ }).click();
  await expect(panel.locator(".studio-question").getByText("Describe how you debug a production incident")).toBeVisible();
  await panel.getByRole("button", { name: "Skip" }).click();
  await expect(panel.getByText("Review paused")).toBeVisible();
  await expect(panel).toHaveClass(/focus-review/);
  await panel.getByRole("button", { name: "Resume review" }).click();
  await expect(panel.locator(".studio-question").getByText("Describe how you debug a production incident")).toBeVisible();
  await expect(page.locator("#motivation")).toHaveValue("My own specific reason for applying.");
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __applied: number }).__applied)).toBe(0);
  expect(errors).toEqual([]);
  expect(await panel.textContent()).not.toContain("\u2014");
});

test("Focus Mode remains usable in a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form><label for="name">Full name</label><input id="name"><label for="email">Email address</label><input id="email"><label for="role">Current role</label><input id="role"><label for="source">How did you hear about this position?</label><select id="source"><option value="">Select one</option><option>Website</option></select><label for="motivation">What interests you about joining us?</label><textarea id="motivation"></textarea></form>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown };
    w.chrome = { runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (v: string) => v, getManifest: () => ({ version: "1.26.0" }), sendMessage: (m: { type: string }, cb: (v: unknown) => void) => cb(m.type === "answers" ? { ok: true, items: [] } : m.type === "history" ? { ok: true, work: [], education: [] } : { ok: true, items: [] }) } };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await expect(panel).toBeVisible();
  await panel.getByRole("button", { name: /Review/ }).click();
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await panel.screenshot({ path: path.join(captures, "review-mobile-day.png") });
  await page.setViewportSize({ width: 195, height: 390 });
  const zoomed = await panel.boundingBox();
  expect(zoomed).not.toBeNull();
  expect(zoomed!.x).toBeGreaterThanOrEqual(0);
  expect(zoomed!.x + zoomed!.width).toBeLessThanOrEqual(195);
  expect(zoomed!.y + zoomed!.height).toBeLessThanOrEqual(390);
});

test("Focus Mode mirrors an opened employer listbox without inventing options", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form id="application"><label for="name">Full name</label><input id="name"><label for="email">Email address</label><input id="email"><label for="role">Current role</label><input id="role"><label for="source">How did you hear about us?</label><button id="source" type="button" aria-haspopup="listbox" aria-controls="source-options">Select one</button><div id="source-options" role="listbox" hidden><div role="option">Careers website</div><div role="option">Friend referral</div></div><label for="skills">Which technical tools have you used?</label><select id="skills" multiple><option value="python">Python</option><option value="sql">SQL</option><option value="rust">Rust</option></select><button type="submit">Submit application</button></form>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __memory: unknown[]; __submits: number };
    w.__memory = []; w.__submits = 0;
    const trigger = document.getElementById("source")!;
    const menu = document.getElementById("source-options")!;
    trigger.addEventListener("click", () => { menu.hidden = !menu.hidden; });
    menu.querySelectorAll("[role=option]").forEach(option => option.addEventListener("click", () => { trigger.textContent = option.textContent; menu.hidden = true; }));
    document.querySelector("form")!.addEventListener("submit", event => { event.preventDefault(); w.__submits++; });
    w.chrome = { runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (v: string) => v, getManifest: () => ({ version: "1.26.0" }), sendMessage: (m: { type: string; item?: Record<string, unknown> }, cb: (v: unknown) => void) => {
      if (m.type === "answers") cb({ ok: true, items: [] });
      else if (m.type === "history") cb({ ok: true, work: [], education: [] });
      else if (m.type === "memory") cb({ ok: true, items: w.__memory });
      else if (m.type === "memorySave") { const entry = { ...m.item, id: 1, revision: 1, reuse_policy: "reusable" }; w.__memory.push(entry); cb({ ok: true, item: entry }); }
      else cb({ ok: false });
    } } };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await panel.getByRole("button", { name: /Review/ }).click();
  await panel.getByRole("button", { name: /How did you hear/ }).click();
  await expect(panel.getByRole("button", { name: "Load employer options" })).toBeVisible();
  await page.locator("#source").click();
  await expect(panel.getByRole("combobox", { name: "Exact employer options" })).toBeVisible();
  await panel.getByRole("combobox", { name: "Exact employer options" }).selectOption({ label: "Friend referral" });
  await expect(page.locator("#source")).toHaveText("Select one");
  await panel.getByRole("button", { name: "Approve & fill" }).click();
  await expect(page.locator("#source")).toHaveText("Friend referral");
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __memory: unknown[] }).__memory.length)).toBe(1);
  await panel.getByRole("button", { name: /Which technical tools/ }).click();
  await panel.locator("#studio-answer").selectOption(["python", "sql"]);
  const skills = await page.locator("#skills").evaluate(select => Array.from((select as HTMLSelectElement).selectedOptions).map(option => option.value));
  expect(skills).toEqual([]);
  await panel.getByRole("button", { name: "Approve & fill" }).click();
  await expect.poll(() => page.locator("#skills").evaluate(select => Array.from((select as HTMLSelectElement).selectedOptions).map(option => option.value))).toEqual(["python", "sql"]);
  expect(await page.evaluate(() => (window as typeof window & { __memory: unknown[] }).__memory.length)).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});

test("Employer motivation text is never read by ACE during Fill, Scan or rerender", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form><label for="name">Full name</label><input id="name"><label for="email">Email address</label><input id="email"><label for="role">Current role</label><input id="role"><label for="technical">Why did you choose eventual consistency?</label><textarea id="technical"></textarea><label for="sponsor">Will you need visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select><label for="motivation">What interests you about joining Cobalt Systems?</label><textarea id="motivation"></textarea><button type="submit">Submit application</button></form>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __reads: number; __readStacks: string[] };
    w.__reads = 0; w.__readStacks = [];
    const field = document.getElementById("motivation") as HTMLTextAreaElement;
    field.value = "Applicant-owned private answer";
    const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!;
    Object.defineProperty(field, "value", {
      configurable: true,
      get() { w.__reads++; w.__readStacks.push(new Error().stack || ""); return descriptor.get!.call(this); },
      set(value: string) { descriptor.set!.call(this, value); },
    });
    w.chrome = { runtime: { lastError: null, onMessage: { addListener() {} }, getURL: (v: string) => v, getManifest: () => ({ version: "1.27.0" }), sendMessage: (m: { type: string }, cb: (v: unknown) => void) => cb(m.type === "answers" ? { ok: true, items: [{ label: "Full name", value: "Example Applicant", aliases: [] }] } : m.type === "history" ? { ok: true, work: [], education: [] } : { ok: true, items: [] }) } };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await panel.getByRole("button", { name: "Fill", exact: true }).click();
  await panel.getByRole("button", { name: "Scan fields" }).click();
  await panel.getByRole("button", { name: /Review/ }).click();
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await panel.getByRole("button", { name: "Minimize ACE" }).click();
  await panel.getByRole("button", { name: "Expand ACE" }).click();
  const evidence = await page.evaluate(() => { const w = window as typeof window & { __reads: number; __readStacks: string[] }; return { stacks: w.__readStacks.filter(stack => !stack.includes("visitNode")) }; });
  expect(evidence.stacks, evidence.stacks.join("\n\n")).toHaveLength(0);
  await expect(page.locator("#motivation")).toHaveValue("Applicant-owned private answer");
  await expect(panel.getByText(/What interests you about joining Cobalt/)).toHaveCount(0);
});

test("Workday search listings do not show an application Review card", async ({ page }) => {
  const origin = "https://selinc.wd1.myworkdaysite.com";
  await page.route(`${origin}/**`, route => route.fulfill({ status: 200, contentType: "text/html", body: "<html><body></body></html>" }));
  await page.goto(`${origin}/en-US/SEL/Search-For-Jobs`);
  await page.setContent(`<main id="workday-page"><h1>Search For Jobs</h1><form>
    <label for="name">Full name</label><input id="name">
    <label for="email">Email address</label><input id="email">
    <label for="role">Current role</label><input id="role">
    <label for="sponsor">Will you need visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select>
    <label for="source">How did you hear about this position?</label><select id="source"><option value="">Select one</option><option>Website</option></select>
  </form></main>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __aceWake?: (message: { type: string }, sender: unknown, respond: (reply: unknown) => void) => void };
    w.chrome = { runtime: { lastError: null, onMessage: { addListener(handler: typeof w.__aceWake) { w.__aceWake = handler; } }, getURL: (v: string) => v, getManifest: () => ({ version: "1.27.0" }), sendMessage: (m: { type: string }, cb: (v: unknown) => void) => cb(m.type === "answers" ? { ok: true, items: [] } : m.type === "history" ? { ok: true, work: [], education: [] } : { ok: true, items: [] }) } };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  await expect(page.locator(".ace-root")).toHaveCount(0);
  await page.evaluate(() => (window as typeof window & { __aceWake: (message: { type: string }, sender: unknown, respond: (reply: unknown) => void) => void }).__aceWake({ type: "wake" }, {}, () => {}));
  await expect(page.locator(".ace-root .focus-compact")).toBeVisible();
  await page.evaluate(() => {
    history.pushState({}, "", "/en-US/SEL/job/Engineer/apply/autofillWithResume");
    document.getElementById("workday-page")!.appendChild(document.createElement("div"));
  });
  await expect(page.locator(".ace-root .focus-compact")).toBeVisible();
  await page.waitForTimeout(650); // Let the debounced Workday route observer register /apply/.
  await page.evaluate(() => {
    history.pushState({}, "", "/en-US/SEL/Search-For-Jobs");
    document.getElementById("workday-page")!.appendChild(document.createElement("div"));
  });
  await expect(page.locator(".ace-root")).toHaveCount(0);
});
