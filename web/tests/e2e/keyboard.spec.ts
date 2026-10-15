import { expect } from "@playwright/test";

import { test } from "./helpers";

test("j, k, Enter and Escape walk the list and the job page", async ({ page }) => {
  await page.goto("/app/opportunities");
  await page.locator("h1").click();
  await page.keyboard.press("j");
  const first = page.locator('.row[aria-selected="true"]');
  await expect(first).toHaveCount(1);
  const firstId = await first.getAttribute("data-id");
  await page.keyboard.press("j");
  await expect(page.locator('.row[aria-selected="true"]')).not.toHaveAttribute("data-id", firstId!);
  await page.keyboard.press("k");
  await expect(page.locator('.row[aria-selected="true"]')).toHaveAttribute("data-id", firstId!);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/app/jobs/${firstId}$`));
  await expect(page.locator(".jp-title")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/app\/opportunities/);
});

test("keys do nothing while typing in the search box", async ({ page }) => {
  await page.goto("/app/opportunities");
  await page.locator("#q").click();
  await page.keyboard.type("jk");
  await expect(page.locator('.row[aria-selected="true"]')).toHaveCount(0);
  await expect(page).toHaveURL(/\/app\/opportunities/);
});
