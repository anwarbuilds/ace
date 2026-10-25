import { expect } from "@playwright/test";

import { TEXT_SCAN, test } from "./helpers";

// The approved Refined typography (design/ace-typography-refresh): one
// self-hosted Inter face, readable sizes, sentence case labels, tabular
// numbers and colour emoji. These pin it, so a later change cannot quietly
// bring back tiny uppercase labels or a second interface face.
const ROUTES = [
  "/app/pulls",
  "/app/opportunities",
  "/app/applications",
  "/app/analytics",
  "/app/dashboard",
  "/app/resume-studio",
  "/app/coverage",
  "/app/settings",
];

// Glyphs drawn as text inside a fixed box (carets, the info mark, the
// remove cross) are icons, not reading text, and keep their size.
const ICON_TEXT = ".grp-caret, .pl-caret, .info, .chip-x";

test("Inter is the interface face, served from this origin, with colour emoji after it", async ({ page }) => {
  await page.goto("/app/pulls");
  await page.evaluate(() => document.fonts.ready);
  const stack = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
  expect(stack).toMatch(/^"?inter"?\s*,/i);
  expect(stack).toContain("Noto Color Emoji");
  expect(stack).toContain("Apple Color Emoji");
  const loaded = await page.evaluate(() =>
    [...document.fonts].some((f) => f.family.replace(/"/g, "").toLowerCase() === "inter" && f.status === "loaded"),
  );
  expect(loaded).toBe(true);
});

for (const route of ROUTES) {
  test(`${route} has no tiny or uppercased reading text`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator("h1").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    const problems = await page.evaluate((iconText) => {
      const out: string[] = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const el = n.parentElement;
        const text = (n.nodeValue ?? "").trim();
        if (!el || !text || el.closest(iconText) || el.closest("svg, script, style, option")) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === "hidden" || el.getClientRects().length === 0) continue;
        const size = parseFloat(cs.fontSize);
        if (size < 11.5) out.push(`${size}px: ${text.slice(0, 40)}`);
        // Company initials are the one deliberate capital treatment.
        if (cs.textTransform === "uppercase" && !el.closest(".co-av")) out.push(`uppercase: ${text.slice(0, 40)}`);
      }
      return out;
    }, ICON_TEXT);
    expect(problems).toEqual([]);
  });
}

test("numbers use tabular figures, not a monospace face", async ({ page }) => {
  await page.goto("/app/pulls");
  await expect(page.locator(".kpi-n").first()).toBeVisible();
  for (const selector of [".kpi-n", ".sb-count", ".pull-when"]) {
    const style = await page.locator(selector).first().evaluate((el) => {
      const cs = getComputedStyle(el);
      return { numeric: cs.fontVariantNumeric, family: cs.fontFamily };
    });
    expect(style.numeric, selector).toContain("tabular-nums");
    expect(style.family.toLowerCase(), selector).toMatch(/^"?inter"?\s*,/);
  }
});

test("a toast reads in the interface face and holds no forbidden dash", async ({ page }) => {
  await page.goto("/app/opportunities?sort=company");
  const row = page.locator(".row[data-id]:not(.grp-head)").first();
  await row.hover();
  await row.locator('button[data-mark="reviewed"]').click();
  const toast = page.locator(".toast");
  await expect(toast).toBeVisible();
  const size = await toast.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(size).toBeGreaterThanOrEqual(13);
  expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
  // Put the mark back as it was.
  await page.locator(".toast .link-btn", { hasText: "Undo" }).click();
});

test("Pulls rows keep the company as the strongest line and show the whole role", async ({ page }) => {
  await page.goto("/app/pulls");
  const summary = page.locator(".pull-entry:not(.quiet) .pull-summary[aria-expanded='false']").first();
  if (await summary.count()) await summary.click();
  const row = page.locator(".job-line").first();
  await expect(row).toBeVisible();
  const style = await row.evaluate((element) => {
    const company = getComputedStyle(element.querySelector(".job-company")!);
    const title = element.querySelector(".job-title") as HTMLElement;
    const role = getComputedStyle(title);
    return {
      companyWeight: Number(company.fontWeight),
      roleWeight: Number(role.fontWeight),
      roleClipped: title.scrollWidth > title.clientWidth + 1,
    };
  });
  expect(style.companyWeight).toBeGreaterThan(style.roleWeight);
  expect(style.roleClipped).toBe(false);
});
