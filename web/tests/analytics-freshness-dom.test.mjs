// Actual route components with fictional RSC replacements, without Chrome.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import Module, {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import ts from "typescript";
import React, {act, Suspense, useState} from "react";
import {createRoot} from "react-dom/client";
import {parseHTML} from "linkedom";

const require=createRequire(import.meta.url);
const sourceRoot=fileURLToPath(new URL("../src",import.meta.url));
const cache=new Map();
let pathname="/app/analytics",refresh=()=>{},replace=()=>{};
function load(filename){
  if(cache.has(filename))return cache.get(filename).exports;
  const mod={exports:{}};cache.set(filename,mod);
  const output=ts.transpileModule(fs.readFileSync(filename,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const sourceRequire=name=>{
    if(name==="next/navigation")return {usePathname:()=>pathname,useRouter:()=>({refresh,replace})};
    if(name.startsWith("."))return load(path.resolve(path.dirname(filename),name+".tsx"));
    return require(name);
  };
  vm.runInThisContext(Module.wrap(output),{filename})(mod.exports,sourceRequire,mod,filename,path.dirname(filename));
  return mod.exports;
}
const {AnalyticsRefresh,ANALYTICS_REFRESH_REQUEST,ANALYTICS_REFRESH_STATE}=load(path.join(sourceRoot,"components/analytics/AnalyticsRefresh.tsx"));
const {AnalyticsFreshness}=load(path.join(sourceRoot,"components/analytics/AnalyticsFreshness.tsx"));

async function mounted(element,run){
  const {window}=parseHTML("<html><body><div id='root'></div></body></html>");
  const keys=["window","document","HTMLElement","Node","Event","IS_REACT_ACT_ENVIRONMENT","BroadcastChannel","setTimeout","clearTimeout","setInterval","clearInterval"];
  const original=new Map(keys.map(key=>[key,globalThis[key]]));
  const previousNow=Date.now;
  const channels=[],timers=new Map();let id=0,now=1_000_000;
  Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,Node:window.Node,Event:window.Event,IS_REACT_ACT_ENVIRONMENT:true});
  Object.defineProperty(window.document,"visibilityState",{value:"visible",configurable:true,writable:true});
  Date.now=()=>now;
  globalThis.BroadcastChannel=class {constructor(name){this.name=name;channels.push(this);}close(){this.closed=true;}};
  globalThis.setTimeout=(fn,delay)=>{const key=++id;timers.set(key,{fn,at:now+delay,repeat:0});return key;};
  globalThis.setInterval=(fn,delay)=>{const key=++id;timers.set(key,{fn,at:now+delay,repeat:delay});return key;};
  globalThis.clearTimeout=globalThis.clearInterval=key=>timers.delete(key);
  const root=createRoot(window.document.getElementById("root"));
  const render=async node=>act(async()=>root.render(node));
  const dispatch=async(target,name)=>act(async()=>target.dispatchEvent(new window.Event(name)));
  const tick=async ms=>{
    now+=ms;
    // Run the due tasks once, including an interval, then let React settle.
    for(const [key,task] of [...timers])if(task.at<=now){
      if(task.repeat)task.at=now+task.repeat;else timers.delete(key);
      await act(async()=>task.fn());
    }
  };
  try{await render(element);await run({container:window.document.getElementById("root"),window,root,render,dispatch,tick,channels,timers});}
  finally{await act(async()=>root.unmount());Date.now=previousNow;for(const[key,value]of original)if(value===undefined)delete globalThis[key];else globalThis[key]=value;pathname="/app/analytics";refresh=()=>{};replace=()=>{};}
}

test("one persistent coordinator uses the initial server read and refreshes once on return",async()=>{
  let calls=0,replaces=0;refresh=()=>{calls++;};replace=()=>{replaces++;};
  await mounted(React.createElement(AnalyticsRefresh),async({render,channels,timers,window,dispatch})=>{
    for(let i=0;i<4;i++)await render(React.createElement(AnalyticsRefresh));
    assert.equal(calls,0);assert.equal(replaces,0);assert.equal(channels.length,1);assert.equal(timers.size,1);
    pathname="/app/applications/inbox";await render(React.createElement(AnalyticsRefresh));
    await dispatch(window,"focus");assert.equal(calls,0);assert.equal(timers.size,0);assert.ok(channels[0].closed);
    pathname="/app/analytics";await render(React.createElement(AnalyticsRefresh));
    assert.equal(calls,1);assert.equal(channels.length,2);assert.equal(timers.size,1);
  });
});

test("polls are bounded to two minutes while visible and wake signals coalesce",async()=>{
  let calls=0;refresh=()=>{calls++;};
  await mounted(React.createElement(AnalyticsRefresh),async({window,dispatch,tick})=>{
    await tick(119_999);assert.equal(calls,0);
    await tick(1);assert.equal(calls,1);
    await dispatch(window,"focus");await dispatch(window.document,"visibilitychange");assert.equal(calls,1);
    window.document.visibilityState="hidden";
    await tick(120_000);await dispatch(window,"focus");assert.equal(calls,1);
    window.document.visibilityState="visible";
    await dispatch(window.document,"visibilitychange");await dispatch(window,"focus");assert.equal(calls,2);
    await tick(120_000);assert.equal(calls,3);
  });
});

test("a decision during an in-flight response queues one follow-up without overlapping reads",async()=>{
  let calls=0,complete;
  const waiting=new Promise(resolve=>{complete=resolve;});
  function Payload({version}){if(version===1)React.use(waiting);return React.createElement("p",null,`Version ${version}`);}
  function Fixture(){const[version,setVersion]=useState(0);refresh=()=>{calls++;setVersion(calls);};return React.createElement(React.Fragment,null,React.createElement(AnalyticsRefresh),React.createElement(Suspense,{fallback:"Waiting"},React.createElement(Payload,{version})));}
  await mounted(React.createElement(Fixture),async({channels,window,dispatch,tick,container})=>{
    await act(async()=>channels[0].onmessage({data:"changed"}));
    assert.equal(calls,1);assert.match(container.textContent,/Version 0/);
    await tick(1_000);await dispatch(window,"focus");
    await act(async()=>{channels[0].onmessage({data:"changed"});channels[0].onmessage({data:"changed"});});
    assert.equal(calls,1,"pending RSC work prevents overlapping refreshes");
    await act(async()=>complete());await tick(1);
    assert.equal(calls,2,"the decision receives one settled follow-up");
    assert.match(container.textContent,/Version 2/);
    await tick(500);assert.equal(calls,2);
  });
});

for(const scope of ["/app/analytics?days=all&tab=outcomes&family=ML_ENGINEERING","/app/applications/analytics?days=custom&start=2026-07-01&end=2026-10-29&q=Fiction&offset=50"]){
  test(`failed refresh retains verified results and Retry recovers the exact selection: ${scope}`,async()=>{
    const props={scope,attemptedAt:1,asOf:"2026-10-30T01:00:00Z",timezone:"America/Los_Angeles",success:true};
    const response=(extra,text)=>React.createElement(AnalyticsFreshness,{...props,...extra},React.createElement("p",{"data-report":true},text));
    await mounted(response({},"Verified 12"),async({container,render,window})=>{
      await render(response({attemptedAt:2,success:false,asOf:null},"Unavailable"));
      assert.equal(container.querySelector("[data-report]").textContent,"Verified 12");
      const status=container.querySelector("[role=status]");
      assert.equal(status.dataset.state,"stale");assert.match(status.textContent,/Refresh failed.*last verified results.*Oct 29.*6:00 PM PDT/);
      assert.equal(status.dataset.analyticsAsOf,props.asOf);
      let retry=0;window.addEventListener(ANALYTICS_REFRESH_REQUEST,()=>{retry++;});
      await act(async()=>container.querySelector("button").click());assert.equal(retry,1);
      await render(response({attemptedAt:3,asOf:"2026-10-30T01:02:00Z"},"Verified 13"));
      assert.equal(container.querySelector("[data-report]").textContent,"Verified 13");
      assert.equal(container.querySelector("[role=status]").dataset.state,"fresh");assert.equal(container.querySelector("button"),null);
    });
  });
}

test("older successes and late failures cannot overwrite newer verified data",async()=>{
  const props={scope:"same",attemptedAt:20,asOf:"2026-10-30T01:10:00Z",timezone:"America/Los_Angeles",success:true};
  const response=(extra,text)=>React.createElement(AnalyticsFreshness,{...props,...extra},React.createElement("p",{"data-report":true},text));
  await mounted(response({},"New"),async({container,render})=>{
    await render(response({attemptedAt:21,asOf:"2026-10-30T01:00:00Z"},"Old"));
    assert.equal(container.querySelector("[data-report]").textContent,"New");
    await render(response({attemptedAt:22,asOf:"2026-10-30T01:12:00Z"},"Newest"));
    await render(response({attemptedAt:19,asOf:null,success:false},"Old failure"));
    assert.equal(container.querySelector("[data-report]").textContent,"Newest");
    assert.equal(container.querySelector("[role=status]").dataset.state,"fresh");
  });
});

test("a changed selection or remount never shows another selection's retained report",async()=>{
  const response=(scope,success,attemptedAt,text)=>React.createElement(AnalyticsFreshness,{scope,success,attemptedAt,asOf:success?"2026-10-30T01:00:00Z":null,timezone:"America/Los_Angeles"},React.createElement("p",null,text));
  await mounted(response("all",true,1,"Private old report"),async({container,render})=>{
    await render(response("company=Other",false,2,"This selection is unavailable"));
    assert.doesNotMatch(container.textContent,/Private old report/);assert.match(container.textContent,/This selection is unavailable/);
    await render(null);await render(response("all",false,3,"Fresh mount is unavailable"));
    assert.doesNotMatch(container.textContent,/Private old report/);assert.match(container.textContent,/Fresh mount is unavailable/);
  });
});

test("a settled refresh without an RSC response shows stale data and a successful retry recovers",async()=>{
  let calls=0;
  function Fixture(){
    const[version,setVersion]=useState(1);
    refresh=()=>{calls++;if(calls>1)setVersion(2);};
    return React.createElement(React.Fragment,null,React.createElement(AnalyticsRefresh),React.createElement(AnalyticsFreshness,{scope:"same",attemptedAt:version,asOf:version===1?"2026-10-30T01:00:00Z":"2026-10-30T01:02:00Z",timezone:"America/Los_Angeles",success:true},React.createElement("p",{"data-report":true},`Verified ${version}`)));
  }
  await mounted(React.createElement(Fixture),async({container,window,dispatch,tick})=>{
    await dispatch(window,"focus");
    assert.equal(calls,1);assert.equal(container.querySelector("[role=status]").dataset.state,"stale");
    assert.match(container.textContent,/Refresh failed.*last verified results/);assert.equal(container.querySelector("[data-report]").textContent,"Verified 1");
    await tick(500);await act(async()=>container.querySelector("button").click());
    assert.equal(calls,2);assert.equal(container.querySelector("[data-report]").textContent,"Verified 2");
    assert.equal(container.querySelector("[role=status]").dataset.state,"fresh");
  });
});

test("a slow request discloses a delayed check without claiming a new verified timestamp",async()=>{
  const props={scope:"same",attemptedAt:1,asOf:"2026-10-30T01:00:00Z",timezone:"America/Los_Angeles",success:true};
  await mounted(React.createElement(AnalyticsFreshness,props,"Verified"),async({container,window})=>{
    const event=phase=>window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE,{detail:{phase,id:42}}));
    await act(async()=>event("started"));assert.equal(container.querySelector("[role=status]").dataset.state,"refreshing");
    await act(async()=>event("delayed"));
    assert.equal(container.querySelector("[role=status]").dataset.state,"stale");assert.match(container.textContent,/Refresh is delayed.*6:00 PM PDT/);
    assert.equal(container.querySelector("button").disabled,true);assert.equal(container.querySelector("[role=status]").dataset.analyticsAsOf,props.asOf);
    await act(async()=>event("settled"));assert.equal(container.querySelector("button").disabled,false);
  });
});

test("offline checks keep the last response and reconnecting requests one fresh server projection",async()=>{
  const descriptor=Object.getOwnPropertyDescriptor(globalThis.navigator,"onLine");
  let calls=0;
  function Fixture(){
    const[version,setVersion]=useState(1);refresh=()=>{calls++;setVersion(version+1);};
    return React.createElement(React.Fragment,null,React.createElement(AnalyticsRefresh),React.createElement(AnalyticsFreshness,{scope:"same",attemptedAt:version,asOf:`2026-10-30T01:0${version}:00Z`,timezone:"America/Los_Angeles",success:true},`Version ${version}`));
  }
  try{
    await mounted(React.createElement(Fixture),async({container,window,dispatch})=>{
      Object.defineProperty(globalThis.navigator,"onLine",{value:false,configurable:true});
      await dispatch(window,"offline");await dispatch(window,"focus");
      await act(async()=>container.querySelector("button").click());
      assert.equal(calls,0);assert.match(container.textContent,/Refresh failed.*last verified results/);assert.match(container.textContent,/Version 1/);
      Object.defineProperty(globalThis.navigator,"onLine",{value:true,configurable:true});
      await dispatch(window,"online");
      assert.equal(calls,1);assert.match(container.textContent,/Version 2/);assert.equal(container.querySelector("[role=status]").dataset.state,"fresh");
    });
  }finally{if(descriptor)Object.defineProperty(globalThis.navigator,"onLine",descriptor);else delete globalThis.navigator.onLine;}
});
