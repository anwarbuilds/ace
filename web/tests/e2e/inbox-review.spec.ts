import { expect } from "@playwright/test";
import { test } from "./helpers";

// All Inbox requests and mutations below are fictional and intercepted.
async function inboxFixture(page: import("@playwright/test").Page) {
  const reviewed: number[]=[];
  const submitted: Record<string,unknown>[]=[];
  const previews: Record<string,unknown>[]=[];
  const applications=[{key:"job:1",company:"Fictional Labs",title:"Fictional engineer",requisition_id:"FIX-1",applied_at:"2026-01-01T12:00:00Z",status:"applied"},
                      {key:"job:2",company:"Imaginary Systems",title:"Fictional developer",requisition_id:"IMG-2",applied_at:"2026-01-03T12:00:00Z",status:"applied"}];
  const rows=Array.from({length:107},(_,i)=>({id:i+1,received_at:"2026-01-10T12:00:00Z",sender:"fixture@example.test",subject:`Fictional interview ${i+1}`,snippet:"Please schedule an interview for requisition FIX-1.",classification:"interview",requisition_id:"FIX-1",decision:"review",candidate_keys:["job:1"],reason:"Matched by its job ID; positive outcomes need your confirmation",selected_application_key:null}));
  await page.route("**/api/inbox/**",async route=>{
    const request=route.request(); const url=new URL(request.url()); const path=url.pathname;
    let body:unknown;
    if(path==="/api/inbox/connection") body={available:true,connected:true,state:"ready",email:"fixture@example.test",last_synced_at:null,last_error:null,auto_outcomes_enabled:false,automation_available:false,auto_rejections:true};
    else if(path==="/api/inbox/applications")body={items:applications};
    else if(path==="/api/inbox/events")body={items:[]};
    else if(/^\/api\/inbox\/messages\/\d+\/full$/.test(path))body={text:"Hello,\n\nPlease schedule an interview for requisition FIX-1.\n\nThe fictional recruiting team"};
    else if(path==="/api/inbox/messages"){
      const pending=rows.filter(row=>!reviewed.includes(row.id));
      const offset=Number(url.searchParams.get("offset")??0);
      body={items:pending.slice(offset,offset+50),total:pending.length,offset,has_more:offset+50<pending.length,counts:{stored:407,needs_review:pending.length,automatic:0,reviewed:reviewed.length,receipts:0,stale:0}};
    }else if(path==="/api/inbox/review"){
      const data=request.postDataJSON();submitted.push(data);reviewed.push(data.message_id);
      body={event_id:1,application_key:data.application_key,status:data.status};
    }else if(path==="/api/inbox/backfill"){
      previews.push(request.postDataJSON());body={next_page_token:"fictional-next-page",preview_only:true};
    }else throw new Error(`Unexpected fictional Inbox request: ${path}`);
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  });
  return {submitted,previews};
}

test("default review queue exposes all pending messages beyond the latest 100",async({page})=>{
  await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await expect(page.getByLabel("Email view")).toHaveValue("pending");
  await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("107");
  await expect(page.locator(".inbox-mail")).toHaveCount(50);
  await expect(page.getByRole("heading",{name:"ACE thinks this is about"})).toBeVisible();
  await page.getByRole("button",{name:"Next messages"}).click();
  await expect(page.locator(".inbox-mail").first()).toContainText("Fictional interview 51");
  await page.getByRole("button",{name:"Next messages"}).click();
  await expect(page.locator(".inbox-mail")).toHaveCount(7);
  await expect(page.getByRole("button",{name:"Next messages"})).toBeDisabled();
});

test("one click records the outcome for the suggested application",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await expect(page.locator(".inbox-full")).toContainText("The fictional recruiting team");
  await page.getByRole("button",{name:"Interview",exact:true}).click();
  await expect(page.getByRole("button",{name:/Waiting for you/})).toContainText("106");
  expect(fixture.submitted).toEqual([{message_id:1,application_key:"job:1",status:"interviewing",expected_status:"applied",confirmed:true,kind:"interview"}]);
});

test("Change picks a different application before recording",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByRole("button",{name:"Change"}).click();
  await page.getByLabel("Search your applications").fill("Imaginary");
  await page.locator(".inbox-options button").filter({hasText:"Imaginary Systems"}).click();
  await expect(page.locator(".inbox-target")).toContainText("Imaginary Systems");
  await page.getByRole("button",{name:"Rejected",exact:true}).click();
  await expect.poll(()=>fixture.submitted.length).toBe(1);
  expect(fixture.submitted[0]).toMatchObject({application_key:"job:2",status:"rejected",kind:"rejection"});
});

test("changing the historical window resets the import page token",async({page})=>{
  const fixture=await inboxFixture(page);
  await page.goto("/app/applications/inbox");
  await page.getByRole("button",{name:"Import past email",exact:true}).click();
  await expect(page.getByRole("button",{name:"Import next page"})).toBeEnabled();
  await page.getByLabel("Import email from the last").selectOption("90");
  await expect(page).toHaveURL(/days=90/);
  await page.getByRole("button",{name:"Import past email",exact:true}).click();
  expect(fixture.previews).toEqual([{days:30,page_token:null},{days:90,page_token:null}]);
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
