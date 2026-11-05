import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const extensionRoot = path.resolve(process.cwd(), "../extension");

// The V5.1 card follows the ACE website's theme (System follows the
// computer); a toggle lasts for the page, and can be closed from the card or the minimized dock. Closing
// lasts on that page until the toolbar's Fill wakes ACE again.
async function mount(page: Page, storage: Record<string, unknown> = {}) {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`<form id="application">
    <label for="name">Full name</label><input id="name">
    <label for="email">Email address</label><input id="email">
    <label for="tradeoff">Explain a distributed systems design tradeoff you faced</label><textarea id="tradeoff"></textarea>
    <label for="sponsor">Will you now or later need visa sponsorship?</label><select id="sponsor"><option value="">Select one</option><option>Yes</option><option>No</option></select>
    <button id="submit" type="submit">Submit application</button>
  </form>`);
  await page.evaluate((initial) => {
    document.title = "Software Engineer | Cobalt Systems";
    const w = window as typeof window & {
      chrome: unknown;
      __storage: Record<string, unknown>;
      __wake?: (m: unknown, s: unknown, r: (v: unknown) => void) => void;
      __submits: number;
    };
    w.__storage = { aceAutoKnown: false, aceAutoLearnRoutine: false, ...initial };
    w.__submits = 0;
    document.querySelector("form")!.addEventListener("submit", (event) => { w.__submits++; event.preventDefault(); });
    w.chrome = {
      storage: { local: {
        get: (defaults: Record<string, unknown>, callback: (value: unknown) => void) => callback({ ...defaults, ...w.__storage }),
        set: (values: Record<string, unknown>) => Object.assign(w.__storage, values),
        remove: (key: string) => { delete w.__storage[key]; },
      } },
      runtime: { id: "fixture-extension",
        lastError: null,
        onMessage: { addListener(listener: typeof w.__wake) { w.__wake = listener; } },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "1.28.0" }),
        sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
          if (message.type === "answers") callback({ ok: true, items: [
            { label: "Full name", value: "Example Applicant", aliases: [] },
            { label: "Email", value: "applicant@example.invalid", aliases: [] },
          ] });
          else if (message.type === "history") callback({ ok: true, work: [], education: [] });
          else if (message.type === "memory") callback({ ok: true, items: [] });
          else callback({ ok: false });
        },
      },
    };
  }, storage);
  for (const file of ["fields.js", "memory.js", "content.js"]) await page.addScriptTag({ path: path.join(extensionRoot, file) });
  const panel = page.locator(".ace-root .ace-panel");
  await expect(panel).toBeVisible();
  return panel;
}

test("the card follows the ACE website theme, and System follows the computer", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  // The ACE website set to Day gives the Day card on a dark computer.
  await expect(await mount(page, { aceSiteTheme: "light" })).not.toHaveClass(/night/);
  // Set to System, the card follows the computer.
  await expect(await mount(page, { aceSiteTheme: "system" })).toHaveClass(/night/);
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator(".ace-root .ace-panel")).not.toHaveClass(/night/);
});

test("a toggle lasts for this page only, and an old saved Night choice is ignored", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  const panel = await mount(page, { aceStudioThemeMode: "night", aceStudioTheme: "night" });
  await expect(panel).not.toHaveClass(/night/);
  await panel.getByRole("button", { name: "Switch to Night theme" }).click();
  await expect(panel).toHaveClass(/night/);
  expect(await page.evaluate(() => Object.keys((window as typeof window & { __storage: Record<string, unknown> }).__storage))).not.toContain("aceSiteTheme");
});

test("Close removes the card from the header and the dock; the toolbar wakes it", async ({ page }) => {
  const panel = await mount(page);
  await panel.getByRole("button", { name: "Close ACE" }).click();
  await expect(page.locator(".ace-root")).toHaveCount(0);

  // Typing on the form does not bring a closed card back.
  await page.locator("#name").fill("Typed by the owner");
  await page.waitForTimeout(600);
  await expect(page.locator(".ace-root")).toHaveCount(0);

  // The toolbar's Fill sends "wake", which reopens it.
  await page.evaluate(() => {
    const w = window as typeof window & { __wake?: (m: unknown, s: unknown, r: (v: unknown) => void) => void };
    w.__wake!({ type: "wake" }, {}, () => {});
  });
  const reopened = page.locator(".ace-root .ace-panel");
  await expect(reopened).toBeVisible();

  // From the minimized dock as well.
  await reopened.getByRole("button", { name: "Minimize ACE" }).click();
  await reopened.getByRole("button", { name: "Close ACE" }).click();
  await expect(page.locator(".ace-root")).toHaveCount(0);

  expect(await page.evaluate(() => (window as typeof window & { __submits: number }).__submits)).toBe(0);
});
