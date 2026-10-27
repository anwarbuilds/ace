// Actual React components and event handlers, fictional API replies, no browser.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import Module, {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import ts from "typescript";
import React, {act} from "react";
import {createRoot} from "react-dom/client";
import {renderToStaticMarkup} from "react-dom/server";
import {parseHTML} from "linkedom";

const nodeRequire=createRequire(import.meta.url);
const sourceRoot=fileURLToPath(new URL("../src",import.meta.url));
const cache=new Map();
let read,send,serverRead;
let refreshes=0;
let notifications=0;
const app={refreshMarks:async()=>{refreshes++;},settleMarks:()=>{notifications++;},toast:()=>{}};
let projectionRefreshes=0;
let pathname="/app/analytics";
const router={replace:()=>{},refresh:()=>{projectionRefreshes++;}};
const params=new URLSearchParams();
const passthrough=({children})=>React.createElement("div",null,children);
const mocks={
  "next/navigation":{useRouter:()=>router,useSearchParams:()=>params,usePathname:()=>pathname},
  "next/link":{__esModule:true,default:({href,children,className})=>React.createElement("a",{href,className},children)},
  "next/form":{__esModule:true,default:({children,...props})=>React.createElement("form",props,children)},
  "@/lib/client":{getJson:(...args)=>read(...args),sendJson:(...args)=>send(...args),RequestError:class extends Error{}},
  "@/components/shell/AppProvider":{useApp:()=>app},
  "@/components/shell/ScrollArea":{ScrollArea:passthrough},
  "@/components/analytics/AnalyticsRefresh":{AnalyticsRefresh:()=>null},
  "@/lib/api":{apiGetOr:(...args)=>serverRead(...args)},
  "@/lib/prefs":{getPrefs:async()=>({tz:"America/Los_Angeles"})},
};
function load(filename){
  if(cache.has(filename))return cache.get(filename).exports;
  const mod={exports:{}};cache.set(filename,mod);
  const output=ts.transpileModule(fs.readFileSync(filename,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const requireSource=name=>{
    if(mocks[name])return mocks[name];
    if(name.endsWith(".css"))return {};
    if(name.startsWith("@/")||name.startsWith(".")){
      const base=name.startsWith("@/")?path.join(sourceRoot,name.slice(2)):path.resolve(path.dirname(filename),name);
      const found=[base+".ts",base+".tsx"].find(fs.existsSync);
      return found?load(found):createRequire(filename)(name);
    }
    return nodeRequire(name);
  };
  vm.runInThisContext(Module.wrap(output),{filename})(mod.exports,requireSource,mod,filename,path.dirname(filename));
  return mod.exports;
}
const {InboxIntelligence}=load(path.join(sourceRoot,"components/inbox/InboxIntelligence.tsx"));
const {InboxReviewPanel}=load(path.join(sourceRoot,"components/inbox/InboxReviewPanel.tsx"));
const RecordsPage=load(path.join(sourceRoot,"app/app/applications/analytics/page.tsx")).default;
async function mounted(element,run){
  const {window}=parseHTML("<html><body><div id='root'></div></body></html>");
  const original=new Map(["window","document","HTMLElement","Node","Event","IS_REACT_ACT_ENVIRONMENT"].map(key=>[key,globalThis[key]]));
  Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,Node:window.Node,Event:window.Event,IS_REACT_ACT_ENVIRONMENT:true});
  Object.defineProperty(window.document,"visibilityState",{value:"visible",configurable:true});
  window.matchMedia=()=>({matches:false});
  const container=window.document.getElementById("root");
  const root=createRoot(container);
  try{
    await act(async()=>{root.render(element);});
    await run(container,window,root);
  }finally{
    await act(async()=>{root.unmount();});
    for(const [key,value] of original)if(value===undefined)delete globalThis[key];else globalThis[key]=value;
  }
}
const complete={days:30,gmail:125,in_ace:125,missing:0,complete:true,checked_at:new Date().toISOString()};
function fixture({coverage=complete,stale=0,state="ready",fail=false}={}){
  const calls=[];
  const connection={coverage,state,connected:true,available:true,email:"owner-fixture@example.test",last_synced_at:new Date().toISOString(),following_changes:true,auto_rejections:true};
  read=async route=>{
    if(route==="/api/inbox/connection")return {...connection};
    if(route==="/api/inbox/messages")return {items:[],total:0,has_more:false,view:"recruiting",latest_received_at:null,counts:{stored:125,needs_review:0,automatic:0,manual:0,reviewed:0,receipts:0,updates:0,stale}};
    if(route==="/api/inbox/applications"||route==="/api/inbox/events")return {items:[]};
    throw Error(`Unexpected fictional read ${route}`);
  };
  send=async(method,route,body)=>{
    calls.push({route,body});
    if(fail)throw Error("Fictional Google read failure");
    if(route==="/api/inbox/recheck"){const checked=stale;stale=0;return {checked,remaining:0,counts:{review:checked}};}
    connection.coverage=calls.length===1?{...complete,in_ace:60,missing:65}:complete;
    return {state:"ready",coverage:connection.coverage,counts:{ignored:60},remaining:connection.coverage.missing,partial:connection.coverage.missing>0};
  };
  return {calls,connection};
}

test("opening Inbox with a recent timestamp but no coverage verifies all batches and rechecks stale email",async()=>{
  const {calls}=fixture({coverage:null,stale:2});
  await mounted(React.createElement(InboxIntelligence),async container=>{
    assert.deepEqual(calls.map(c=>c.route),["/api/inbox/sync","/api/inbox/sync","/api/inbox/recheck"]);
    assert.match(container.textContent,/Gmail has 125 emails from the last 30 days. All are in ACE/);
    assert.match(container.textContent,/All caught up/);
    assert.match(container.textContent,/Read 2 older emails again/);
    assert.match(container.textContent,/Verify further back/);
    assert.doesNotMatch(container.textContent,/Import next page/);
  });
});

test("a parser bump rechecks on open even after a recent verified Gmail check",async()=>{
  const {calls}=fixture({stale:2});
  await mounted(React.createElement(InboxIntelligence),async()=>{
    assert.equal(calls.at(-1).route,"/api/inbox/recheck");
  });
});

test("failed verification displays the failure and refreshes already saved changes",async()=>{
  const {calls}=fixture({coverage:null,fail:true});
  const before=refreshes;
  const beforeNotifications=notifications;
  const beforeProjection=projectionRefreshes;
  await mounted(React.createElement(InboxIntelligence),async container=>{
    assert.equal(calls.length,1);
    assert.match(container.textContent,/Fictional Google read failure/);
    assert.doesNotMatch(container.textContent,/All caught up/);
    assert.equal(refreshes,before+1);
    assert.equal(notifications,beforeNotifications+1);
    assert.equal(projectionRefreshes,beforeProjection+1);
  });
});

test("paused Inbox never starts automatic reads",async()=>{
  const {calls}=fixture({state:"paused",coverage:null,stale:5});
  await mounted(React.createElement(InboxIntelligence),async container=>{
    assert.equal(calls.length,0);
    assert.match(container.textContent,/Gmail sync is paused/);
  });
});

test("mismatched company warning cancels the actual outcome handler, and explicit override records once",async()=>{
  const message={id:9182,sender:"Fictional Redwood <redwood@myworkday.com>",subject:"Redwood application update",snippet:"An application update.",received_at:"2026-10-26T12:00:00Z",classification:"unclear",decision:"review",candidate_keys:["job:2"],reason:"Fictional uncertainty",selected_application_key:null};
  const application={key:"job:2",company:"Imaginary Systems",title:"Fictional engineer",status:"applied",applied_at:"2026-10-01T12:00:00Z"};
  read=async()=>({...message,text:"Redwood application update",document:"<p>Fictional</p>",blocked_images:0});
  const writes=[];
  send=async(method,route,body)=>{writes.push({route,body});};
  await mounted(React.createElement(InboxReviewPanel,{message,applications:[application],events:[],busy:false,action:async run=>run()}),async(container,window)=>{
    assert.match(container.textContent,/This email does not name Imaginary Systems/);
    const button=[...container.querySelectorAll("button")].find(b=>b.querySelector("strong")?.textContent==="Rejection");
    let prompts=0;
    window.confirm=()=>{prompts++;return false;};
    await act(async()=>{button.dispatchEvent(new window.Event("click",{bubbles:true}));});
    assert.equal(prompts,1);assert.equal(writes.length,0);
    window.confirm=()=>true;
    await act(async()=>{button.dispatchEvent(new window.Event("click",{bubbles:true}));});
    assert.equal(writes.length,1);
    assert.equal(writes[0].body.application_key,"job:2");
    assert.equal(writes[0].body.status,"rejected");
  });
});

test("the actual records page explains empty rejection searches with status, date and email links",async()=>{
  let asked;
  serverRead=async(route,fallback,query)=>{
    asked=query;
    return {record_total:0,record_limit:50,record_offset:0,record_query:"fictional mac",records:[],days:"30",start:"2026-09-27",end:"2026-10-26",timezone:"America/Los_Angeles",
      not_listed:{application_total:1,email_total:1,applications:[{key:"job:7",company:"Fictional Mac",title:"Software engineer",status:"applied",submitted_at:"2026-08-26T12:00:00Z",outside_range:true,href:"/app/jobs/7"}],emails:[{id:52,subject:"Fictional Mac application update",decision:"review",classification:"unclear",received_at:"2026-10-26T12:00:00Z"}]}};
  };
  const tree=await RecordsPage({searchParams:Promise.resolve({evidence:"rejection",q:"fictional mac",days:"30"})});
  const html=renderToStaticMarkup(tree);
  assert.equal(asked.days,"30");
  assert.match(html,/Where is my application\?/);
  assert.match(html,/Outside the selected submission dates/);
  assert.match(html,/Applied/);
  assert.match(html,/Needs you/);
  assert.match(html,/Application email/);
  assert.match(html,/href="\/app\/jobs\/7"/);
  assert.match(html,/href="\/app\/applications\/inbox\?message=52"/);
  assert.match(html,/Search all applications, all time/);
  await RecordsPage({searchParams:Promise.resolve({evidence:"rejection"})});
  assert.equal(asked.days,"all");
});

test("retrying an interrupted wider verification keeps its 90-day window",async()=>{
  params.set("days","90");
  fixture();
  const calls=[];
  send=async(method,route,body)=>{
    calls.push({route,body});
    if(calls.length===2)throw Error("Fictional interrupted window");
    const coverage={...complete,days:90,...(calls.length===1?{in_ace:60,missing:65}:{})};
    return {state:"ready",counts:{ignored:60},remaining:coverage.missing,partial:coverage.missing>0,coverage};
  };
  try{
    await mounted(React.createElement(InboxIntelligence),async(container,window)=>{
      await act(async()=>{container.querySelector(".inbox-backfill button").dispatchEvent(new window.Event("click",{bubbles:true}));});
      assert.match(container.textContent,/Fictional interrupted window/);
      await act(async()=>{container.querySelector(".inbox-status .btn.primary").dispatchEvent(new window.Event("click",{bubbles:true}));});
      assert.deepEqual(calls.map(c=>c.body.days),[90,90,90]);
      assert.match(container.textContent,/All caught up/);
    });
  }finally{params.delete("days");}
});


test("Analytics refreshes on opening, cross-tab evidence messages, focus and return navigation",async()=>{
  const ActualRefresh=load(path.join(sourceRoot,"components/analytics/AnalyticsRefresh.tsx")).AnalyticsRefresh;
  const previous=globalThis.BroadcastChannel;
  const channels=[];
  globalThis.BroadcastChannel=class {constructor(name){this.name=name;channels.push(this);}close(){this.closed=true;}};
  try{
    const before=projectionRefreshes;
    await mounted(React.createElement(ActualRefresh),async(container,window,root)=>{
      assert.equal(projectionRefreshes,before+1);
      assert.equal(channels[0].name,"ace-marks");
      await act(async()=>{channels[0].onmessage({data:"changed"});});
      assert.equal(projectionRefreshes,before+2);
      await act(async()=>{window.dispatchEvent(new window.Event("focus"));});
      assert.equal(projectionRefreshes,before+3);
      pathname="/app/applications/analytics";
      await act(async()=>{root.render(React.createElement(ActualRefresh));});
      assert.equal(projectionRefreshes,before+4);
    });
    assert.equal(channels[0].closed,true);
  }finally{globalThis.BroadcastChannel=previous;pathname="/app/analytics";}
});

test("records expose excluded email links separately from counted evidence",async()=>{
  serverRead=async()=>({record_total:1,record_limit:50,record_offset:0,record_query:"",records:[{key:"job:88",company:"Fictional Labs",title:"Engineer",status:"rejected",family:"SOFTWARE_ENGINEERING",submitted_at:"2026-10-01T12:00:00Z",href:"/app/jobs/88",evidence:[{kind:"rejection",at:null,message_id:null}],excluded_evidence:[{message_id:909,reason:"before_application_window"}]}],days:"all",start:"2026-10-01",end:"2026-10-26",timezone:"America/Los_Angeles"});
  const html=renderToStaticMarkup(await RecordsPage({searchParams:Promise.resolve({})}));
  assert.match(html,/Email predates the application window/);
  assert.match(html,/Not counted as verified email evidence/);
  assert.match(html,/inbox\?message=909/);
  assert.match(html,/Review excluded email/);
});


test("an old recorded email loads its own event history so Undo survives the global 100-event limit",async()=>{
  const message={id:9292,sender:"Fictional Labs <talent@fictional.example>",subject:"Fictional application update",snippet:"Fictional",received_at:"2026-10-01T12:00:00Z",classification:"rejection",decision:"automatic",candidate_keys:["job:3"],reason:"Fictional confirmed rejection",selected_application_key:"job:3"};
  const application={key:"job:3",company:"Fictional Labs",title:"Engineer",status:"rejected",applied_at:"2026-09-01T12:00:00Z"};
  const calls=[];
  read=async(route,params)=>{
    if(route==="/api/inbox/events"){
      assert.equal(params.get("message_id"),"9292");
      return {items:[{id:12,application_key:"job:3",kind:"rejection",before:"applied",after:"rejected",actor:"verified_automation",gmail_message_id:9292,undo_of_id:null}]};
    }
    return {...message,text:"Fictional update",document:"<p>Fictional</p>",blocked_images:0};
  };
  send=async(method,route)=>{calls.push(route);};
  await mounted(React.createElement(InboxReviewPanel,{message,applications:[application],events:[],busy:false,action:async run=>run()}),async(container,window)=>{
    const undo=[...container.querySelectorAll("button")].find(button=>button.textContent==="Undo this change");
    assert.equal(Boolean(undo),true);
    await act(async()=>{undo.dispatchEvent(new window.Event("click",{bubbles:true}));});
    assert.deepEqual(calls,["/api/inbox/events/12/undo"]);
  });
});
