import { expect, test as base } from "@playwright/test";

import { DRAWN_SCAN, OWNER, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

// Signed out: a fresh context with no session cookie.
const anon = base.extend({
  context: async ({ context, baseURL }, run) => {
    await setThemeCookies(context, baseURL!, "dark");
    await run(context);
  },
});

anon("a signed-out visit to the app goes to sign in", async ({ page }) => {
  await page.goto("/app/opportunities");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fopportunities$/);
  await expect(page.getByRole("heading", { name: "Career intelligence, always on." })).toBeVisible();
});

anon("the public home is available without a session", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Career intelligence, always on." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in", exact: true }).first()).toHaveAttribute("href", "/login");
});

anon("the API refuses an anonymous reader", async ({ request }) => {
  for (const path of ["/api/jobs", "/api/answers", "/api/export.json", "/api/marks"]) {
    const res = await request.get(path);
    expect(res.status(), path).toBe(401);
  }
});

anon("signed-out pages leak no private data in their HTML", async ({ page }) => {
  const res = await page.request.get("/app/answers", { maxRedirects: 0 });
  expect([307, 308]).toContain(res.status());
  const body = await res.text();
  expect(body).not.toContain("Pinecrest");
});

for (const theme of ["dark", "light"] as const) {
  for (const route of ["/", "/login", "/signed-out"] as const) {
    anon(`${route} renders cleanly in ${theme}`, async ({ page, context, baseURL }) => {
      await setThemeCookies(context, baseURL!, theme);
      const errors = watchErrors(page);
      await page.goto(route);
      await expect(page.locator(".auth-wordmark").first()).toHaveText("ace");
      await expect(page.locator(".wine-art-a")).toBeVisible();
      const art = await page.locator(".wine-art-a").boundingBox();
      expect(art).not.toBeNull();
      expect(art!.x).toBeGreaterThanOrEqual(0);
      expect(art!.x + art!.width).toBeLessThanOrEqual(1440);
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}

anon("a wrong password says so and stays on the page", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Continue with Email" }).click();
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill("not the demo password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".auth-err")).toHaveText("That email and password do not match.");
  await expect(page).toHaveURL(/\/login/);
});

anon("signing in returns to the page that was asked for", async ({ page }) => {
  await page.goto("/login?next=%2Fapp%2Fanswers");
  await page.getByRole("button", { name: "Continue with Email" }).click();
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app\/answers$/);
  await expect(page.locator("h1")).toContainText("Answers");
});

anon("next cannot send the reader to another site", async ({ page }) => {
  await page.goto("/login?next=%2F%2Fevil.example%2F");
  await page.getByRole("button", { name: "Continue with Email" }).click();
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app\/pulls$/);
});

anon("a deep link survives signing in", async ({ page }) => {
  await page.goto("/app/analytics");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fanalytics$/);
  await page.getByRole("button", { name: "Continue with Email" }).click();
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(OWNER.email);
  await page.getByLabel("Password").fill(OWNER.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app\/analytics$/);
});

anon("unconfigured providers do not claim a successful sign-in", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page.getByRole("heading", { name: "Google sign-in" })).toBeVisible();
  await expect(page.getByText("This private workspace has not configured Google sign-in.")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("pages carry the security headers", async ({ page }) => {
  const res = await page.goto("/app");
  const headers = res!.headers();
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
});

test("a change without the CSRF header is refused", async ({ page }) => {
  await page.goto("/app");
  const status = await page.evaluate(async () => {
    const res = await fetch("/api/answers", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: [] }),
    });
    return res.status;
  });
  expect(status).toBe(403);
});

test("the extension page pairs it, and the token reads only answers", async ({ page, playwright, baseURL }) => {
  await page.goto("/app/settings");
  await expect(page.getByText(`Signed in as ${OWNER.email}`)).toBeVisible();
  await page.goto("/app/extension");
  await page.getByRole("button", { name: "Pair the extension" }).click();
  const code = (await page.getByLabel("Pairing code").textContent())!.trim();
  expect(code).toMatch(/^[A-Z2-9]{4} [A-Z2-9]{4}$/);

  // The extension, a different client with no cookies.
  const extension = await playwright.request.newContext({ baseURL });
  const paired = await extension.post("/api/extension/pair", { data: { code, name: "Chrome extension" } });
  expect(paired.ok()).toBe(true);
  const { token } = await paired.json();
  const bearer = { Authorization: `Bearer ${token}` };
  expect((await extension.get("/api/answers", { headers: bearer })).status()).toBe(200);
  expect((await extension.get("/api/jobs", { headers: bearer })).status()).toBe(403);

  await page.reload();
  const row = page.locator(".pair-list .lineitem", { hasText: "Chrome extension" }).first();
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Unpair" }).click();
  await expect(page.locator(".toast")).toContainText("Extension unpaired");
  await expect.poll(async () => (await extension.get("/api/answers", { headers: bearer })).status()).toBe(401);
  await extension.dispose();
});

test("signing out ends the session", async ({ page }) => {
  await page.goto("/signed-out");
  await expect(page).toHaveURL(/\/app\/pulls$/);
  await page.goto("/logout");
  await expect(page).toHaveURL(/\/signed-out$/);
  await expect(page.getByRole("heading", { name: "You’re signed out" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Go to public home" })).toHaveAttribute("href", "/");
  await page.goto("/app/pulls");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fpulls$/);
});
