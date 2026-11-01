import fs from "node:fs";
import path from "node:path";
import { expect } from "@playwright/test";
import { DRAWN_SCAN, TEXT_SCAN, setThemeCookies, test, watchErrors } from "./helpers";

/** Model the failed API branch in the actual Flight response. The browser must
 * retain the previous server children, not render this failed-read placeholder. */
function failedAnalyticsPayload(body:string) {
  let changed=false;
  const visit=(value:unknown):void=>{
    if(Array.isArray(value)){value.forEach(visit);return;}
    if(!value||typeof value!=="object")return;
    const row=value as Record<string,unknown>;
    if(typeof row.scope==="string"&&"attemptedAt" in row&&row.success===true){
      row.success=false;row.asOf=null;
      row.children=["$","p",null,{children:"Fictional failed server read"}];changed=true;
    }
    Object.values(row).forEach(visit);
  };
  const result=body.split("\n").map(line=>{
    const colon=line.indexOf(":");if(colon<0)return line;
    try{const value=JSON.parse(line.slice(colon+1));visit(value);return line.slice(0,colon+1)+JSON.stringify(value);}catch{return line;}
  }).join("\n");
  expect(changed,"the fixture must replace the real Analytics freshness props").toBe(true);
  return result;
}

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
      await expect(page.locator(".an-page")).toHaveCount(1);
      await page.evaluate(()=>window.scrollTo(0,0));
      await expect(page.getByRole("heading",{name:"Analytics",exact:true})).toBeInViewport();
      expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
      expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
      await expect(page.locator('.an-tabs a[aria-current="page"]')).toHaveCount(1);
      await page.screenshot({path:path.join(root,`${theme}-${tab}.png`)});
      await page.screenshot({path:path.join(root,`${theme}-${tab}-full.png`),fullPage:true});
      if(tab==="overview"){
        await page.setViewportSize(theme==="dark"?{width:1536,height:1024}:{width:1672,height:941});
        await page.screenshot({path:path.join(root,`${theme}-overview-reference.png`)});
        const geometry=await page.evaluate(()=>Object.fromEntries([".sb",".tb",".an-page",".an-hero",".an-filters",".an-inbox-band",".an-inbox-workflow",".an-band-coverage",".an-metric",".an-tabs",".an-overview-top>.an-panel",".an-overview-bottom>.an-panel",".an-date-toggle svg",".an-week-picker .nic",".an-weekly",".an-donut"].map(selector=>[selector,[...document.querySelectorAll(selector)].map(element=>{const box=element.getBoundingClientRect(),style=getComputedStyle(element);return {x:box.x,y:box.y,width:box.width,height:box.height,font:style.fontFamily,fontSize:style.fontSize,weight:style.fontWeight,lineHeight:style.lineHeight,letterSpacing:style.letterSpacing};})])));
        expect(Math.abs(geometry[".an-inbox-band"][0].height-96)).toBeLessThan(2);
        expect(Math.abs(geometry[".an-overview-top>.an-panel"][0].x-geometry[".sb"][0].width-28)).toBeLessThan(1);
        const right=geometry[".an-overview-top>.an-panel"][1];
        expect(Math.abs(right.x+right.width-(theme==="dark"?1536:1672)+28)).toBeLessThan(1);
        await expect(page.locator(".an-classified-email-evidence,.an-audit-note,.an-bottom-links")).toHaveCount(0);
        fs.mkdirSync(path.resolve("test-results"),{recursive:true});
        fs.writeFileSync(path.resolve("test-results",`overview-${theme}-geometry.json`),JSON.stringify(geometry,null,2));
        await page.setViewportSize({width:1672,height:941});
      }
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
  await expect(page.locator('.an-date-toggle svg rect')).toHaveAttribute("width","18");
  await expect(page.locator('.an-date-toggle svg path')).toHaveAttribute("d","M7 2v6M17 2v6M3 11h18");
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
  await expect(page.locator(".an-page")).toHaveCount(1);
  await expect(page.locator(".an-line-chart .an-x-tick").first()).toBeVisible();
  await page.evaluate(()=>document.fonts.ready);
  const ticks=await page.locator(".an-line-chart .an-x-tick").evaluateAll(nodes=>nodes.map(node=>{const b=node.getBoundingClientRect();return {left:b.left,right:b.right};}));
  expect(ticks.every((tick,index)=>index===0||tick.left>=ticks[index-1].right)).toBe(true);
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
  test.setTimeout(90_000);
  await page.goto("/app/analytics?days=30");
  const headline=await page.locator(".an-metric-value").nth(1).innerText();
  const panel=page.locator(".an-week-card");
  const current=await panel.locator("time").first().getAttribute("datetime");
  await expect(panel.locator("h2")).toHaveText("This week");
  await expect(panel.getByRole("button",{name:"Next week",exact:true})).toBeDisabled();
  await expect(panel.locator('input[type="date"]')).toHaveCount(0);
  await page.getByRole("button",{name:"Previous week",exact:true}).click();
  await expect(page).toHaveURL(/week=/);
  await expect(panel.locator("time").first()).not.toHaveAttribute("datetime",current!);
  await expect(panel.locator("h2")).not.toHaveText("This week");
  await expect(panel.locator(".an-column")).toHaveCount(7);
  await expect(page.locator(".an-metric-value").nth(1)).toHaveText(headline);
  const week=new URL(page.url()).searchParams.get("week")!;
  const verifyWeek=async(family="")=>{
    const end=new Date(Date.parse(`${week}T12:00:00Z`)+6*86400000).toISOString().slice(0,10);
    await expect(panel.locator("h2 time").first()).toHaveAttribute("datetime",week);
    await expect(panel.locator("h2 time").last()).toHaveAttribute("datetime",end);
    const params=new URLSearchParams({days:"custom",start:week,end,tz:"America/Los_Angeles",records:"1",limit:"100",...(family?{family}:{})});
    const data=await(await page.request.get(`/api/analytics?${params}`)).json();
    const records=[...data.records];
    for(let offset=100;offset<data.record_total;offset+=100){params.set("offset",String(offset));records.push(...(await(await page.request.get(`/api/analytics?${params}`)).json()).records);}
    expect(new Set(records.map((r:{key:string})=>r.key)).size).toBe(data.record_total);
    await expect(panel.locator(".an-foot")).toContainText(`${data.record_total} unique submissions in this week`);
    const bars=panel.locator(".an-column");
    for(let index=0;index<7;index++){
      const date=new Date(Date.parse(`${week}T12:00:00Z`)+index*86400000).toISOString().slice(0,10);
      const count=records.filter((row:{submitted_at:string})=>new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(row.submitted_at)?row.submitted_at:row.submitted_at+"Z").toLocaleDateString("en-CA",{timeZone:"America/Los_Angeles"})===date).length;
      await expect(bars.nth(index).locator(".an-column-plot span")).toHaveText(String(count));
      const href=new URL((await bars.nth(index).getAttribute("href"))!,"https://fixture.test");
      expect(href.searchParams.get("start")).toBe(date);expect(href.searchParams.get("end")).toBe(date);
    }
  };
  await verifyWeek();
  for(const days of ["14 days","90 days","All time","30 days"]){
    await page.getByRole("button",{name:days,exact:true}).click();
    await expect(panel.locator("time").first()).toHaveAttribute("datetime",week);
    await verifyWeek();
  }
  await page.getByLabel("Application role family").selectOption("SOFTWARE_ENGINEERING");
  await expect(page).toHaveURL(/family=SOFTWARE_ENGINEERING/);
  await verifyWeek("SOFTWARE_ENGINEERING");
  await panel.getByRole("button",{name:"Next week",exact:true}).click();
  await expect(panel.locator("h2")).toHaveText("This week");
  await expect(panel.getByRole("button",{name:"Next week",exact:true})).toBeDisabled();
  await expect(page).not.toHaveURL(/week=/);
  await panel.getByRole("button",{name:"Previous week",exact:true}).click();
  await panel.getByRole("button",{name:"This week",exact:true}).click();
  await expect(panel.locator("h2")).toHaveText("This week");
  await expect(page).not.toHaveURL(/week=/);
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

test("historical arrows cross calendar years and reset without a weekly date picker",async({page})=>{
  await page.goto("/app/analytics?days=14&week=2025-12-29");
  const panel=page.locator(".an-week-card");
  await expect(panel.locator("h2")).toHaveText(`Dec 29, 2025${String.fromCharCode(0x2013)}Jan 4, 2026`);
  await expect(panel.locator(".an-column")).toHaveCount(7);
  await panel.getByRole("button",{name:"Previous week",exact:true}).click();
  await expect(panel.locator("h2")).toHaveText(`Dec 22${String.fromCharCode(0x2013)}Dec 28, 2025`);
  await expect(page).toHaveURL(/week=2025-12-22/);
  await panel.getByRole("button",{name:"Next week",exact:true}).click();
  await expect(page).toHaveURL(/week=2025-12-29/);
  await panel.getByRole("button",{name:"This week",exact:true}).click();
  await expect(panel.locator("h2")).toHaveText("This week");
  await expect(panel.getByRole("button",{name:"Next week",exact:true})).toBeDisabled();
  await expect(panel.locator("input")).toHaveCount(0);
  await expect(page.getByRole("button",{name:"14 days",exact:true})).toHaveAttribute("aria-pressed","true");
  for(const future of await panel.locator(".an-column[data-future]").all()){
    await expect(future).toHaveAttribute("aria-label",/future day/);
    await expect(future.locator(".an-column-plot span")).toHaveText("");
    await expect(future).not.toHaveAttribute("href");
  }
});

test("Overview fills the desktop content area and keeps the six company modules in order",async({page})=>{
  await page.setViewportSize({width:1672,height:941});
  await page.goto("/app/analytics?days=30");
  await expect(page.getByRole("heading",{name:"Applications over time",exact:true})).toBeVisible();
  await expect(page.locator(".an-page")).toHaveCount(1);
  await expect(page.locator(".an-overview-top .an-panel").first()).toBeVisible();
  const cards=await page.locator(".an-metric").evaluateAll(nodes=>nodes.map(node=>{const b=node.getBoundingClientRect();return {y:b.y,height:b.height};}));
  expect(cards).toHaveLength(5);
  expect(new Set(cards.map(b=>b.y)).size).toBe(1);
  expect(Math.max(...cards.map(b=>b.height))-Math.min(...cards.map(b=>b.height))).toBeLessThan(1);
  await expect(page.locator(".an-overview-charts>.an-grid>.an-panel")).toHaveCount(4);
  await expect(page.getByRole("heading",{name:"Recognized hiring progress",exact:true})).toHaveCount(0);
  await expect(page.getByText("About these metrics and evidence",{exact:true})).toHaveCount(0);
  await expect(page.getByRole("link",{name:"Export applications CSV",exact:true})).toHaveCount(0);
  let previousHeight=0;
  for(const viewport of [{width:1920,height:1080},{width:1920,height:1440},{width:2560,height:1440}]){
    await page.setViewportSize(viewport);
    const shell=(await page.locator(".shell-main").boundingBox())!;
    const top=(await page.locator(".an-overview-top").boundingBox())!;
    const bottom=(await page.locator(".an-overview-bottom").boundingBox())!;
    expect(Math.abs(top.x-shell.x-28)).toBeLessThan(1);
    expect(Math.abs(top.x+top.width-viewport.width+28)).toBeLessThan(1);
    expect(Math.abs(bottom.x-top.x)).toBeLessThan(1);
    expect(Math.abs(bottom.width-top.width)).toBeLessThan(1);
    expect(Math.abs(bottom.y+bottom.height-viewport.height+24)).toBeLessThan(2);
    if(previousHeight&&viewport.width===1920)expect(top.height).toBeGreaterThan(previousHeight+100);
    previousHeight=top.height;
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
    await page.screenshot({path:path.join(root,`expanded-overview-${viewport.width}x${viewport.height}.png`)});
  }
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

for(const theme of ["light","dark"] as const){
  test(`${theme}: classified hiring progress is visible separately from confirmed application stages`,async({page,context,baseURL})=>{
    await setThemeCookies(context,baseURL!,theme);
    await page.setViewportSize({width:1672,height:941});
    const errors=watchErrors(page);
    const before=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
    const progress=before.classified_email_evidence;
    expect(progress.total).toBe(4);
    expect(progress.categories).toMatchObject({online_assessment:1,interview:1,offer:1,application_confirmation:1,rejection:0});
    expect(progress.linked_messages+progress.company_messages+progress.unlinked_messages).toBe(4);
    expect(progress.application_status_changed).toBe(false);
    expect(progress.date_basis).toBe("email_received");
    await page.goto("/app/analytics?days=all&tab=outcomes");
    const panel=page.locator(".an-classified-email-evidence");
    await expect(panel.getByRole("heading",{name:"Recognized hiring progress",exact:true})).toBeVisible();
    await expect(panel).toContainText("4 classified emails in this scope.");
    await expect(panel).toContainText("A later rejection does not erase an earlier assessment or interview.");
    for(const [kind,label] of [["online_assessment","Assessment invitation emails"],["interview","Interview invitation emails"],["offer","Offer emails"]]){
      const link=panel.getByRole("link",{name:new RegExp(`^${label}`)});
      await expect(link.locator("b")).toHaveText("1");
      const href=await link.getAttribute("href");
      const exact=new URL(href!,"https://fixture.test");
      expect(exact.pathname).toBe("/app/applications/analytics");
      expect(Object.fromEntries(exact.searchParams)).toMatchObject({days:"all",tz:"America/Los_Angeles",emails:"1",email_kind:kind});
      const records=await(await page.request.get(`/api/analytics?${exact.searchParams}`)).json();
      expect(records.email_total).toBe(1);expect(records.email_records).toHaveLength(1);
      expect(records.email_records[0].classification).toBe(kind);
      await link.click();
      await expect(page.getByRole("heading",{name:"Recruiting email evidence",exact:true})).toBeVisible();
      await expect(page.locator(".an-record-row")).toHaveCount(1);
      await expect(page.getByRole("link",{name:"View email",exact:true})).toHaveAttribute("href",`/app/applications/inbox?message=${records.email_records[0].id}`);
      await page.goto("/app/analytics?days=all&tab=outcomes");
    }
    await expect(panel).toContainText("Acknowledgements: 1");
    await expect(panel).toContainText("email counts, not additional applications or confirmed stage totals");
    await expect(page.locator(".an-metric").nth(0).locator("strong")).toHaveText(String(before.submitted));
    await expect(page.locator(".an-metric").nth(3).locator("strong")).toHaveText(String(before.assessments));
    const invitationCard=page.locator(".an-metric").nth(4);
    await expect(invitationCard.locator("strong")).toHaveText(String(progress.categories.interview));
    await expect(invitationCard).toContainText("Invitation emails by receipt date");
    await invitationCard.click();
    await expect(page.getByRole("heading",{name:"Recruiting email evidence",exact:true})).toBeVisible();
    await expect(page.locator(".an-record-row")).toHaveCount(progress.categories.interview);
    await expect(page.locator(".an-record-row").first()).toContainText("Interview");
    await page.goto("/app/analytics?days=all&tab=outcomes");
    expect(await page.evaluate(TEXT_SCAN)).toEqual([]);
    expect(await page.evaluate(DRAWN_SCAN)).toEqual([]);
    const directory=path.resolve("../artifacts/inbox-intelligence-validation");
    fs.mkdirSync(directory,{recursive:true});
    await panel.screenshot({path:path.join(directory,`${theme}-analytics-classified-progress.png`)});
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
    await panel.screenshot({path:path.join(directory,`${theme}-analytics-classified-progress-mobile.png`)});
    const after=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
    for(const key of ["submitted","statuses","positive","assessments","interviews","classified_email_evidence"])expect(after[key]).toEqual(before[key]);
    expect(errors).toEqual([]);
  });
}

test("July email floor excludes the older offer while preserving application metrics and boundary evidence",async({page})=>{
  const before=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
  expect(before.evidence_scope).toMatchObject({start:"2026-07-01",timezone:"America/Los_Angeles",start_at:"2026-07-01T07:00:00Z",application_cohort_unchanged:true});
  expect(before.classified_email_evidence.total).toBe(4);
  expect(before.classified_email_evidence.categories.application_confirmation).toBe(1);
  expect(before.classified_email_evidence.categories.offer).toBe(1);
  expect(before.classified_email_evidence.start).toBe("2026-07-01");
  const older=await(await page.request.get("/api/inbox/messages?decision=offers&q=Fictional%20pre-July")).json();
  expect(older.total).toBe(0);
  expect(older.items).toEqual([]);
  expect(older.counts.offers).toBe(1);
  const assessments=await(await page.request.get("/api/inbox/messages?decision=assessments")).json();
  const boundary=assessments.items.find((message:{subject:string})=>message.subject==="Fictional online assessment email history");
  expect(boundary).toBeTruthy();
  expect(Date.parse(boundary.received_at)).toBe(Date.parse("2026-07-01T07:00:00Z"));
  await page.goto("/app/analytics?days=all&tab=outcomes");
  const panel=page.locator(".an-classified-email-evidence");
  await expect(panel.getByLabel("Email history period")).toContainText("Since July 1, 2026");
  await expect(panel).toContainText("Email receipt dates: 2026-07-01");
  await expect(panel).not.toContainText("Email receipt dates: All dates");
  await expect(page.locator(".an-metric").first().locator("strong")).toHaveText(String(before.submitted));
  const after=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
  for(const key of ["submitted","statuses","positive","assessments","interviews","classified_email_evidence"])expect(after[key]).toEqual(before[key]);
});

for(const route of ["/app/analytics?days=all&tab=outcomes&interval=weekly","/app/applications/analytics?days=all&limit=25&q=Engineer"]){
  test(`failed server refresh retains the verified selection and Retry recovers: ${route}`,async({page})=>{
    await page.goto(route);
    const report=page.locator("div.an-page");
    await expect(report).toHaveCount(1);
    await expect(report).toBeVisible();
    const original=await report.innerText();
    const asOf=await page.locator(".an-freshness").getAttribute("data-analytics-as-of");
    let fail=true;
    await page.route(url=>url.pathname===new URL(route,"https://fixture.test").pathname,async request=>{
      if(request.request().headers().rsc!=="1"||request.request().headers()["next-router-prefetch"]||!fail)return request.continue();
      const response=await request.fetch();
      await request.fulfill({response,body:failedAnalyticsPayload(await response.text())});
    });
    await page.evaluate(()=>window.dispatchEvent(new Event("ace-analytics-refresh")));
    await expect(page.locator('.an-freshness[data-state="stale"]')).toContainText("Refresh failed. Showing the last verified results");
    expect(await report.innerText()).toBe(original);
    expect(await page.locator(".an-freshness").getAttribute("data-analytics-as-of")).toBe(asOf);
    await expect(page.getByText("Fictional failed server read",{exact:true})).toHaveCount(0);
    expect(new URL(page.url()).search).toBe(new URL(route,"https://fixture.test").search);
    fail=false;
    await page.getByRole("button",{name:"Retry refresh",exact:true}).click();
    await expect(page.locator('.an-freshness[data-state="fresh"]')).toContainText("Updated");
    await expect(page.getByRole("button",{name:"Retry refresh",exact:true})).toHaveCount(0);
    expect(new URL(page.url()).search).toBe(new URL(route,"https://fixture.test").search);
  });
}

test("a delayed RSC transport preserves the last verified report and completes without overlapping refreshes",async({page})=>{
  await page.clock.install();
  await page.goto("/app/analytics?days=all&tab=outcomes");
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  const original=await page.locator(".an-metric-value").first().innerText();
  const asOf=await page.locator(".an-freshness").getAttribute("data-analytics-as-of");
  let release!:()=>void,reads=0,held=true;
  const waiting=new Promise<void>(resolve=>{release=resolve;});
  await page.route(url=>url.pathname==="/app/analytics",async route=>{
    if(route.request().headers().rsc!=="1"||route.request().headers()["next-router-prefetch"])return route.continue();
    reads++;
    if(held){const response=await route.fetch();await waiting;held=false;await route.fulfill({response});}
    else await route.continue();
  });
  await page.evaluate(()=>window.dispatchEvent(new Event("ace-analytics-refresh")));
  await expect(page.locator('.an-freshness[data-state="refreshing"]')).toBeVisible();
  await page.clock.fastForward(31_000);
  await expect(page.locator('.an-freshness[data-state="stale"]')).toContainText("Refresh is delayed");
  expect(await page.locator(".an-metric-value").first().innerText()).toBe(original);
  expect(await page.locator(".an-freshness").getAttribute("data-analytics-as-of")).toBe(asOf);
  await page.evaluate(()=>{window.dispatchEvent(new Event("focus"));const channel=new BroadcastChannel("ace-marks");channel.postMessage("changed");channel.close();});
  expect(reads).toBe(1);
  release();
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  await page.clock.fastForward(500);
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  expect(reads).toBeLessThanOrEqual(2);
  await expect(page).toHaveURL(/days=all&tab=outcomes/);
});

test("offline Analytics keeps verified results and checks automatically when the network returns",async({page,context})=>{
  await page.goto("/app/analytics?days=all&tab=role-resume");
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  const original=await page.locator(".an-metric-value").first().innerText();
  const asOf=await page.locator(".an-freshness").getAttribute("data-analytics-as-of");
  try{
    await context.setOffline(true);
    await expect(page.locator('.an-freshness[data-state="stale"]')).toContainText("last verified results");
    await page.getByRole("button",{name:"Retry refresh",exact:true}).click();
    expect(await page.locator(".an-metric-value").first().innerText()).toBe(original);
    expect(await page.locator(".an-freshness").getAttribute("data-analytics-as-of")).toBe(asOf);
  }finally{await context.setOffline(false);}
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  await expect(page).toHaveURL(/days=all&tab=role-resume/);
});

test("owner receipt feedback supersedes a stale offer reading in API categories and the Inbox",async({page})=>{
  const query="Fictional%20owner%20receipt%20feedback";
  const before=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
  const offers=await(await page.request.get(`/api/inbox/messages?decision=offers&q=${query}`)).json();
  expect(offers.total).toBe(0);
  expect(offers.items).toEqual([]);
  expect(offers.counts.offers).toBe(1);
  const receipts=await(await page.request.get(`/api/inbox/messages?decision=receipt&q=${query}`)).json();
  expect(receipts.total).toBe(1);
  expect(receipts.items[0]).toMatchObject({classification:"application_confirmation",saved_classification:"offer",decision:"receipt",selected_application_key:null,understanding:{classification_source:"owner_decision"}});
  const writes:string[]=[];
  page.on("request",request=>{if(new URL(request.url()).pathname.startsWith("/api/inbox/")&&!["GET","HEAD"].includes(request.method()))writes.push(`${request.method()} ${new URL(request.url()).pathname}`);});
  await page.goto(`/app/applications/inbox?decision=receipt&q=${query}`);
  await expect(page.locator(".inbox-mail")).toHaveCount(1);
  await expect(page.locator(".inbox-mail .inbox-kind")).toHaveText("Acknowledgement");
  await expect(page.locator(".inbox-inspector .inbox-kind")).toHaveText("Acknowledgement");
  await expect(page.locator(".inbox-inspector .inbox-state")).toHaveText("Acknowledgement filed");
  await expect(page.getByLabel("ACE understanding")).toContainText("Your classification: Acknowledgement");
  await expect(page.getByLabel("ACE understanding")).toContainText("earlier classifier reading is retained for audit");
  await expect(page.locator(".inbox-kind.k-offer")).toHaveCount(0);
  await expect(page.locator(".inbox-inspector .inbox-target")).toHaveCount(0);
  expect(writes).toEqual([]);
  const after=await(await page.request.get("/api/analytics?days=all&tz=America%2FLos_Angeles")).json();
  for(const key of ["submitted","statuses","positive","assessments","interviews","classified_email_evidence"])expect(after[key]).toEqual(before[key]);
});

// Mutates only the disposable Analytics fixture, after its read-only assertions.
test("a committed Inbox acknowledgement correction updates open Analytics without reloading",async({page,context})=>{
  const messageRead=await page.request.get("/api/inbox/messages?q=Fictional%20offer%20email%20history");
  expect(messageRead.ok(),await messageRead.text()).toBe(true);
  const messages=await messageRead.json();
  const message=messages.items.find((row:{subject:string})=>row.subject==="Fictional offer email history");
  expect(message,"the dedicated fictional Analytics seed must be present").toBeTruthy();
  await page.goto("/app/analytics?days=all&tab=outcomes");
  const offer=page.locator('.an-classified-email-evidence a').filter({has:page.getByText("Offer emails",{exact:true})}).locator("b");
  const before=Number((await offer.innerText()).replaceAll(",",""));
  const applications=await page.locator(".an-metric-value").first().innerText();
  const editor=await context.newPage();
  await editor.goto(`/app/applications/inbox?decision=all&message=${message.id}`);
  await expect(editor.locator(".inbox-inspector h2")).toHaveText(message.subject);
  await editor.getByRole("button",{name:"Link or correct this email",exact:true}).click();
  const saved=editor.waitForResponse(response=>response.url().includes(`/api/inbox/messages/${message.id}/decision`)&&response.request().method()==="PATCH");
  await editor.getByRole("group",{name:"What is this email?",exact:true}).getByRole("button",{name:/^Acknowledgement/}).click();
  expect((await saved).ok()).toBe(true);
  const committed=await(await editor.request.get(`/api/inbox/messages/${message.id}`)).json();
  expect(committed.decision).toBe("receipt");expect(committed.classification).toBe("application_confirmation");
  await page.bringToFront();
  await expect(offer).toHaveText(String(before-1));
  await expect(page.locator(".an-metric-value").first()).toHaveText(applications);
  await expect(page.locator('.an-classified-email-evidence')).toContainText("Acknowledgements:");
  await expect(page.locator('.an-freshness[data-state="fresh"]')).toBeVisible();
  await editor.close();
});
