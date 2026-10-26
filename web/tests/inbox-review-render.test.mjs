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

const { InboxReviewPanel, senderParts, since, likelyApplications } = loadSource(path.join(sourceRoot, "components/inbox/InboxReviewPanel.tsx"));
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
  assert.match(html, /Choose the application first/);
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
  const workday = { ...message, sender: "generalmotors@myworkday.com", subject: "Your interest in Software Engineer at GM", candidate_keys: [] };
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
