import fs from "node:fs";
import path from "node:path";
import { expect } from "@playwright/test";
import { DRAWN_SCAN, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

test.use({timezoneId:"America/Los_Angeles"});

const tabs = [["overview","Applications over time"],["outcomes","Applications old enough to evaluate"],["role-resume","Application outcomes by role"],["companies","Top companies in your pipeline"]] as const;
const root = path.resolve("../artifacts/analytics-validation");
fs.mkdirSync(root,{recursive:true});

for (const theme of ["light","dark"] as const) {
  test(`${theme}: four approved tab layouts use persisted evidence without browser errors`,async({page,context,baseURL})=>{
    test.setTimeout(120_000);
    await setThemeCookies(context,baseURL!,theme);
    await page.setViewportSize({width:1672,height:941});
    const errors=watchErrors(page);
    const report=await(await page.request.get("/api/analytics?days=30&tz=America%2FLos_Angeles")).json();
    const before=await(await page.request.get("/api/marks")).json();
    for (const [tab,title] of tabs) {
      await page.goto(`/app/analytics?days=30&tab=${tab}`);
      await expect(page.getByRole("heading",{name:title,exact:true})).toBeVisible();
      await expect(page.locator(".an-metric").first().locator(".an-metric-value")).toHaveText(String(report.submitted));
      await expect(page.locator(".an-metric").nth(1).locator(".an-metric-value")).toHaveText(String(report.week_total));
      await page.evaluate(()=>document.fonts.ready);
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
      expect(await page.locator('.an-tabs a[aria-current="page"]').count()).toBe(1);
      await page.screenshot({path:path.join(root,`${theme}-${tab}.png`)});
      await page.screenshot({path:path.join(root,`${theme}-${tab}-full.png`),fullPage:true});
    }
    expect((await(await page.request.get("/api/marks")).json()).applications_total).toBe(before.applications_total);
    expect(errors).toEqual([]);
  });
}

test("role, time and custom date filters are bookmarkable and keep lifetime counts",async({page})=>{
  await page.goto("/app/analytics?days=90&tab=role-resume");
  const lifetime=await page.locator(".tb-applied strong").innerText();
  await page.getByLabel("Application role family").selectOption("SOFTWARE_ENGINEERING");
  await expect(page).toHaveURL(/family=SOFTWARE_ENGINEERING/);
  await expect(page.locator(".an-tabs [aria-current='page']")).toHaveText("Role and resume");
  const data=await(await page.request.get("/api/analytics?days=90&family=SOFTWARE_ENGINEERING&tz=America%2FLos_Angeles")).json();
  await expect(page.locator(".an-metric-value").first()).toHaveText(String(data.submitted));
  await page.getByRole("button",{name:"14 days",exact:true}).click();
  await expect(page).toHaveURL(/days=14/);
  await page.getByRole("button",{name:"Choose dates"}).click();
  await page.getByLabel("From",{exact:true}).fill("2026-01-01");
  await page.getByLabel("Through",{exact:true}).fill("2026-01-31");
  await page.getByRole("button",{name:"Apply dates",exact:true}).click();
  await expect(page).toHaveURL(/days=custom/);
  await expect(page.locator(".an-metric-value").first()).toHaveText("0");
  await page.reload();
  await expect(page.getByLabel("From",{exact:true})).toHaveValue("2026-01-01");
  await expect(page.locator(".tb-applied strong")).toHaveText(lifetime);
});

test("Inbox review links open relevant ambiguity and preview filters without writes",async({page})=>{
  await page.goto("/app/analytics?tab=outcomes&days=90");
  const before=await(await page.request.get("/api/marks")).json();
  await page.getByRole("link",{name:/Ambiguous matches/}).click();
  await expect(page).toHaveURL(/decision=ambiguous/);
  await expect(page.locator(".inbox-mail")).toHaveCount(1);
  await expect(page.getByText("Analytics evidence filter:",{exact:false})).toBeVisible();
  expect((await(await page.request.get("/api/marks")).json()).applications_total).toBe(before.applications_total);
});

test("disconnected Gmail is honest, resume attribution is absent, rates unavailable",async({page})=>{
  await page.goto("/app/analytics?tab=role-resume&days=90");
  const connection=await(await page.request.get("/api/inbox/connection")).json();
  expect(connection.connected).toBe(false);
  await expect(page.locator(".an-inbox-band")).toContainText("Not connected");
  await expect(page.locator(".an-panel",{hasText:"Submitted resume versions"})).toContainText("Not recorded");
  await expect(page.getByText("Not enough comparable applications",{exact:true})).toBeVisible();
  await expect(page.locator(".an-page")).not.toContainText("96%");
});

test("company selector, verified petitions, logo asset and monogram fallback work",async({page})=>{
  await page.goto("/app/analytics?days=90&tab=companies");
  await expect(page.locator(".an-petition-chart")).toBeVisible();
  const data=await(await page.request.get("/api/analytics?days=90")).json();
  expect(data.annual.length).toBeGreaterThan(0);
  expect(data.reports.every((r:{url:string})=>new URL(r.url).hostname==="www.uscis.gov")).toBe(true);
  await expect(page.locator(".company-logo").first()).toBeVisible();
  expect((await page.request.get("/company-logos/google.ico")).ok()).toBe(true);
  await page.getByLabel("Company evidence").selectOption("Google");
  await expect(page).toHaveURL(/company=Google/);
  await expect(page.getByText("No verified USCIS approval and denial series for Google.", {exact:true})).toBeVisible();
  // The owner removed the sponsorship methodology section on 2026-10-26.
  await expect(page.getByText("Sponsorship evidence methodology")).toHaveCount(0);
  await expect(page.locator("a[href='#analytics-methodology']")).toHaveCount(0);
});

test("chart controls, data table and keyboard navigation work",async({page})=>{
  await page.goto("/app/analytics?days=30");
  await page.getByLabel("Chart interval").selectOption("weekly");
  await expect(page.getByRole("img",{name:/Unique submissions by calendar week/})).toBeVisible();
  await page.getByText("View chart data",{exact:true}).click();
  await expect(page.locator(".an-chart-details[open]")).toBeVisible();
  await page.locator(".an-tabs a").nth(1).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/tab=outcomes/);
  await expect(page.locator(".an-tabs [aria-current='page']")).toHaveText("Outcomes");
});

test("Pulls calendar preserves cards, date navigation and company-first application controls",async({page})=>{
  await page.goto("/app/pulls");
  const calendar=page.locator(".pull-calendar");
  await expect(calendar.getByRole("heading",{name:"Jump to any date"})).toBeVisible();
  const positions=await page.locator(".pull-rail").evaluate(el=>Array.from(el.children).map(child=>({text:child.textContent,y:child.getBoundingClientRect().top})));
  expect(positions[0].text).toContain("Jump to any date");
  expect(positions[1].text).toContain("Discovery status");
  expect(positions[2].text).toContain("at a glance");
  const today=await calendar.locator("input").inputValue();
  await calendar.getByRole("button",{name:"Previous month"}).click();
  await calendar.getByRole("link",{name:/View discovery history/}).first().click();
  await expect(page).toHaveURL(/date=/);
  await calendar.locator("input").fill(today);
  await expect(page).not.toHaveURL(/date=/);
  await expect(calendar.locator(".calendar-head strong")).toHaveText(new Date(`${today}T12:00:00Z`).toLocaleDateString("en-US",{month:"long",year:"numeric",timeZone:"UTC"}));
  const row=page.locator(".job-line").first();
  await expect(row.locator(".company-logo")).toBeVisible();
  await expect(row.getByRole("button",{name:/Mark applied|Clear applied/})).toBeVisible();
  expect((await row.locator(".job-company").boundingBox())!.y).toBeLessThan((await row.locator(".job-title").boundingBox())!.y);
});

for(const width of [1600,1440,1280,1024,390]) {
  test(`all tabs fit ${width}px and preserve readable controls`,async({page})=>{
    await page.setViewportSize({width,height:941});
    for(const [tab,title] of tabs){
      await page.goto(`/app/analytics?tab=${tab}&days=90`);
      await expect(page.getByRole("heading",{name:title,exact:true})).toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
      const clipped=await page.locator(".an-page").evaluate(root=>Array.from(root.querySelectorAll("h1,h2,.an-metric strong,.an-filters button,.an-tabs a")).filter(el=>el.scrollWidth>el.clientWidth+2).map(el=>el.textContent));
      expect(clipped).toEqual([]);
      if(width===390)await page.screenshot({path:path.join(root,`mobile-${tab}.png`),fullPage:true});
    }
  });
}

test("Analytics refreshes after an application is saved in another tab",async({page,context})=>{
  await page.goto("/app/analytics?days=all");
  const before=Number((await page.locator(".an-metric-value").first().innerText()).replaceAll(",",""));
  const editor=await context.newPage();
  await editor.goto("/app/opportunities?sort=company");
  const row=editor.locator('.row[data-id]:not(.grp-head)').filter({has:editor.locator('button[data-mark="applied"][aria-pressed="false"]')}).first();
  const id=await row.getAttribute("data-id");
  await editor.goto(`/app/jobs/${id}`);
  const applied=editor.locator('.status-grid button[data-mark="applied"]');
  await applied.click();
  await expect(page.locator(".an-metric-value").first()).toHaveText(String(before+1));
  await applied.click();
  await expect(page.locator(".an-metric-value").first()).toHaveText(String(before));
  await editor.close();
});

test("official logo renders locally and failed image falls back cleanly",async({page})=>{
  const data=await(await page.request.get("/api/analytics?days=90&tz=America%2FLos_Angeles")).json();
  const stamp=new Date(`${data.end}T12:00:00Z`);stamp.setUTCDate(stamp.getUTCDate()-45);
  const day=stamp.toISOString().slice(0,10);
  const url=`/app/analytics?tab=companies&days=custom&start=${day}&end=${day}`;
  await page.goto(url);
  const companies=page.locator(".an-company-table");
  const logo=companies.getByRole("img",{name:"Google logo",exact:true});
  await expect(logo).toBeVisible();
  expect(await logo.evaluate((el:HTMLImageElement)=>el.complete&&el.naturalWidth>0)).toBe(true);
  await page.route("**/company-logos/google.ico",route=>route.abort());
  await page.reload();
  await expect(companies.getByLabel("Google monogram",{exact:true})).toBeVisible();
  await expect(logo).toHaveCount(0);
});

test("Analytics data is private and uses no-store responses",async({browser,page,baseURL})=>{
  const anonymous=await browser.newContext();
  const unauthenticated=await anonymous.request.get(`${baseURL}/api/analytics`);
  expect(unauthenticated.status()).toBe(401);
  await anonymous.close();
  const response=await page.request.get("/api/analytics?days=all");
  expect(response.ok()).toBe(true);
  expect(response.headers()["cache-control"]).toContain("no-store");
  const data=await response.json();
  const marks=await(await page.request.get("/api/marks")).json();
  expect(data.total_submitted).toBe(marks.applications_total);
  expect(data.submitted).toBe(marks.applications_total);
  const csv=await page.request.get("/api/applications/export.csv");
  expect(csv.ok()).toBe(true);
  expect(csv.headers()["content-type"]).toContain("text/csv");
});

test("200-percent equivalent viewport reflow and keyboard theme control",async({page})=>{
  await page.setViewportSize({width:836,height:470});
  for(const [tab,title] of tabs){
    await page.goto(`/app/analytics?tab=${tab}&days=90`);
    await expect(page.getByRole("heading",{name:title,exact:true})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
  }
  const theme=page.getByRole("button",{name:/Theme: Night/});
  await theme.focus();
  await page.keyboard.press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme","light");
  await page.screenshot({path:path.join(root,"reflow-836-theme-keyboard.png"),fullPage:true});
});

test("date, status and evidence drilldowns show the exact Applications selection",async({page})=>{
  const errors=watchErrors(page);
  await page.goto("/app/analytics?days=90");
  const expected=await page.locator(".an-metric-value").first().innerText();
  await page.locator(".an-metric").first().click();
  await expect(page).toHaveURL(/\/app\/applications\/analytics/);
  await expect(page.locator(".an-hero p")).toContainText(`${expected} unique applications`);
  const row=page.locator(".an-record-row").first();
  await expect(row.getByRole("link",{name:"Open application"})).toBeVisible();
  await page.goto("/app/analytics?days=90");
  await page.locator(".an-statuses a").first().click();
  await expect(page).toHaveURL(/status=applied/);
  expect(await page.locator(".an-record-row").evaluateAll(rows=>rows.every(row=>row.getAttribute("data-status")==="applied"))).toBe(true);
  await page.goto("/app/analytics?days=90");
  await page.getByRole("link",{name:/Online assessments/}).click();
  await expect(page).toHaveURL(/evidence=online_assessment/);
  await expect(page.locator(".an-record-row").first()).toContainText(/online assessment/i);
  await page.screenshot({path:path.join(root,"application-drilldown.png"),fullPage:true});
  await page.setViewportSize({width:390,height:941});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
  expect(errors).toEqual([]);
  await page.screenshot({path:path.join(root,"application-drilldown-mobile.png"),fullPage:true});
});

test("Rejected companies opens rejected applications that can be searched and paged",async({page})=>{
  const errors=watchErrors(page);
  await page.goto("/app/analytics?tab=companies&days=all");
  const panel=page.locator(".an-rejections");
  await expect(panel.getByRole("heading",{name:"Rejected companies"})).toBeVisible();
  await expect(page.getByText("Companies that rejected you")).toHaveCount(0);
  await panel.getByRole("link",{name:/View rejected applications/}).click();
  await expect(page).toHaveURL(/evidence=rejection/);
  await expect(page.getByRole("heading",{name:"Rejected applications",level:1})).toBeVisible();
  const company=(await page.locator(".an-record-company strong").first().innerText()).trim();
  await page.getByRole("link",{name:"25",exact:true}).click();
  await expect(page).toHaveURL(/limit=25/);
  await page.getByRole("searchbox",{name:/Search rejected applications/}).fill(company);
  await page.getByRole("button",{name:"Search",exact:true}).click();
  await expect(page).toHaveURL(/q=/);
  await expect(page).toHaveURL(/limit=25/);
  expect(await page.locator(".an-record-company strong").allInnerTexts()).toEqual(expect.arrayContaining([company]));
  expect((await page.locator(".an-record-company strong").allInnerTexts()).every(name=>name.trim()===company)).toBe(true);
  await expect(page.getByText(/match(es)? for/)).toBeVisible();
  await page.getByRole("link",{name:"Clear search"}).click();
  await expect(page).not.toHaveURL(/q=/);
  expect(errors).toEqual([]);
});


test("calendar aggregation and historical weeks preserve headline scope",async({page})=>{
  await page.goto("/app/analytics?days=30");
  const headline=await page.locator(".an-metric-value").nth(1).innerText();
  const current=await page.getByLabel("Week containing date").inputValue();
  await page.getByRole("button",{name:"Previous week",exact:true}).click();
  await expect(page).toHaveURL(/week=/);
  await expect(page.getByLabel("Week containing date")).not.toHaveValue(current);
  await expect(page.locator(".an-metric-value").nth(1)).toHaveText(headline);
  await page.getByLabel("Chart interval").selectOption("monthly");
  await expect(page.getByRole("img",{name:/Unique submissions by calendar month/})).toBeVisible();
  await page.getByLabel("Chart interval").selectOption("daily");
  await page.getByText("View chart data",{exact:true}).click();
  const href=await page.locator(".an-chart-details tbody a").first().getAttribute("href");
  const start=new URL(href!,"http://fixture.test").searchParams.get("start")!;
  await page.locator(".an-chart-details tbody a").first().click();
  await expect(page).toHaveURL(/days=custom/);
  await expect(page.locator(".an-hero p")).toContainText(start);
});

test("reference desktop keeps five aligned KPIs and the six company modules in order",async({page})=>{
  await page.setViewportSize({width:1672,height:941});
  await page.goto("/app/analytics?days=30");
  const cards=await page.locator(".an-metric").evaluateAll(nodes=>nodes.map(node=>{const b=node.getBoundingClientRect();return {y:b.y,height:b.height};}));
  expect(cards).toHaveLength(5);
  expect(new Set(cards.map(b=>b.y)).size).toBe(1);
  expect(Math.max(...cards.map(b=>b.height))-Math.min(...cards.map(b=>b.height))).toBeLessThan(1);
  const left=(await page.locator(".an-overview-top .an-panel").first().boundingBox())!;
  expect(Math.abs(left.x-299)).toBeLessThan(8);
  expect(Math.abs(left.y-471)).toBeLessThan(25);
  expect(Math.abs(left.width-800)).toBeLessThan(20);
  await page.goto("/app/analytics?tab=companies&days=30");
  const panels=await page.locator(".an-grid .an-panel h2").allTextContents();
  expect(panels).toEqual(["Top companies in your pipeline","Companies with verified sponsorship evidence","Historical H-1B petition outcomes","Employer outcome history","Historical petition activity","Sponsorship evidence"]);
});

for (const route of ["/app/analytics?days=all", "/app/applications/analytics?days=all"]) {
  test(`Analytics settles after opening and after an evidence refresh: ${route}`,async({page})=>{
    const requests:string[]=[];
    const errors=watchErrors(page);
    // This regression needs Inbox navigation, not a Gmail body or email frame.
    // Use an empty fictional Inbox; Analytics still reads the real demo API.
    await page.route(/\/api\/inbox\/messages(?:\?|$)/,request=>request.fulfill({
      status:200,contentType:"application/json",body:JSON.stringify({items:[],total:0,has_more:false,view:"pending",latest_received_at:null,counts:{stored:0,needs_review:0,automatic:0,manual:0,reviewed:0,receipts:0,updates:0,stale:0}}),
    }));
    page.on("request",request=>{
      const url=new URL(request.url());
      const headers=request.headers();
      if(url.pathname===new URL(route,"http://fixture.test").pathname && headers.rsc==="1" && !headers["next-router-prefetch"])requests.push(request.url());
    });
    if(route.startsWith("/app/analytics?")){
      await page.goto("/app/applications/inbox");
      await page.getByRole("link",{name:"Analytics",exact:true}).click();
    }else await page.goto(route);
    await expect(page.getByRole("heading",{name:route.startsWith("/app/analytics?")?"Analytics":"Application records",exact:true})).toBeVisible();
    // Catch the continuous half-second response cycle, allowing initial loading
    // to finish. The shell's intentional two-minute poll is outside this window.
    await page.waitForTimeout(1500);
    const opened=requests.length;
    await page.waitForTimeout(3000);
    expect(requests.length,"opening Analytics must settle").toBe(opened);
    await page.evaluate(()=>{
      const channel=new BroadcastChannel("ace-marks");
      channel.postMessage("changed");
      channel.close();
    });
    await expect.poll(()=>requests.length).toBeGreaterThan(opened);
    await page.waitForTimeout(1500);
    const updated=requests.length;
    await page.waitForTimeout(3000);
    expect(requests.length,"an evidence refresh must also settle").toBe(updated);
    if(route.startsWith("/app/analytics?")){
      await page.getByRole("link",{name:"Inbox Intelligence",exact:true}).click();
      await expect(page.getByRole("heading",{name:"Inbox Intelligence",exact:true})).toBeVisible();
      await page.goBack();
      await expect(page.getByRole("heading",{name:"Analytics",exact:true})).toBeVisible();
      await page.waitForTimeout(1500);
      const returned=requests.length;
      await page.waitForTimeout(3000);
      expect(requests.length,"returning from Inbox must settle").toBe(returned);
    }
    expect(errors).toEqual([]);
  });
}
