import { expect } from "@playwright/test";

import { DRAWN_SCAN, setThemeCookies, test, TEXT_SCAN, watchErrors } from "./helpers";

test("owner profile edits and email verification entry render in both themes", async ({ page, context, baseURL }) => {
  const errors = watchErrors(page);
  await page.goto("/app/settings#account");
  await expect(page.getByRole("heading", { name: "Your ACE identity" })).toBeVisible();
  const firstName = await page.getByLabel("First name").inputValue() === "Alex" ? "Avery" : "Alex";
  await page.getByLabel("First name").fill(firstName);
  await page.getByLabel("Last name").fill("Rivera");
  await page.getByLabel("Phone number").fill("+1 206 555 0199");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Profile saved")).toBeVisible();
  await expect(page.locator(".sb-user")).toContainText(`${firstName} Rivera`);
  await expect(page.locator(".sb-user-s")).toHaveCount(0);
  await page.getByRole("button", { name: "Change sign-in email" }).click();
  await expect(page.getByLabel("New email address")).toBeVisible();
  await expect(page.getByLabel("Current password")).toBeVisible();
  await page.getByRole("button", { name: "Cancel email change" }).click();
  const photo = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAALUlEQVR4nGNs0nBjoCVgoqnpoxaMWjBqwagFoxaMWjBqwagFoxaMWjBqARUBAO0wATBh/Kh9AAAAAElFTkSuQmCC",
    "base64",
  );
  await page.getByLabel("Choose a profile photo").setInputFiles({
    name: "photo.png", mimeType: "image/png", buffer: photo,
  });
  await expect(page.locator(".account-avatar img")).toBeVisible();
  await expect(page.locator(".sb-avatar img")).toBeVisible();
  for (const theme of ["dark", "light"] as const) {
    await setThemeCookies(context, baseURL!, theme);
    await page.reload();
    await expect(page.getByLabel("First name")).toHaveValue(firstName);
    await expect(page.getByLabel("Last name")).toHaveValue("Rivera");
    await expect(page.getByLabel("Phone number")).toHaveValue("+1 206 555 0199");
    await expect(page.locator(".account-avatar")).toBeVisible();
    expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
    expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
    if (process.env.ACE_SCREENSHOT_DIR) {
      await page.screenshot({ path: `${process.env.ACE_SCREENSHOT_DIR}/account-${theme}.png`, fullPage: true });
    }
  }
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.locator(".account-avatar img")).toHaveCount(0);
  expect(errors).toEqual([]);
});
