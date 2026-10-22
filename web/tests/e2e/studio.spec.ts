import { expect } from "@playwright/test";

import { test } from "./helpers";

// Writes facts and assessments: demo data only.

test("the overview shows the matching resume and the knowledge base", async ({ page }) => {
  await page.goto("/app/resume-studio");
  await expect(page.locator("h1")).toHaveText("Resume Studio");
  await expect(page.getByText("Resume used for matching")).toBeVisible();
  await expect(page.locator(".tab", { hasText: "Knowledge base" })).toBeVisible();
  await expect(page.locator(".studio-v2-sheet")).toHaveCount(0);
  await expect(page.getByText("alex-rivera-resume.docx", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download original file" })).toBeVisible();
});

test("the signed-in identity replaces the generic workspace label", async ({ page }) => {
  await page.goto("/app/settings#account");
  await expect(page.getByRole("heading", { name: "Your ACE identity" })).toBeVisible();
  await expect(page.locator(".sb-user-t")).toHaveText("Demo");
  await expect(page.locator(".sb-user-s")).toHaveText("demo@ace.example");
  await expect(page.getByLabel("Full name")).toBeVisible();
  await expect(page.getByText("Personal workspace")).toHaveCount(0);
  await expect(page.getByText("Private, owner")).toHaveCount(0);
});

test("verifying a suggested fact can be undone", async ({ page }) => {
  await page.goto("/app/resume-studio/facts?status=review");
  const card = page.locator(".st-fact", { has: page.locator(".st-status-suggested") }).first();
  const title = (await card.locator("h3").textContent())!.trim();
  await card.getByRole("button", { name: "Verify" }).click();
  await expect(page.locator(".toast")).toContainText("Marked verified");
  await page.locator(".toast .link-btn", { hasText: "Undo" }).click();
  await expect(page.locator(".toast")).toContainText("Marked suggested");
  await expect(page.locator(".st-fact", { hasText: title }).locator(".st-status-suggested").first()).toBeVisible();
});

test("a fact shows the resume lines it was read from", async ({ page }) => {
  await page.goto("/app/resume-studio/facts?kind=experience");
  const card = page.locator(".st-fact").first();
  await card.getByText("Read from your resume").click();
  await expect(card.locator(".st-source pre")).toContainText("Example Analytics");
});

test("the checker scores a stored job with quoted evidence", async ({ page }) => {
  await page.goto("/app/opportunities");
  const href = await page.locator("a.j-title").first().getAttribute("href");
  const id = href!.match(/\/app\/jobs\/(\d+)/)![1];
  await page.goto(`/app/jobs/${id}`);
  await page.getByRole("link", { name: "Check my resume for this role" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/resume-studio/check\\?job=${id}`));
  await page.getByRole("button", { name: "Check this resume" }).click();
  await expect(page.getByText("Estimated ace compatibility score")).toBeVisible();
  await expect(page.locator(".st-comp")).toHaveCount(4);
  await page.getByRole("link", { name: "Saved to history" }).click();
  await expect(page).toHaveURL(/\/app\/resume-studio\/history\/\d+/);
});

test("a pasted job that is too thin says so instead of scoring zero", async ({ page }) => {
  await page.goto("/app/resume-studio/check");
  await page.getByRole("tab", { name: "Paste a description" }).click();
  await page.getByPlaceholder("The full job description, including its requirements").fill("Great team. Apply now.");
  await page.getByRole("button", { name: "Check this resume" }).click();
  await expect(page.locator(".st-hero")).toContainText("Insufficient job data");
  await expect(page.locator(".st-dial-n").first()).toHaveText("?");
});
