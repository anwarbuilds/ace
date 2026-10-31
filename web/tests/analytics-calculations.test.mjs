import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { test } from "node:test";
import ts from "typescript";
const source = fs.readFileSync(new URL("../src/lib/analyticsCalculations.ts", import.meta.url), "utf8");
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loadedModule = { exports: {} };
vm.runInThisContext(`(function(exports){${output}\n})`)(loadedModule.exports);
const { calculateSupplement, calendarWeek, compareCounts, groupSubmissions, localDate, mondayOf, shiftDate, weekDateLabels } = loadedModule.exports;
const report = (extra = {}) => ({ as_of: "2026-10-27T19:00:00Z", timezone: "America/Los_Angeles", start: "2026-10-26", end: "2026-10-27", days: "custom", submitted: 2, week_total: 2, ...extra });
const row = (key, stamp) => ({ key: `job:${key}`, applied_at: stamp });

test("weeks align to Monday and clip edge buckets to the selected cohort", () => {
  const daily = Array.from({ length: 14 }, (_, i) => ({ date: shiftDate("2026-03-04", i), count: 1 }));
  assert.deepEqual(groupSubmissions(daily, "weekly", "2026-03-04", "2026-03-17"), [
    { date: "2026-03-04", end: "2026-03-08", count: 5 },
    { date: "2026-03-09", end: "2026-03-15", count: 7 },
    { date: "2026-03-16", end: "2026-03-17", count: 2 },
  ]);
});
test("calendar months include leap day and do not mean fixed 30-day groups", () => {
  const daily = [{ date: "2024-02-28", count: 2 }, { date: "2024-02-29", count: 3 }, { date: "2024-03-01", count: 5 }];
  assert.deepEqual(groupSubmissions(daily, "monthly", "2024-02-28", "2024-03-01"), [
    { date: "2024-02-28", end: "2024-02-29", count: 5 }, { date: "2024-03-01", end: "2024-03-01", count: 5 },
  ]);
});
test("date boundaries honor Los Angeles midnight across spring and fall DST", () => {
  assert.equal(localDate("2026-03-09T06:59:59Z", "America/Los_Angeles"), "2026-03-08");
  assert.equal(localDate("2026-03-09T07:00:00Z", "America/Los_Angeles"), "2026-03-09");
  assert.equal(localDate("2026-11-02T07:59:59Z", "America/Los_Angeles"), "2026-11-01");
  assert.equal(shiftDate("2026-03-08", 1), "2026-03-09");
  assert.equal(mondayOf("2027-01-01"), "2026-12-28");
});
test("incomplete week compares the same weekday and time, excluding the rest of last week", () => {
  const rows = [row(1,"2026-10-26T18:00:00Z"), row(2,"2026-10-27T18:00:00Z"), row(3,"2026-10-19T18:00:00Z"), row(4,"2026-10-20T18:00:00Z"), row(5,"2026-10-20T21:00:00Z")];
  const data = calculateSupplement(report(), rows, "daily");
  assert.equal(data.weekTrend.current, 2);
  assert.equal(data.weekTrend.previous, 2);
  assert.equal(data.weekTrend.percent, 0);
  assert.equal(data.week.reduce((sum,p)=>sum+p.count,0), 2);
  assert.equal(data.week.at(-1).date, "2026-11-01");
});
test("selected period comparison excludes the unmatched remainder of its last day", () => {
  const rows = [row(1,"2026-10-26T18:00:00Z"), row(2,"2026-10-27T18:00:00Z"), row(3,"2026-10-24T18:00:00Z"), row(4,"2026-10-25T20:00:00Z")];
  const data=calculateSupplement(report(),rows,"daily");
  assert.equal(data.submissionTrend.previous,1);
  assert.equal(data.submissionTrend.percent,100);
});
test("historical week navigation does not move headline cards or the selected timeline", () => {
  const rows=[row(1,"2026-10-26T18:00:00Z"),row(2,"2026-10-27T18:00:00Z"),row(3,"2026-10-20T18:00:00Z")];
  const current=calculateSupplement(report(),rows,"daily");
  const historical=calculateSupplement(report(),rows,"daily","2026-10-21");
  assert.deepEqual(historical.timeline,current.timeline);
  assert.deepEqual(historical.weekTrend,current.weekTrend);
  assert.equal(historical.weekStart,"2026-10-19");
  assert.equal(historical.week.reduce((sum,p)=>sum+p.count,0),1);
  assert.equal(historical.currentWeek,false);
});
test("all time includes undated history without inventing chart dates or prior periods", () => {
  const rows=[row(1,"2026-10-26T18:00:00Z"),row(2,null)];
  const data=calculateSupplement(report({days:"all",week_total:1}),rows,"monthly");
  assert.equal(data.submissionTrend,null);
  assert.equal(data.timeline.reduce((sum,p)=>sum+p.count,0),1);
});
test("incomplete or duplicate identity snapshots cannot display supplemental counts", () => {
  const one=row(1,"2026-10-26T18:00:00Z");
  assert.equal(calculateSupplement(report(),[one],"daily"),null);
  assert.equal(calculateSupplement(report(),[one,one],"daily"),null);
  assert.equal(calculateSupplement(report(),[one,row(2,"invalid")],"daily"),null);
});
test("zero denominator is New or No prior activity, never a fabricated percentage", () => {
  assert.equal(compareCounts(5,0,"").label,"New");
  assert.equal(compareCounts(5,0,"").percent,null);
  assert.equal(compareCounts(0,0,"").label,"No prior activity");
  assert.equal(compareCounts(0,4,"").percent,-100);
});
test("future and malformed week parameters fall back to the actual current week", () => {
  const rows=[row(1,"2026-10-26T18:00:00Z"),row(2,"2026-10-27T18:00:00Z")];
  for(const asked of ["2026-11-30","2026-02-30","invalid"])
    assert.equal(calculateSupplement(report(),rows,"daily",asked).weekStart,"2026-10-26");
});

test("weekly windows and date labels cross month and year boundaries one Monday at a time", () => {
  assert.deepEqual(calendarWeek("2026-10-31"), {start:"2026-10-26",end:"2026-11-01",current:true});
  assert.deepEqual(calendarWeek("2027-01-01","2026-12-24"), {start:"2026-12-21",end:"2026-12-27",current:false});
  assert.deepEqual(weekDateLabels("2026-10-26","2026-11-01"), {start:"Oct 26",end:"Nov 1, 2026"});
  assert.deepEqual(weekDateLabels("2026-10-19","2026-10-25"), {start:"Oct 19",end:"Oct 25, 2026"});
  assert.deepEqual(weekDateLabels("2026-12-28","2027-01-03"), {start:"Dec 28, 2026",end:"Jan 3, 2027"});
});
test("seven Pacific daily buckets reconcile unique identities across Sunday midnight and fall DST", () => {
  const rows=[row(1,"2026-10-26T06:59:59Z"),row(2,"2026-10-26T07:00:00Z"),
    row(3,"2026-11-01T08:30:00Z"),row(4,"2026-11-01T09:30:00Z"),row(5,"2026-11-02T07:59:59Z"),row(6,"2026-11-02T08:00:00Z")];
  const d=report({as_of:"2026-11-03T20:00:00Z",start:"2026-10-25",end:"2026-11-03",submitted:6,week_total:1});
  const selected=calculateSupplement(d,rows,"daily","2026-10-28");
  assert.equal(selected.week.length,7);
  assert.deepEqual(selected.week.map(day=>day.count),[1,0,0,0,0,0,3]);
  assert.equal(selected.week.reduce((sum,day)=>sum+day.count,0),4);
  assert.equal(selected.currentWeekTotal,1);
});
test("weekly data is independent of 14, 30, 90 and all-time cohorts", () => {
  const rows=[row(1,"2026-10-27T18:00:00Z"),row(2,"2026-10-05T18:00:00Z"),row(3,"2026-09-05T18:00:00Z"),row(4,"2026-08-05T18:00:00Z")];
  const cases=[["14","2026-10-14",1],["30","2026-09-28",2],["90","2026-07-30",4],["all","2026-08-05",4]];
  for(const [days,start,submitted] of cases){
    const result=calculateSupplement(report({days,start,submitted,week_total:1}),rows,"daily","2026-10-05");
    assert.deepEqual(result.week.map(day=>day.count),[1,0,0,0,0,0,0]);
  }
});
test("mismatched current-week totals or daily buckets refuse supplemental data", () => {
  const rows=[row(1,"2026-10-26T18:00:00Z"),row(2,"2026-10-27T18:00:00Z")];
  assert.equal(calculateSupplement(report({week_total:3}),rows,"daily"),null);
  assert.equal(calculateSupplement(report({week:[{date:"2026-10-26",count:2},{date:"2026-10-27",count:0}]}),rows,"daily"),null);
});
test("weekly Pacific boundaries stay separate from another reporting timezone", () => {
  const rows=[row(1,"2026-10-26T06:59:59Z"),row(2,"2026-10-26T07:00:00Z")];
  const utc=report({timezone:"UTC",week_total:2});
  const pacific=report({week_total:1});
  const result=calculateSupplement(utc,rows,"daily",undefined,pacific);
  assert.equal(result.currentWeekTotal,1);
  assert.deepEqual(result.week.map(day=>day.count),[1,0,0,0,0,0,0]);
});
