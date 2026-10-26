import { expect } from "@playwright/test";
import { test, setThemeCookies, watchErrors } from "./helpers";

// These routes read the isolated demo database. The employer names below are
// public brand identities; no actual applications, answers or mail are used.
for (const theme of ["light", "dark"] as const) {
  for (const width of [1672, 700, 390]) {
    test(`${theme} ${width}px: company pages retain verified logos and visible fallbacks`, async ({ page, context, baseURL }) => {
      await setThemeCookies(context, baseURL!, theme);
      await page.setViewportSize({ width, height: 941 });
      const errors = watchErrors(page);
      const before = await (await page.request.get("/api/marks")).json();
      for (const [name, asset] of [["Apple", "apple.ico"], ["FedEx Freight", "fedex-freight.png"], ["General Motors", "general-motors.png"], ["Southern Company", "southern-company.png"]]) {
        await page.goto(`/app/company/${encodeURIComponent(name)}`);
        const logo = page.locator(".page-hero").getByRole("img", { name: `${name} logo`, exact: true });
        await expect(logo).toBeVisible();
        await expect(logo).toHaveAttribute("src", `/company-logos/${asset}`);
        await expect.poll(() => logo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
        expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
        await expect(page.getByRole("link", { name: "View opportunities" })).toHaveAttribute("href", `/app/opportunities?company=${encodeURIComponent(name)}`);
      }
      await page.goto("/app/company/Fictional%20Labs");
      await expect(page.getByLabel("Fictional Labs monogram", { exact: true })).toHaveText("FL");
      await expect(page.locator(".page-hero img")).toHaveCount(0);
      expect((await (await page.request.get("/api/marks")).json()).applications_total).toBe(before.applications_total);
      expect(errors).toEqual([]);
    });
  }
}

test("a failed official image has a readable fallback and the next company still loads", async ({ page }) => {
  await page.route("**/company-logos/apple.ico", route => route.abort());
  await page.goto("/app/company/Apple");
  await expect(page.getByLabel("Apple monogram", { exact: true })).toHaveText("A");
  await expect(page.locator(".page-hero img")).toHaveCount(0);
  await page.goto("/app/company/General%20Motors");
  await expect(page.getByRole("img", { name: "General Motors logo", exact: true })).toBeVisible();
});
