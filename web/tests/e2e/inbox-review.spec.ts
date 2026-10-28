import { expect } from "@playwright/test";
import { test, setThemeCookies } from "./helpers";
import fs from "node:fs/promises";
import path from "node:path";

// All Inbox requests and mutations below are fictional and intercepted.
async function inboxFixture(page: import("@playwright/test").Page, options: {lastSync?: string | null; ambiguous?:boolean; unlinked?:boolean; company?:boolean; backgroundSyncEnabled?:boolean} = {}) {
  const reviewed: number[]=[];
  const submitted: Record<string,unknown>[]=[];
  const filed: Record<string,unknown>[]=[];
  const previews: Record<string,unknown>[]=[];
  const syncs: number[]=[];
  const windows: number[]=[];
  const searches: string[]=[];
  const added: Record<string,unknown>[]=[];
  const undos:number[]=[];
  let companyUndone=false;
  const applications=[{key:"job:1",company:"Fictional Labs",title:"Fictional engineer",requisition_id:"FIX-1",applied_at:"2026-01-01T12:00:00Z",status:"applied"},
                      {key:"job:2",company:"Imaginary Systems",title:"Fictional developer",requisition_id:"IMG-2",applied_at:"2026-01-03T12:00:00Z",status:"applied"}];
  if(options.ambiguous||options.company)applications.push({...applications[0],key:"job:3",title:"Fictional developer"});
  const rows=Array.from({length:107},(_,i)=>({id:i+1,received_at:"2026-01-10T12:00:00Z",sender:"Fictional Talent <fixture@example.test>",subject:`Fictional interview ${i+1} at Fictional Labs`,snippet:"Please schedule an interview for requisition FIX-1.",classification:"interview",requisition_id:"FIX-1",decision:"review",candidate_keys:options.ambiguous?["job:1","job:3"]:["job:1"],reason:"Matched by its job ID; positive outcomes need your confirmation",selected_application_key:null,understanding:{classification_reason:"The employer invites the candidate to an interview.",classification_state:"recognized",matching_state:options.ambiguous?"ambiguous":"unlinked",workflow_state:"awaiting_link",update_policy:"confirmation_required",review_reason:"Two applications share this requisition. Choose the correct application.",evidence_source:"retained_excerpt",evidence_excerpt:"Please schedule an interview for requisition FIX-1."}}));
  const recorded={id:500,received_at:"2026-01-11T12:00:00Z",sender:"Wayfern Talent <no-reply@ashbyhq.example>",subject:"Update on your application at Wayfern",snippet:"Thank you for applying",classification:"rejection",requisition_id:null,decision:"automatic",candidate_keys:["job:2"],reason:"Clear rejection matched by its exact title",selected_application_key:"job:2"};
  const unlinked={id:600,received_at:"2025-12-15T12:00:00Z",sender:"Fictional Labs Talent <talent@fictional.example>",subject:"Earlier application update at Fictional Labs",snippet:"We will not move forward with your application.",classification:"rejection",requisition_id:null,decision:"unlinked",candidate_keys:[],reason:"Recognized rejection; all recorded applications at this employer were submitted after this email. Retained as unlinked evidence, excluded from application outcomes",selected_application_key:null,understanding:{decision_type:"Automatic classification",classification_reason:"The employer communicates a rejection.",classification_state:"recognized",matching_state:"unlinked",workflow_state:"unlinked_outcome",update_policy:"no_status_change",review_reason:null,evidence_source:"retained_excerpt",evidence_excerpt:"We will not move forward with your application."}};
  const companyMessage={id:700,received_at:"2026-01-12T12:00:00Z",sender:"Fictional Labs Talent <talent@fictional.example>",subject:"Company decision from Fictional Labs",snippet:"We will not move forward with your application.",classification:"rejection",requisition_id:null,decision:"company_rejection",candidate_keys:["job:1","job:3"],reason:"Company rejection recorded; the email does not need a role-level application match",selected_application_key:null,understanding:{decision_type:"Automatic classification",classification_reason:"The employer communicates a rejection.",classification_state:"recognized",matching_state:"company",workflow_state:"company_recorded",update_policy:"company_recorded",review_reason:null,evidence_source:"retained_excerpt",evidence_excerpt:"We will not move forward with your application."}};
  const companyEvent={id:77,application_key:"email:700",gmail_message_id:700,kind:"company_rejection",before:null,after:null,actor:"verified_automation",reason:"Rejection received from Fictional Labs; no individual application changed",recorded_at:"2026-01-12T12:00:00Z",undo_of_id:null,scope:"company",company:"Fictional Labs"};
  const companyState=()=>companyUndone?{...companyMessage,decision:"review",reason:"You undid the company rejection",understanding:{...companyMessage.understanding,decision_type:"Owner decision",matching_state:"ambiguous",workflow_state:"owner_review",update_policy:"confirmation_required",review_reason:"You undid the company rejection"}}:companyMessage;
  const lastSync=options.lastSync===undefined?new Date().toISOString():options.lastSync;
  await page.route("**/api/inbox/**",async route=>{
    const request=route.request(); const url=new URL(request.url()); const path=url.pathname;
    let body:unknown;
    const pending=[...(options.company&&companyUndone?[companyState()]:[]),...rows.filter(row=>!reviewed.includes(row.id))];
    if(path==="/api/inbox/connection") body={available:true,connected:true,state:"ready",email:"fixture@example.test",last_synced_at:syncs.length?new Date().toISOString():lastSync,following_changes:true,background_sync_enabled:options.backgroundSyncEnabled,last_error:null,auto_outcomes_enabled:false,automation_available:false,auto_rejections:true,coverage:{days:windows.at(-1)??0,scope:"job_mail",includes_spam_trash:false,gmail:407,in_ace:407,missing:0,complete:true,checked_at:new Date().toISOString()}};
    else if(path==="/api/inbox/applications"&&request.method()==="POST"){const data=request.postDataJSON();added.push(data);reviewed.push(data.message_id);body={event_id:2,application_key:"external:9",status:data.status,created:true};}
    else if(path==="/api/inbox/applications")body={items:applications};
    else if(path==="/api/inbox/events")body={items:options.company?[companyEvent,...(companyUndone?[{...companyEvent,id:78,kind:"undo",actor:"owner",undo_of_id:77,scope:"email",company:null}]:[])]:[]};
    else if(path==="/api/inbox/events/77/undo"&&request.method()==="POST"){undos.push(77);companyUndone=true;body={event_id:78,status:"review"};}
    else if(/^\/api\/inbox\/messages\/\d+\/full$/.test(path)){
      const id=Number(path.split("/")[4]);
      const selected=id===recorded.id?recorded:id===unlinked.id?unlinked:id===companyMessage.id?companyState():rows.find(row=>row.id===id)??rows[0];
      const historical=selected.decision==="unlinked"||id===companyMessage.id;
      const content=historical?selected.snippet:"Please schedule an interview for requisition FIX-1.";
      body={sender:selected.sender,to:"fixture@example.test",subject:selected.subject,received_at:selected.received_at,text:`Hello Fictional Labs,\n\n${content}\n\nThe fictional recruiting team`,document:`<!doctype html><html><head><meta charset="utf-8"></head><body><p>Hello Fictional Labs,</p><p>${content}</p><p>The fictional recruiting team</p></body></html>`,current_reading:{classification:historical?"rejection":"interview",reason:historical?"The employer communicates a rejection.":"The employer requests an interview time.",variant:historical?"explicit_rejection":"invitation",excerpt:content,complete:true},format:"html",blocked_images:0,message_id_header:`<fixture-${id}@example.test>`,thread_id:`thread-${id}`};
    }
    else if(/^\/api\/inbox\/messages\/\d+$/.test(path)){const id=Number(path.split("/").pop());body=id===recorded.id?recorded:id===unlinked.id?unlinked:id===companyMessage.id?companyState():rows[0];}
    else if(path==="/api/inbox/messages"){
      const decision=url.searchParams.get("decision")??"all";
      const q=url.searchParams.get("q");
      if(q)searches.push(q);
      const view=decision==="auto"?(pending.length?"pending":"recruiting"):decision;
      const historical=options.unlinked?[unlinked]:[];
      const company=options.company&&!companyUndone?[companyState()]:[];
      const listed=(view==="automatic"?[recorded,...company]:view==="company_rejection"?company:view==="unlinked_outcome"?historical:["recruiting","all"].includes(view)?[...pending,...historical,...company]:pending).filter(row=>!q||row.subject.toLowerCase().includes(q.toLowerCase()));
      const offset=Number(url.searchParams.get("offset")??0);
      body={items:listed.slice(offset,offset+50),total:listed.length,offset,has_more:offset+50<listed.length,view,latest_received_at:"2026-01-11T12:00:00Z",counts:{stored:407,needs_review:pending.length,automatic:1+company.length,manual:0,reviewed:reviewed.length,receipts:0,updates:0,unlinked:historical.length,company_rejections:company.length,stale:0}};
    }else if(path==="/api/inbox/review"){
      const data=request.postDataJSON();submitted.push(data);reviewed.push(data.message_id);
      body={event_id:1,application_key:data.application_key,status:data.status};
    }else if(/^\/api\/inbox\/messages\/\d+\/decision$/.test(path)){
      const data=request.postDataJSON();filed.push(data);reviewed.push(Number(path.split("/")[4]));
      body={id:Number(path.split("/")[4]),decision:data.action};
    }else if(path==="/api/inbox/sync"){
      syncs.push(Date.now());windows.push(request.postDataJSON().days);body={state:"ready",counts:{automatic:1,ignored:2},remaining:0,partial:false,coverage:{days:windows.at(-1),scope:"job_mail",includes_spam_trash:false,gmail:407,in_ace:407,missing:0,complete:true,checked_at:new Date().toISOString()},as_of:new Date().toISOString()};
    }else if(path==="/api/inbox/recheck"){
      body={checked:0,remaining:0,counts:{}};
    }else if(path==="/api/inbox/backfill"){
      previews.push(request.postDataJSON());body={next_page_token:"fictional-next-page",preview_only:true};
    }else throw new Error(`Unexpected fictional Inbox request: ${path}`);
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  });
  return {submitted,filed,previews,syncs,windows,searches,added,undos,applications};
}

test("default review queue exposes all pending messages beyond the latest 100",async({page})=>{
  await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await expect(page.getByLabel("Email view")).toHaveValue("pending");
  await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("107");
  await expect(page.locator(".inbox-status")).toContainText("107 emails need you");
  await expect(page.locator(".inbox-mail")).toHaveCount(50);
  await expect(page.getByRole("heading",{name:"ACE thinks this is about"})).toBeVisible();
  await page.getByRole("button",{name:"Next messages"}).click();
  await expect(page.locator(".inbox-mail").first()).toContainText("Fictional interview 51");
  await page.getByRole("button",{name:"Next messages"}).click();
  await expect(page.locator(".inbox-mail")).toHaveCount(7);
  await expect(page.getByRole("button",{name:"Next messages"})).toBeDisabled();
});

test("the email is shown as it arrived, in a frame that runs no scripts",async({page})=>{
  await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  const frame=page.locator("iframe.inbox-frame");
  await expect(frame).toHaveAttribute("sandbox","allow-same-origin allow-popups allow-popups-to-escape-sandbox");
  await expect(page.frameLocator("iframe.inbox-frame").locator("body")).toContainText("The fictional recruiting team");
  await expect(page.getByRole("link",{name:"Open in Gmail"})).toHaveAttribute("href",/rfc822msgid%3Afixture-1%40example\.test/);
  await page.getByRole("button",{name:"Show as plain text"}).click();
  await expect(page.locator(".inbox-full")).toContainText("The fictional recruiting team");
});

test("one click records the outcome for the suggested application",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await expect(page.getByRole("button",{name:/^Interview/})).toHaveClass(/suggested/);
  await page.getByRole("button",{name:/^Interview/}).click();
  await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("106");
  expect(fixture.submitted).toEqual([{message_id:1,application_key:"job:1",status:"interviewing",expected_status:"applied",confirmed:true,kind:"interview"}]);
});

test("an acknowledgement or status update is filed without touching the application",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  const decisions=page.getByRole("group",{name:"What is this email?",exact:true});
  await decisions.getByRole("button",{name:/^Acknowledgement/}).click();
  await expect.poll(()=>fixture.filed.length).toBe(1);
  await decisions.getByRole("button",{name:/^Status update/}).click();
  await expect.poll(()=>fixture.filed.length).toBe(2);
  expect(fixture.filed).toEqual([{action:"receipt"},{action:"update"}]);
  expect(fixture.submitted).toEqual([]);
});

test("Change picks a different application before recording",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByRole("button",{name:"Change"}).click();
  await page.getByLabel("Search your applications").fill("Imaginary");
  await page.locator(".inbox-options button").filter({hasText:"Imaginary Systems"}).click();
  await expect(page.locator(".inbox-target")).toContainText("Imaginary Systems");
  await expect(page.getByText("This email does not name Imaginary Systems.",{exact:false})).toBeVisible();
  page.once("dialog",dialog=>dialog.dismiss());
  await page.getByRole("button",{name:/^Rejection/}).click();
  expect(fixture.submitted).toEqual([]);
  page.once("dialog",dialog=>dialog.accept());
  await page.getByRole("button",{name:/^Rejection/}).click();
  await expect.poll(()=>fixture.submitted.length).toBe(1);
  expect(fixture.submitted[0]).toMatchObject({application_key:"job:2",status:"rejected",kind:"rejection"});
});

test("opening the page checks Gmail once when the last check is old",async({page})=>{
  const fixture=await inboxFixture(page,{lastSync:"2026-01-01T00:00:00Z"});
  await page.goto("/app/applications/inbox");
  await expect.poll(()=>fixture.syncs.length).toBe(1);
  await expect(page.locator(".inbox-status")).toContainText("Found 3 new emails: 1 recorded automatically, 2 with no application outcome.");
  await page.waitForTimeout(500);
  expect(fixture.syncs.length).toBe(1);
  await page.getByRole("button",{name:"Sync now"}).click();
  await expect.poll(()=>fixture.syncs.length).toBe(2);
});

test("a recent check does not sync again, and search reaches every imported email",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await expect(page.locator(".inbox-status")).toContainText("Gmail checked just now");
  await page.getByLabel("Search email").fill("interview 107");
  await page.getByRole("button",{name:"Search",exact:true}).click();
  await expect(page).toHaveURL(/q=interview\+107/);
  await expect(page.locator(".inbox-mail")).toHaveCount(1);
  expect(fixture.searches).toContain("interview 107");
  expect(fixture.syncs).toEqual([]);
});

test("a link from Analytics opens that exact email",async({page})=>{
  await inboxFixture(page);
  await page.goto("/app/applications/inbox?message=500");
  await expect(page.locator(".inbox-inspector h2")).toHaveText("Update on your application at Wayfern");
  await expect(page.getByText("ACE recorded this email.")).toBeVisible();
});

test("full history is the default and narrower checks never replace it silently",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByText("Verify mailbox history").click();
  await page.getByRole("button",{name:"Verify selected history",exact:true}).click();
  await expect.poll(()=>fixture.windows.length).toBe(1);
  await expect(page.getByRole("button",{name:"Verify selected history",exact:true})).toBeEnabled();
  await page.getByLabel("Email coverage").selectOption("90");
  await expect(page).toHaveURL(/days=90/);
  await page.getByRole("button",{name:"Verify selected history",exact:true}).click();
  await expect.poll(()=>fixture.windows.length).toBe(2);
  expect(fixture.windows).toEqual([0,90]);
  await expect(page.locator(".inbox-status")).not.toContainText("All caught up");
  expect(fixture.previews).toEqual([]);
  await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("107");
});

test("selecting another email starts again from its own suggestion",async({page})=>{
  await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByRole("button",{name:"Change"}).click();
  await expect(page.getByLabel("Search your applications")).toBeVisible();
  await page.locator(".inbox-mail").nth(1).click();
  await expect(page.getByLabel("Search your applications")).toHaveCount(0);
  await expect(page.locator(".inbox-target")).toContainText("Fictional Labs");
});

test("an application missing from ACE is added from the email with its outcome",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByRole("button",{name:"Change"}).click();
  await page.getByRole("button",{name:"Not in ACE yet? Add it from this email"}).click();
  await page.getByLabel("Company",{exact:true}).fill("Wayfern Fiction");
  await page.getByLabel("Role",{exact:true}).fill("Fictional engineer");
  page.once("dialog",dialog=>dialog.accept());
  await page.getByRole("button",{name:/^Rejection/}).click();
  await expect.poll(()=>fixture.added.length).toBe(1);
  expect(fixture.added[0]).toMatchObject({message_id:1,company:"Wayfern Fiction",title:"Fictional engineer",status:"rejected",kind:"rejection",applied_on:null});
  expect(fixture.submitted).toEqual([]);
});


for(const theme of ["light","dark"] as const){
  test(`${theme}: company rejection is recorded without a role choice and Undo returns only its email to review`,async({page,context,baseURL})=>{
    await setThemeCookies(context,baseURL!,theme);
    const fixture=await inboxFixture(page,{company:true});
    await page.setViewportSize({width:1672,height:941});
    await page.goto("/app/applications/inbox");
    await expect(page.locator(".inbox-status")).toContainText("107 emails need you");
    await expect(page.getByRole("button",{name:/Recorded automatically/})).toContainText("2");
    await page.getByLabel("Email view").selectOption("company_rejection");
    await expect(page).toHaveURL(/decision=company_rejection/);
    await expect(page.locator(".inbox-mail")).toHaveCount(1);
    const inspector=page.locator(".inbox-inspector");
    await expect(inspector.locator(".inbox-state")).toHaveText("Company rejection recorded");
    await expect(inspector.getByRole("heading",{name:"ACE recorded the company rejection."})).toBeVisible();
    await expect(inspector).toContainText("Fictional Labs: rejection received. No role choice is needed.");
    await expect(page.getByLabel("ACE understanding")).toContainText("Application linkage: company. A company rejection was recorded.");
    await expect(page.getByLabel("Search your applications")).toHaveCount(0);
    await expect(page.getByRole("button",{name:/^Rejection/})).toHaveCount(0);
    await expect(page.frameLocator("iframe.inbox-frame").locator("body")).toContainText("We will not move forward with your application.");
    const root=path.resolve("../artifacts/inbox-intelligence-validation");
    await fs.mkdir(root,{recursive:true});
    await page.screenshot({path:path.join(root,`${theme}-inbox-company-rejection.png`),fullPage:true});
    await page.getByRole("button",{name:"Undo this change",exact:true}).click();
    await expect.poll(()=>fixture.undos).toEqual([77]);
    await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("108");
    await expect(page.getByRole("button",{name:/Recorded automatically/})).toContainText("1");
    await expect(page.locator(".inbox-mail")).toHaveCount(0);
    await page.getByLabel("Email view").selectOption("pending");
    await expect(page.locator(".inbox-mail").first()).toContainText("Company decision from Fictional Labs");
    await expect(page.locator(".inbox-inspector .inbox-state")).toHaveText("Needs you");
    await expect(page.getByRole("button",{name:/^Rejection/})).toBeDisabled();
    expect(fixture.submitted).toEqual([]);
    expect(fixture.added).toEqual([]);
    expect(fixture.filed).toEqual([]);
    expect(fixture.applications.map(application=>application.status)).toEqual(["applied","applied","applied"]);
  });

  test(`${theme}: recognized historical evidence remains searchable without an owner task`,async({page,context,baseURL})=>{
    await setThemeCookies(context,baseURL!,theme);
    const fixture=await inboxFixture(page,{unlinked:true,backgroundSyncEnabled:true});
    await page.setViewportSize({width:1672,height:941});
    await page.goto("/app/applications/inbox");
    await expect(page.locator(".inbox-status")).toContainText("107 emails need you");
    await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("107");
    const evidence=page.getByRole("button",{name:"1 recognized historical outcomes without an eligible application",exact:true});
    await expect(evidence.locator("..")).toContainText("excluded from application outcomes in Analytics. Linking is optional.");
    await evidence.click();
    await expect(page).toHaveURL(/decision=unlinked_outcome/);
    await expect(page.getByLabel("Email view")).toHaveValue("unlinked_outcome");
    await expect(page.locator(".inbox-mail")).toHaveCount(1);
    await expect(page.locator(".inbox-mail")).not.toHaveClass(/needs/);
    const inspector=page.locator(".inbox-inspector");
    await expect(inspector.locator(".inbox-state")).toHaveText("Recognized, unlinked");
    await expect(page.getByLabel("ACE understanding")).toContainText("Application linkage: unlinked. No application status changed.");
    await expect(inspector).toContainText("No application outcome was recorded. Linking is optional; the email remains searchable.");
    await expect(inspector).not.toContainText("Why it waits:");
    await expect(page.getByRole("button",{name:/^Rejection/})).toBeDisabled();
    await expect(page.getByRole("button",{name:/^Decide later/})).toHaveCount(0);
    await expect(page.frameLocator("iframe.inbox-frame").locator("body")).toContainText("We will not move forward with your application.");
    const root=path.resolve("../artifacts/inbox-intelligence-validation");
    await fs.mkdir(root,{recursive:true});
    await page.screenshot({path:path.join(root,`${theme}-inbox-unlinked.png`),fullPage:true});
    await page.getByRole("button",{name:"How ACE decides",exact:true}).click();
    await expect(page.getByText("While sync is on, ACE checks Gmail about every three minutes even when this page is closed.",{exact:false})).toBeVisible();
    await expect(page.getByText("Google limits or a large import can delay a check.",{exact:false})).toBeVisible();
    await page.screenshot({path:path.join(root,`${theme}-inbox-background-rules.png`),fullPage:true});
    expect(fixture.submitted).toEqual([]);
    expect(fixture.filed).toEqual([]);
    expect(fixture.added).toEqual([]);
    expect(fixture.syncs).toEqual([]);
  });

  test(`${theme}: intent, linkage and authorization remain separate in the existing Inbox`,async({page,context,baseURL})=>{
    await setThemeCookies(context,baseURL!,theme);
    const fixture=await inboxFixture(page,{ambiguous:true});
    await page.setViewportSize({width:1672,height:941});
    await page.goto("/app/applications/inbox");
    const explanation=page.getByLabel("ACE understanding");
    await expect(explanation).toContainText("Application linkage: ambiguous");
    await expect(explanation).toContainText("Decision needed: Two applications share this requisition");
    await expect(explanation.locator("blockquote")).toContainText("Please schedule an interview");
    await expect(page.getByRole("button",{name:/^Rejection/})).toBeDisabled();
    expect(fixture.submitted).toEqual([]);
    expect(fixture.filed).toEqual([]);
    const root=path.resolve("../artifacts/inbox-intelligence-validation");
    await fs.mkdir(root,{recursive:true});
    await page.screenshot({path:path.join(root,`${theme}-inbox.png`),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await expect(explanation).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
    await page.screenshot({path:path.join(root,`${theme}-inbox-mobile.png`),fullPage:true});
  });
}
