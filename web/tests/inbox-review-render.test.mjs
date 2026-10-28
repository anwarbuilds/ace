// Render the actual review component with fictional props, without Chrome.
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
    if (name.startsWith(".")) return createRequire(filename)(name);
    if (!name.startsWith("@/")) return nodeRequire(name);
    const base = path.join(sourceRoot, name.slice(2));
    const found = [base + ".ts", base + ".tsx"].find(fs.existsSync);
    assert.ok(found, `Missing source module ${name}`);
    return loadSource(found);
  };
  vm.runInThisContext(Module.wrap(output), { filename })(loadedModule.exports, sourceRequire, loadedModule, filename, path.dirname(filename));
  return loadedModule.exports;
}

const { InboxReviewPanel, senderParts, since, likelyApplications, applicationFromEmail } = loadSource(path.join(sourceRoot, "components/inbox/InboxReviewPanel.tsx"));
const message = { id: 1, received_at: "2026-01-01T12:00:00Z", sender: "Fictional Talent <fixture@example.test>", subject: "Fictional interview", snippet: "Fictional interview invitation", classification: "interview", requisition_id: "FIX-1", decision: "review", candidate_keys: ["job:1"], reason: "Matched by its job ID; positive outcomes need your confirmation", selected_application_key: null };
const applications = [{ key: "job:1", company: "Fictional Labs", title: "Fictional engineer", requisition_id: "FIX-1", applied_at: "2025-12-01T12:00:00Z", status: "applied" }];
function render(selected = message, apps = applications, events = []) {
  return renderToStaticMarkup(React.createElement(InboxReviewPanel, { message: selected, applications: apps, events, busy: false, action: async () => { throw Error("Rendering must not mutate"); } }));
}
// A one-click choice: its label, its hint and, when suggested, ACE's reading.
const choice = (html, label) => html.match(new RegExp(`<button[^>]*><strong>${label}</strong>[\\s\\S]*?</button>`))?.[0] ?? "";
const CHANGES = ["Rejection", "Assessment", "Recruiter reply", "Interview", "Offer"];
const FILINGS = ["Acknowledgement", "Status update", "Not about my applications"];

for (const decision of ["review", "exact_preview", "deferred"]) {
  test(`${decision}: ACE's likeliest application is chosen and each outcome is one click`, () => {
    const html = render({ ...message, decision });
    assert.match(html, /ACE thinks this is about/);
    assert.match(html, /Fictional Labs/);
    assert.match(html, /Loading the email from Gmail/);
    assert.match(html, /Fictional interview invitation/);
    assert.match(html, /<strong>Fictional Talent<\/strong>/);
    assert.match(html, /&lt;fixture@example.test&gt;/);
    assert.match(html, /Why it waits: Matched by its job ID/);
    for (const label of [...CHANGES, ...FILINGS]) {
      assert.ok(choice(html, label), `${label} choice`);
      assert.doesNotMatch(choice(html, label), /disabled/);
    }
    assert.match(choice(html, "Interview"), /class="inbox-choice suggested"/);
    assert.match(choice(html, "Interview"), /ACE.s reading/);
    assert.doesNotMatch(choice(html, "Rejection"), /suggested/);
    assert.equal(Boolean(choice(html, "Decide later")), decision !== "deferred");
    assert.doesNotMatch(html, /type="checkbox"/);
  });
}

test("a rejection ACE was unsure about suggests Rejection", () => {
  const html = render({ ...message, classification: "possible_rejection" });
  assert.match(html, /Possible rejection/);
  assert.match(choice(html, "Rejection"), /suggested/);
});

test("without a likely application the outcome buttons wait for a choice", () => {
  const html = render({ ...message, candidate_keys: [] });
  assert.match(html, /Which application\?/);
  assert.match(html, /Search company, role or job ID/);
  assert.match(choice(html, "Rejection"), /disabled/);
  assert.match(html, /Choose the application above, or add it from this email/);
  assert.doesNotMatch(choice(html, "Not about my applications"), /disabled/);
});

test("an email ACE found nothing in can still be decided by hand", () => {
  const html = render({ ...message, decision: "ignored", classification: "unknown" });
  assert.match(html, /Nothing recorded/);
  assert.match(html, /ACE found no application outcome in it\./);
  assert.ok(choice(html, "Rejection"));
  assert.ok(!choice(html, "Decide later"));
});

test("a filed acknowledgement says so and can be changed", () => {
  const html = render({ ...message, decision: "receipt", classification: "application_confirmation" });
  assert.match(html, /Filed as an acknowledgement\./);
  assert.match(choice(html, "Acknowledgement"), /disabled/);
  assert.match(choice(html, "Acknowledgement"), /suggested/);
  assert.doesNotMatch(choice(html, "Status update"), /disabled/);
});

test("a recognized unlinked outcome explains its evidence without asking for a decision", () => {
  const html = render({
    ...message,
    classification: "rejection",
    decision: "unlinked",
    candidate_keys: [],
    reason: "This authenticated rejection predates every recorded application at this employer.",
    understanding: {
      decision_type: "Automatic classification",
      classification_reason: "The employer communicates a rejection.",
      classification_state: "recognized",
      matching_state: "unlinked",
      workflow_state: "unlinked_outcome",
      update_policy: "no_status_change",
      review_reason: null,
      evidence_source: "retained_excerpt",
      evidence_excerpt: "We will not move forward with your application.",
    },
  });
  assert.match(html, /Recognized, unlinked/);
  assert.match(html, /ACE.s classification: Rejection/);
  assert.match(html, /Application linkage: unlinked\. No application status changed\./);
  assert.match(html, /No eligible application existed in ACE when this email arrived/);
  assert.match(html, /No application outcome was recorded\. Linking is optional; the email remains searchable/);
  assert.match(html, /predates every recorded application at this employer/);
  assert.match(choice(html, "Rejection"), /disabled/);
  assert.match(choice(html, "Rejection"), /suggested/);
  assert.doesNotMatch(html, /Needs you|Why it waits:|Decision needed:|Undo this change|ACE recorded this email/);
  assert.ok(!choice(html, "Decide later"));
});

test("a recorded email offers Undo instead of outcome buttons", () => {
  const recorded = { ...message, decision: "automatic", classification: "rejection", selected_application_key: "job:1", reason: "Clear rejection matched by its job ID" };
  const events = [{ id: 7, application_key: "job:1", kind: "rejection", before: "applied", after: "rejected", actor: "verified_automation", reason: "fixture", recorded_at: "2026-01-02T00:00:00Z", undo_of_id: null, gmail_message_id: 1 }];
  const html = render(recorded, applications, events);
  assert.match(html, /ACE recorded this email/);
  assert.match(html, /Recorded by ACE/);
  assert.match(html, /Undo this change/);
  assert.ok(!choice(html, "Rejection"));
  const undone = render(recorded, applications, [...events, { ...events[0], id: 8, kind: "undo", undo_of_id: 7 }]);
  assert.match(undone, /Undo it from Audit trail/);
});

test("company rejection evidence uses its scoped event and needs no application choice",()=>{
  const recorded={...message,classification:"rejection",decision:"company_rejection",selected_application_key:null,
    candidate_keys:["job:1","job:2"],reason:"Company rejection recorded; the email does not need a role-level application match",
    understanding:{decision_type:"Automatic classification",classification_reason:"The employer communicates a rejection.",classification_state:"recognized",matching_state:"company",workflow_state:"company_recorded",update_policy:"company_recorded",review_reason:null,evidence_source:"retained_excerpt",evidence_excerpt:"We will not move forward."}};
  const event={id:77,application_key:"email:1",gmail_message_id:1,kind:"company_rejection",before:null,after:null,actor:"verified_automation",reason:"Rejection received from Fictional Labs; no individual application changed",recorded_at:"2026-01-02T00:00:00Z",undo_of_id:null,scope:"company",company:"Fictional Labs"};
  const html=render(recorded,applications,[event]);
  assert.match(html,/Company rejection recorded/);
  assert.match(html,/ACE recorded the company rejection/);
  assert.match(html,/Fictional Labs: rejection received\. No role choice is needed/);
  assert.match(html,/Application linkage: company\. A company rejection was recorded\. No role choice is needed/);
  assert.match(html,/Undo this change/);
  assert.doesNotMatch(html,/Which application\?|Search your applications|Changes the application|Why it waits:|Needs you/);
  assert.ok(!choice(html,"Rejection"));
  assert.ok(!choice(html,"Decide later"));
  const undone=render(recorded,applications,[event,{...event,id:78,kind:"undo",actor:"owner",undo_of_id:77}]);
  assert.doesNotMatch(undone,/Undo this change/);
});

test("drawn rules and dashes in the email excerpt are not shown", () => {
  const html = render({ ...message, snippet: "Hello\n-----\nTeam \u2014 Fictional Labs" });
  assert.doesNotMatch(html, /-----|\u2014/);
});

test("empty selection explains how to begin", () => {
  assert.match(render(null), /Choose an email on the left/);
});

test("sender names, addresses and relative times read plainly", () => {
  assert.deepEqual(senderParts('"Fictional Talent" <talent@example.test>'), { name: "Fictional Talent", address: "talent@example.test" });
  assert.deepEqual(senderParts("talent@example.test"), { name: "talent@example.test", address: "talent@example.test" });
  const now = Date.parse("2026-01-01T12:00:00Z");
  assert.equal(since("2026-01-01T11:59:40Z", now), "just now");
  assert.equal(since("2026-01-01T11:57:00Z", now), "3 minutes ago");
  assert.equal(since("2026-01-01T10:00:00Z", now), "2 hours ago");
  assert.equal(since("2025-12-30T12:00:00Z", now), "2 days ago");
  assert.equal(since("2026-01-01T11:57:00Z", 0), "");
});

test("when ACE could not tell, the sender and subject suggest applications without typing", () => {
  const apps = [
    { key: "job:7", company: "General Motors", title: "Software Engineer", requisition_id: null, applied_at: "2026-10-01T12:00:00Z", status: "applied" },
    { key: "job:8", company: "Greenheck Group", title: "Application Developer II", requisition_id: null, applied_at: "2026-10-01T12:00:00Z", status: "applied" },
    { key: "job:9", company: "Fictional Labs", title: "Software Engineer", requisition_id: null, applied_at: "2026-10-01T12:00:00Z", status: "applied" },
  ];
  const workday = { ...message, sender: "generalmotors@myworkday.com", subject: "Your interest in Software Engineer at GM", snippet: "Thank you for your interest.", candidate_keys: [] };
  assert.deepEqual(likelyApplications(workday, apps).map(a => a.key), ["job:7"]);
  assert.deepEqual(likelyApplications({ ...workday, sender: "greenheckgroup@myworkday.com", subject: "Application Received for Application Developer II" }, apps).map(a => a.key), ["job:8"]);
  assert.deepEqual(likelyApplications({ ...workday, sender: "Talent <no-reply@us.greenhouse-mail.io>", subject: "Your application" }, apps), []);
  const html = render(workday, apps);
  assert.match(html, /Possible matches from the sender and subject/);
  assert.match(html, /General Motors/);
  assert.doesNotMatch(html, /Greenheck Group/);
  assert.match(choice(html, "Rejection"), /disabled/);
  assert.doesNotMatch(html, /&lt;generalmotors@myworkday.com&gt;/);
});

test("an application missing from ACE can be added from the email, prefilled from what it says", () => {
  const cir = { ...message, sender: "cir@myworkday.com", subject: "Thank you for your interest!", classification: "rejection", candidate_keys: [] };
  const text = "Thank you for your interest in a role with Cambridge. We have found ourselves in the fortunate position of having a wide range of qualified candidates. After reviewing your application for the Full Stack Software Engineer , we've made the decision to move forward with other candidates at this time.";
  assert.deepEqual(applicationFromEmail(cir, text), { company: "Cambridge", title: "Full Stack Software Engineer" });
  const relx = { ...cir, sender: "relx@myworkday.com", subject: "Thank you for your interest, Software Engineer II" };
  assert.deepEqual(applicationFromEmail(relx, "We appreciate the time you took."), { company: "RELX", title: "Software Engineer II" });
  assert.deepEqual(applicationFromEmail({ ...cir, sender: "generalmotors@myworkday.com", subject: "Your interest in Software Engineer at GM" }, "Hello."), { company: "Generalmotors", title: "Software Engineer" });
  const html = render(cir, []);
  assert.match(html, /Not in ACE yet\? Add it from this email/);
  assert.match(html, /or add it from this email, to record an outcome/);
  assert.match(choice(html, "Rejection"), /disabled/);
});

test("the email text and initials tenants suggest the stored application", () => {
  const apps = [
    { key: "job:31", company: "Cambridge Investment Research", title: "Full Stack Software Engineer", requisition_id: null, applied_at: "2026-10-01T12:00:00Z", status: "applied" },
    { key: "job:32", company: "Global Fiction", title: "Software Engineer", requisition_id: null, applied_at: "2026-10-01T12:00:00Z", status: "applied" },
  ];
  const cir = { ...message, sender: "cir@myworkday.com", subject: "Thank you for your interest!", snippet: "Thank you for your interest.", candidate_keys: [] };
  assert.deepEqual(likelyApplications(cir, apps).map(a => a.key), ["job:31"]);
  const other = { ...cir, sender: "Talent <no-reply@us.greenhouse-mail.io>" };
  assert.deepEqual(likelyApplications(other, apps, "Thank you for your interest in a role with Cambridge.").map(a => a.key), ["job:31"]);
  assert.deepEqual(likelyApplications(other, apps, "A global team of fictional people."), []);
});


const { companyNamed, confirmCompany } = loadSource(path.join(sourceRoot, "components/inbox/InboxReviewPanel.tsx"));
const { coverageText, verifyInbox } = loadSource(path.join(sourceRoot, "lib/inboxSync.ts"));

test("unclear recruiting mail is labeled Application correspondence and stays actionable", () => {
  const html = render({...message, classification:"unclear"});
  assert.match(html, /Application correspondence/);
  assert.doesNotMatch(choice(html,"Rejection"), /disabled/);
});

test("an absent company warns before any outcome is recorded and requires a deliberate override", () => {
  const html = render(message);
  assert.match(html, /This email does not name Fictional Labs/);
  let prompts=0;
  const confirm=warning=>{prompts++;assert.match(warning,/Record it for Fictional Labs anyway/);return false;};
  assert.equal(confirmCompany(message,"Fictional Labs","",confirm),false);
  assert.equal(prompts,1);
  assert.equal(confirmCompany(message,"Fictional Labs","",()=>true),true);
  assert.equal(confirmCompany(message,"Fictional Labs","Thank you for applying to Fictional Labs.",()=>{throw Error("Named employer needs no extra confirmation");}),true);
});

test("company warning recognizes squashed names, initials and exact Workday tenants", () => {
  assert.equal(companyNamed({...message,sender:"fictionallabs@myworkday.com"},"Fictional Labs"),true);
  assert.equal(companyNamed({...message,subject:"FL application update"},"Fictional Labs"),true);
  assert.equal(companyNamed({...message,subject:"An update"},"Imaginary Systems","IS Application Update"),true);
  assert.equal(companyNamed({...message,subject:"An update"},"Imaginary Systems","This is an application update."),false);
  assert.equal(companyNamed({...message,sender:"frr@myworkday.com"},"Fictional Robotics Research"),true);
  assert.equal(companyNamed(message,"Imaginary Systems"),false);
});

const coverage=(missing=0,complete=true)=>({days:90,scope:"job_mail",includes_spam_trash:false,gmail:125,in_ace:125-missing,missing,complete,checked_at:"2026-10-26T12:00:00Z"});
test("coverage copy never calls an unverified or partial listing complete", () => {
  assert.match(coverageText(null),/has not been verified/);
  assert.match(coverageText(coverage()),/Gmail has 125 job-mail search candidates from the last 90 days. All are in ACE/);
  assert.match(coverageText(coverage(65)),/65 are not in ACE yet/);
  assert.match(coverageText(coverage(0,false)),/listing is incomplete/);
  assert.doesNotMatch(coverageText(coverage(0,false)),/All are in ACE/);
});

test("verification loops until every email is saved and automatically rechecks old evidence", async () => {
  const calls=[],progress=[];
  const replies=[
    {state:"ready",counts:{ignored:60},remaining:65,partial:true,coverage:coverage(65)},
    {state:"ready",counts:{review:60},remaining:5,partial:true,coverage:coverage(5)},
    {state:"ready",counts:{automatic:5},remaining:0,partial:false,coverage:coverage()},
    {checked:25,remaining:2,counts:{automatic:4,review:21}},
    {checked:2,remaining:0,counts:{review:2}},
  ];
  const result=await verifyInbox({days:90,stale:27,post:async(path,body)=>{calls.push({path,body});return replies.shift();},progress:note=>progress.push(note)});
  assert.equal(calls.length,5);
  assert.deepEqual(calls.slice(0,3).map(c=>c.body),[{days:90},{days:90},{days:90}]);
  assert.deepEqual(calls.slice(3).map(c=>c.path),["/api/inbox/recheck","/api/inbox/recheck"]);
  assert.deepEqual(result,{counts:{ignored:60,review:60,automatic:5},rechecked:27,recorded:4});
  assert.match(progress[0],/60 of 125 emails in ACE/);
});

test("quota failure propagates after saved progress without claiming success", async () => {
  let calls=0;
  const failure=Error("Fictional quota");
  await assert.rejects(verifyInbox({days:90,stale:2,post:async()=>{if(calls++)throw failure;return {state:"ready",counts:{ignored:60},remaining:65,partial:true,coverage:coverage(65)};},progress:()=>{}}),error=>error===failure);
  assert.equal(calls,2);
});

test("busy, paused, incomplete listing, cancellation and stalled recheck never finish as success", async () => {
  for(const state of ["busy","paused"]){
    let calls=0;
    await assert.rejects(verifyInbox({days:30,stale:0,post:async()=>{calls++;return {state};},progress:()=>{}}),/running|paused/);
    assert.equal(calls,1);
  }
  await assert.rejects(verifyInbox({days:90,stale:0,post:async()=>({state:"ready",counts:{},remaining:0,partial:true,coverage:coverage(0,false)}),progress:()=>{}}),/listing could not finish/);
  await assert.rejects(verifyInbox({days:90,stale:0,active:()=>false,post:()=>{throw Error("Must not send after leaving");},progress:()=>{}}),/stopped/);
  let calls=0;
  await assert.rejects(verifyInbox({days:90,stale:2,post:async()=>calls++?{checked:0,remaining:2,counts:{}}:{state:"ready",counts:{},remaining:0,partial:false,coverage:coverage()},progress:()=>{}}),/could not finish rechecking/);
});


test("full history continues through zero-pending listing/history phases and discloses its scope",async()=>{
  const full={...coverage(),days:0,scope:"job_mail",includes_spam_trash:false};
  const replies=[
    {state:"ready",counts:{},remaining:0,more:true,partial:true,coverage:{...full,complete:false,phase:"listing"}},
    {state:"ready",counts:{},remaining:0,more:true,partial:true,coverage:{...full,complete:false,phase:"history"}},
    {state:"ready",counts:{},remaining:0,more:false,partial:false,coverage:{...full,complete:true,phase:"complete"}},
  ];
  const calls=[];
  await verifyInbox({days:0,stale:0,post:async(path,body)=>{calls.push(body);return path==="/api/inbox/recheck"?{checked:0,remaining:0,counts:{}}:replies.shift();},progress:()=>{}});
  assert.deepEqual(calls,[{days:0},{days:0},{days:0},{limit:25}]);
  assert.match(coverageText(full),/job-mail search across all dates/);
  assert.match(coverageText(full),/Permanently deleted mail is unavailable/);
  assert.doesNotMatch(coverageText({...full,complete:false}),/All are in ACE/);
  await assert.rejects(verifyInbox({days:0,stale:0,post:async()=>({state:"ready",counts:{},remaining:0,partial:false,coverage:coverage()}),progress:()=>{}}),/different history selection/);
});



test("rechecks stop when the owner pauses or changes the Gmail connection",async()=>{
  for(const state of ["paused","disconnected"]){
    await assert.rejects(verifyInbox({days:90,stale:1,post:async path=>path==="/api/inbox/sync"?{state:"ready",counts:{},remaining:0,partial:false,coverage:coverage()}:{state,checked:1,remaining:1,counts:{}},progress:()=>{}}),/connection was paused or changed/);
  }
});


test("a pending scope cannot masquerade as a completed zero-remaining recheck",async()=>{
  const full={...coverage(),days:0,scope:"job_mail",includes_spam_trash:false};
  await assert.rejects(verifyInbox({days:0,stale:0,post:async path=>path==="/api/inbox/sync"?
    {state:"ready",counts:{},remaining:0,partial:false,coverage:full}:
    {checked:0,remaining:0,scope_pending:true,counts:{}},progress:()=>{}}),/scope needs verification/);
  assert.match(coverageText(full),/Search terms may miss some job mail/);
});

test("classification, linkage and permission are explained separately", () => {
  const html = render({...message,understanding:{classification_reason:"The employer requests a hiring assessment.",classification_state:"recognized",matching_state:"ambiguous",workflow_state:"awaiting_link",update_policy:"confirmation_required",review_reason:"Two applications share this requisition.",evidence_source:"retained_excerpt",evidence_excerpt:"Please complete the coding challenge."}});
  assert.match(html,/ACE understanding/);
  assert.match(html,/The employer requests a hiring assessment/);
  assert.match(html,/Application linkage: ambiguous/);
  assert.match(html,/Decision needed: Two applications share this requisition/);
  assert.match(html,/No status change is authorized/);
});


test("ambiguous and unverified employer identities require an explicit application choice",()=>{
  for(const matching_state of ["ambiguous","identity_uncertain"]){
    const html=render({...message,understanding:{classification_reason:"The email communicates a rejection.",classification_state:"recognized",matching_state,workflow_state:"owner_review",update_policy:"confirmation_required",review_reason:"Choose the actual employer application.",evidence_source:"retained_excerpt",evidence_excerpt:"Fictional evidence"}});
    assert.match(choice(html,"Rejection"),/disabled/);
    assert.match(html,/Which application/);
    assert.doesNotMatch(html,/ACE thinks this is about/);
  }
});
