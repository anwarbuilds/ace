import path from "node:path";
import fs from "node:fs";
import { expect, test } from "@playwright/test";

const extensionRoot = path.resolve(process.cwd(), "../extension");
const captures = path.resolve(process.cwd(), "../artifacts/extension-v4");

test("V4 reviews unknown fields, learns safely, detects new fields and never submits", async ({ page }) => {
  fs.mkdirSync(captures, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form id="application">
    <label for="name">Full name</label><input id="name">
    <label for="email">Email address</label><input id="email">
    <label for="tradeoff">Explain a distributed systems design tradeoff you faced</label><textarea id="tradeoff"></textarea>
    <label for="motivation">Why do you want to join Northstar Labs?</label><textarea id="motivation"></textarea>
    <label for="sponsor">Will you now or later need visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select>
    <button type="submit" id="employer-submit">Submit application</button>
  </form>`);
  await page.evaluate(() => { document.title = "Associate Software Engineer | Northstar Labs"; });
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __memory: unknown[]; __submits: number; __applied: number };
    w.__memory = [];
    w.__submits = 0;
    w.__applied = 0;
    const form = document.querySelector("form")!;
    form.addEventListener("submit", event => { w.__submits++; event.preventDefault(); });
    const originalSubmit = HTMLFormElement.prototype.submit;
    const originalRequestSubmit = HTMLFormElement.prototype.requestSubmit;
    const originalFetch = window.fetch;
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method: string, url: string | URL, async: boolean = true, username?: string | null, password?: string | null) {
      if (String(method).toUpperCase() === "POST" && /apply|submit|application/i.test(String(url))) w.__submits++;
      return originalOpen.call(this, method, url, async, username, password);
    };
    window.fetch = function (input, init) {
      if (String(init?.method || "GET").toUpperCase() === "POST") w.__submits++;
      return originalFetch(input, init);
    };
    HTMLFormElement.prototype.submit = function () { w.__submits++; };
    HTMLFormElement.prototype.requestSubmit = function () { w.__submits++; };
    document.getElementById("employer-submit")!.addEventListener("click", () => { w.__submits++; });
    w.chrome = { runtime: {
      onMessage: { addListener() {} },
      getURL: (value: string) => value,
      getManifest: () => ({ version: "1.26.0" }),
      sendMessage: (message: { type: string; item?: Record<string, unknown>; id?: number }, callback: (reply: unknown) => void) => {
        if (/applied|applicationMark/i.test(message.type)) w.__applied++;
        if (message.type === "answers") callback({ ok: true, items: [
          { label: "Full name", value: "Example Applicant", aliases: [] },
          { label: "Email", value: "applicant@example.invalid", aliases: [] },
          { label: "Need sponsorship in future", value: "Yes", aliases: [] },
        ] });
        else if (message.type === "history") callback({ ok: true, work: [], education: [] });
        else if (message.type === "memory") callback({ ok: true, items: w.__memory });
        else if (message.type === "memorySave") {
          const entry = { ...message.item, id: 1, revision: 1, reuse_policy: "reusable" };
          w.__memory.push(entry);
          callback({ ok: true, item: entry });
        } else callback({ ok: false });
      },
    } };
    void originalSubmit;
    void originalRequestSubmit;
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) {
    await page.addScriptTag({ path: path.join(extensionRoot, file) });
  }
  const panel = page.locator(".ace-root .ace-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button", { name: "Fill all known answers", exact: false })).toBeVisible();
  await panel.getByRole("button", { name: "Fill all known answers", exact: false }).click();
  await expect(page.locator("#name")).toHaveValue("Example Applicant");
  await expect(page.locator("#email")).toHaveValue("applicant@example.invalid");
  await expect(page.locator("#sponsor")).toHaveValue("");
  await expect(page.locator("#tradeoff")).toHaveValue("");
  await panel.screenshot({ path: path.join(captures, "v4-overview-day.png") });
  await page.screenshot({ path: path.join(captures, "v4-full-page-day.png") });
  await panel.getByRole("button", { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  await expect(panel.getByText("Explain a distributed systems design tradeoff you faced")).toBeVisible();
  await panel.screenshot({ path: path.join(captures, "v4-review-day.png") });
  await panel.getByRole("textbox", { name: "Your answer" }).fill("Synthetic approved architecture answer.");
  await panel.getByRole("button", { name: "Fill answer" }).click();
  await expect(page.locator("#tradeoff")).toHaveValue("Synthetic approved architecture answer.");
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __memory: unknown[] }).__memory.length)).toBe(1);
  await panel.getByRole("combobox", { name: "Exact employer options" }).selectOption("Yes");
  await panel.getByRole("button", { name: "Fill answer" }).click();
  await expect(page.locator("#sponsor")).toHaveValue("Yes");
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __memory: unknown[] }).__memory.length)).toBe(1);
  await page.locator("form").evaluate(form => {
    const label = document.createElement("label");
    label.htmlFor = "sponsor-again";
    label.textContent = "Will you require future visa sponsorship for this position?";
    const select = document.createElement("select");
    select.id = "sponsor-again";
    for (const value of ["", "Yes", "No"]) select.add(new Option(value || "Select one", value));
    form.append(label, select);
  });
  await expect(page.locator("#sponsor-again")).toHaveValue("");
  await panel.getByRole("button", { name: "Settings & activity" }).click();
  await panel.getByRole("button", { name: "Memory", exact: true }).click();
  await expect(panel.getByText("Synthetic approved architecture answer.")).toBeVisible();
  await panel.screenshot({ path: path.join(captures, "v4-memory-day.png") });
  await page.locator("form").evaluate(form => {
    document.title = "Backend Engineer | Cedarcloud Labs";
    const label = document.createElement("label");
    label.setAttribute("for", "equivalent");
    label.textContent = "Describe a difficult distributed architecture tradeoff you handled";
    const textarea = document.createElement("textarea");
    textarea.id = "equivalent";
    form.append(label, textarea);
  });
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __aceInternals: { formSignature: () => string } }).__aceInternals.formSignature().includes("describe a difficult distributed"))).toBe(true);
  await panel.getByRole("button", { name: "Fill all known answers" }).click();
  await expect(page.locator("#equivalent")).toHaveValue("Synthetic approved architecture answer.");
  await expect(panel.getByText(/Cedarcloud Labs/).first()).toBeVisible();
  await page.locator("#email").fill("manual@example.invalid");
  await panel.getByRole("button", { name: "Scan fields" }).click();
  await panel.getByRole("button", { name: "Fill all known answers" }).click();
  await expect(page.locator("#email")).toHaveValue("manual@example.invalid");
  await page.locator("form").evaluate(form => {
    const label = document.createElement("label");
    label.htmlFor = "new-question";
    label.textContent = "Describe how you debug a production incident";
    const textarea = document.createElement("textarea");
    textarea.id = "new-question";
    form.append(label, textarea);
  });
  await panel.getByRole("button", { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  await expect(panel.getByText("Describe how you debug a production incident")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __applied: number }).__applied)).toBe(0);
  await panel.getByRole("button", { name: /^(Back to fill|Overview)$/ }).click();
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await expect(panel.getByRole("button", { name: "Switch to Day theme" }).locator("svg")).toBeVisible();
  await panel.screenshot({ path: path.join(captures, "v4-overview-night.png") });
  await page.screenshot({ path: path.join(captures, "v4-full-page-night.png") });
  await panel.getByRole("button", { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  await panel.screenshot({ path: path.join(captures, "v4-review-night.png") });
  await panel.getByRole("button", { name: "Settings & activity" }).click();
  await panel.getByRole("button", { name: "Memory", exact: true }).click();
  await panel.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Undo last fill" }).locator("svg")).toBeVisible();
  await panel.screenshot({ path: path.join(captures, "v4-activity-night.png") });
  expect(errors).toEqual([]);
  expect(await panel.textContent()).not.toContain("\u2014");
});

test("Memory explains an outdated server and reconnects without a page reload", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form><label for="name">Full name</label><input id="name"><label for="email">Email address</label><input id="email"><label for="profile">LinkedIn profile</label><input id="profile"><label for="question">Explain a distributed systems design tradeoff you faced</label><textarea id="question"></textarea><label for="sponsor">Will you require visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select></form>`);
  await page.evaluate(() => {
    const w = window as typeof window & { chrome: unknown; __memoryOffline: boolean };
    w.__memoryOffline = true;
    w.chrome = { runtime: {
      onMessage: { addListener() {} },
      getURL: (value: string) => value,
      getManifest: () => ({ version: "1.26.0" }),
      sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
        if (message.type === "answers") callback({ ok: true, items: [{ label: "Full name", value: "Example Applicant", aliases: [] }, { label: "Email", value: "applicant@example.invalid", aliases: [] }] });
        else if (message.type === "memory") callback(w.__memoryOffline ? { ok: false, error: "HTTP 404" } : { ok: true, items: [] });
        else if (message.type === "memorySave") callback({ ok: false, error: "HTTP 404" });
        else if (message.type === "history") callback({ ok: true, work: [], education: [] });
        else callback({ ok: false });
      },
    } };
  });
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await expect(panel.getByText("Answer Memory needs the ACE server V4 update. Existing answers are safe.")).toBeVisible();
  await panel.getByRole("button", { name: /^(Answer remaining questions|Check answers|Review$)/ }).click();
  await panel.getByRole("textbox", { name: "Your answer" }).fill("Synthetic answer that cannot be saved yet");
  await panel.getByRole("button", { name: "Fill answer" }).click();
  await expect(page.locator("#question")).toHaveValue("");
  await expect(panel.getByText(/field remains for review because its answer was not saved/)).toBeVisible();
  await panel.getByRole("button", { name: "Settings & activity" }).click();
  await panel.getByRole("button", { name: "Memory", exact: true }).click();
  await expect(panel.getByText("Unavailable", { exact: true })).toBeVisible();
  await page.evaluate(() => { (window as typeof window & { __memoryOffline: boolean }).__memoryOffline = false; });
  await panel.getByRole("button", { name: "Retry connection" }).click();
  await expect(panel.getByText("Connected", { exact: true })).toBeVisible();
  await expect(panel.getByText("Answer Memory needs the ACE server V4 update. Existing answers are safe.")).toHaveCount(0);
});
