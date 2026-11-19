import { expect } from "@playwright/test";

import { DRAWN_SCAN, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

// A copy from Zapply's list credits the list with a followed link, as its
// terms ask, and says it was not read from the employer's own board. The
// demo holds one fictional copy.

for (const theme of ["dark", "light"] as const) {
  test(`a Zapply copy credits Zapply's list (${theme})`, async ({ page, context, baseURL, request }) => {
    await setThemeCookies(context, baseURL!, theme);
    const res = await request.get("/api/jobs?source=zapply");
    expect(res.ok()).toBe(true);
    const body = (await res.json()) as { items: { id: number; source: string; company: string }[] };
    const copy = body.items.find((item) => item.source === "zapply");
    expect(copy, "the demo holds one Zapply copy").toBeTruthy();

    const errors = watchErrors(page);
    await page.goto(`/app/jobs/${copy!.id}`);
    await expect(page.locator(".jp-title")).toBeVisible();
    const credit = page.getByRole("link", { name: "Zapply’s new grad list" });
    await expect(credit).toHaveAttribute("href", "https://github.com/zapplyjobs/New-Grad-Software-Engineering-Jobs-2027");
    // A followed link: no nofollow.
    expect(await credit.getAttribute("rel")).not.toContain("nofollow");
    await expect(page.locator(".kv")).toContainText(`(a copy; not read from ${copy!.company}’s own board)`);
    await page.waitForLoadState("networkidle");
    expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
    expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
    expect(errors).toEqual([]);

    if (process.env.ACE_SCREENSHOT_DIR) {
      const fs = await import("node:fs");
      const path = await import("node:path");
      const dir = path.resolve(process.env.ACE_SCREENSHOT_DIR, theme);
      fs.mkdirSync(dir, { recursive: true });
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.screenshot({ path: path.join(dir, "zapply-copy-job.png") });
    }
  });
}
