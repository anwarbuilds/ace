import { expect, test } from "@playwright/test";

import { OWNER } from "./helpers";

// The old single-file UI that FastAPI serves at "/" until the switch. It
// must keep working with sign-in on: a sign-in card when signed out, and
// changes that carry the CSRF token once signed in.
const OLD_UI = process.env.OLD_UI_URL ?? "http://127.0.0.1:8000";

test("the old UI asks to sign in, then works", async ({ page }) => {
  await page.goto(`${OLD_UI}/`);
  const card = page.locator(".signin");
  await expect(card).toBeVisible();
  await expect(card.locator(".signin-mark")).toHaveText("ace");

  await card.getByLabel("Email").fill(OWNER.email);
  await card.getByLabel("Password").fill("not the demo password");
  await card.getByRole("button", { name: "Sign in" }).click();
  await expect(card.locator(".signin-err")).toHaveText("That email and password do not match.");

  await card.getByLabel("Password").fill(OWNER.password);
  await card.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".signin")).toHaveCount(0);
  await expect(page.locator(".row").first()).toBeVisible();

  // A change goes through: the wrapper adds the CSRF header.
  const status = await page.evaluate(async () => {
    const before = await (await fetch("/api/answers")).json();
    const res = await fetch("/api/answers", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(before),
    });
    return res.status;
  });
  expect(status).toBe(200);
});
