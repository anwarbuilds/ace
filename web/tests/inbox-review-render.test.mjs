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
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const sourceRequire = (name) => {
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
const message = { id: 1, received_at: "2026-01-01T12:00:00Z", sender: "fixture@example.test", subject: "Fictional interview", snippet: "Fictional interview invitation", classification: "interview", requisition_id: "FIX-1", decision: "review", candidate_keys: ["job:1"], reason: "Exact application needs confirmation", selected_application_key: null };
const applications = [{ key: "job:1", company: "Fictional Labs", title: "Fictional engineer", requisition_id: "FIX-1", applied_at: "2025-12-01T12:00:00Z", status: "applied" }];
function render(selected = message, apps = applications) {
  return renderToStaticMarkup(React.createElement(InboxReviewPanel, { message: selected, applications: apps, busy: false, action: async () => { throw Error("Rendering must not mutate"); }, showPending: () => {} }));
}

for (const decision of ["review", "exact_preview", "deferred"]) {
  test(`${decision}: renders explicit application and outcome choices without a rejection default`, () => {
    const html = render({ ...message, decision });
    assert.match(html, /1\. Choose the exact application/);
    assert.match(html, /2\. Choose what the email confirms/);
    assert.match(html, /Search your applications/);
    assert.match(html, /Fictional Labs/);
    assert.match(html, /<option value="" selected="">Choose an outcome after reading the email/);
    assert.doesNotMatch(html, /<option value="rejected" selected/);
    assert.match(html, /<button[^>]*disabled=""[^>]*>Confirm application outcome/);
    assert.match(html, /Not about an application/);
    assert.match(html, /Defer for later/);
  });
}

for (const decision of ["ignored", "manual", "automatic"]) {
  test(`${decision}: explains why no pending review form is shown`, () => {
    const html = render({ ...message, decision });
    assert.match(html, /It has no pending outcome to confirm/);
    assert.match(html, /Show messages awaiting review/);
    assert.doesNotMatch(html, /Confirm application outcome/);
  });
}

test("no application can be confirmed without a stored application choice", () => {
  const html = render(message, []);
  assert.match(html, /No applications match that search/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Confirm application outcome/);
});

test("empty selection explains how to begin", () => {
  assert.match(render(null), /Select a message on the left/);
});
