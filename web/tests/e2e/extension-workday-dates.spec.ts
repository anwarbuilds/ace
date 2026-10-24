import path from "node:path";

import { expect, test } from "@playwright/test";

test("Workday month inputs receive the right dates for each saved job", async ({ page }) => {
  await page.goto("data:text/html,<html><body></body></html>");
  await page.setContent(`
    <form>
      <label for="resume">Resume/CV</label><input id="resume" type="file">
      <label for="name">First Name</label><input id="name" value="Example">
      <label for="email">Email</label><input id="email" value="example@example.test">
      <section class="job">
        <h2>Work Experience 1</h2>
        <label for="company-1">Company</label><input id="company-1" value="Example Research Lab">
        <label for="title-1">Job Title</label><input id="title-1" value="Research Assistant">
        <label for="current-1">I currently work here</label><input id="current-1" type="checkbox" checked>
        <label for="from-1">From</label><input id="from-1" type="month">
      </section>
      <section class="job">
        <h2>Work Experience 2</h2>
        <label for="company-2">Company</label><input id="company-2" value="Example Engineering Group">
        <label for="title-2">Job Title</label><input id="title-2" value="Software Engineer">
        <label for="current-2">I currently work here</label><input id="current-2" type="checkbox">
        <label for="from-2">From</label><input id="from-2" type="month">
        <label for="to-2">To</label><input id="to-2" type="month">
      </section>
      <section class="job">
        <h2>Work Experience 3</h2>
        <label for="company-3">Company</label><input id="company-3" value="Example Design Studio">
        <label for="title-3">Job Title</label><input id="title-3" value="Intern">
        <label for="from-3">From</label><input id="from-3" type="month" value="2020-06">
        <label for="to-3">To</label><input id="to-3" type="month">
      </section>
      <section class="job">
        <h2>Work Experience 4</h2>
        <label for="company-4">Company</label><input id="company-4" value="Unmatched Example Company">
        <label for="title-4">Job Title</label><input id="title-4" value="Analyst">
        <label for="from-4">From</label><input id="from-4" type="month">
        <label for="to-4">To</label><input id="to-4" type="month">
      </section>
    </form>
  `);
  await page.evaluate(() => {
    const work = [
      { employer: "Example Design Studio", job_title: "Intern", is_current: false,
        start_month: 5, start_year: 2020, end_month: 8, end_year: 2020 },
      { employer: "Example Research Lab", job_title: "Research Assistant", is_current: true,
        start_month: 2, start_year: 2024, end_month: null, end_year: null },
      { employer: "Example Engineering Group", job_title: "Software Engineer", is_current: false,
        start_month: 7, start_year: 2021, end_month: 11, end_year: 2023 },
    ];
    // A controlled form restores its last committed state on blur.
    document.querySelectorAll<HTMLInputElement>('input[type="month"]').forEach((input) => {
      let committed = input.value;
      input.addEventListener("input", () => { committed = input.value; });
      input.addEventListener("blur", () => { input.value = committed; });
    });
    (window as typeof window & { chrome: unknown }).chrome = {
      runtime: {
        onMessage: { addListener() {} },
        getURL: (value: string) => value,
        getManifest: () => ({ version: "test" }),
        sendMessage: (message: { type: string }, callback: (reply: unknown) => void) => {
          callback(message.type === "answers"
            ? { ok: true, items: [{ label: "Email", value: "example@example.test", aliases: [] }] }
            : { ok: true, work, education: [] });
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
  )).toMatch(/^Filled 4 fields/);

  await expect(page.locator("#from-1")).toHaveValue("2024-02");
  await expect(page.locator("#from-2")).toHaveValue("2021-07");
  await expect(page.locator("#to-2")).toHaveValue("2023-11");
  await expect(page.locator("#from-3")).toHaveValue("2020-06");
  await expect(page.locator("#to-3")).toHaveValue("2020-08");
  await expect(page.locator("#from-4")).toHaveValue("");
  await expect(page.locator("#to-4")).toHaveValue("");
});
