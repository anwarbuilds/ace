import { expect } from "@playwright/test";

import { signIn, test } from "./helpers";

test("old route names redirect to the new ones", async ({ page }) => {
  for (const [from, to] of [
    ["/app/queue", "/app/opportunities"],
    ["/app", "/app/pulls"],
    ["/app/activity", "/app/pulls"],
    ["/app/dashboard", "/app/analytics"],
    ["/app/applied", "/app/applications"],
    ["/app/resume", "/app/resume-studio"],
    ["/app/skills", "/app/insights/skills"],
    ["/app/browse/software-engineering", "/app/opportunities"],
    ["/app/companies/Pinecrest%20AI", "/app/opportunities"],
  ]) {
    await page.goto(from);
    await expect(page).toHaveURL(new RegExp(`${to}$`));
  }
});

test("the desktop sidebar collapses, persists and expands", async ({ page }) => {
  await page.goto("/app/pulls");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(page.locator(".sb")).toHaveClass(/collapsed/);
  await expect(page.locator(".sb-text").first()).toBeHidden();
  await page.reload();
  await expect(page.locator(".sb")).toHaveClass(/collapsed/);
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect(page.locator(".sb")).not.toHaveClass(/collapsed/);
});

test("an old #job link opens that job's page", async ({ page }) => {
  await page.goto("/app/opportunities");
  const href = await page.locator("a.j-title").first().getAttribute("href");
  const id = href!.split("/").pop();
  await page.goto(`/#job/${id}`);
  await expect(page).toHaveURL(new RegExp(`/app/jobs/${id}$`));
});

test("sort, tier and page live in the URL and survive a reload", async ({ page }) => {
  await page.goto("/app/opportunities");
  // New grad first is the default; turning another sort on makes it lead.
  await expect(page.locator(".chip.on", { hasText: "New grad first" })).toContainText("1st");
  await page.locator(".chip", { hasText: "Fits my experience" }).click();
  await expect(page).toHaveURL(/sort=experience_fit_first(%2C|,)new_grad_first(%2C|,)unapplied_first/);
  await page.locator(".chip", { hasText: "Top tier" }).click();
  await expect(page).toHaveURL(/tier=TOP_TIER/);
  await page.reload();
  await expect(page.locator(".chip.on", { hasText: "Top tier" })).toBeVisible();
  await expect(page.locator(".chip.on", { hasText: "Fits my experience" })).toContainText("1st");
  await expect(page.locator(".sort-says")).toContainText("Showing roles that fit your experience first, then new grad roles");
  for (const tier of await page.locator(".co-tier").allTextContents()) expect(tier).toBe("Top tier");
});

test("numbered pages move through the list and Back returns", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page.locator(".pager-says")).toContainText(/^1 to 50 of /);
  const first = await page.locator("a.j-title").first().textContent();
  await page.locator(".pager-btn", { hasText: /^2$/ }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator(".pager-says")).toContainText(/^51 to /);
  await expect(page.locator('.pager-btn[aria-current="page"]')).toHaveText("2");
  await page.goBack();
  await expect(page.locator(".pager-says")).toContainText(/^1 to 50 of /);
  await expect(page.locator("a.j-title").first()).toHaveText(first!);
});

test("search is debounced into the URL and narrows the list", async ({ page }) => {
  await page.goto("/app/opportunities");
  await page.keyboard.press("/");
  await expect(page.locator("#q")).toBeFocused();
  await page.keyboard.type("Quorvane");
  await expect(page).toHaveURL(/q=Quorvane/);
  for (const name of await page.locator(".co-name").allTextContents()) expect(name).toBe("Quorvane");
  await page.locator(".link-btn", { hasText: "Clear all" }).click();
  await expect(page).not.toHaveURL(/q=/);
});

test("the tabs carry their professional names", async ({ page }) => {
  await page.goto("/app/opportunities");
  const tabs = await page.locator(".tab").allTextContents();
  expect(tabs.map((t) => t.replace(/\d[\d,]*$/, "").trim())).toEqual([
    "All opportunities",
    "Strong matches",
    "New since your last visit",
    "Latest discoveries",
  ]);
  await page.locator(".tab", { hasText: "Strong matches" }).click();
  await expect(page).toHaveURL(/view=matched/);
  for (const t of await page.locator(".m-tier").allTextContents()) expect(t).toBe("HIGH");
});

test("a first visit learns the time zone without losing a click", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ timezoneId: "America/New_York" });
  await signIn(context, baseURL!);
  const page = await context.newPage();
  await page.goto(`${baseURL}/app/opportunities`);
  await page.locator(".pager-btn", { hasText: /^2$/ }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect.poll(async () => (await context.cookies()).find((c) => c.name === "ace_tz")?.value).toBe("America/New_York");
  await context.close();
});

test("one role posted per vertical folds into a group that opens", async ({ page }) => {
  // Searched, so the group is on page one whatever earlier tests marked.
  await page.goto("/app/opportunities?q=Pinecrest");
  const head = page.locator(".grp-head").first();
  await expect(head).toContainText("similar openings");
  await expect(page.locator(".grp-member")).toHaveCount(0);
  await head.click();
  await expect(head).toHaveAttribute("aria-expanded", "true");
  expect(await page.locator(".grp-member").count()).toBeGreaterThanOrEqual(3);
});
