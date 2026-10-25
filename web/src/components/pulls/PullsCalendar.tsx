"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { NavIcon } from "@/components/shell/NavIcon";
import type { PullFilter } from "@/lib/types";

export function PullsCalendar({ date, today, filter }: {date:string; today:string; filter:PullFilter}) {
  const router=useRouter();
  const [month,setMonth]=useState(date.slice(0,7));
  const first=new Date(`${month}-01T12:00:00Z`);
  const year=first.getUTCFullYear(); const m=first.getUTCMonth();
  const length=new Date(Date.UTC(year,m+1,0)).getUTCDate();
  const href=(day:string)=>`/app/pulls?${new URLSearchParams({...day===today?{}:{date:day},...filter==="all"?{}:{filter}})}`;
  const move=(direction:number)=>setMonth(new Date(Date.UTC(year,m+direction,1,12)).toISOString().slice(0,7));
  return <section className="panel pull-calendar"><h3>Jump to any date</h3><p>Select a day to view its discovery history.</p><div className="calendar-head"><strong>{first.toLocaleDateString("en-US",{month:"long",year:"numeric",timeZone:"UTC"})}</strong><div><button onClick={()=>move(-1)} aria-label="Previous month"><NavIcon name="left" size="sm"/></button> <button onClick={()=>move(1)} disabled={month>=today.slice(0,7)} aria-label="Next month"><NavIcon name="right" size="sm"/></button></div></div><div className="calendar-days">{["Su","Mo","Tu","We","Th","Fr","Sa"].map(day=><span key={day}>{day}</span>)}{Array.from({length:first.getUTCDay()},(_,i)=><span key={`blank${i}`} aria-hidden="true"/>)}{Array.from({length},(_,i)=>{const day=`${month}-${String(i+1).padStart(2,"0")}`;return day>today?<span className="calendar-future" key={day}>{i+1}</span>:<Link key={day} href={href(day)} scroll={false} aria-label={`View discovery history for ${day}`} aria-current={day===date?"date":undefined}>{i+1}</Link>;})}</div><label>Go directly to a date<input type="date" value={date} max={today} autoComplete="off" onChange={e=>{if(e.target.value&&e.target.value<=today)router.push(href(e.target.value),{scroll:false});}}/></label><Link className="calendar-today" href={href(today)} scroll={false}>Today</Link><p className="quiet-note">Only recorded Pulls appear for the selected day. Future dates cannot be selected.</p></section>;
}
