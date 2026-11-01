"use client";

import { useSyncExternalStore } from "react";
import { applicationRecordsHref, type AnalyticsData } from "@/lib/analytics";
import { ANALYTICS_WEEK_TIMEZONE, calendarWeek, compareCounts, localDate, shiftDate, weekDateLabels, type AnalyticsSupplement, type ChartPoint } from "@/lib/analyticsCalculations";
import { AnalyticsWeekPicker } from "./AnalyticsFilters";
import { ColumnChart } from "./AnalyticsCharts";

const WEEK_CHANGE = "ace-analytics-week-change";
const subscribe = (update: () => void) => {
  window.addEventListener("popstate", update);
  window.addEventListener(WEEK_CHANGE, update);
  return () => { window.removeEventListener("popstate", update); window.removeEventListener(WEEK_CHANGE, update); };
};
const requestedWeek = () => new URLSearchParams(window.location.search).get("week") ?? "";
const number = (value: number) => value.toLocaleString("en-US");
function WeekRange({start,end}:{start:string;end:string}) {
  const labels=weekDateLabels(start,end);
  return <span className="an-week-range"><time dateTime={start}>{labels.start}</time><span className="an-week-separator">{String.fromCharCode(0x2013)}</span><time dateTime={end}>{labels.end}</time></span>;
}
type WeeklySupplement = Pick<AnalyticsSupplement,"weekToday"|"weeklyCounts"|"weekStart"|"week"|"weekTrend">;
function summary(rows: ChartPoint[], trend: AnalyticsSupplement["weekTrend"], historical: boolean) {
  const total=rows.reduce((sum,row)=>sum+row.count,0);
  let text=`${number(total)} applications ${historical?"in this week":"this week"}.`;
  if(trend?.percent!=null){
    const amount=Math.abs(Math.round(trend.percent));
    const comparison=historical?"the previous week":"the same point last week";
    text=trend.percent===0 ? `${text} No change from ${comparison}.` : `${number(total)} applications ${historical?"in this week":"this week"}, a ${amount||"less than 1"}% ${trend.percent>0?"increase":"decrease"} from ${comparison}.`;
  }else if(trend)text+=trend.previous===0?" No prior-week activity to compare.":"";
  const maximum=Math.max(0,...rows.map(row=>row.count));
  if(maximum){
    const peak=rows.filter(row=>row.count===maximum);
    text+=peak.length===1?` Most active on ${new Date(`${peak[0].date}T12:00:00Z`).toLocaleDateString("en-US",{weekday:"long",timeZone:"UTC"})}, with ${number(maximum)} ${maximum===1?"submission":"submissions"}.`:` Peak daily activity: ${number(maximum)} submissions.`;
  }
  return text;
}

export function AnalyticsWeeklyChart({ d, supplement, initialWeek }: { d: Pick<AnalyticsData,"as_of"|"timezone"|"week"|"days"|"start"|"end"|"family">; supplement?: WeeklySupplement|null; initialWeek?: string }) {
  const asked=useSyncExternalStore(subscribe,requestedWeek,()=>initialWeek??"");
  const today=supplement?.weekToday??localDate(d.as_of,ANALYTICS_WEEK_TIMEZONE);
  const window=calendarWeek(today,asked), historical=!window.current;
  const counts=supplement?.weeklyCounts;
  const read=(start:string):ChartPoint[]=>Array.from({length:7},(_,i)=>{const date=shiftDate(start,i);return {date,end:date,count:date>today?0:counts?.[date]??0};});
  const selected=supplement?.weekStart===window.start?supplement.week:!historical&&d.timezone===ANALYTICS_WEEK_TIMEZONE?d.week.map(row=>({...row,end:row.date})):null;
  const rows=counts?read(window.start):selected;
  const trend=historical&&counts&&rows?compareCounts(rows.reduce((sum,row)=>sum+row.count,0),read(shiftDate(window.start,-7)).reduce((sum,row)=>sum+row.count,0),"Completed Pacific calendar weeks."):!historical?supplement?.weekTrend??null:null;
  const change=counts?(start:string)=>{
    const next=new URL(globalThis.window.location.href);
    if(start===calendarWeek(today).start)next.searchParams.delete("week");else next.searchParams.set("week",start);
    // Native history integrates with Next search params without a route request.
    globalThis.window.history.pushState(null,"",`${next.pathname}${next.search}${next.hash}`);
    globalThis.window.dispatchEvent(new Event(WEEK_CHANGE));
  }:undefined;
  return <section className="an-panel an-week-card" data-week-start={window.start}>
    <header className="an-panel-head"><div className="an-panel-title"><h2>{historical?<WeekRange start={window.start} end={window.end}/>:"This week"}</h2><AnalyticsWeekPicker start={window.start} today={today} onChange={change}/></div><p>{historical?"Application activity for this Monday to Sunday week.":<WeekRange start={window.start} end={window.end}/>}</p></header>
    {rows?<><ColumnChart weekly label={`Calendar week submissions, ${window.start} through ${window.end}, ${ANALYTICS_WEEK_TIMEZONE}`} rows={rows.map(row=>({label:new Date(`${row.date}T12:00:00Z`).toLocaleDateString("en-US",{weekday:"short",timeZone:"UTC"}),detail:row.date,count:row.count,future:row.date>today,href:applicationRecordsHref({...d,timezone:ANALYTICS_WEEK_TIMEZONE,days:"custom",start:row.date,end:row.date})}))}/><p className="an-foot an-week-context">{summary(rows,trend,historical)}</p></>:<div className="an-unavailable"><strong>Unavailable</strong><p>Submissions for this week could not be verified. Return to this week or retry the report.</p></div>}
  </section>;
}
