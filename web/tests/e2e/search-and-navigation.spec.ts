import { expect } from "@playwright/test";

import { ROUTES, test } from "./helpers";

// What the owner types is theirs: no field outside sign-in may leave the
// browser to remember it, so a search never returns as a dropdown of past
// entries. Sign-in and account fields name what they hold instead.
test("no text field leaves the browser to remember what was typed", async ({ page }) => {
  for (const route of ROUTES) {
    await page.goto(route);
    await page.locator("main").waitFor();
    const loose = await page.evaluate(() =>
      [...document.querySelectorAll("input, textarea")]
        .filter((el) => !(el instanceof HTMLInputElement) || !["checkbox", "radio", "file", "hidden", "submit", "button", "range", "color"].includes(el.type))
        .filter((el) => !el.getAttribute("autocomplete") && !el.closest("form[autocomplete=off]"))
        .map((el) => `${el.tagName.toLowerCase()} ${el.id || el.getAttribute("name") || el.getAttribute("aria-label") || el.getAttribute("placeholder")}`),
    );
    expect(loose, route).toEqual([]);
  }
});

test("the search box has one focus ring and no key chip", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator(".search .kbd")).toHaveCount(0);
  await page.keyboard.press("/");
  const q = page.locator("#q");
  await expect(q).toBeFocused();
  await expect(q).toHaveAttribute("autocomplete", "off");
  await expect(q).toHaveAttribute("aria-keyshortcuts", "/");
  // The box draws the ring; the field inside draws none of its own.
  expect(await q.evaluate((el) => getComputedStyle(el).outlineStyle)).toBe("none");
  expect(await page.locator(".search").evaluate((el) => getComputedStyle(el).boxShadow)).not.toBe("none");
});

test("a click on the next page dims the list until that page arrives", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator(".pager-says")).toContainText(/^1 to 50 of /);
  await page.evaluate(() => {
    const w = window as typeof window & { __dimmed?: boolean };
    new MutationObserver(() => {
      if ("navigating" in document.documentElement.dataset) w.__dimmed = true;
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-navigating"] });
  });
  await page.locator(".pager-btn", { hasText: /^2$/ }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator(".pager-says")).toContainText(/^51 to /);
  expect(await page.evaluate(() => (window as typeof window & { __dimmed?: boolean }).__dimmed)).toBe(true);
  await expect(page.locator("html")).not.toHaveAttribute("data-navigating");
});
