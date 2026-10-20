import fs from "node:fs";
import path from "node:path";

import { expect, test as base, type Page, type TestInfo } from "@playwright/test";

import { DRAWN_SCAN, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

const PUBLIC_ROUTES = [
  ["home", "/"],
  ["sign-in", "/login"],
  ["signed-out", "/signed-out"],
] as const;

const PRIVATE_ROUTES = [
  ["pulls", "/app/pulls"],
  ["opportunities", "/app/opportunities"],
  ["applications", "/app/applications"],
  ["analytics", "/app/analytics"],
  ["resume-studio", "/app/resume-studio"],
  ["autofill-extension", "/app/extension"],
  ["archive", "/app/archive"],
  ["coverage", "/app/coverage"],
  ["settings", "/app/settings"],
] as const;

function screenshotPath(testInfo: TestInfo, theme: string, name: string) {
  const configured = process.env.ACE_SCREENSHOT_DIR;
  if (!configured) return testInfo.outputPath(`${theme}-${name}.png`);
  const directory = path.resolve(configured, theme);
  fs.mkdirSync(directory, { recursive: true });
  return path.join(directory, `${name}.png`);
}

async function verifyAndCapture(
  page: Page,
  testInfo: TestInfo,
  theme: "dark" | "light",
  name: string,
  errors: string[],
) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
  expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
  expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: screenshotPath(testInfo, theme, name) });
}

for (const theme of ["dark", "light"] as const) {
  for (const [name, route] of PUBLIC_ROUTES) {
    base(`V2 ${name} in ${theme}`, async ({ page, context, baseURL }, testInfo) => {
      await setThemeCookies(context, baseURL!, theme);
      const errors = watchErrors(page);
      await page.goto(route);
      await expect(page.locator(".auth-wordmark").first()).toHaveText("ace");
      await expect(page.locator(".wine-art-a")).toBeVisible();
      await verifyAndCapture(page, testInfo, theme, name, errors);
    });
  }

  test.describe(`V2 workspace in ${theme}`, () => {
    test.beforeEach(async ({ context, baseURL }) => setThemeCookies(context, baseURL!, theme));

    for (const [name, route] of PRIVATE_ROUTES) {
      test(`${name} screenshot`, async ({ page }, testInfo) => {
        const errors = watchErrors(page);
        await page.goto(route);
        await expect(page.locator("h1").first()).toBeVisible();
        await verifyAndCapture(page, testInfo, theme, name, errors);
      });
    }
  });
}

test("theme survives direct navigation and refresh", async ({ page, context, baseURL }) => {
  await setThemeCookies(context, baseURL!, "light");
  await page.goto("/app/pulls");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.goto("/app/resume-studio");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
