import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const extension = path.resolve(process.cwd(), "../extension");
type ShadowWindow = typeof window & {
  chrome: unknown;
  __shadow: { messages: string[]; saves: unknown[]; submits: number; reads: number; commits: string[] };
  __makeForm: (checkout?: boolean) => void;
  __wake: (message: unknown, sender: unknown, reply: (value: unknown) => void) => void;
};

// Fictional web components; nothing here is copied from an employer's form.
async function mount(page: Page, options: { late?: boolean; checkout?: boolean; empty?: boolean } = {}) {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent('<spl-application></spl-application>');
  await page.evaluate(({ late, checkout, empty }) => {
    document.title = "Engineer | Fictional Starling Labs";
    const w = window as ShadowWindow;
    w.__shadow = { messages: [], saves: [], submits: 0, reads: 0, commits: [] };
    HTMLFormElement.prototype.submit = HTMLFormElement.prototype.requestSubmit = () => { w.__shadow.submits++; };
    document.addEventListener("submit", event => { event.preventDefault(); w.__shadow.submits++; });
    w.__makeForm = (shopping = false) => {
      const root = document.querySelector("spl-application")!.attachShadow({ mode: "open" });
      root.innerHTML = '<form><section></section><button type="submit">Submit application</button></form>';
      root.querySelector("form")!.addEventListener("submit", event => { event.preventDefault(); w.__shadow.submits++; });
      const labels = ["Full name", "Email", "Phone", shopping ? "City" : "LinkedIn profile"];
      labels.forEach((label, index) => {
        const host = document.createElement("spl-input"); host.id = `question-${index}`;
        root.querySelector("section")!.append(host);
        host.attachShadow({ mode: "open" }).innerHTML = `<label for="control">${label}</label><input id="control">`;
      });
      if (!shopping) {
        const section = document.createElement("section");
        section.innerHTML = '<label for="auth">Are you legally authorized to work in the US?</label><select id="auth"><option value="">Select one</option><option>Yes</option><option>No</option></select><label for="foreign">Are you authorized to work in Canada?</label><select id="foreign"><option value="">Select one</option><option>Yes</option><option>No</option></select><label for="motivation">Why this company?</label><textarea id="motivation"></textarea><label for="technical">Why did you choose eventual consistency?</label><textarea id="technical"></textarea>';
        root.querySelector("form")!.append(section);
        const motivation = root.getElementById("motivation") as HTMLTextAreaElement;
        Object.defineProperty(motivation, "value", { get() { w.__shadow.reads++; return "Fictional employer-only text"; }, set() { throw new Error("Motivation must stay untouched"); } });
      }
      // A framework outside the nested input's root must see both Fill and Undo.
      root.addEventListener("input", event => {
        const control = event.composedPath()[0];
        if (control instanceof HTMLInputElement) w.__shadow.commits.push(control.value);
      });
    };
    w.chrome = {
      storage: { local: {
        get(defaults: Record<string, unknown>, reply: (value: unknown) => void) { reply({ ...defaults, aceAutoLearnRoutine: true }); },
        set() {}, remove() {},
      } },
      runtime: { id: "fixture-extension", lastError: null,
        getURL: (value: string) => value, getManifest: () => ({ version: "1.31.7" }),
        onMessage: { addListener(listener: ShadowWindow["__wake"]) { w.__wake = listener; } },
        sendMessage(message: { type: string; item?: unknown }, reply: (value: unknown) => void) {
          w.__shadow.messages.push(message.type);
          if (message.type === "answers") reply({ ok: true, items: [
            { label: "Full name", value: "Example Applicant" }, { label: "Email", value: "applicant@example.test" },
            { label: "Phone", value: "5550100100" }, { label: "Work authorisation", value: "Yes" },
          ] });
          else if (message.type === "history") reply({ ok: true, work: [], education: [] });
          else if (message.type === "memory") reply({ ok: true, items: [] });
          else if (message.type === "memorySave") { w.__shadow.saves.push(message.item); reply({ ok: false }); }
          else reply({ ok: false });
        },
      },
    };
    if (!late && !empty) w.__makeForm(checkout);
  }, options);
  for (const name of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extension, name) });
  return page.locator(".ace-root .ace-panel");
}

test("nested shadow fields keep their labels, accept composed Fill and Undo, and preserve answer rules", async ({ page }) => {
  const panel = await mount(page);
  await expect(panel).toBeVisible();
  await expect(page.locator("#question-0 input")).toHaveValue("");
  await panel.getByRole("button", { name: "Fill all known answers", exact: true }).click();
  await expect(page.locator("#question-0 input")).toHaveValue("Example Applicant");
  await expect(page.locator("#question-1 input")).toHaveValue("applicant@example.test");
  await expect(page.locator("#question-2 input")).toHaveValue("5550100100");
  await expect(page.locator("#auth")).toHaveValue("Yes");
  await expect(page.locator("#foreign")).toHaveValue("");
  expect(await page.evaluate(() => (window as ShadowWindow).__shadow.commits)).toContain("applicant@example.test");
  await panel.getByRole("button", { name: "Undo fill", exact: true }).click();
  await expect(page.locator("#question-0 input")).toHaveValue("");
  await expect(page.locator("#question-1 input")).toHaveValue("");
  await expect(page.locator("#auth")).toHaveValue("");
  await panel.getByRole("button", { name: "Scan fields", exact: true }).click();
  await expect(panel).not.toContainText("Why this company?");
  const state = await page.evaluate(() => (window as ShadowWindow).__shadow);
  expect(state.reads).toBe(0); expect(state.submits).toBe(0);
  expect(state.messages.some(message => /applied|submit|applicationMark/i.test(message))).toBe(false);
  expect(state.commits).toContain("");
});

test("late shadow roots and fields appear passively and trusted owner edits are observed once", async ({ page }) => {
  const panel = await mount(page, { late: true });
  await expect(panel).toHaveCount(0);
  await page.evaluate(() => (window as ShadowWindow).__makeForm());
  await expect(panel).toBeVisible();
  await page.locator("#technical").fill("Fictional consistency tradeoff");
  await page.locator("#question-1 input").click();
  await expect.poll(() => page.evaluate(() => (window as ShadowWindow).__shadow.saves.length)).toBe(1);
  await page.evaluate(() => {
    const label = document.createElement("label"); label.textContent = "Preferred testing tool";
    label.append(document.createElement("input"));
    document.querySelector("spl-application")!.shadowRoot!.querySelector("form")!.append(label);
  });
  await expect(panel).toContainText("of 8 questions answered");
  await expect(page.locator("#question-0 input")).toHaveValue("");
  expect(await page.evaluate(() => (window as ShadowWindow).__shadow.reads)).toBe(0);
});

test("a shadow checkout stays quiet through field and label changes", async ({ page }) => {
  const panel = await mount(page, { checkout: true });
  await page.waitForTimeout(2200);
  await expect(panel).toHaveCount(0);
  expect(await page.evaluate(() => (window as ShadowWindow).__shadow.messages)).toEqual([]);
});

test("zero-question card disables Fill in Day and Night and keeps Scan available", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "light" });
  const panel = await mount(page, { empty: true });
  await expect(panel).toHaveCount(0);
  await page.evaluate(() => (window as ShadowWindow).__wake({ type: "wake" }, {}, () => {}));
  for (let index = 0; index < 2; index++) {
    await expect(panel).toBeVisible();
    if (index === 0) await expect(panel).not.toHaveClass(/night/);
    else await expect(panel).toHaveClass(/night/);
    await expect(panel).toContainText("No questions found");
    await expect(panel).not.toContainText(/Form detected|0 of 0|Check answers/);
    await expect(panel.getByRole("button", { name: "Fill all known answers", exact: true })).toBeDisabled();
    await expect(panel.getByRole("button", { name: "Scan fields", exact: true })).toBeEnabled();
    const bounds = await panel.boundingBox();
    expect(bounds!.width).toBeLessThanOrEqual(320);
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    await panel.screenshot({ path: testInfo.outputPath(index ? "shadow-empty-night.png" : "shadow-empty-day.png") });
    await panel.locator('[data-ace="theme"]').click();
  }
  expect(await page.evaluate(() => (window as ShadowWindow).__shadow.submits)).toBe(0);
});
