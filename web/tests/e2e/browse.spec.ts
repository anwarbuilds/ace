import { expect } from "@playwright/test";

import { test } from "./helpers";

test("home is Pulls: windows newest first, quiet ones included, and a window opens its jobs", async ({ page }) => {
  await page.goto("/app/pulls");
  await expect(page.locator("h1")).toHaveText("Pulls");
  await expect(page.locator(".sb-link[aria-current=page]")).toContainText("Pulls");
  await expect(page.locator(".pull-entry").first()).toBeVisible();
  await expect(page.locator(".pull-entry.quiet").first()).toBeVisible();
  // Checked, answered and failed are separate numbers.
  await expect(page.locator(".pull-stats").first()).toContainText("sources checked");
  await expect(page.locator(".pull-stats").first()).toContainText("failed");
  const hit = page.locator(".pull-entry:not(.quiet)").nth(1).locator(".pull-summary");
  await hit.click();
  await expect(hit).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".pull-results .job-line").first()).toBeVisible();
  await page.locator(".filterchip", { hasText: "Quiet checks" }).click();
  await expect(page).toHaveURL(/filter=quiet/);
  for (const t of await page.locator(".pull-title").allTextContents()) expect(t).not.toContain("relevant opportunit");
});

test("marking a job applied from a pull persists", async ({ page }) => {
  await page.goto("/app/pulls");
  const line = page.locator(".pull-results .job-line").filter({ hasNot: page.locator(".tag.green") }).first();
  const title = (await line.locator(".job-title").textContent())!.trim();
  await line.getByRole("button", { name: "Mark applied" }).click();
  await expect(page.locator(".toast")).toContainText("Marked applied");
  await page.reload();
  const again = page.locator(".pull-results .job-line", { hasText: title }).first();
  await expect(again.locator(".tag.green")).toHaveText("Applied");
  await again.getByRole("button", { name: "Clear applied" }).click();
});

test("analytics groups roles by tier and family, and a row opens them", async ({ page }) => {
  await page.goto("/app/analytics");
  await expect(page.locator("h1")).toHaveText("Analytics");
  await page.locator(".db-tr .db-name", { hasText: /^Big tech$/ }).click();
  await expect(page).toHaveURL(/\/app\/opportunities\?tier=BIG_TECH/);
});

test("analytics trend and role filters live in the URL", async ({ page }) => {
  await page.goto("/app/analytics");
  await page.getByLabel("Trend range").selectOption("30");
  await page.getByLabel("Discovery role family").selectOption("AI_ML_ENGINEERING");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/days=30.*family=AI_ML_ENGINEERING/);
  await expect(page.getByText("Applied, last 30 days")).toBeVisible();
  await expect(page.getByRole("link", { name: "Clear" })).toBeVisible();
});

test("there is no command palette and no search-or-jump box", async ({ page }) => {
  await page.goto("/app/pulls");
  await expect(page.getByText("Search or jump to")).toHaveCount(0);
  await page.keyboard.press("Control+k");
  await expect(page.locator(".palette")).toHaveCount(0);
});

test("the whole page scrolls under a fixed header and sidebar", async ({ page }) => {
  await page.goto("/app/opportunities");
  await page.evaluate(() => window.scrollTo(0, 1200));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await expect(page.locator(".tb")).toBeInViewport();
  await expect(page.locator(".sb-brand")).toBeInViewport();
});
