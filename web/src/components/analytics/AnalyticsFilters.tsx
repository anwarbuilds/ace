"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

const subscribe = () => () => {};
const clientReady = () => true;
const serverReady = () => false;
function useReady() { return useSyncExternalStore(subscribe, clientReady, serverReady); }
import { familyLabel } from "@/lib/format";
import { CompanyLogo } from "@/components/CompanyLogo";

export function AnalyticsFilters({ families, today }: { families: string[]; today: string }) {
  const ready = useReady();
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const [dates, setDates] = useState(params.get("days") === "custom");
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
    <div className="an-ranges" aria-label="Submission date range" role="group">{[["14", "14 days"], ["30", "30 days"], ["90", "90 days"], ["all", "All time"]].map(([value, label]) => <button disabled={!ready} type="button" key={value} aria-pressed={(params.get("days") ?? "30") === value} onClick={() => {setDates(false);change("days", value);}}>{label}</button>)}</div>
    <button disabled={!ready} className="an-date-toggle" aria-expanded={dates} onClick={() => setDates(!dates)}><span aria-hidden="true">▦</span> Choose dates</button>
    {dates && <form className="an-date-popover" onSubmit={e => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      const next = new URLSearchParams(params);
      next.set("days", "custom"); next.set("start", String(form.get("start"))); next.set("end", String(form.get("end")));
      router.push(`${path}?${next}`, { scroll: false });
    }}><label>From<input type="date" name="start" required max={today} defaultValue={params.get("start") ?? today} autoComplete="off" /></label><label>Through<input type="date" name="end" required max={today} defaultValue={params.get("end") ?? today} autoComplete="off" /></label><button type="submit">Apply dates</button></form>}
  </div>;
}

export function AnalyticsCompanySelect({ companies, value }: { companies: string[]; value: string }) {
  const ready = useReady();
  const router = useRouter();
  const params = useSearchParams();
  return <label className="an-company-select">{value && <CompanyLogo name={value} size="compact" />}<span className="sr">Company evidence</span><select disabled={!ready} value={value} onChange={e => {const next = new URLSearchParams(params); next.set("company", e.target.value); router.push(`/app/analytics?${next}`, { scroll: false });}}>{companies.map(name => <option key={name}>{name}</option>)}</select></label>;
}


export function AnalyticsChartInterval({monthly}: {monthly: boolean}) {
  const ready=useReady();
  const router=useRouter();
  const params=useSearchParams();
  return <label className="an-chart-mode"><span className="sr">Chart interval</span><select disabled={!ready} value={monthly ? "monthly" : params.get("interval") === "weekly" ? "weekly" : "daily"} onChange={event=>{const next=new URLSearchParams(params);next.set("interval",event.target.value);router.push(`/app/analytics?${next}`,{scroll:false});}}>{monthly ? <option value="monthly">Monthly</option> : <><option value="daily">Daily</option><option value="weekly">7-day totals</option></>}</select></label>;
}
