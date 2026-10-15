import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const baseURL = process.env.WEB_URL ?? "http://127.0.0.1:3000";
const output = process.env.AUTH_SCREENSHOT_DIR ?? "test-results/auth-visual";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH ?? "/usr/bin/google-chrome" });

await mkdir(output, { recursive: true });

for (const theme of ["dark", "light"]) {
  const context = await browser.newContext({ viewport: { width: 1672, height: 480 } });
  await context.addCookies([{ name: "ace_theme", value: theme, url: baseURL }]);
  const page = await context.newPage();
  await page.goto(`${baseURL}/login`);
  await page.locator(".auth-backdrop").waitFor();
  await page.screenshot({ path: `${output}/${theme}-sign-in.png` });

  await page.setViewportSize({ width: 1672, height: 461 });
  await page.goto(`${baseURL}/signed-out`);
  await page.locator(".auth-signedout-panel").waitFor();
  await page.screenshot({ path: `${output}/${theme}-sign-out.png` });
  await context.close();
}

for (const [name, width, height] of [
  ["desktop-1440x900", 1440, 900],
  ["laptop-1280x800", 1280, 800],
  ["mobile-390x844", 390, 844],
]) {
  const context = await browser.newContext({ viewport: { width, height } });
  await context.addCookies([{ name: "ace_theme", value: "dark", url: baseURL }]);
  const page = await context.newPage();
  await page.goto(`${baseURL}/login`);
  await page.locator(".auth-signin-panel").waitFor();
  await page.screenshot({ path: `${output}/dark-${name}-sign-in.png` });
  await context.close();
}

await browser.close();
