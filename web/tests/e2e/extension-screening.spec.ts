import path from "node:path";

import { expect, test } from "@playwright/test";


test("screening autofill uses only saved matching answers", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`
    <form>
      <label for="school">What school do you most recently attend?</label><input id="school">
      <label for="employer">Have you ever worked at ServiceNow in any capacity?</label><input id="employer">
      <label for="pwc">Are you currently employed or have you ever been employed by PwC?</label><input id="pwc">
      <label for="federal">Within the past 5 years, have you ever been an employee of the U.S. Federal Government?</label><input id="federal">
      <label for="conflict">Are you a current employee of the U.S. Federal Government participating in a matter involving ServiceNow or its financial interests?</label><input id="conflict">
      <label for="signature">Name (Signature Field)</label><input id="signature">
      <label for="privacy">You declare that you have read and understand the privacy notice of ServiceNow</label><input id="privacy" type="checkbox">
    </form>
  `);
  await page.evaluate(() => {
    const bank = [
      { label: "University", value: "Example University", aliases: [] },
      { label: "Previously employed by ServiceNow", value: "No", aliases: [] },
      { label: "Employed by the federal government", value: "Yes", aliases: [] },
      { label: "Full name", value: "Example Person", aliases: [] },
    ];
    (window as typeof window & { chrome: unknown }).chrome = {
      runtime: {
        onMessage: { addListener() {} },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "test" }),
        sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
          callback(message.type === "answers"
            ? { ok: true, items: bank }
            : { ok: true, work: [], education: [] });
        },
      },
    };
  });

  const extensionRoot = path.resolve(process.cwd(), "../extension");
  await page.addScriptTag({ path: path.join(extensionRoot, "fields.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "memory.js") });
  await page.addScriptTag({ path: path.join(extensionRoot, "content.js") });
  await expect.poll(() => page.evaluate(() => Boolean(document.querySelector(".ace-root")))).toBe(true);
  await page.evaluate(() => document.dispatchEvent(new KeyboardEvent("keydown", {
    key: "a", altKey: true, bubbles: true,
  })));
  await expect.poll(() => page.evaluate(() =>
    document.querySelector(".ace-root")?.shadowRoot?.querySelector(".ace-title")?.textContent ?? "",
  )).toMatch(/^Filled/);

  await expect(page.locator("#school")).toHaveValue("Example University");
  for (const id of ["employer", "pwc", "federal", "conflict", "signature"]) {
    await expect(page.locator(`#${id}`)).toHaveValue("");
  }
  await expect(page.locator("#privacy")).not.toBeChecked();
});
