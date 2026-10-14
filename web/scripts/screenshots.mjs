// Screenshot pages in both themes at desktop, tablet and phone widths.
// Usage: BASE=http://localhost:3000 OUT=/tmp/shots node scripts/screenshots.mjs /app/opportunities [...]
// Point it at demo data only: screenshots of real data must never be committed.
import { chromium } from "@playwright/test";

const base = process.env.BASE ?? "http://localhost:3000";
const out = process.env.OUT ?? "/tmp/ace-shots";
const sizes = (process.env.SIZES ?? "desktop").split(",");
const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  phone: { width: 390, height: 844 },
};
const pages = process.argv.slice(2);
const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
for (const size of sizes) {
  for (const theme of ["dark", "light"]) {
    const ctx = await browser.newContext({ viewport: VIEWPORTS[size], deviceScaleFactor: 1 });
    await ctx.addCookies([
      { name: "ace_theme", value: theme, url: base },
      { name: "ace_tz", value: "America/Los_Angeles", url: base },
    ]);
    const page = await ctx.newPage();
    page.on("pageerror", (e) => console.log("pageerror", e.message));
    for (const p of pages) {
      await page.goto(base + p, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const name = `${out}/${size}_${theme}_${p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "")}.png`;
      await page.screenshot({ path: name });
      console.log(name);
    }
    await ctx.close();
  }
}
await browser.close();
