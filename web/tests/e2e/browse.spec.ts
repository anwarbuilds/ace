import { expect } from "@playwright/test";

import { test } from "./helpers";

test("home is a shop front: a top pick, then rows that lead to their own pages", async ({ page }) => {
  await page.goto("/app");
  await expect(page.locator(".hero")).toBeVisible();
  const row = page.locator(".row-sec", { has: page.locator(".row-title", { hasText: "New grad" }) });
  await expect(row.locator(".jc").first()).toBeVisible();
  await row.getByRole("link", { name: "See all" }).click();
  await expect(page).toHaveURL(/\/app\/browse\/new-grad$/);
  await expect(page.locator("h1")).toHaveText("New grad");
});

test("the department strip moves between group pages, and Back returns", async ({ page }) => {
  await page.goto("/app/browse/new-grad");
  await page.locator(".site-cat", { hasText: "Big tech" }).click();
  await expect(page).toHaveURL(/\/app\/browse\/big-tech$/);
  await expect(page.locator(".site-cat[aria-current=page]")).toHaveText("Big tech");
  await page.goBack();
  await expect(page).toHaveURL(/\/app\/browse\/new-grad$/);
});

test("a group page sorts, filters and pages through the URL", async ({ page }) => {
  await page.goto("/app/browse/software-engineering");
  await page.locator(".side-opt", { hasText: "Newest" }).click();
  await expect(page).toHaveURL(/sort=newest/);
  await page.locator(".side-opt", { hasText: "Top tier" }).first().click();
  await expect(page).toHaveURL(/sort=newest&tier=TOP_TIER/);
  for (const t of await page.locator(".jc .co-tier").allTextContents()) expect(t).toBe("Top tier");
});

test("a card opens the role's own page", async ({ page }) => {
  await page.goto("/app/browse/strong-matches");
  const card = page.locator(".jc").first();
  const title = (await card.locator(".jc-title").textContent())!.trim();
  await card.click();
  await expect(page).toHaveURL(/\/app\/jobs\/\d+/);
  await expect(page.locator(".jp-title")).toHaveText(title);
});

test("companies: directory, a company page, and breadcrumbs back", async ({ page }) => {
  await page.goto("/app/companies");
  await page.getByLabel("Find a company").fill("Pinecrest");
  await page.locator(".co-card", { hasText: "Pinecrest AI" }).click();
  await expect(page).toHaveURL(/\/app\/companies\/Pinecrest%20AI$/);
  await expect(page.locator("h1")).toHaveText("Pinecrest AI");
  await expect(page.locator(".jc").first()).toBeVisible();
  await page.locator(".crumbs a", { hasText: "Companies" }).click();
  await expect(page).toHaveURL(/\/app\/companies$/);
});

test("the whole page scrolls under a fixed header, with a footer at the end", async ({ page }) => {
  await page.goto("/app/opportunities");
  await page.evaluate(() => window.scrollTo(0, 1200));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await expect(page.locator(".site")).toBeInViewport();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(page.locator(".foot")).toBeInViewport();
});
