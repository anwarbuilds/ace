import { expect } from "@playwright/test";

import { DRAWN_SCAN, ROUTES, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

// Every route renders in both themes with no errors and no dash, typed
// or drawn. This is the guard the user asked for repeatedly.
for (const theme of ["dark", "light"] as const) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ context, baseURL }) => setThemeCookies(context, baseURL!, theme));

    for (const route of ROUTES) {
      test(`${route} renders cleanly`, async ({ page }) => {
        const errors = watchErrors(page);
        await page.goto(route);
        await expect(page.locator("h1").first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        if (theme === "light") await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
        else await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
        expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
        expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
        expect(errors).toEqual([]);
      });
    }

    test("a job page renders cleanly", async ({ page }) => {
      const errors = watchErrors(page);
      await page.goto("/app/opportunities");
      await page.locator("a.j-title").first().click();
      await expect(page).toHaveURL(/\/app\/jobs\/\d+$/);
      await expect(page.locator(".jp-title")).toBeVisible();
      await page.waitForLoadState("networkidle");
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

test("the wordmark is lowercase ace and nothing else", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator(".side .brand")).toHaveText("ace");
});

test("Saved is not in the navigation, but saved roles stay reachable", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator(".side .nav-item", { hasText: "Saved" })).toHaveCount(0);
  await page.goto("/app/saved");
  await expect(page.locator("h1")).toHaveText("Saved");
});

test("an unknown job id is a friendly not-found page", async ({ page }) => {
  await page.goto("/app/jobs/99999999");
  await expect(page.getByText("That opportunity could not be found")).toBeVisible();
});
