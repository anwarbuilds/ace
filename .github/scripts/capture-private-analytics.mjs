// Optional owner-private visual review. No raw snapshot or screenshot is saved
// to Git or uploaded: only a recipient-encrypted artifact leaves this process.
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { createRequire } from "node:module";

const encoded = process.env.ACE_PRIVATE_ANALYTICS_CAPTURE;
if (!encoded) {
  console.log("No private capture bundle supplied.");
  process.exit(0);
}
const require = createRequire(path.resolve("web/package.json"));
const { chromium } = require("@playwright/test");
let server, browser;
try {
  const bundle = JSON.parse(zlib.gunzipSync(Buffer.from(encoded, "base64")));
  const cssRoot = "web/.next/static/css";
  const css = fs.readdirSync(cssRoot).filter(name => name.endsWith(".css"))
    .map(name => fs.readFileSync(path.join(cssRoot, name), "utf8")).join("\n")
    + "\n" + fs.readFileSync("web/src/app/app/analytics/analytics.css", "utf8");
  const font = fs.readFileSync("web/src/app/fonts/InterVariable.woff2");
  server = http.createServer((request, response) => {
    const name = new URL(request.url, "http://127.0.0.1").pathname.slice(1);
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Security-Policy", "default-src 'none'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; script-src 'none'; base-uri 'none'; form-action 'none'");
    if (name === "shared.css") { response.setHeader("Content-Type", "text/css"); response.end(css); }
    else if (name === "Inter.woff2") { response.setHeader("Content-Type", "font/woff2"); response.end(font); }
    else if (Object.hasOwn(bundle.pages, name)) { response.setHeader("Content-Type", "text/html; charset=utf-8"); response.end(bundle.pages[name]); }
    else { response.statusCode = 404; response.end(); }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" && url.port === String(port) ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  const captures = [], geometry = [];
  for (const theme of ["dark", "light"]) {
    await page.setViewportSize(theme === "dark" ? { width: 1536, height: 1024 } : { width: 1672, height: 941 });
    for (const historical of [false, true]) {
      const suffix = historical ? "-historical" : "";
      await page.goto(`http://127.0.0.1:${port}/${theme}${suffix}.html`);
      await page.evaluate(() => document.fonts.ready);
      captures.push({ name: `actual-${theme}-overview${suffix}.png`, data: (await page.screenshot()).toString("base64") });
      geometry.push(await page.evaluate(({ theme, historical }) => ({
        theme, historical, viewport: [innerWidth, innerHeight], overflow: document.documentElement.scrollWidth > innerWidth,
        fontLoaded: document.fonts.check("14px InterCapture"),
        bounds: Object.fromEntries([".sb", ".tb", ".an-hero", ".an-filters", ".an-inbox-band", ".an-metric", ".an-tabs", ".an-overview-top>.an-panel", ".an-overview-bottom>.an-panel", ".an-date-toggle svg", ".an-week-picker .nic", ".an-weekly", ".an-donut"].map(selector => [selector,
          [...document.querySelectorAll(selector)].map(element => {
            const box = element.getBoundingClientRect(), style = getComputedStyle(element);
            return { x: box.x, y: box.y, width: box.width, height: box.height, font: style.fontFamily, fontSize: style.fontSize, weight: style.fontWeight, lineHeight: style.lineHeight, letterSpacing: style.letterSpacing };
          }),
        ])),
      }), { theme, historical }));
    }
  }
  if (geometry.some(row => row.overflow || !row.fontLoaded)) throw new Error("Capture geometry failed");
  const key = crypto.randomBytes(32), nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, nonce);
  const cleartext = zlib.gzipSync(Buffer.from(JSON.stringify({ captures, geometry, provenance: bundle.provenance, source: process.env.GITHUB_SHA })));
  const ciphertext = Buffer.concat([cipher.update(cleartext), cipher.final()]);
  const encryptedKey = crypto.publicEncrypt({ key: bundle.recipient, padding: crypto.constants.RSA_PKCS1_OAEP_PADDING, oaepHash: "sha256" }, key);
  fs.mkdirSync("artifacts", { recursive: true });
  fs.writeFileSync("artifacts/analytics-private-capture.enc", JSON.stringify({ version: 1, key: encryptedKey.toString("base64"), nonce: nonce.toString("base64"), tag: cipher.getAuthTag().toString("base64"), ciphertext: ciphertext.toString("base64") }));
  console.log("Four private captures encrypted for the local recipient; no raw data uploaded.");
} catch (error) {
  console.error(`Private capture failed (${error.name}); private diagnostics withheld.`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
}
