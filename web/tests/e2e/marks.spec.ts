import { expect } from "@playwright/test";

import { test } from "./helpers";

// These write marks, which is why the suite runs on demo data only.

async function markOf(request: import("@playwright/test").APIRequestContext, id: string) {
  const res = await request.get(`/api/jobs/${id}`);
  return (await res.json()) as { is_saved: boolean; review_state: string | null; applied_at: string | null };
}

test("save from the row dock, then undo it", async ({ page, request }) => {
  await page.goto("/app/opportunities?sort=company");
  const row = page.locator(".row[data-id]:not(.grp-head)").first();
  const id = (await row.getAttribute("data-id"))!;
  const before = await markOf(request, id);
  await row.hover();
  await row.locator('button[data-mark="saved"]').click();
  await expect(page.locator(".toast")).toContainText(before.is_saved ? "Removed from saved" : "Saved");
  await expect.poll(async () => (await markOf(request, id)).is_saved).toBe(!before.is_saved);
  await page.locator(".toast .link-btn", { hasText: "Undo" }).click();
  await expect.poll(async () => (await markOf(request, id)).is_saved).toBe(before.is_saved);
});

test("marking applied on the job page shows at once and persists", async ({ page, request }) => {
  await page.goto("/app/opportunities");
  const id = (await page.locator(".row[data-id]:not(.grp-head)").first().getAttribute("data-id"))!;
  await page.goto(`/app/jobs/${id}`);
  const applied = page.locator('.status-grid button[data-mark="applied"]');
  const wasOn = (await applied.getAttribute("class"))!.includes(" on");
  await applied.click();
  await expect(applied).toHaveClass(wasOn ? /^(?!.*\bon\b)/ : /\bon\b/);
  await expect.poll(async () => Boolean((await markOf(request, id)).applied_at)).toBe(!wasOn);
  await page.reload();
  await expect(applied).toHaveClass(wasOn ? /^(?!.*\bon\b)/ : /\bon\b/);
  // Put it back as it was.
  await applied.click();
  await expect.poll(async () => Boolean((await markOf(request, id)).applied_at)).toBe(wasOn);
});

test("a missing score says why, never n/a", async ({ page }) => {
  await page.goto("/app/opportunities?sort=best_match&page=5");
  const reasons = await page.locator(".m-unscored").allTextContents();
  for (const r of reasons) expect(["Not scored yet", "No description", "Too little to score", "No resume"]).toContain(r);
  expect(await page.locator("body").textContent()).not.toContain("n/a");
});
