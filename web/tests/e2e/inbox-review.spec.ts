import { expect } from "@playwright/test";
import { test } from "./helpers";

// All Inbox requests and mutations below are fictional and intercepted.
async function inboxFixture(page: import("@playwright/test").Page, options: {lastSync?: string | null} = {}) {
  const reviewed: number[]=[];
  const submitted: Record<string,unknown>[]=[];
  const filed: Record<string,unknown>[]=[];
  const previews: Record<string,unknown>[]=[];
  const syncs: number[]=[];
  const windows: number[]=[];
  const searches: string[]=[];
  const added: Record<string,unknown>[]=[];
  const applications=[{key:"job:1",company:"Fictional Labs",title:"Fictional engineer",requisition_id:"FIX-1",applied_at:"2026-01-01T12:00:00Z",status:"applied"},
                      {key:"job:2",company:"Imaginary Systems",title:"Fictional developer",requisition_id:"IMG-2",applied_at:"2026-01-03T12:00:00Z",status:"applied"}];
  const rows=Array.from({length:107},(_,i)=>({id:i+1,received_at:"2026-01-10T12:00:00Z",sender:"Fictional Talent <fixture@example.test>",subject:`Fictional interview ${i+1} at Fictional Labs`,snippet:"Please schedule an interview for requisition FIX-1.",classification:"interview",requisition_id:"FIX-1",decision:"review",candidate_keys:["job:1"],reason:"Matched by its job ID; positive outcomes need your confirmation",selected_application_key:null}));
  const recorded={id:500,received_at:"2026-01-11T12:00:00Z",sender:"Wayfern Talent <no-reply@ashbyhq.example>",subject:"Update on your application at Wayfern",snippet:"Thank you for applying",classification:"rejection",requisition_id:null,decision:"automatic",candidate_keys:["job:2"],reason:"Clear rejection matched by its exact title",selected_application_key:"job:2"};
  const lastSync=options.lastSync===undefined?new Date().toISOString():options.lastSync;
  await page.route("**/api/inbox/**",async route=>{
    const request=route.request(); const url=new URL(request.url()); const path=url.pathname;
    let body:unknown;
    const pending=rows.filter(row=>!reviewed.includes(row.id));
    if(path==="/api/inbox/connection") body={available:true,connected:true,state:"ready",email:"fixture@example.test",last_synced_at:syncs.length?new Date().toISOString():lastSync,following_changes:true,last_error:null,auto_outcomes_enabled:false,automation_available:false,auto_rejections:true,coverage:{days:windows.at(-1)??0,scope:"job_mail",includes_spam_trash:false,gmail:407,in_ace:407,missing:0,complete:true,checked_at:new Date().toISOString()}};
    else if(path==="/api/inbox/applications"&&request.method()==="POST"){const data=request.postDataJSON();added.push(data);reviewed.push(data.message_id);body={event_id:2,application_key:"external:9",status:data.status,created:true};}
    else if(path==="/api/inbox/applications")body={items:applications};
    else if(path==="/api/inbox/events")body={items:[]};
    else if(/^\/api\/inbox\/messages\/\d+\/full$/.test(path)){
      const selected=Number(path.split("/")[4])===recorded.id?recorded:rows.find(row=>row.id===Number(path.split("/")[4]))??rows[0];
      body={sender:selected.sender,to:"fixture@example.test",subject:selected.subject,received_at:"2026-01-10T12:00:00Z",text:"Hello Fictional Labs,\n\nPlease schedule an interview for requisition FIX-1.\n\nThe fictional recruiting team",document:"<!doctype html><html><head><meta charset=\"utf-8\"></head><body><p>Hello Fictional Labs,</p><p>Please schedule an interview for requisition FIX-1.</p><p>The fictional recruiting team</p></body></html>",format:"html",blocked_images:0,message_id_header:"<fixture-1@example.test>",thread_id:"thread-1"};
    }
    else if(/^\/api\/inbox\/messages\/\d+$/.test(path))body=Number(path.split("/").pop())===recorded.id?recorded:rows[0];
    else if(path==="/api/inbox/messages"){
      const decision=url.searchParams.get("decision")??"all";
      const q=url.searchParams.get("q");
      if(q)searches.push(q);
      const view=decision==="auto"?(pending.length?"pending":"recruiting"):decision;
      const listed=(view==="automatic"?[recorded]:pending).filter(row=>!q||row.subject.toLowerCase().includes(q.toLowerCase()));
      const offset=Number(url.searchParams.get("offset")??0);
      body={items:listed.slice(offset,offset+50),total:listed.length,offset,has_more:offset+50<listed.length,view,latest_received_at:"2026-01-11T12:00:00Z",counts:{stored:407,needs_review:pending.length,automatic:1,manual:0,reviewed:reviewed.length,receipts:0,updates:0,stale:0}};
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
  return {submitted,filed,previews,syncs,windows,searches,added};
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
