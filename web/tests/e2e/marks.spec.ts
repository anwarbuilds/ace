import { expect, type APIRequestContext, type Page } from "@playwright/test";

import { test } from "./helpers";

// These write marks, which is why the suite runs on demo data only.

async function markOf(request: APIRequestContext, id: string) {
  const res = await request.get(`/api/jobs/${id}`);
  return (await res.json()) as { is_saved: boolean; review_state: string | null; applied_at: string | null };
}

async function applicationTotal(request: APIRequestContext): Promise<number> {
  const res = await request.get("/api/marks");
  expect(res.ok()).toBe(true);
  return (await res.json()).applications_total as number;
}

async function expectGlobalTotal(page: Page, total: number) {
  const formatted = total.toLocaleString("en-US");
  await expect(page.locator(".tb-applied strong")).toHaveText(formatted);
  await expect(page.locator('.sb-link[href="/app/applications"] .sb-count')).toHaveText(formatted);
}

async function openUnappliedJob(page: Page): Promise<string> {
  await page.goto("/app/opportunities?sort=company");
  const button = page.locator('.row[data-id]:not(.grp-head) button[data-mark="applied"][aria-pressed="false"]').first();
  await expect(button).toBeVisible();
  const id = (await button.locator("xpath=ancestor::tr").getAttribute("data-id"))!;
  await page.goto(`/app/jobs/${id}`);
  return id;
}

test("mark reviewed from the row dock, then undo it", async ({ page, request }) => {
  await page.goto("/app/opportunities?sort=company");
  const row = page.locator(".row[data-id]:not(.grp-head)").first();
  const id = (await row.getAttribute("data-id"))!;
  const before = (await markOf(request, id)).review_state;
  await row.hover();
  await row.locator('button[data-mark="reviewed"]').click();
  await expect(page.locator(".toast")).toContainText(before === "reviewed" ? "Review cleared" : "Marked reviewed");
  await expect.poll(async () => (await markOf(request, id)).review_state).toBe(before === "reviewed" ? null : "reviewed");
  await page.locator(".toast .link-btn", { hasText: "Undo" }).click();
  await expect.poll(async () => (await markOf(request, id)).review_state).toBe(before);
});

test("there is no save star anywhere", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator('[data-mark="saved"]')).toHaveCount(0);
  await page.locator("a.j-title").first().click();
  await expect(page.locator(".jp-title")).toBeVisible();
  await expect(page.locator('[data-mark="saved"]')).toHaveCount(0);
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

test("application totals update instantly, reject duplicate clicks, persist and stay consistent", async ({ page, request }) => {
  const before = await applicationTotal(request);
  const id = await openUnappliedJob(page);
  const applied = page.locator('.status-grid button[data-mark="applied"]');
  let releaseRequest!: () => void;
  const gate = new Promise<void>((resolve) => { releaseRequest = resolve; });
  let writes = 0;
  await page.route(`**/api/marks/${id}`, async (route) => {
    if (route.request().method() !== "PUT") return route.continue();
    writes += 1;
    await gate;
    await route.continue();
  });

  await applied.click();
  await applied.click();
  await expectGlobalTotal(page, before + 1);
  expect(writes).toBe(1);
  releaseRequest();
  await expect.poll(() => applicationTotal(request)).toBe(before + 1);
  await page.unroute(`**/api/marks/${id}`);

  await page.reload();
  await expectGlobalTotal(page, before + 1);
  await expect(applied).toHaveClass(/\bon\b/);
  await page.goto("/app/pulls");
  await expect(page.locator(".kpi", { hasText: "Total applications" }).locator(".kpi-n")).toHaveText(String(before + 1));
  await page.goto("/app/applications");
  await expect(page.locator(".head-row .h1-count")).toHaveText(String(before + 1));
  await page.goto("/app/analytics");
  await expect(page.locator(".kpi", { hasText: "Applications" }).first().locator(".kpi-n")).toHaveText(String(before + 1));

  await page.goto(`/app/jobs/${id}`);
  await applied.click();
  await expect.poll(() => applicationTotal(request)).toBe(before);
});

test("a failed application save rolls every count back", async ({ page, request }) => {
  const before = await applicationTotal(request);
  const id = await openUnappliedJob(page);
  const applied = page.locator('.status-grid button[data-mark="applied"]');
  let rejectRequest!: () => void;
  const gate = new Promise<void>((resolve) => { rejectRequest = resolve; });
  await page.route(`**/api/marks/${id}`, async (route) => {
    if (route.request().method() !== "PUT") return route.continue();
    await gate;
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "simulated failure" }) });
  });

  await applied.click();
  await expectGlobalTotal(page, before + 1);
  rejectRequest();
  await expect(page.locator(".toast")).toContainText("Could not save that change");
  await expectGlobalTotal(page, before);
  await expect(applied).not.toHaveClass(/\bon\b/);
  expect(await applicationTotal(request)).toBe(before);
});

test("promoting an application changes its stage without changing its total", async ({ page, request }) => {
  const before = await applicationTotal(request);
  await openUnappliedJob(page);
  const screening = page.locator('button[data-status="screening"]');
  await screening.click();
  await expect(screening).toHaveClass(/\bon\b/);
  await expectGlobalTotal(page, before + 1);
  await expect.poll(() => applicationTotal(request)).toBe(before + 1);

  const interviewing = page.locator('button[data-status="interviewing"]');
  await interviewing.click();
  await expect(interviewing).toHaveClass(/\bon\b/);
  await expectGlobalTotal(page, before + 1);

  await page.locator('.status-grid button[data-mark="applied"]').click();
  await expect.poll(() => applicationTotal(request)).toBe(before);
});

test("a missing score says why, never n/a", async ({ page }) => {
  await page.goto("/app/opportunities?sort=best_match&page=5");
  const reasons = await page.locator(".m-unscored").allTextContents();
  for (const r of reasons) expect(["Not scored yet", "No description", "Too little to score", "No resume"]).toContain(r);
  expect(await page.locator("body").textContent()).not.toContain("n/a");
});
