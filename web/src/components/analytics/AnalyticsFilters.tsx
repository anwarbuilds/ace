"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

const subscribe = () => () => {};
const clientReady = () => true;
const serverReady = () => false;
function useReady() { return useSyncExternalStore(subscribe, clientReady, serverReady); }
import { familyLabel } from "@/lib/format";
import { CompanyLogo } from "@/components/CompanyLogo";
import { NavIcon } from "@/components/shell/NavIcon";
import { mondayOf, shiftDate } from "@/lib/analyticsCalculations";

export function AnalyticsFilters({ families, today }: { families: string[]; today: string }) {
  const ready = useReady();
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const [dates, setDates] = useState(params.get("days") === "custom" || Boolean(params.get("start") || params.get("end")));
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key === "days") { next.delete("start"); next.delete("end"); }
    router.push(`${path}?${next}`, { scroll: false });
  };
  return <div className="an-filters">
    <label className="sr" htmlFor="analytics-family">Application role family</label>
    <select disabled={!ready} id="analytics-family" value={params.get("family") ?? ""} onChange={e => change("family", e.target.value)}>
      <option value="">All roles</option>{families.map(f => <option value={f} key={f}>{familyLabel(f)}</option>)}
    </select>
    <div className="an-ranges" aria-label="Submission date range" role="group">{[["14", "14 days"], ["30", "30 days"], ["90", "90 days"], ["all", "All time"]].map(([value, label]) => <button disabled={!ready} type="button" key={value} aria-pressed={(params.get("days") ?? (params.get("start") || params.get("end") ? "custom" : "all")) === value} onClick={() => {setDates(false);change("days", value);}}>{label}</button>)}</div>
    <button disabled={!ready} className="an-date-toggle" aria-expanded={dates} onClick={() => setDates(!dates)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 11h18"/></svg> Choose dates</button>
    {dates && <form className="an-date-popover" onSubmit={e => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      const start = String(form.get("start")), end = String(form.get("end"));
      if (start > end) { e.currentTarget.querySelector<HTMLInputElement>('[name="end"]')?.setCustomValidity("Choose an end date on or after the start date."); e.currentTarget.reportValidity(); return; }
      const next = new URLSearchParams(params);
      next.set("days", "custom"); next.set("start", String(form.get("start"))); next.set("end", String(form.get("end")));
      router.push(`${path}?${next}`, { scroll: false });
    }}><label>From<input type="date" name="start" required max={today} defaultValue={params.get("start") ?? today} autoComplete="off" onInput={e=>e.currentTarget.form?.querySelector<HTMLInputElement>('[name="end"]')?.setCustomValidity("")} /></label><label>Through<input type="date" name="end" required max={today} defaultValue={params.get("end") ?? today} autoComplete="off" onInput={e=>e.currentTarget.setCustomValidity("")} /></label><button type="submit">Apply dates</button></form>}
  </div>;
}

export function AnalyticsCompanySelect({ companies, value }: { companies: string[]; value: string }) {
  const ready = useReady();
  const router = useRouter();
  const params = useSearchParams();
  return <label className="an-company-select">{value && <CompanyLogo name={value} size="compact" />}<span className="sr">Company evidence</span><select disabled={!ready} value={value} onChange={e => {const next = new URLSearchParams(params); next.set("company", e.target.value); router.push(`/app/analytics?${next}`, { scroll: false });}}>{companies.map(name => <option key={name}>{name}</option>)}</select></label>;
}


export function AnalyticsChartInterval({monthly, interval, detailed = true}: {monthly?: boolean; interval?: string; detailed?: boolean}) {
  const ready=useReady();
  const router=useRouter();
  const params=useSearchParams();
  return <label className="an-chart-mode"><span className="sr">Chart interval</span><select disabled={!ready} value={interval ?? (monthly ? "monthly" : params.get("interval") ?? "daily")} onChange={event=>{const next=new URLSearchParams(params);next.set("interval",event.target.value);router.push(`/app/analytics?${next}`,{scroll:false});}}><option value="daily" disabled={!detailed && monthly}>Daily</option><option value="weekly" disabled={!detailed && monthly}>Weekly</option><option value="monthly">Monthly</option></select></label>;
}

export function AnalyticsWeekPicker({ start, today }: { start: string; today: string }) {
  const ready = useReady(), router = useRouter(), params = useSearchParams();
  const current = mondayOf(today);
  const change = (day: string) => { const next = new URLSearchParams(params); const monday = mondayOf(day) > current ? current : mondayOf(day); if (monday === current) next.delete("week"); else next.set("week", monday); router.push(`/app/analytics?${next}`, { scroll: false }); };
  return <div className="an-week-picker" role="group" aria-label="Displayed calendar week">{start < current && <button className="an-week-reset" disabled={!ready} onClick={()=>change(current)}>This week</button>}<button disabled={!ready} aria-label="Previous week" onClick={()=>change(shiftDate(start,-7))}><NavIcon name="left" size="sm"/></button><button disabled={!ready || start >= current} aria-label="Next week" onClick={()=>change(shiftDate(start,7))}><NavIcon name="right" size="sm"/></button></div>;
}
