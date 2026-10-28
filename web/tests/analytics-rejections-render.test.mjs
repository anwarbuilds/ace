// Render the Analytics Companies tab with fictional data, without Chrome.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import Module, { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { parseHTML } from "linkedom";
const nodeRequire = createRequire(import.meta.url);
const sourceRoot = fileURLToPath(new URL("../src", import.meta.url));
const cache = new Map();

function loadSource(filename) {
  if (cache.has(filename)) return cache.get(filename).exports;
  const loadedModule = { exports: {} };
  cache.set(filename, loadedModule);
  const output = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const sourceRequire = (name) => {
    // The filters need Next's app router; this test is about the panels.
    if (name === "./AnalyticsFilters") return { AnalyticsFilters: () => null, AnalyticsCompanySelect: () => null, AnalyticsChartInterval: () => null, AnalyticsWeekPicker: () => null };
    if (name.startsWith(".")) {
      // A sibling component, or data such as the logo provenance JSON.
      const near = path.resolve(path.dirname(filename), name);
      const source = [near + ".ts", near + ".tsx"].find(fs.existsSync);
      return source ? loadSource(source) : createRequire(filename)(name);
    }
    if (!name.startsWith("@/")) return nodeRequire(name);
    const base = path.join(sourceRoot, name.slice(2));
    const found = [base + ".ts", base + ".tsx"].find(fs.existsSync);
    assert.ok(found, `Missing source module ${name}`);
    return loadSource(found);
  };
  vm.runInThisContext(Module.wrap(output), { filename })(loadedModule.exports, sourceRequire, loadedModule, filename, path.dirname(filename));
  return loadedModule.exports;
}

const { AnalyticsView } = loadSource(path.join(sourceRoot, "components/analytics/AnalyticsView.tsx"));
const zero = { submitted: 0, eligible: 0, responses: 0, rejections: 0, assessments: 0, interviews: 0, rate: null };
const base = {
  as_of: "2026-10-26T18:00:00Z", timezone: "America/Los_Angeles", start: "2026-09-27", end: "2026-10-26", days: "30", family: null,
  available_families: [], total_submitted: 9, submitted: 9, undated: 0, week_total: 1, positive: 0, assessments: 0, interviews: 0,
  has_outcome_evidence: true, statuses: { applied: 6, rejected: 3 }, daily: [], granularity: "daily",
  week: Array.from({ length: 7 }, (_, i) => ({ date: `2026-10-${20 + i}`, count: 0 })),
  cohort: { eligible: 0, positive: 0, rejected: 0, pending: 0, unknown: 0, rate: null, coverage: "" }, timing: [], median_days: null, timing_sample: 0,
  evidence: { positive: 0, rejected: 3, manual: 2, automatic: 1 }, review: { needs_review: 0, exact_preview: 0, ambiguous: 0 }, roles: [],
  attribution: { resume: "Not recorded", channel: "Not recorded", combinations: [] },
  companies: [{ name: "Wayfern", ...zero, submitted: 6, latest: "rejection", latest_at: null }], selected_company: "Wayfern",
  rejected_companies: [
    { name: "Wayfern", rejections: 2, applications: 6, latest_at: "2026-10-26T17:30:00Z", dated: 1, in_progress: 4,
      roles: ["Full-Stack Software Engineer", "Machine Learning Engineer, Perception", "Data Platform Engineer"] },
    { name: "Northwind Robotics", rejections: 1, applications: 3, latest_at: null, dated: 0, in_progress: 0, roles: ["Software Engineer, New Grad"] }],
  rejection_summary: { applications: 3, companies: 2, dated: 1, latest_at: "2026-10-26T17:30:00Z" },
  verified_companies: [], reports: [], annual: [],
};
const render = (d) => renderToStaticMarkup(React.createElement(AnalyticsView, { d, connection: null, tab: "companies", query: { tab: "companies" } }));

test("Rejected companies keeps the card grid, newest first, with no table or paging here", () => {
  const html = render(base);
  assert.match(html, /<h2>Rejected companies<\/h2>/);
  assert.doesNotMatch(html, /Companies that rejected you/);
  assert.match(html, /2 companies, 3 rejections, for applications in this selection\./);
  assert.match(html, /<ul class="an-rejected-list">/);
  assert.match(html, /<strong>Wayfern<\/strong><small>Latest Oct 26, 2026<\/small><\/span><b>2 of 6<\/b>/);
  assert.match(html, /<strong>Northwind Robotics<\/strong><small>Date not recorded<\/small>/);
  assert.ok(html.indexOf("Wayfern") < html.indexOf("Northwind Robotics"));
  assert.match(html, /company=Wayfern&amp;evidence=rejection/);
  assert.match(html, /View rejected applications/);
  assert.doesNotMatch(html, /an-rejected-table|an-rejection-stats|Dated by an email/);
  assert.doesNotMatch(html, /Newest \d+ of/);
  assert.doesNotMatch(html, /[\u2013\u2014]/);
});

test("many rejected companies show the newest 15 and send the rest to the searchable list", () => {
  const many = Array.from({ length: 20 }, (_, i) => ({ name: `Fiction ${i + 1}`, rejections: 1, applications: 1, latest_at: null, dated: 0, roles: [], in_progress: 0 }));
  const html = render({ ...base, rejected_companies: many });
  assert.equal((html.match(/<li>/g) ?? []).length, 15);
  assert.match(html, /Newest 15 of 20 companies\./);
  assert.match(html, /Search all rejected applications/);
});

test("the sponsorship methodology section is gone from the Companies tab", () => {
  const html = render(base);
  assert.doesNotMatch(html, /Sponsorship evidence methodology|analytics-methodology|>Methodology/);
  assert.match(html, /Companies with verified sponsorship evidence/);
});

test("with no rejection the panel says so instead of showing an empty table", () => {
  const html = render({ ...base, rejected_companies: [], rejection_summary: { applications: 0, companies: 0, dated: 0, latest_at: null } });
  assert.match(html, /<h2>Rejected companies<\/h2>/);
  assert.match(html, /No rejection is recorded for applications in this selection/);
  assert.doesNotMatch(html, /an-rejected-table/);
});


test("the six approved Companies modules precede the retained rejection grid", () => {
  const html=render(base);
  assert.ok(html.indexOf("Sponsorship evidence</h2>") < html.indexOf("Rejected companies</h2>"));
});
for(const tab of ["overview","outcomes","role-resume","companies"]) {
  test(`${tab}: real fixture values and missing evidence keep their distinct meanings`,()=>{
    const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection:{connected:true,state:"paused",available:true,last_synced_at:null},tab,query:{tab}}));
    assert.match(html,/an-metric-value">9</);
    assert.doesNotMatch(html,/>74<|>919<|Aster Systems|Arcadia Cloud|96%/);
    if(tab!=="companies") { assert.match(html,/>Paused</);assert.doesNotMatch(html,/an-connected">Paused/); }
    if(tab==="overview")assert.match(html,/outcome pairs/);
    if(tab==="role-resume")assert.match(html,/Not recorded/);
  });
}

test("Analytics exposes incomplete Gmail coverage even on the Companies tab",()=>{
  const connection={connected:true,state:"ready",available:true,last_synced_at:"2026-10-26T18:00:00Z",coverage:{days:30,gmail:949,in_ace:516,missing:433,complete:true,checked_at:"2026-10-26T18:00:00Z"}};
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection,tab:"companies",query:{}}));
  assert.match(html,/Gmail has 949 emails from the last 30 days. 433 are not in ACE yet/);
  assert.doesNotMatch(html,/All are in ACE/);
});

test("Analytics shows selected-scope evidence exclusions and total pending mail including deferred",()=>{
  const d={...base,review:{needs_review:2,exact_preview:1,ambiguous:1,deferred:4},inbox_audit:{stored_messages:30,pending_messages:7,stale_messages:5,excluded_events:{before_application_window:2}}};
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:{connected:true,state:"ready",last_synced_at:"2026-10-26T18:00:00Z"},tab:"outcomes",query:{}}));
  assert.match(html,/7 messages await review/);
  assert.match(html,/30 emails imported in total; 7 await your decision; 5 need a re-read/);
  assert.match(html,/2 outcome events in this selection are.*excluded from verified email evidence/);
  assert.match(html,/decision=deferred/);
  assert.match(html,/Decide later/);
  assert.match(html,/has not been verified/);
});

test("recognized unlinked outcomes have an evidence link without inflating review or confirmed outcomes",()=>{
  const d={...base,
    cohort:{...base.cohort,eligible:9,positive:2,rejected:3,pending:4},
    review:{needs_review:2,exact_preview:1,ambiguous:1,deferred:4,unlinked:6},
    inbox_audit:{stored_messages:30,pending_messages:7,stale_messages:0,excluded_events:{}},
  };
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:{connected:true,state:"ready",last_synced_at:"2026-10-26T18:00:00Z"},tab:"outcomes",query:{}}));
  const {document}=parseHTML(html);
  const evidence=document.querySelector('.an-review-list a[href="/app/applications/inbox?decision=unlinked_outcome"]');
  assert.ok(evidence,"recognized historical evidence remains reachable from Analytics");
  assert.equal(evidence.querySelector("strong").textContent,"Unlinked historical outcomes");
  assert.equal(evidence.querySelector("b").textContent,"6");
  assert.match(evidence.textContent,/Recognized evidence without an eligible application; excluded from outcome totals/);
  assert.match(document.querySelector(".an-inbox-copy").textContent,/7 messages await review/);
  assert.match(document.querySelector(".an-audit-note").textContent,/30 emails imported in total; 7 await your decision/);
  assert.equal(document.querySelector(".an-cohort-strip").getAttribute("aria-label"),"Confirmed positive replies: 2; Confirmed rejections: 3; Still pending: 4; Other or unknown evidence: 0");
  const review=document.querySelector('.an-review-list a[href="/app/applications/inbox?decision=review"]');
  assert.equal(review.querySelector("b").textContent,"2");
});

test("Analytics omits an empty unlinked evidence card for both older and current API replies",()=>{
  for(const unlinked of [undefined,0]){
    const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d:{...base,review:{...base.review,unlinked}},connection:null,tab:"outcomes",query:{}}));
    assert.doesNotMatch(html,/Unlinked historical outcomes|decision=unlinked_outcome/);
    assert.match(html,/Inbox evidence review/);
  }
});


test("an empty cohort has no invented zero-denominator percentage",()=>{
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection:null,tab:"outcomes",query:{}}));
  assert.match(html,/>n\/a</);
  assert.doesNotMatch(html,/>0%</);
});
