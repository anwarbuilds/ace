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

const { InboxReviewPanel } = loadSource(path.join(sourceRoot, "components/inbox/InboxReviewPanel.tsx"));
const message = { id: 1, received_at: "2026-01-01T12:00:00Z", sender: "fixture@example.test", subject: "Fictional interview", snippet: "Fictional interview invitation", classification: "interview", requisition_id: "FIX-1", decision: "review", candidate_keys: ["job:1"], reason: "Matched by its job ID; positive outcomes need your confirmation", selected_application_key: null };
const applications = [{ key: "job:1", company: "Fictional Labs", title: "Fictional engineer", requisition_id: "FIX-1", applied_at: "2025-12-01T12:00:00Z", status: "applied" }];
function render(selected = message, apps = applications, events = []) {
  return renderToStaticMarkup(React.createElement(InboxReviewPanel, { message: selected, applications: apps, events, busy: false, action: async () => { throw Error("Rendering must not mutate"); } }));
}
const button = (html, label) => html.match(new RegExp(`<button[^>]*>${label}</button>`))?.[0] ?? "";

for (const decision of ["review", "exact_preview", "deferred"]) {
  test(`${decision}: ACE's likeliest application is chosen and each outcome is one click`, () => {
    const html = render({ ...message, decision });
    assert.match(html, /ACE thinks this is about/);
    assert.match(html, /Fictional Labs/);
    assert.match(html, /Loading the full email/);
    assert.match(html, /Fictional interview invitation/);
    for (const label of ["Rejected", "Interview", "Assessment", "Offer", "Just a receipt", "Not about my applications"]) {
      assert.ok(button(html, label), `${label} button`);
      assert.doesNotMatch(button(html, label), /disabled/);
    }
    assert.match(button(html, "Interview"), /class="btn primary"/);
    assert.doesNotMatch(button(html, "Rejected"), /primary/);
    assert.equal(Boolean(button(html, "Decide later")), decision !== "deferred");
    assert.doesNotMatch(html, /type="checkbox"/);
  });
}

test("without a likely application the outcome buttons wait for a choice", () => {
  const html = render({ ...message, candidate_keys: [] });
  assert.match(html, /Which application\?/);
  assert.match(html, /Search company, role or job ID/);
  assert.match(button(html, "Rejected"), /disabled/);
  assert.match(html, /Choose the application first/);
  assert.doesNotMatch(button(html, "Not about my applications"), /disabled/);
});

test("an email ACE ignored can still be decided by hand", () => {
  const html = render({ ...message, decision: "ignored", classification: "unknown" });
  assert.match(html, /No recruiting outcome found/);
  assert.ok(button(html, "Rejected"));
});

test("a recorded email offers Undo instead of outcome buttons", () => {
  const recorded = { ...message, decision: "automatic", classification: "rejection", selected_application_key: "job:1", reason: "Clear rejection matched by its job ID" };
  const events = [{ id: 7, application_key: "job:1", kind: "rejection", before: "applied", after: "rejected", actor: "verified_automation", reason: "fixture", recorded_at: "2026-01-02T00:00:00Z", undo_of_id: null, gmail_message_id: 1 }];
  const html = render(recorded, applications, events);
  assert.match(html, /ACE recorded this email/);
  assert.match(html, /Undo this change/);
  assert.ok(!button(html, "Rejected"));
  const undone = render(recorded, applications, [...events, { ...events[0], id: 8, kind: "undo", undo_of_id: 7 }]);
  assert.match(undone, /Undo it from Audit trail/);
});

test("drawn rules and dashes in the email excerpt are not shown", () => {
  const html = render({ ...message, snippet: "Hello\n-----\nTeam — Fictional Labs" });
  assert.doesNotMatch(html, /-----|—/);
});

test("empty selection explains how to begin", () => {
  assert.match(render(null), /Choose an email on the left/);
});
