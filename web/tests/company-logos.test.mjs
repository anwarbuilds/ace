// Actual React components, fictional employer records, no browser or services.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import Module, { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import ts from "typescript";
import React, { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRoot } from "react-dom/client";
import { parseHTML } from "linkedom";
const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL("../", import.meta.url));
const cache = new Map();
const evidenceQueries = [];
function load(filename) {
  if (cache.has(filename)) return cache.get(filename).exports;
  if (filename.endsWith(".json")) return JSON.parse(fs.readFileSync(filename,"utf8"));
  const mod = {exports:{}}; cache.set(filename,mod);
  const output = ts.transpileModule(fs.readFileSync(filename,"utf8"), {fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const localRequire = name => {
    if (name === "next/link") return {__esModule:true,default:({children,...props})=>{delete props.prefetch;return React.createElement("a",props,children);}};
    if (name === "@/lib/api") return {apiGetOr:async(...args)=>{evidenceQueries.push({path:args[0],params:args[2]});return {petition_history:[]};}};
    if (name === "@/components/shell/ScrollArea") return {ScrollArea:({children})=>React.createElement("div",null,children)};
    if (name.startsWith("@/") || name.startsWith(".")) {
      const base = name.startsWith("@/") ? path.join(root,"src",name.slice(2)) : path.resolve(path.dirname(filename),name);
      const found = [base,base+".ts",base+".tsx",base+".json"].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());
      assert.ok(found,`Missing source ${name}`);return load(found);
    }
    return require(name);
  };
  vm.runInThisContext(Module.wrap(output),{filename})(mod.exports,localRequire,mod,filename,path.dirname(filename));
  return mod.exports;
}
const { CompanyLogo } = load(path.join(root,"src/components/CompanyLogo.tsx"));
const { CompanyIdentity } = load(path.join(root,"src/components/CompanyIdentity.tsx"));
const { Avatar,CompanyCell } = load(path.join(root,"src/components/bits.tsx"));
const { companyLogoFor,normalizeCompanyIdentity } = load(path.join(root,"src/lib/companyLogos.ts"));
const manifest = JSON.parse(fs.readFileSync(path.join(root,"public/company-logos/provenance.json"),"utf8"));
const html = (Component,props) => renderToStaticMarkup(React.createElement(Component,props));

test("requested employers and reviewed legal variants resolve consistently",()=>{
  for(const [name,asset] of [["Apple","apple.ico"],[" APPLE, INC. ","apple.ico"],["FedEx Freight","fedex-freight.png"],["FedEx Freight, Inc.","fedex-freight.png"],["GM","general-motors.png"],["General Motors LLC","general-motors.png"],["Southern Company","southern-company.png"],["Hive","hive.ico"]]){
    assert.equal(companyLogoFor(name)?.asset,asset);assert.ok(html(CompanyLogo,{name}).includes(`/company-logos/${asset}`));
  }
});
test("similar names, unknown subsidiaries and prototype properties never borrow marks",()=>{
  for(const name of ["Applewood Fictional Labs","Not Apple","Apple Fictional Subsidiary","General Motorsports","FedEx Freight Services Fictional","Workday tenant: Apple","Fictional Hive Logistics","toString","__proto__",""]){
    assert.equal(companyLogoFor(name),undefined,name);assert.doesNotMatch(html(CompanyLogo,{name}),/src="\/company-logos\//);
  }
});
test("all identities are unambiguous and all local bytes match official provenance",()=>{
  const identities=new Map();
  for(const row of manifest){
    assert.match(row.source,/^https:\/\//);assert.match(row.asset,/^[a-z0-9-]+\.(ico|png|webp|jpg|gif)$/);
    assert.equal(createHash("sha256").update(fs.readFileSync(path.join(root,"public/company-logos",row.asset))).digest("hex"),row.sha256);
    for(const name of [row.company,...row.aliases]){
      const key=normalizeCompanyIdentity(name);assert.ok(!identities.has(key)||identities.get(key)===row.company,`Collision: ${name}`);
      identities.set(key,row.company);assert.equal(companyLogoFor(name)?.asset,row.asset);
    }
  }
  const files=fs.readdirSync(path.join(root,"public/company-logos")).filter(f=>/\.(ico|png|webp|jpg|gif)$/.test(f));
  assert.deepEqual(files.sort(),manifest.map(r=>r.asset).sort());
});
test("list and detail avatars use the same authentic mark and size variants",()=>{
  assert.match(html(CompanyCell,{name:"Apple",tier:"BIG_TECH"}),/src="\/company-logos\/apple.ico"/);
  assert.match(html(Avatar,{name:"Apple",large:true}),/company-logo--large co-av lg/);
  assert.match(html(Avatar,{name:"FedEx Freight"}),/fedex-freight.png/);
  assert.match(html(CompanyIdentity,{name:"General Motors"}),/general-motors.png/);
});
test("empty and unknown names have visible accessible fallbacks and never request remote images",()=>{
  for(const [name,initials] of [["Fictional Labs","FL"],["","C"],["   ","C"]]){
    const markup=html(CompanyLogo,{name});assert.match(markup,new RegExp(`>${initials}</span>`));
    assert.match(markup,name.trim() ? /checking official logo/ : /logo unavailable/);assert.doesNotMatch(markup,/src="https?:/);
  }
  for(const row of manifest)assert.match(html(CompanyLogo,{name:row.company}),/src="\/company-logos\//);
});
test("company evidence pages include the logo even when official outcome evidence is unavailable",async()=>{
  const {default:CompanyPage}=load(path.join(root,"src/app/app/company/[name]/page.tsx"));
  for(const [name,asset]of [["Apple","apple.ico"],["FedEx%20Freight","fedex-freight.png"],["General%20Motors","general-motors.png"]]){
    const markup=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({name})}));
    assert.match(markup,/company-logo--large/);assert.ok(markup.includes(asset));
    assert.match(markup,/No verified official report/);assert.ok(markup.includes(`company=${encodeURIComponent(decodeURIComponent(name))}`));
    assert.equal(evidenceQueries.at(-1).path,"/api/company-intelligence");
    assert.equal(evidenceQueries.at(-1).params.name,decodeURIComponent(name));
  }
  const malformed=renderToStaticMarkup(await CompanyPage({params:Promise.resolve({name:"Fictional%Labs"})}));
  assert.match(malformed,/Fictional%Labs/);assert.match(malformed,/checking official logo/);
});
test("broken and cached failed images fall back and recover when the employer changes",async()=>{
  const {window}=parseHTML("<html><body><div id='root'></div></body></html>");
  const previous={window:globalThis.window,document:globalThis.document,act:globalThis.IS_REACT_ACT_ENVIRONMENT};
  globalThis.window=window;globalThis.document=window.document;globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const host=window.document.getElementById("root"),mounted=createRoot(host);
  const render=async name=>act(async()=>mounted.render(React.createElement(CompanyLogo,{name})));
  try {
    await render("Apple");assert.match(host.innerHTML,/apple.ico/);
    await act(async()=>host.querySelector("img").dispatchEvent(new window.Event("error")));
    assert.equal(host.querySelector("img"),null);assert.equal(host.textContent,"A");
    await render("General Motors");assert.match(host.innerHTML,/general-motors.png/);
    await render("Fictional Labs");assert.equal(host.textContent,"FL");
    assert.equal(host.querySelector("img").getAttribute("src"),"/api/company-logo?name=Fictional%20Labs");
    assert.equal(host.querySelector("img").getAttribute("data-pending"),"true");
    await act(async()=>host.querySelector("img").dispatchEvent(new window.Event("load")));
    assert.equal(host.textContent,"");assert.equal(host.querySelector("img").getAttribute("data-pending"),null);
    await render("Future Fictional Brand");assert.equal(host.textContent,"FF");
    await act(async()=>host.querySelector("img").dispatchEvent(new window.Event("error")));
    assert.equal(host.querySelector("img"),null);assert.equal(host.textContent,"FF");
    await render("Apple");assert.match(host.innerHTML,/apple.ico/);
    await act(async()=>mounted.render(null));
    const createElement=window.document.createElement.bind(window.document);
    window.document.createElement=(tag,...args)=>{
      const element=createElement(tag,...args);
      if(tag==="img")Object.defineProperties(element,{complete:{value:true},naturalWidth:{value:0}});
      return element;
    };
    await render("Apple");assert.equal(host.querySelector("img"),null);assert.equal(host.textContent,"A");
    window.document.createElement=createElement;
    await render("FedEx Freight");assert.match(host.innerHTML,/fedex-freight.png/);
  } finally {
    await act(async()=>mounted.unmount());globalThis.window=previous.window;globalThis.document=previous.document;globalThis.IS_REACT_ACT_ENVIRONMENT=previous.act;
  }
});
