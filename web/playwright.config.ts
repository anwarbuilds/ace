import { defineConfig, devices } from "@playwright/test";

// Runs against a live app: Next.js on WEB_URL in front of the FastAPI
// demo database (backend/scripts/seed_demo.py). Nothing here starts the
// servers, so the same suite runs locally and in CI. Some tests write
// marks, so point it at demo data, never the live database.
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.WEB_URL ?? "http://localhost:3000",
    // The same zone the signed-in fixtures' cookie names. A browser elsewhere
    // makes the app correct the cookie and refresh every page 400 ms after it
    // loads, and from 00:00 to 08:00 UTC that refresh also moves Pulls to
    // another day, so tests failed only at certain hours.
    timezoneId: "America/Los_Angeles",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : undefined,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
