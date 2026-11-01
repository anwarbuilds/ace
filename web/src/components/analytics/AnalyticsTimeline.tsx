"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { NavIcon } from "@/components/shell/NavIcon";
import type { ChartPoint, Interval } from "@/lib/analyticsCalculations";

export function AnalyticsTimeline({ points, interval }: { points: (ChartPoint & {href:string})[]; interval: Interval }) {
  const frame=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null),button=useRef<HTMLButtonElement>(null);
  const [width,setWidth]=useState(760),[active,setActive]=useState<number|null>(null);
  const id=useId().replace(/\W/g,"");
  useEffect(()=>{
    const node=frame.current;if(!node)return;
    const measure=()=>setWidth(Math.max(280,Math.round(node.getBoundingClientRect().width)));
    measure();const observer=new ResizeObserver(measure);observer.observe(node);return()=>observer.disconnect();
  },[]);
  const maximum=Math.max(1,...points.map(row=>row.count)), rough=maximum/4;
  const magnitude=10**Math.floor(Math.log10(rough));
  const step=[1,2,5,10].map(value=>value*magnitude).find(value=>value>=rough)??magnitude*10;
  const top=Math.max(1,step)*4;
  const left=34,right=width-12,base=120,plotHeight=108;
  const plotted=points.map((point,index)=>({...point,x:left+index/Math.max(1,points.length-1)*(right-left),y:base-point.count/top*plotHeight}));
  const line=plotted.map(point=>`${point.x},${point.y}`).join(" ");
  const stride=Math.max(1,Math.round(points.length/Math.min(11,Math.max(3,Math.floor((right-left)/62)))));
  const date=(value:string,full=false)=>new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US",{month:"short",...(interval==="monthly"?{year:"numeric"}:{day:"numeric",...(full?{year:"numeric"}:{})}),timeZone:"UTC"});
  const point=active==null?null:plotted[active];
  return <div ref={frame} className="an-line-chart">
    <svg viewBox={`0 0 ${width} 150`} role="img" aria-label={`Unique submissions by ${interval==="weekly"?"calendar week":interval==="monthly"?"calendar month":"submission date"}`} onMouseLeave={()=>setActive(null)}>
      <defs><linearGradient id={`submissions-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--an-chart-line,var(--accent))" stopOpacity=".18"/><stop offset="100%" stopColor="var(--an-chart-line,var(--accent))" stopOpacity=".035"/></linearGradient></defs>
      {[0,1,2,3,4].map(index=><g key={index}><line x1={left} x2={right} y1={base-index*plotHeight/4} y2={base-index*plotHeight/4} stroke="var(--border-subtle)"/><text x={left-14} y={base+4-index*plotHeight/4} textAnchor="end">{Number((top*index/4).toFixed(2))}</text></g>)}
      <line x1={left} x2={left} y1={12} y2={base} stroke="var(--border-subtle)"/>
      {plotted.length>0&&<><polygon points={`${left},${base} ${line} ${right},${base}`} fill={`url(#submissions-${id})`}/><polyline points={line} fill="none" stroke="var(--an-chart-line,var(--accent))" strokeWidth="2.2"/>{plotted.map((row,index)=><g key={row.date}>
        {plotted.length<=100&&<Link prefetch={false} href={row.href} aria-label={`${row.date}${row.end!==row.date?` through ${row.end}`:""}: ${row.count} submissions. Open applications.`} onMouseEnter={()=>setActive(index)} onFocus={()=>setActive(index)} onBlur={()=>setActive(null)}><circle cx={row.x} cy={row.y} r={active===index?4.3:3.2} fill="var(--an-chart-line,var(--accent))" stroke="var(--surface-1)" strokeWidth="1.3"><title>{`${date(row.date,true)}: ${row.count} submissions`}</title></circle></Link>}
        {(index===plotted.length-1||(index%stride===0&&plotted.length-1-index>=stride*.7))&&<text className="an-x-tick" x={row.x} y="143" textAnchor={index===plotted.length-1?"end":"middle"}>{date(row.date)}</text>}
      </g>)}</>}
    </svg>
    {point&&<div className="an-chart-tooltip" role="status" style={{left:Math.min(width-150,Math.max(8,point.x-65)),top:Math.max(0,point.y-54)}}><strong>{date(point.date,true)}</strong><span>{point.count.toLocaleString("en-US")} applications</span></div>}
    <div className="an-chart-data-action"><button ref={button} type="button" aria-haspopup="dialog" onClick={()=>dialog.current?.showModal()}><NavIcon name="file" size="sm"/>View chart data</button></div>
    <dialog ref={dialog} className="an-chart-dialog" aria-labelledby={`chart-data-${id}`} onClose={()=>button.current?.focus()} onClick={event=>{if(event.target===dialog.current){const node=dialog.current;if(!node)return;const box=node.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)node.close();}}}>
      <header><div><h2 id={`chart-data-${id}`}>Application submissions</h2><p>Exact counts behind this chart. Open a row to inspect its records.</p></div><button type="button" aria-label="Close chart data" onClick={()=>dialog.current?.close()}><NavIcon name="x"/></button></header>
      <div className="an-chart-table-scroll"><table className="an-chart-table"><thead><tr><th>Submission dates</th><th>Applications</th><th>Records</th></tr></thead><tbody>{points.map(row=><tr key={row.date}><th><time dateTime={row.date}>{date(row.date,true)}</time>{row.end!==row.date&&<> to <time dateTime={row.end}>{date(row.end,true)}</time></>}</th><td>{row.count.toLocaleString("en-US")}</td><td><Link prefetch={false} href={row.href}>View applications <NavIcon name="right" size="sm"/></Link></td></tr>)}</tbody></table></div>
    </dialog>
  </div>;
}
