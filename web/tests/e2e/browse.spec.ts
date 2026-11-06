import { expect } from "@playwright/test";

import { test } from "./helpers";

test("home is Pulls: windows newest first, quiet ones included, and a window opens its jobs", async ({ page }) => {
  await page.goto("/app/pulls");
  await expect(page.locator("h1")).toHaveText("Pulls");
  await expect(page.locator(".sb-link[aria-current=page]")).toContainText("Pulls");
  await expect(page.locator(".pull-entry").first()).toBeVisible();
  await expect(page.locator(".pull-entry.quiet").first()).toBeVisible();
  // Legacy poll history and successful boards are distinct from recent attempts.
  const stats = await (await page.request.get("/api/stats")).json();
  const sourceKpi = page.locator(".kpi", { hasText: "Sources polling" });
  await expect(sourceKpi.locator(".kpi-n")).toHaveText(stats.sources_polled.toLocaleString("en-US"));
  await expect(sourceKpi.locator(".kpi-f")).toContainText(
    `of ${stats.sources_enabled.toLocaleString("en-US")} enabled`,
  );
  await expect(page.locator(".pull-stats").first()).toContainText("boards read");
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

test("Pulls shows the legacy experience and applied-before badges", async ({ page }) => {
  await page.route("**/api/jobs?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    if (body.items?.length >= 2) {
      body.items[0] = {
        ...body.items[0],
        is_early_career: true,
        required_experience_years: null,
      };
      body.items[1] = {
        ...body.items[1],
        is_early_career: false,
        required_experience_years: 3,
        applied_at: null,
        application_status: null,
        applied_before: {
          job_id: 999999,
          title: "Software Engineer",
          location: "Austin, TX",
          applied_at: "2026-10-19T12:00:00Z",
          is_active: true,
          requisition_id: null,
          count: 1,
        },
      };
    }
    await route.fulfill({ response, json: body });
  });
  await page.goto("/app/pulls");
  const lines = page.locator(".pull-results .job-line");
  await expect(lines.nth(1)).toBeVisible();
  await expect(lines.first().locator(".job-tags .exp-early")).toHaveText("Early career");
  await expect(lines.nth(1).locator(".job-tags .exp-known")).toHaveText("3 yrs max");
  await expect(lines.nth(1).locator(".job-tags .badge.before")).toContainText("Applied before");
});

test("an opened Pull stays open after job navigation and reload until closed", async ({ page }) => {
  await page.goto("/app/pulls");
  const entry = page.locator(".pull-entry:not(.quiet)").nth(1);
  const id = await entry.getAttribute("id");
  expect(id).toMatch(/^pull-\d+$/);
  const summary = entry.locator(".pull-summary");
  await summary.click();
  await expect(summary).toHaveAttribute("aria-expanded", "true");
  await expect(entry.locator(".job-title").first()).toBeVisible();
  await entry.locator(".job-title").first().scrollIntoViewIfNeeded();
  const place = await page.evaluate(() => window.scrollY);
  expect(place).toBeGreaterThan(0);
  await entry.locator(".job-company").first().click();
  await page.getByRole("link", { name: "Open company page" }).click();
  await expect(page).toHaveURL(/\/app\/company\//);
  await page.goBack();
  await expect(page.locator(`#${id} .pull-summary`)).toHaveAttribute("aria-expanded", "true");
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(place - 120);
  await entry.locator(".job-title").first().click();
  await expect(page.locator(".jp-back")).toContainText("Back to pulls");
  await page.locator(".jp-back").click();
  const returned = page.locator(`#${id}`);
  await expect(returned.locator(".pull-summary")).toHaveAttribute("aria-expanded", "true");
  await expect(returned.locator(".job-title").first()).toBeVisible();
  await page.reload();
  await expect(page.locator(`#${id} .pull-summary`)).toHaveAttribute("aria-expanded", "true");
  await page.locator(`#${id} .pull-summary`).click();
  await page.reload();
  await expect(page.locator(`#${id} .pull-summary`)).toHaveAttribute("aria-expanded", "false");
});

test("there is no command palette and no search-or-jump box", async ({ page }) => {
  await page.goto("/app/pulls");
  await expect(page.getByText("Search or jump to")).toHaveCount(0);
  await page.keyboard.press("Control+k");
  await expect(page.locator(".palette")).toHaveCount(0);
});

test("the whole page scrolls under a fixed header and sidebar", async ({ page }) => {
  await page.goto("/app/opportunities");
  // Asked again each time: the list streams in, and a scroll sent before it
  // arrives has nowhere to go.
  await expect
    .poll(() => page.evaluate(() => { window.scrollTo(0, 1200); return window.scrollY; }))
    .toBeGreaterThan(0);
  await expect(page.locator(".tb")).toBeInViewport();
  await expect(page.locator(".sb-brand")).toBeInViewport();
});
