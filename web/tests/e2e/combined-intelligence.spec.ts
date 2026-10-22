import fs from "node:fs";
import path from "node:path";

import { expect, type TestInfo } from "@playwright/test";

import { DRAWN_SCAN, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

function capturePath(info: TestInfo, theme: string, name: string) {
  const dir = path.resolve(process.env.ACE_SCREENSHOT_DIR ?? "../artifacts/combined-intelligence", theme);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${name}.png`);
}

for (const theme of ["dark", "light"] as const) {
  test.describe(`Combined Intelligence ${theme}`, () => {
    test.beforeEach(async ({ context, baseURL }) => setThemeCookies(context, baseURL!, theme));

    test("Pulls shows company above role without losing application action", async ({ page }, info) => {
      const errors = watchErrors(page);
      await page.goto("/app/pulls");
      const entries = page.locator(".pull-entry:not(.quiet)");
      for (let i = 0; i < await entries.count(); i++) {
        const entry = entries.nth(i);
        const summary = entry.locator(".pull-summary");
        if (await summary.getAttribute("aria-expanded") === "false") await summary.click();
        try {
          await expect(entry.locator(".job-line").first()).toBeVisible({timeout: 3000});
          break;
        } catch {
          // A historical Pull can contain roles that have since closed.
        }
      }
      const row = page.locator(".job-line").first();
      await expect(row.locator(".job-company")).toBeVisible();
      await expect(row.locator(".job-title")).toBeVisible();
      await expect(row.getByRole("button", { name: /Mark applied|Clear applied/ })).toBeVisible();
      const geometry = await row.evaluate((element) => {
        const company = element.querySelector(".job-company")!.getBoundingClientRect();
        const role = element.querySelector(".job-title")!.getBoundingClientRect();
        return { companyTop: company.top, roleTop: role.top, companySize: parseFloat(getComputedStyle(element.querySelector(".job-company")!).fontSize), roleSize: parseFloat(getComputedStyle(element.querySelector(".job-title")!).fontSize) };
      });
      expect(geometry.companyTop).toBeLessThan(geometry.roleTop);
      expect(geometry.companySize).toBeGreaterThan(geometry.roleSize);
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(errors).toEqual([]);
      await page.screenshot({ path: capturePath(info, theme, "pulls-company-first"), fullPage: true });
      const beforeScroll = await page.evaluate(() => window.scrollY);
      await row.locator(".job-company").click();
      await expect(page.getByRole("dialog", { name: /Company intelligence for/ })).toBeVisible();
      await expect(page.getByText("Company workforce sponsorship rate: Not available.")).toBeVisible();
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      await page.screenshot({ path: capturePath(info, theme, "company-intelligence") });
      await page.getByRole("button", { name: "Close company intelligence" }).click();
      expect(await page.evaluate(() => window.scrollY)).toBe(beforeScroll);
    });

    for (const [tab, name] of [["overview", "command-center"], ["outcomes", "outcome-lab"], ["strategy", "strategy-studio"], ["companies", "company-radar"], ["market", "market-signals"], ["international", "international-lens"], ["actions", "action-center"]] as const) {
      test(`dashboard ${name} uses persisted data`, async ({ page }, info) => {
        const errors = watchErrors(page);
        await page.goto(`/app/dashboard?tab=${tab}`);
        await expect(page.getByRole("heading", { name: "Career Intelligence" })).toBeVisible();
        await expect(page.getByText("ACE records as of")).toBeVisible();
        expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
        expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
        expect(errors).toEqual([]);
        await page.screenshot({ path: capturePath(info, theme, name), fullPage: true });
      });
    }

    test("action center can complete and reopen without changing applications", async ({ page }) => {
      await page.goto("/app/dashboard?tab=actions");
      const before = (await (await page.request.get("/api/marks")).json()).applications_total;
      const actions = page.locator(".intelligence-actions");
      await expect(actions.getByRole("heading", {name: "Evidence-linked actions"})).toBeVisible();
      const first = actions.locator(".intelligence-action").first();
      await expect(first).toBeVisible();
      const title = await first.locator("strong").innerText();
      await first.getByRole("button", {name: "Complete"}).click();
      await page.reload();
      await actions.locator("details").getByText(/handled actions/).click();
      const handled = actions.locator("details .intelligence-action").filter({hasText:title}).first();
      await handled.getByRole("button", {name: "Reopen"}).click();
      await expect(actions.locator(".intelligence-action").filter({hasText:title}).first().getByRole("button", {name: "Complete"})).toBeVisible();
      expect((await (await page.request.get("/api/marks")).json()).applications_total).toBe(before);
    });

    test("Inbox remains honest without Gmail configuration", async ({ page }, info) => {
      const errors = watchErrors(page);
      await page.goto("/app/applications/inbox");
      await expect(page.getByRole("heading", { name: "Never guess the application." })).toBeVisible();
      await expect(page.getByText("Setup required")).toBeVisible();
      await expect(page.getByText("Pending status protection: ON")).toBeVisible();
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(errors).toEqual([]);
      await page.screenshot({ path: capturePath(info, theme, "inbox-unconnected"), fullPage: true });
    });
  });
}
