import type { BrowserContext, Page } from "@playwright/test";

export const ROUTES = [
  "/app",
  "/app/opportunities",
  "/app/activity",
  "/app/applications",
  "/app/archive",
  "/app/saved",
  "/app/resume-studio",
  "/app/resume-studio/facts",
  "/app/resume-studio/documents",
  "/app/resume-studio/check",
  "/app/resume-studio/history",
  "/app/insights/skills",
  "/app/answers",
  "/app/coverage",
  "/app/settings",
];

export async function setThemeCookies(context: BrowserContext, baseURL: string, theme: "dark" | "light") {
  await context.addCookies([
    { name: "ace_theme", value: theme, url: baseURL },
    { name: "ace_tz", value: "America/Los_Angeles", url: baseURL },
  ]);
}

/** Collect uncaught page errors and console errors while a test runs. */
export function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text()}`);
  });
  return errors;
}

// A dash the user can read: em dash, horizontal bar, figure dash, minus
// sign, or an en dash with spaces around it. An unspaced en dash is a
// range ("2–4 years") and is allowed. Textareas hold the user's own
// words and are skipped.
export const TEXT_SCAN = `(() => {
  const BAD = /[\\u2014\\u2015\\u2012\\u2212]|\\s\\u2013\\s/;
  const found = [];
  const walk = (n) => {
    if (n.nodeType === 3) {
      const p = n.parentElement;
      if (p && !/^(TEXTAREA|SCRIPT|STYLE|NOSCRIPT)$/.test(p.tagName) && BAD.test(n.nodeValue)) found.push(n.nodeValue.trim().slice(0, 80));
      return;
    }
    if (n.nodeType !== 1 || /^(TEXTAREA|SCRIPT|STYLE)$/.test(n.tagName)) return;
    for (const a of ["title", "placeholder", "aria-label"]) {
      const v = n.getAttribute(a);
      if (v && BAD.test(v)) found.push(a + ": " + v.slice(0, 80));
    }
    for (let c = n.firstChild; c; c = c.nextSibling) walk(c);
  };
  walk(document.body);
  return found;
})()`;

// Ported from backend/tests/browser/scans.py: a dash can be drawn as well
// as typed. A visible, inked box 6 to 40px wide and at most 3px tall is
// one, except the fill inside a progress track, whose width is its value.
export const DRAWN_SCAN = `(() => {
  const win = window, doc = document, found = [];
  const TYPED = /[\\u2012-\\u2015\\u2212]/;
  const shown = (r, cs) => r.width > 0 && r.height > 0 && cs.display !== "none" && cs.visibility !== "hidden" && parseFloat(cs.opacity) > 0;
  const shortBar = (w, h) => w >= 6 && w <= 40 && h > 0 && h <= 3;
  const inked = (cs) => (cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent") || cs.backgroundImage !== "none" || parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderBottomWidth) > 0;
  const name = (el) => { const c = typeof el.className === "string" ? el.className.trim() : ""; return el.tagName.toLowerCase() + (c ? "." + c.split(/\\s+/).join(".") : ""); };
  for (const el of doc.querySelectorAll("body *")) {
    if (el.closest("svg")) continue;
    const cs = win.getComputedStyle(el), r = el.getBoundingClientRect();
    const pr = el.parentElement ? el.parentElement.getBoundingClientRect() : null;
    const fill = pr !== null && pr.height <= 6 && pr.width > r.width;
    if (!fill && shown(r, cs) && shortBar(r.width, r.height) && inked(cs)) found.push(name(el) + " is a " + Math.round(r.width) + "x" + Math.round(r.height) + " bar");
    for (const p of ["::before", "::after"]) {
      const ps = win.getComputedStyle(el, p), c = ps.content;
      if (!c || c === "none" || c === "normal") continue;
      if (TYPED.test(c)) found.push(name(el) + p + " holds a dash character");
      const w = parseFloat(ps.width), h = parseFloat(ps.height);
      if (ps.display !== "none" && shortBar(w, h) && inked(ps)) found.push(name(el) + p + " is drawn as a " + w + "x" + h + " bar");
    }
  }
  return found;
})()`;

import { test as base } from "@playwright/test";

/** A returning visitor: theme and time zone already known, as after the
 *  first visit. The first visit's one-off refresh is tested on its own. */
export const OWNER = {
  email: process.env.ACE_TEST_EMAIL ?? "demo@ace.example",
  password: process.env.ACE_TEST_PASSWORD ?? "ace demo password",
};

/** Sign in through the API, as the login form does, so the context holds
 *  the owner's session and CSRF cookies. */
export async function signIn(context: BrowserContext, baseURL: string) {
  const res = await context.request.post(`${baseURL}/api/auth/login`, { data: OWNER });
  if (!res.ok()) throw new Error(`sign-in failed: ${res.status()} ${await res.text()}`);
}

/** A signed-in, returning visitor: theme and time zone already known, as
 *  after the first visit. The first visit's one-off refresh, and signing
 *  in itself, are tested on their own. */
export const test = base.extend({
  context: async ({ context, baseURL }, run) => {
    await setThemeCookies(context, baseURL!, "dark");
    await signIn(context, baseURL!);
    await run(context);
  },
  // The standalone API client too, for tests that check what was stored.
  request: async ({ request, baseURL }, run) => {
    const res = await request.post(`${baseURL}/api/auth/login`, { data: OWNER });
    if (!res.ok()) throw new Error(`sign-in failed: ${res.status()}`);
    await run(request);
  },
});
