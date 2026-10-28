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
  "server-only":{},
  "next/navigation":{useRouter:()=>router,useSearchParams:()=>params,usePathname:()=>pathname},
  "next/link":{__esModule:true,default:({href,children,className})=>React.createElement("a",{href,className},children)},
  "next/form":{__esModule:true,default:({children,...props})=>React.createElement("form",props,children)},
  "@/lib/client":{getJson:(...args)=>read(...args),sendJson:(...args)=>send(...args),RequestError:class extends Error{}},
  "@/components/shell/AppProvider":{useApp:()=>app,AppProvider:passthrough},
  "@/components/shell/ScrollArea":{ScrollArea:passthrough},
  "@/components/analytics/AnalyticsRefresh":{AnalyticsRefresh:()=>null},
  "@/lib/api":{apiGetOr:(...args)=>serverRead(...args),authStatus:async()=>({signed_in:true})},
  "@/lib/prefs":{getPrefs:async()=>({tz:"America/Los_Angeles"}),getPrevVisit:async()=>null},
  "@/components/analytics/AnalyticsView":{AnalyticsView:()=>React.createElement("h1",null,"Fictional Analytics")},
  "@/components/shell/AnswersDock":{AnswersDock:()=>null},
  "@/components/shell/NavigationState":{NavigationState:()=>null},
  "@/components/shell/Sidebar":{Sidebar:()=>null},
  "@/components/shell/Topbar":{Topbar:()=>null,MobileBar:()=>null},
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
      // Relative and alias imports must meet the same mocked server boundary.
      const alias="@/"+path.relative(sourceRoot,base).split(path.sep).join("/");
      if(mocks[alias])return mocks[alias];
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
const complete={days:0,scope:"job_mail",includes_spam_trash:false,gmail:125,in_ace:125,missing:0,complete:true,checked_at:new Date().toISOString()};
function fixture({coverage=complete,stale=0,state="ready",fail=false,pending=0,unlinked=0,backgroundSyncEnabled}={}){
  const calls=[];
  const connection={coverage,state,connected:true,available:true,email:"owner-fixture@example.test",last_synced_at:new Date().toISOString(),following_changes:true,auto_rejections:true,background_sync_enabled:backgroundSyncEnabled};
  read=async route=>{
    if(route==="/api/inbox/connection")return {...connection};
    if(route==="/api/inbox/messages")return {items:[],total:0,has_more:false,view:"recruiting",latest_received_at:null,counts:{stored:125,needs_review:pending,automatic:0,manual:0,reviewed:0,receipts:0,updates:0,unlinked,stale}};
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
    assert.match(container.textContent,/Gmail has 125 emails matching the job-mail search across all dates.*All are in ACE/);
    assert.match(container.textContent,/Job-mail check complete/);
    assert.match(container.textContent,/Read 2 older emails again/);
    assert.match(container.textContent,/Verify mailbox history/);
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
    assert.doesNotMatch(container.textContent,/Job-mail check complete/);
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

for(const backgroundSyncEnabled of [true,false,undefined]){
  test(`Inbox rules describe background checks only when the server enables them (${backgroundSyncEnabled})`,async()=>{
    const {calls}=fixture({backgroundSyncEnabled});
    await mounted(React.createElement(InboxIntelligence),async(container,window)=>{
      const rules=[...container.querySelectorAll(".intelligence-tabs button")].find(button=>button.textContent==="How ACE decides");
      await act(async()=>{rules.dispatchEvent(new window.Event("click",{bubbles:true}));});
      if(backgroundSyncEnabled){
        assert.match(container.textContent,/While sync is on, ACE checks Gmail about every three minutes even when this page is closed/);
        assert.match(container.textContent,/Google limits or a large import can delay a check/);
      }else{
        assert.match(container.textContent,/ACE checks Gmail when you open this page and every few minutes while it stays open/);
        assert.doesNotMatch(container.textContent,/even when this page is closed/);
      }
      assert.match(container.textContent,/Sync now also checks for new mail/);
      assert.match(container.textContent,/Nothing is sent, changed or deleted in Gmail/);
      assert.deepEqual(calls,[],"reading the rules never starts a sync or changes automation");
    });
  });
}

test("recognized historical evidence opens its own filter without adding to the waiting count",async()=>{
  const {calls}=fixture({pending:2,unlinked:6});
  const replace=router.replace;
  const destinations=[];
  router.replace=(url)=>destinations.push(url);
  try{
    await mounted(React.createElement(InboxIntelligence),async(container,window)=>{
      assert.match(container.querySelector(".inbox-status h2").textContent,/2 emails need you/);
      const note=[...container.querySelectorAll(".inbox-status-note")].find(item=>item.textContent.includes("recognized historical outcomes"));
      assert.ok(note);
      assert.match(note.textContent,/6 recognized historical outcomes without an eligible application/);
      assert.match(note.textContent,/excluded from application outcomes in Analytics\. Linking is optional/);
      assert.ok(container.querySelector('.inbox-queue-tools option[value="unlinked_outcome"]'));
      await act(async()=>{note.querySelector("button").dispatchEvent(new window.Event("click",{bubbles:true}));});
      assert.equal(destinations.length,1);
      assert.equal(new URL(destinations[0],"https://fixture.example").searchParams.get("decision"),"unlinked_outcome");
      assert.deepEqual(calls,[],"opening retained evidence must not record an application outcome");
    });
  }finally{router.replace=replace;}
});

test("an unlinked historical rejection changes an application only after an explicit owner choice",async()=>{
  const message={id:98721,sender:"Fictional Labs <talent@fictional.example>",subject:"Fictional Labs application update",snippet:"We will not move forward with your application.",received_at:"2026-01-10T12:00:00Z",classification:"rejection",decision:"unlinked",candidate_keys:[],reason:"The rejection predates every recorded application at this employer.",selected_application_key:null};
  const application={key:"job:98721",company:"Fictional Labs",title:"Engineer",status:"applied",applied_at:"2026-09-01T12:00:00Z"};
  const reads=[],writes=[];
  read=async route=>{reads.push(route);return {...message,text:"Fictional Labs application update. We will not move forward with your application.",document:"<p>Fictional rejection</p>",blocked_images:0};};
  send=async(method,route,body)=>{writes.push({method,route,body});};
  await mounted(React.createElement(InboxReviewPanel,{message,applications:[application],events:[],busy:false,action:async run=>run()}),async(container,window)=>{
    const rejection=[...container.querySelectorAll("button")].find(button=>button.querySelector("strong")?.textContent==="Rejection");
    assert.equal(rejection.disabled,true);
    assert.match(container.textContent,/Linking is optional; the email remains searchable/);
    assert.doesNotMatch(container.textContent,/Why it waits:|Undo this change|Decide later/);
    assert.deepEqual(writes,[]);
    assert.deepEqual(reads,["/api/inbox/messages/98721/full"],"viewing unlinked evidence must not request recorded-outcome history");
    const option=container.querySelector(".inbox-options button");
    assert.ok(option,"optional manual linkage remains available");
    await act(async()=>{option.dispatchEvent(new window.Event("click",{bubbles:true}));});
    assert.equal(rejection.disabled,false);
    assert.deepEqual(writes,[],"selecting an application alone must not change its status");
    await act(async()=>{rejection.dispatchEvent(new window.Event("click",{bubbles:true}));});
    assert.deepEqual(writes,[{method:"POST",route:"/api/inbox/review",body:{message_id:98721,application_key:"job:98721",status:"rejected",expected_status:"applied",confirmed:true,kind:"rejection"}}]);
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
  assert.match(html,/Application correspondence/);
  assert.match(html,/href="\/app\/jobs\/7"/);
  assert.match(html,/href="\/app\/applications\/inbox\?message=52"/);
  assert.match(html,/Search all applications, all time/);
  await RecordsPage({searchParams:Promise.resolve({evidence:"rejection"})});
  assert.equal(asked.days,"all");
});

test("retrying an interrupted wider verification keeps its 90-day window",async()=>{
  params.set("days","90");
  fixture({coverage:{...complete,days:90}});
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
      assert.doesNotMatch(container.textContent,/Job-mail check complete/);
      assert.match(container.textContent,/does not verify your full mailbox history/);
    });
  }finally{params.delete("days");}
});


test("Analytics uses its initial server response and refreshes on evidence, focus and return navigation",async()=>{
  const ActualRefresh=load(path.join(sourceRoot,"components/analytics/AnalyticsRefresh.tsx")).AnalyticsRefresh;
  const previous=globalThis.BroadcastChannel;
  const channels=[];
  globalThis.BroadcastChannel=class {constructor(name){this.name=name;channels.push(this);}close(){this.closed=true;}};
  try{
    const before=projectionRefreshes;
    await mounted(React.createElement(ActualRefresh),async(container,window,root)=>{
      assert.equal(projectionRefreshes,before+0);
      assert.equal(channels[0].name,"ace-marks");
      await act(async()=>{channels[0].onmessage({data:"changed"});});
      assert.equal(projectionRefreshes,before+1);
      await act(async()=>{window.dispatchEvent(new window.Event("focus"));});
      assert.equal(projectionRefreshes,before+2);
      pathname="/app/applications/analytics";
      await act(async()=>{root.render(React.createElement(ActualRefresh));});
      assert.equal(projectionRefreshes,before+3);
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


test("Inbox opens on full retained history and never treats a recent-window check as full coverage",async()=>{
  const {calls}=fixture({coverage:{...complete,days:30}});
  await mounted(React.createElement(InboxIntelligence),async container=>{
    assert.ok(calls.length>0);
    assert.ok(calls.filter(c=>c.route==="/api/inbox/sync").every(c=>c.body.days===0));
    assert.equal(container.querySelector(".inbox-backfill select").value,"0");
    assert.match(container.textContent,/Spam and Trash excluded/);
  });
});

test("Analytics overview and records request all time unless the owner selects dates",async()=>{
  const AnalyticsPage=load(path.join(sourceRoot,"app/app/analytics/page.tsx")).default;
  const queries=[];
  serverRead=async(route,fallback,query)=>{if(route==="/api/analytics")queries.push(query);return null;};
  await AnalyticsPage({searchParams:Promise.resolve({})});
  await RecordsPage({searchParams:Promise.resolve({})});
  await AnalyticsPage({searchParams:Promise.resolve({days:"30"})});
  await AnalyticsPage({searchParams:Promise.resolve({start:"2026-10-01",end:"2026-10-26"})});
  assert.deepEqual(queries.map(q=>q.days),["all","all","30","custom"]);
});



test("filing acknowledgements and updates uses only the email decision endpoint",async()=>{
  const {calls}=fixture();
  const previousRead=read;
  const message={id:70991,sender:"Fictional Talent <fixture@example.test>",subject:"Fictional interview at Fictional Labs",snippet:"Please schedule an interview for requisition FIX-1.",received_at:"2026-01-10T12:00:00Z",classification:"interview",decision:"review",candidate_keys:["job:1"],reason:"Positive outcome needs confirmation",selected_application_key:null};
  read=async(route,...args)=>{
    if(route==="/api/inbox/messages"){const page=await previousRead(route,...args);return {...page,items:[message],total:1,counts:{...page.counts,needs_review:1}};}
    if(route==="/api/inbox/applications")return {items:[{key:"job:1",company:"Fictional Labs",title:"Fictional engineer",status:"applied",applied_at:"2026-01-01T12:00:00Z"}]};
    if(route.endsWith("/full"))return {...message,text:"Fictional Labs application",document:"<p>Fictional</p>",blocked_images:0};
    return previousRead(route,...args);
  };
  await mounted(React.createElement(InboxIntelligence),async(container,window)=>{
    for(const label of ["Acknowledgement","Status update"]){
      const button=[...container.querySelectorAll("button")].find(b=>b.querySelector("strong")?.textContent===label);
      assert.ok(button);
      await act(async()=>{button.dispatchEvent(new window.Event("click",{bubbles:true}));});
    }
    assert.deepEqual(calls.map(c=>({route:c.route,action:c.body.action})),[{route:"/api/inbox/messages/70991/decision",action:"receipt"},{route:"/api/inbox/messages/70991/decision",action:"update"}]);
    assert.doesNotMatch(container.textContent,/The operation failed/);
  });
});


test("review totals render as one formatted number without concatenated counters",async()=>{
  fixture({pending:1318});
  await mounted(React.createElement(InboxIntelligence),async container=>{
    assert.match(container.querySelector(".inbox-status").textContent,/1,318 emails need you/);
    assert.match(container.querySelector(".inbox-queue-tools select").textContent,/Waiting for you \(1,318\)/);
    assert.doesNotMatch(container.textContent,/13018/);
  });
});


test("Analytics response replacement cannot restart refresh coordination in the persistent shell",async()=>{
  const ActualRefresh=load(path.join(sourceRoot,"components/analytics/AnalyticsRefresh.tsx")).AnalyticsRefresh;
  const originalRefresh=mocks["@/components/analytics/AnalyticsRefresh"].AnalyticsRefresh;
  const originalRouter=mocks["next/navigation"].useRouter;
  const previousChannel=globalThis.BroadcastChannel;
  const channels=[];
  globalThis.BroadcastChannel=class {constructor(){channels.push(this);}close(){this.closed=true;}};
  mocks["@/components/analytics/AnalyticsRefresh"].AnalyticsRefresh=ActualRefresh;
  // Next can return a new contextual router wrapper after a route response.
  mocks["next/navigation"].useRouter=()=>({...router});
  serverRead=async(route,fallback)=>route==="/api/analytics"?{}:fallback;
  const Layout=load(path.join(sourceRoot,"app/app/layout.tsx")).default;
  const Page=load(path.join(sourceRoot,"app/app/analytics/page.tsx")).default;
  const response=async generation=>Layout({children:React.cloneElement(await Page({searchParams:Promise.resolve({})}),{key:generation})});
  const before=projectionRefreshes;
  try{
    pathname="/app/analytics";
    await mounted(await response(0),async(container,window,root)=>{
      assert.equal(projectionRefreshes,before);
      for(let generation=1;generation<=4;generation++){
        const tree=await response(generation);
        await act(async()=>{root.render(tree);});
      }
      assert.equal(projectionRefreshes,before,"server page replacement must settle without requesting another response");
      assert.equal(channels.length,1,"one persistent evidence listener, independent of page replacements");
      pathname="/app/applications/inbox";
      const inbox=await Layout({children:React.createElement("h1",null,"Fictional Inbox")});
      await act(async()=>{root.render(inbox);});
      await act(async()=>{window.dispatchEvent(new window.Event("focus"));});
      assert.equal(projectionRefreshes,before,"Analytics must not refresh other routes");
      assert.equal(channels[0].closed,true);
      pathname="/app/analytics";
      const back=await response(5);
      await act(async()=>{root.render(back);});
      assert.equal(projectionRefreshes,before+1,"return navigation refreshes exactly once");
    });
    assert.ok(channels.every(channel=>channel.closed));
  }finally{
    mocks["@/components/analytics/AnalyticsRefresh"].AnalyticsRefresh=originalRefresh;
    mocks["next/navigation"].useRouter=originalRouter;
    globalThis.BroadcastChannel=previousChannel;
    pathname="/app/analytics";
  }
});


test("Analytics supplemental reader uses complete identities and sends only aggregates to the UI",async()=>{
  const {readAnalyticsSupplement}=load(path.join(sourceRoot,"lib/analyticsRead.ts"));
  const d={as_of:"2026-10-27T19:00:00Z",timezone:"America/Los_Angeles",start:"2026-10-26",end:"2026-10-27",days:"custom",family:null,total_submitted:2,submitted:2,week_total:2};
  const calls=[];
  serverRead=async(route)=>{calls.push(route);return {items:[{key:"job:1",applied_at:"2026-10-26T18:00:00Z",company:"Private fictional label"},{key:"external:2",applied_at:"2026-10-27T18:00:00Z"}]};};
  const result=await readAnalyticsSupplement(d,"daily");
  assert.deepEqual(calls,["/api/inbox/applications"]);
  assert.equal(result.timeline.reduce((sum,p)=>sum+p.count,0),2);
  assert.doesNotMatch(JSON.stringify(result),/job:1|external:2|Private fictional label/);
  serverRead=async()=>({items:[]});
  assert.equal(await readAnalyticsSupplement(d,"daily"),null);
});

test("Analytics role detail reads every page and refuses changed or duplicated snapshots",async()=>{
  const {readAnalyticsSupplement}=load(path.join(sourceRoot,"lib/analyticsRead.ts"));
  const d={as_of:"2026-10-27T19:00:00Z",timezone:"America/Los_Angeles",start:"2026-09-01",end:"2026-09-30",days:"custom",family:"SOFTWARE_ENGINEERING",submitted:101,week_total:0};
  const row=i=>({key:`job:${i}`,submitted_at:"2026-09-03T12:00:00Z"});
  const queries=[];
  serverRead=async(route,fallback,q)=>{queries.push(q);return {record_total:101,records:q.offset?[row(100)]:Array.from({length:100},(_,i)=>row(i))};};
  const result=await readAnalyticsSupplement(d,"weekly");
  assert.equal(result.timeline.reduce((sum,p)=>sum+p.count,0),101);
  assert.deepEqual(queries.map(q=>q.offset??"0"),["0","100"]);
  assert.ok(queries.every(q=>q.records==="1"&&q.family===d.family&&q.days==="all"));
  serverRead=async(route,fallback,q)=>({record_total:q.offset?102:101,records:[row(0)]});
  assert.equal(await readAnalyticsSupplement(d,"weekly"),null);
  serverRead=async(route,fallback,q)=>({record_total:101,records:q.offset?[row(0)]:Array.from({length:100},(_,i)=>row(i))});
  assert.equal(await readAnalyticsSupplement(d,"weekly"),null);
});
