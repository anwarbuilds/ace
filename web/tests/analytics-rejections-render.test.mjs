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

test("company rejection emails have their own date scope and links without changing rejected applications",()=>{
  const d={...base,
    company_rejections:[{company:"Silverpine Labs",messages:2,latest_at:"2026-10-25T01:00:00Z",message_ids:[902,901]},
      {company:"Northwind Robotics",messages:1,latest_at:"2026-10-23T12:00:00Z",message_ids:[903]}],
    company_rejection_summary:{companies:2,messages:3,latest_at:"2026-10-25T01:00:00Z",date_basis:"email_received",start:"2026-10-01",end:"2026-10-25",family_excluded_messages:0},
  };
  const {document}=parseHTML(render(d));
  const panel=document.querySelector(".an-company-rejection-evidence");
  assert.ok(panel);
  assert.match(panel.textContent,/Employer identified; the individual application or role is not assigned/);
  assert.match(panel.textContent,/Email outcome dates: 2026-10-01 through 2026-10-25/);
  assert.match(panel.textContent,/Filtered by when the email arrived, separately from application submission dates/);
  assert.match(panel.textContent,/3 rejection emails from 2 companies/);
  assert.match(panel.textContent,/separate from rejected application totals/);
  assert.match(panel.textContent,/Latest Oct 24, 2026/);
  assert.match(panel.textContent,/No individual application status changes/);
  assert.match(panel.textContent,/does not enter role stages, response timing or application cohort rates/);
  for(const id of [901,902,903]){
    assert.ok(panel.querySelector(`a[href="/app/applications/inbox?decision=company_rejection&message=${id}"]`),`email ${id} remains inspectable`);
  }
  assert.ok(panel.querySelector('a[href="/app/applications/inbox?decision=company_rejection"]'));
  assert.equal(panel.querySelectorAll(".an-rejected-list li").length,2);
  assert.equal(panel.querySelector(".an-rejected-list b").textContent,"2 emails");
  assert.doesNotMatch(panel.innerHTML,/evidence=rejection|2 of 6/);
  const exact=document.querySelector(".an-rejections:not(.an-company-rejection-evidence)");
  assert.match(exact.textContent,/2 companies, 3 rejections, for applications in this selection/);
  assert.match(exact.textContent,/2 of 6/);
});

test("company-only evidence cannot appear as role family outcomes and offers a scoped all-role view",()=>{
  const d={...base,family:"ML_ENGINEERING",company_rejections:[],
    company_rejection_summary:{companies:0,messages:0,latest_at:null,date_basis:"email_received",start:"2026-10-01",end:"2026-10-25",family_excluded_messages:3},
  };
  const query={tab:"companies",family:"ML_ENGINEERING",company:"Silverpine Labs",days:"90"};
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"companies",query}));
  const {document}=parseHTML(html);
  const panel=document.querySelector(".an-company-rejection-evidence");
  assert.match(panel.textContent,/3 company rejection emails are excluded from this role family selection because the role is not verified/);
  assert.equal(panel.querySelectorAll(".an-rejected-list li").length,0);
  const link=[...panel.querySelectorAll("a")].find(a=>a.textContent==="View all role families");
  const destination=new URL(link.getAttribute("href"),"https://fixture.example");
  assert.equal(destination.searchParams.has("family"),false);
  assert.equal(destination.searchParams.get("company"),"Silverpine Labs");
  assert.equal(destination.searchParams.get("days"),"90");
  assert.equal(destination.searchParams.get("tab"),"companies");
});

test("all-time company evidence retains historical dates without borrowing the first submission date",()=>{
  const html=render({...base,days:"all",company_rejections:[{company:"Silverpine Labs",messages:1,latest_at:"2025-02-10T12:00:00Z",message_ids:[904]}],
    company_rejection_summary:{companies:1,messages:1,latest_at:"2025-02-10T12:00:00Z",date_basis:"email_received",start:null,end:"2026-10-25",family_excluded_messages:0},
  });
  const {document}=parseHTML(html);
  const panel=document.querySelector(".an-company-rejection-evidence");
  assert.match(panel.textContent,/Email outcome dates: All dates through 2026-10-25/);
  assert.match(panel.textContent,/1 rejection email from 1 company/);
  assert.match(panel.textContent,/Latest Feb 10, 2025/);
  assert.ok(panel.querySelector('a[href="/app/applications/inbox?decision=company_rejection&message=904"]'));
  assert.doesNotMatch(panel.textContent,/Submission dates|2026-09-27/);
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

const classifiedEvidence={total:19,categories:{rejection:6,online_assessment:7,interview:3,offer:1,recruiter_reply:1,action_required:1},date_basis:"email_received",application_status_changed:false,family_excluded_messages:0,company_excluded_messages:0};
for(const tab of ["overview","outcomes"]){
  test(`${tab}: recognized hiring progress survives later rejection without inflating application metrics`,()=>{
    const d={...base,days:"all",positive:2,assessments:1,interviews:1,statuses:{applied:6,rejected:3},classified_email_evidence:classifiedEvidence};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab,query:{tab}})));
    const panel=document.querySelector(".an-classified-email-evidence");
    assert.ok(panel);
    assert.match(panel.textContent,/Email receipt dates: All dates through 2026-10-26.*America\/Los_Angeles/);
    assert.match(panel.textContent,/19 classified emails in this scope/);
    assert.match(panel.textContent,/A later rejection does not erase an earlier assessment or interview/);
    assert.match(panel.textContent,/email counts, not additional applications or confirmed stage totals/);
    for(const [filter,label,count] of [["assessments","Assessment emails",7],["interviews","Interview emails",3],["offers","Offer emails",1],["classified_rejection","Rejection emails classified and filed",6]]){
      const link=panel.querySelector(`a[href="/app/applications/inbox?decision=${filter}"]`);
      assert.equal(link.querySelector("strong").textContent,label);
      assert.equal(link.querySelector("b").textContent,String(count));
    }
    assert.match(panel.textContent,/Recruiter reply emails: 1.*Other action instructions: 1/);
    assert.ok(panel.querySelector('a[href="/app/applications/inbox?decision=classified_action"]'));
    const metrics=[...document.querySelectorAll(".an-metric")];
    const metric=label=>metrics.find(node=>node.querySelector(".an-metric-label").textContent===label);
    assert.equal(metric("Applications sent").querySelector("strong").textContent,"9");
    assert.equal(metric("Meaningful replies").querySelector("strong").textContent,"2");
    assert.equal(metric("Online assessments").querySelector("strong").textContent,"1");
    assert.equal(metric("Interview invitations").querySelector("strong").textContent,"1");
    assert.match(metric("Online assessments").textContent,/including later rejections/);
    assert.match(panel.textContent,/historical invitations may already be completed or cancelled/);
    assert.doesNotMatch(panel.innerHTML,/evidence=online_assessment|evidence=interview|evidence=rejection/);
  });
}

test("recognized email progress explains unknown company and role exclusions in scoped views",()=>{
  const d={...base,family:"ML_ENGINEERING",classified_email_evidence:{...classifiedEvidence,total:0,categories:{rejection:0,online_assessment:0,interview:0,offer:0,recruiter_reply:0,action_required:0},family_excluded_messages:13,company_excluded_messages:6}};
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"outcomes",query:{family:"ML_ENGINEERING",company:"Wayfern"}})));
  const panel=document.querySelector(".an-classified-email-evidence");
  assert.ok(panel);
  assert.match(panel.textContent,/13 classified emails lack a verified role family and are excluded from this family selection/);
  assert.match(panel.textContent,/6 classified emails lack a verified company and are excluded from this company selection/);
  assert.match(panel.textContent,/0 classified emails in this scope/);
  assert.equal(document.querySelectorAll(".an-cohort-strip span").length,0,"unattributed emails cannot create application cohort outcomes");
});

test("missing or empty classified evidence does not add a fabricated progress panel",()=>{
  for(const evidence of [undefined,{...classifiedEvidence,total:0,categories:{rejection:0,online_assessment:0,interview:0,offer:0,recruiter_reply:0,action_required:0}}]){
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d:{...base,classified_email_evidence:evidence},connection:null,tab:"overview",query:{}})));
    assert.equal(document.querySelector(".an-classified-email-evidence"),null);
  }
});

test("unverified source counts describe message meaning without confirming employer outcomes",()=>{
  for(const count of [1,3]){
    const d={...base,classified_email_evidence:{...classifiedEvidence,unverified_source_messages:count}};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"overview",query:{}})));
    const panel=document.querySelector(".an-classified-email-evidence");
    const note=panel.querySelector('[role="note"][aria-label="Unverified email sources"]');
    assert.ok(note);
    assert.match(note.textContent,new RegExp(`^${count} classified ${count===1?"email has an unverified sender":"emails have unverified senders"}`));
    assert.match(note.textContent,/message meaning only; no employer or application outcome is verified/);
    assert.match(panel.textContent,/19 classified emails in this scope/);
    assert.equal(document.querySelector(".an-metric strong").textContent,"9");
    assert.equal(panel.querySelector('a[href="/app/applications/inbox?decision=classified_rejection"] b').textContent,"6");
  }
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d:{...base,classified_email_evidence:{...classifiedEvidence,unverified_source_messages:0}},connection:null,tab:"overview",query:{}})));
  assert.equal(document.querySelector('[aria-label="Unverified email sources"]'),null);
});

test("recognized progress uses effective email dates while application cohorts keep their own selection",()=>{
  const evidence_scope={start:"2026-07-01",timezone:"America/Los_Angeles",start_at:"2026-07-01T07:00:00Z",application_cohort_unchanged:true};
  for(const [days,start,effective] of [["all","2025-01-01","2026-07-01"],["custom","2026-09-01","2026-09-01"]]){
    const d={...base,days,start,evidence_scope,classified_email_evidence:{...classifiedEvidence,start:effective,end:"2026-10-26"}};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"outcomes",query:{}})));
    const panel=document.querySelector(".an-classified-email-evidence");
    assert.match(panel.querySelector('[aria-label="Email history period"]').textContent,/Since July 1, 2026/);
    assert.match(panel.textContent,new RegExp(`Email receipt dates: ${effective} through 2026-10-26`));
    assert.match(panel.textContent,/Application submission dates and confirmed stage history remain separate/);
    assert.equal(document.querySelector(".an-metric strong").textContent,"9");
    assert.match(document.querySelector(".an-bottom-links").textContent,new RegExp(`Submission dates.*${start}`));
    assert.doesNotMatch(panel.textContent,/Email receipt dates: All dates/);
  }
});
