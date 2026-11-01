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
    if (name === "next/form") return function FormFixture(props){return React.createElement("form",props);};
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
const { CorrespondenceRecords } = loadSource(path.join(sourceRoot, "components/analytics/CorrespondenceRecords.tsx"));
const { ApplicationMetrics, InboxBand } = loadSource(path.join(sourceRoot, "components/analytics/AnalyticsSummary.tsx"));
const { emailRecordsHref } = loadSource(path.join(sourceRoot, "lib/analytics.ts"));
const emailLink=(panel,kind,scope)=>[...panel.querySelectorAll("a")].find(link=>{
  const url=new URL(link.getAttribute("href"),"https://fixture.example");
  return url.searchParams.get("emails")==="1"&&url.searchParams.get("email_kind")===kind&&(!scope||url.searchParams.get("email_scope")===scope);
});
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

test("Overview headings, seven bars and exact historical links share the selected week",()=>{
  const renderOverview=(supplement,week)=>parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection:null,tab:"overview",query:{days:"30",week},supplement}))).document;
  const dates=["2026-10-19","2026-10-20","2026-10-21","2026-10-22","2026-10-23","2026-10-24","2026-10-25"];
  const supplement={timeline:[],interval:"daily",weekStart:dates[0],weekEnd:dates[6],currentWeek:false,currentWeekTotal:1,
    week:dates.map((date,index)=>({date,end:date,count:index===2?2:0})),submissionTrend:null,weekTrend:null};
  const document=renderOverview(supplement,"2026-10-19");
  const panel=document.querySelector(".an-week-card");
  assert.equal(panel.querySelector("h2").textContent,`Oct 19${String.fromCharCode(0x2013)}Oct 25, 2026`);
  assert.deepEqual([...panel.querySelectorAll(".an-column>span")].map(node=>node.textContent),["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]);
  assert.match(panel.querySelector(".an-foot").textContent,/2 applications in this week/);
  for(const [index,link] of [...panel.querySelectorAll(".an-column")].entries()){
    const url=new URL(link.getAttribute("href"),"https://fixture.test");
    assert.equal(url.searchParams.get("start"),dates[index]);
    assert.equal(url.searchParams.get("end"),dates[index]);
    assert.equal(url.searchParams.get("days"),"custom");
    assert.equal(url.searchParams.get("tz"),"America/Los_Angeles");
  }
  const currentWeek=Array.from({length:7},(_,index)=>{const date=new Date(Date.UTC(2026,9,26+index)).toISOString().slice(0,10);return {date,end:date,count:index===0?1:0};});
  const current=renderOverview({...supplement,week:currentWeek,weekStart:"2026-10-26",weekEnd:"2026-11-01",currentWeek:true},undefined).querySelector(".an-week-card");
  assert.equal(current.querySelector("h2").textContent,"This week");
  assert.equal(current.querySelector(".an-panel-head p").textContent,`Oct 26${String.fromCharCode(0x2013)}Nov 1, 2026`);
  assert.equal(current.querySelectorAll(".an-column[data-future]").length,6);
  assert.equal(current.querySelectorAll("a.an-column").length,1);
  for(const future of current.querySelectorAll(".an-column[data-future]")){
    assert.match(future.getAttribute("aria-label"),/future day/);
    assert.equal(future.querySelector(".an-column-plot span").textContent,"");
  }
  const unavailable=renderOverview(null,"2026-10-19").querySelector(".an-week-card");
  assert.match(unavailable.querySelector("h2").textContent,/Oct 19/);
  assert.match(unavailable.textContent,/could not be verified/);
  assert.equal(unavailable.querySelectorAll(".an-column").length,0,"a failed historical read must not substitute current bars");
});

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
  const category=new URL(emailLink(panel,"rejection","company").getAttribute("href"),"https://fixture.example");
  assert.equal(category.pathname,"/app/applications/analytics");
  assert.equal(category.searchParams.get("start"),base.start);
  assert.equal(category.searchParams.get("end"),base.end);
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

test("Companies removes the evidence disclosure without inventing a response rate",()=>{
  const connection={connected:true,state:"ready",available:true,last_synced_at:"2026-10-26T18:00:00Z",coverage:{days:30,gmail:949,in_ace:516,missing:433,complete:true,checked_at:"2026-10-26T18:00:00Z"}};
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection,tab:"companies",query:{}}));
  assert.doesNotMatch(html,/About these metrics|949 emails|All are in ACE|applications\/export/);
  assert.match(html,/an-rate-na[^>]*>Unavailable/);
});

test("Analytics shows selected-scope evidence exclusions and total pending mail including deferred",()=>{
  const d={...base,review:{needs_review:2,exact_preview:1,ambiguous:1,deferred:4},inbox_audit:{stored_messages:30,pending_messages:7,stale_messages:5,excluded_events:{before_application_window:2}}};
  const html=renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:{connected:true,state:"ready",last_synced_at:"2026-10-26T18:00:00Z"},tab:"outcomes",query:{}}));
  assert.match(html,/7 messages await review/);
  assert.doesNotMatch(html,/About these metrics and evidence|an-audit-note/);
  assert.match(html,/decision=deferred/);
  assert.match(html,/Decide later/);
  assert.match(html,/Application decisions held for confirmation/);
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
  assert.equal(document.querySelector(".an-audit-note"),null);
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
for(const tab of ["overview","outcomes","role-resume","companies"]){
  test(`${tab}: no removed evidence disclosure, application export or recognized progress returns`,()=>{
    const d={...base,days:"all",positive:2,assessments:1,interviews:1,classified_email_evidence:classifiedEvidence};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab,query:{tab}})));
    assert.equal(document.querySelector(".an-classified-email-evidence,.an-audit-note,.an-bottom-links"),null);
    assert.equal(document.querySelector('a[href="/api/applications/export.csv"]'),null);
    assert.equal(document.querySelectorAll(".an-metric").length,5);
    if(tab==="overview")assert.equal(document.querySelectorAll(".an-overview-charts>.an-grid>.an-panel").length,4);
    if(tab==="outcomes")assert.equal(document.querySelectorAll(".an-outcomes>.an-column-stack>.an-panel").length,4);
    const card=[...document.querySelectorAll(".an-metric")].find(node=>node.querySelector(".an-metric-label").textContent==="Interview invitations");
    assert.equal(card.querySelector("strong").textContent,"3");
  });
}

test("interview headline counts recognized invitation emails even with zero verified application stages",()=>{
  for(const [invites,stages] of [[1,0],[0,2],[3,1]])for(const tab of ["overview","outcomes"]){
    const d={...base,days:"custom",start:"2026-10-01",end:"2026-10-26",family:"ML_ENGINEERING",interviews:stages,
      classified_email_evidence:{...classifiedEvidence,categories:{...classifiedEvidence.categories,interview:invites}}};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab,query:{company:"Wayfern"}})));
    const card=[...document.querySelectorAll(".an-metric")].find(node=>node.querySelector(".an-metric-label").textContent==="Interview invitations");
    assert.equal(card.querySelector("strong").textContent,String(invites));
    assert.equal(card.querySelector("p").textContent,"Invitation emails by receipt date");
    const target=new URL(card.getAttribute("href"),"https://fixture.test");
    assert.equal(target.pathname,"/app/applications/analytics");
    assert.deepEqual(Object.fromEntries(target.searchParams),{days:"custom",tz:"America/Los_Angeles",start:"2026-10-01",end:"2026-10-26",family:"ML_ENGINEERING",emails:"1",email_kind:"interview",company:"Wayfern"});
    assert.equal(document.querySelector(".an-audit-note"),null);
    assert.match(card.querySelector(".an-trend-missing").title,new RegExp(`Verified application interview stages: ${stages}`));
    assert.match(card.querySelector(".an-trend-missing").title,/Invitation emails use receipt dates and do not assign an application stage/);
  }
});

test("missing interview email projection is unavailable rather than a fabricated zero or stage fallback",()=>{
  for(const evidence of [undefined,{...classifiedEvidence,categories:{rejection:6}}]){
    const d={...base,interviews:2,classified_email_evidence:evidence};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(ApplicationMetrics,{d})));
    const card=[...document.querySelectorAll(".an-metric")].find(node=>node.querySelector(".an-metric-label").textContent==="Interview invitations");
    assert.equal(card.querySelector("strong").textContent,"Unavailable");
  }
});

test("unlinked, unverified and lifecycle email categories cannot inflate the 30-day outcome groups",()=>{
  for(const evidence of [classifiedEvidence,{...classifiedEvidence,unverified_source_messages:3,linked_messages:0,company_messages:19,unlinked_messages:0},{...classifiedEvidence,categories:{...classifiedEvidence.categories,application_confirmation:4,assessment_completed:2,interview_cancelled:1,status_update:3}}]){
    const d={...base,cohort:{...base.cohort,eligible:11,positive:2,rejected:3,pending:4,unknown:2},classified_email_evidence:evidence};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"outcomes",query:{}})));
    assert.deepEqual([...document.querySelectorAll(".an-cohort-metrics strong")].map(node=>node.textContent),["11","5","4"]);
    assert.equal(document.querySelector(".an-donut strong").textContent,"11");
    assert.equal(document.querySelector(".an-classified-email-evidence"),null);
    assert.doesNotMatch(document.querySelector(".an-cohort-metrics").textContent,/response rate|47%/);
  }
});

test("email drilldowns preserve original report dates while the shared projection applies receipt scope",()=>{
  for(const days of ["14","30","90","all","custom"]){
    const d={...base,days,start:"2026-05-01",family:"ML_ENGINEERING",classified_email_evidence:{...classifiedEvidence,start:"2026-07-01",end:"2026-10-26"}};
    const destination=new URL(emailRecordsHref(d,{email_kind:"interview",company:"Silverpine & Rose"}),"https://fixture.example");
    assert.equal(destination.pathname,"/app/applications/analytics");
    for(const [key,value] of Object.entries({emails:"1",email_kind:"interview",days,tz:"America/Los_Angeles",family:"ML_ENGINEERING",company:"Silverpine & Rose"}))assert.equal(destination.searchParams.get(key),value,key);
    assert.equal(destination.searchParams.get("start"),days==="all"?null:"2026-05-01");
    assert.equal(destination.searchParams.get("end"),days==="all"?null:d.end);
    assert.equal(destination.searchParams.has("evidence"),false,"recognized meaning never requests an application-stage filter");
  }
});

test("email records distinguish verified links, company evidence and recognized unlinked history",()=>{
  const d={...base,classified_email_evidence:{...classifiedEvidence,start:"2026-07-01",end:"2026-10-26"},email_total:3,email_offset:0,email_limit:25,email_records:[
    {id:701,classification:"interview",decision:"classified_action",received_at:"2026-09-12T06:30:00Z",application_key:null,company:null,subject:"A conversation about the engineering role"},
    {id:702,classification:"rejection",decision:"company_rejection",received_at:"2026-10-01T17:00:00Z",application_key:null,company:"Silverpine Labs",subject:"Application update"},
    {id:703,classification:"online_assessment",decision:"manual",received_at:"2026-10-02T17:00:00Z",application_key:"job:803",company:"Silverpine Labs",subject:"Your assessment invitation"},
  ]};
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(CorrespondenceRecords,{d,query:{emails:"1",days:"all",tz:base.timezone}})));
  const rows=[...document.querySelectorAll(".an-record-row")];
  assert.equal(rows.length,3);
  assert.match(rows[0].textContent,/Interview.*Sep 11, 2026.*No verified application link/);
  assert.match(rows[1].textContent,/Silverpine Labs.*Company evidence; role not assigned/);
  assert.match(rows[2].textContent,/Verified application link/);
  assert.equal(rows[0].querySelector('a[href^="/app/jobs/"]'),null);
  assert.equal(rows[1].querySelector('a[href^="/app/jobs/"]'),null);
  assert.ok(rows[2].querySelector('a[href="/app/jobs/803"]'));
  for(const id of [701,702,703])assert.ok(document.querySelector(`a[href="/app/applications/inbox?message=${id}"]`));
  assert.match(document.querySelector("h1").nextElementSibling.textContent,/3 distinct effective emails.*Receipt dates 2026-07-01 to 2026-10-26/);
  assert.match(document.querySelector(".an-foot").textContent,/later rejection preserves earlier valid assessment and interview history/);
  assert.equal(document.querySelector('th[data-label="Current status"]'),null);
});

test("email pagination and search preserve classification and receipt-date filters",()=>{
  const query={emails:"1",email_kind:"rejection",email_scope:"company",days:"custom",start:"2026-09-01",end:"2026-09-30",tz:base.timezone,company:"Silverpine Labs",q:"application update",limit:"25"};
  const d={...base,email_total:31,email_offset:0,email_limit:25,email_records:[],classified_email_evidence:{...classifiedEvidence,start:query.start,end:query.end}};
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(CorrespondenceRecords,{d,query})));
  const next=[...document.querySelectorAll("a")].find(link=>link.textContent==="Next emails");
  const destination=new URL(next.getAttribute("href"),"https://fixture.example");
  for(const [key,value] of Object.entries({...query,offset:"25"}))assert.equal(destination.searchParams.get(key),value,key);
  const form=document.querySelector('form[role="search"]');
  for(const key of ["emails","email_kind","email_scope","start","end","tz","company"])assert.equal(form.querySelector(`input[name="${key}"]`).getAttribute("value"),query[key]);
  assert.equal(form.querySelector('input[name="q"]').getAttribute("value"),query.q);
  assert.equal(form.querySelector('input[name="offset"]'),null,"search restarts pagination");
  const allTime=[...document.querySelectorAll("a")].find(link=>link.textContent==="All time");
  const allUrl=new URL(allTime.getAttribute("href"),"https://fixture.example");
  assert.equal(allUrl.searchParams.get("days"),"all");
  assert.equal(allUrl.searchParams.has("start"),false);
  assert.equal(allUrl.searchParams.has("end"),false);
  assert.equal(allUrl.searchParams.get("email_kind"),"rejection");
  assert.equal(allUrl.searchParams.get("email_scope"),"company");
});

test("returning from email evidence retains the application cohort instead of its July receipt floor",()=>{
  for(const query of [{emails:"1",email_kind:"interview",days:"all",tz:base.timezone},{emails:"1",email_kind:"interview",days:"custom",start:"2026-05-01",end:"2026-10-26",tz:base.timezone}]){
    const d={...base,email_total:0,email_offset:0,email_limit:50,email_records:[],classified_email_evidence:{...classifiedEvidence,start:"2026-07-01",end:"2026-10-26"}};
    const {document}=parseHTML(renderToStaticMarkup(React.createElement(CorrespondenceRecords,{d,query})));
    const back=[...document.querySelectorAll("a")].find(link=>link.textContent==="Back to Analytics");
    const destination=new URL(back.getAttribute("href"),"https://fixture.example");
    assert.equal(destination.searchParams.get("days"),query.days);
    assert.equal(destination.searchParams.get("start"),query.start??null);
    assert.equal(destination.searchParams.get("end"),query.end??null);
    assert.equal(destination.searchParams.has("email_kind"),false);
    assert.match(document.querySelector("h1").nextElementSibling.textContent,/Receipt dates 2026-07-01 to 2026-10-26/);
    assert.match(document.querySelector(".an-record-pagination").textContent,/0 emails/);
  }
});


test("Inbox workflow uses verified links and confirmed evidence, never company-only identity",()=>{
  const connected={connected:true,state:"ready",available:true,last_synced_at:"2026-10-26T17:00:00Z"};
  const renderBand=d=>parseHTML(renderToStaticMarkup(React.createElement(InboxBand,{d,connection:connected,expanded:true}))).document;
  const linked=renderBand({...base,classified_email_evidence:{linked_messages:2}});
  assert.equal(linked.querySelectorAll(".an-step-recorded").length,4);
  assert.match(linked.querySelector(".an-inbox-workflow").textContent,/Finds applications.*Confirms responses.*Links to your records/);
  const unlinked=renderBand({...base,evidence:{manual:0,automatic:0},classified_email_evidence:{linked_messages:0,company_messages:4}});
  assert.equal(unlinked.querySelectorAll(".an-step-recorded").length,1);
  assert.match(unlinked.querySelector(".an-inbox-workflow").textContent,/No verified matches.*Not recorded.*No verified links/);
  assert.match(unlinked.querySelector(".an-band-coverage").textContent,/Not verified.*Check in Inbox/);
});

test("Gmail coverage displays only checked consistent job-mail evidence and labels emails",()=>{
  const coverage={days:30,scope:"job_mail",gmail:40,in_ace:36,missing:4,complete:true,checked_at:"2026-10-26T17:00:00Z"};
  const band=extra=>parseHTML(renderToStaticMarkup(React.createElement(InboxBand,{d:base,connection:{connected:true,state:"ready",available:true,last_synced_at:coverage.checked_at,coverage:{...coverage,...extra}},expanded:true}))).document.querySelector(".an-band-coverage");
  assert.match(band({}).textContent,/90%.*36 of 40 emails/);
  assert.match(band({}).title,/separate from application filters/);
  assert.doesNotMatch(band({}).textContent,/applications/);
  for(const extra of [{complete:false},{scope:"all"},{checked_at:"invalid"},{checked_at:"2026-10-27T18:00:00Z"},{in_ace:41},{missing:3},{gmail:-1}])assert.match(band(extra).textContent,/Not verified/);
  assert.match(band({gmail:0,in_ace:0,missing:0}).textContent,/No emails.*0 of 0 emails/);
});

test("weekly context uses real comparisons and the peak day without inventing a zero-base percentage",()=>{
  const counts={"2026-10-12":1,"2026-10-19":2,"2026-10-21":1};
  const renderWeek=weeklyCounts=>parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d:base,connection:null,tab:"overview",query:{week:"2026-10-19"},supplement:{weeklyCounts,timeline:[],interval:"daily",weekToday:"2026-10-26",weekStart:"2026-10-19",week:[],weekTrend:null}}))).document.querySelector(".an-week-context").textContent;
  assert.match(renderWeek(counts),/3 applications in this week, a 200% increase from the previous week. Most active on Monday, with 2 submissions/);
  assert.match(renderWeek({"2026-10-19":2}),/No prior-week activity to compare/);
  assert.doesNotMatch(renderWeek({"2026-10-19":2}),/%/);
});


test("the 30-day partition, meaningful metric cards and donut use the same exact denominator",()=>{
  const d={...base,cohort:{...base.cohort,eligible:11,positive:3,rejected:2,pending:4,unknown:2}};
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"outcomes",query:{}})));
  assert.deepEqual([...document.querySelectorAll(".an-cohort-metrics strong")].map(node=>node.textContent),["11","5","4"]);
  assert.deepEqual([...document.querySelectorAll(".an-partition-key span")].map(node=>node.textContent),["3 (27%)","2 (18%)","4 (36%)","2 (18%)"]);
  assert.equal(document.querySelector(".an-donut strong").textContent,"11");
  assert.match(document.querySelector(".an-donut").getAttribute("style"),/#aaa2b0/);
  assert.match(document.querySelector(".an-window").textContent,/30-day observation window/);
  assert.match(document.querySelector(".an-cohort-panel .an-info").getAttribute("aria-label"),/selected period and role.*Undated applications are excluded/);
  const underlying=new URL(document.querySelector(".an-outcome-evidence .an-jump").getAttribute("href"),"https://fixture.test");
  assert.equal(underlying.searchParams.get("eligible"),"1");
});

test("an empty age-qualified selection is explained while timing retains its separate real sample",()=>{
  const d={...base,median_days:2.5,timing_sample:4,timing:[{label:"0 to 7 days",count:4},{label:"8 to 14 days",count:0},{label:"15 to 30 days",count:0},{label:"30+ days",count:0}]};
  const {document}=parseHTML(renderToStaticMarkup(React.createElement(AnalyticsView,{d,connection:null,tab:"outcomes",query:{}})));
  assert.match(document.querySelector(".an-cohort-empty").textContent,/No applications in this selection are 30 days old yet/);
  assert.equal(document.querySelector(".an-cohort-strip"),null);
  assert.match(document.querySelector(".an-timing-context").textContent,/Median 2.5 days.*4 dated applications/);
  assert.equal(document.querySelectorAll(".an-timing-panel .an-column").length,4);
  assert.match(document.querySelector(".an-timing-panel .an-info").getAttribute("aria-label"),/including those under 30 days old/);
});
