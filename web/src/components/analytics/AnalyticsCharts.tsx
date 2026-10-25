
import { CHART_COLORS } from "@/lib/analytics";
import { AnalyticsChartInterval } from "./AnalyticsFilters";
export function MiniBar({ value, max, color = CHART_COLORS[0] }: { value: number; max: number; color?: string }) {
  return <span className="an-mini-track" aria-hidden="true"><span style={{ width: `${max ? Math.min(100, value / max * 100) : 0}%`, background: color }} /></span>;
}
export function LineChart({ data, monthly, interval = "daily" }: { data: {date: string; count: number}[]; monthly: boolean; interval?: string }) {
  const id = `analytics-submissions-${data[0]?.date ?? "empty"}`;
  const mode = interval === "weekly" ? "weekly" : "daily";
  const grouped = mode === "weekly" && !monthly ? data.reduce<{date: string; count: number}[]>((all, row, i) => {if (i % 7 === 0) all.push({...row}); else all[all.length - 1].count += row.count; return all;}, []) : data;
  const max = Math.max(4, ...grouped.map(d => d.count));
  const top = Math.ceil(max / 4) * 4;
  const points = grouped.map((d, i) => ({...d, x: 35 + i / Math.max(1, grouped.length - 1) * 705, y: 130 - d.count / top * 112}));
  const line = points.map(p => `${p.x},${p.y}`).join(" ");
  return <div className="an-line-chart">
    <AnalyticsChartInterval monthly={monthly} />
    <svg viewBox="0 0 760 164" role="img" aria-label={`Unique submissions by ${monthly ? "month" : mode === "weekly" ? "7-day interval" : "submission date"}`}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".17"/><stop offset="100%" stopColor="var(--accent)" stopOpacity=".04"/></linearGradient></defs>
      {[0,1,2,3,4].map(i => <g key={i}><line x1="35" x2="748" y1={130-i*28} y2={130-i*28} stroke="var(--border)" strokeOpacity=".55"/><text x="20" y={134-i*28} textAnchor="end">{top*i/4}</text></g>)}
      {points.length > 0 && <><polygon points={`35,130 ${line} ${points.at(-1)!.x},130`} fill={`url(#${id})`} /><polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="2.5"/>{points.map((p, i) => <g key={p.date}><circle tabIndex={0} aria-label={`${p.date}: ${p.count} submissions`} cx={p.x} cy={p.y} r="3.6" fill="var(--accent)" stroke="var(--surface-1)" strokeWidth="1.5"><title>{`${p.date}: ${p.count} submissions`}</title></circle>{(i % Math.max(1, Math.ceil(points.length / 9)) === 0 || i === points.length-1) && <text x={p.x} y="152" textAnchor="middle">{new Date(p.date.length === 7 ? `${p.date}-01T12:00:00Z` : `${p.date}T12:00:00Z`).toLocaleDateString("en-US", {month:"short", ...(monthly ? {year:"2-digit"} : {day:"numeric"}), timeZone:"UTC"})}</text>}</g>)}</>}
    </svg>
    <details className="an-chart-details"><summary>View chart data</summary><div>{grouped.map(d => <span key={d.date}>{d.date}: <b>{d.count}</b></span>)}</div></details>
  </div>;
}
export function ColumnChart({ rows, label, weekly = false }: { rows: {label: string; count: number; detail?: string}[]; label: string; weekly?: boolean }) {
  const max = Math.max(1, ...rows.map(r => r.count));
  return <div className={`an-columns${weekly ? " an-weekly" : ""}`} role="img" aria-label={`${label}. ${rows.map(r => `${r.detail ?? r.label}: ${r.count}`).join("; ")}`}>
    {rows.map((r,i) => <div className="an-column" key={r.label} tabIndex={0} aria-label={`${r.detail ?? r.label}: ${r.count}`}><span>{r.count}</span><div className="an-column-space"><i style={{height: `${r.count/max*100}%`, background: weekly ? `linear-gradient(180deg, ${CHART_COLORS[0]}, ${CHART_COLORS[1]})` : CHART_COLORS[i%CHART_COLORS.length]}} /></div><span>{r.label}</span></div>)}
  </div>;
}
export function Donut({ rows, label }: { rows: {label: string; count: number}[]; label: string }) {
  const total = rows.reduce((n,r)=>n+r.count,0);
  let current=0;
  const stops=rows.map((r,i)=>{ const start=current;current+=total?r.count/total*100:0;return `${CHART_COLORS[i%CHART_COLORS.length]} ${start}% ${current}%`; });
  return <div className="an-donut" role="img" aria-label={`${label}. ${rows.map(r=>`${r.label}: ${r.count}`).join("; ")}`} style={{background: total ? `conic-gradient(${stops.join(",")})` : "var(--surface-2)"}}><div><strong>{total}</strong><span>{label}</span></div></div>;
}
export function PetitionChart({ rows }: { rows: {period:string; approvals:number; denials:number; rate:number|null}[] }) {
  const max=Math.max(1,...rows.map(r=>r.approvals+r.denials));
  return <div className="an-petition-chart"><div className="an-chart-key"><span><i style={{background:CHART_COLORS[0]}}/> Approvals</span><span><i style={{background:CHART_COLORS[1]}}/> Denials</span><span><i style={{background:CHART_COLORS[2]}}/> Approval rate</span></div><svg viewBox="0 0 590 122" role="img" aria-label={`USCIS I-129 petition decisions. ${rows.map(r=>`${r.period}: ${r.approvals} approvals, ${r.denials} denials, ${r.rate == null ? "rate unavailable" : `${Math.round(r.rate*100)} percent approved`}`).join("; ")}`}>
    {[0,1,2,3,4].map(i=><g key={i}><line x1="42" x2="544" y1={96-i*20} y2={96-i*20} stroke="var(--border)"/><text x="35" y={100-i*20} textAnchor="end">{Math.round(max*i/4).toLocaleString("en-US")}</text><text x="552" y={100-i*20}>{i*25}%</text></g>)}
    {rows.map((r,i)=>{const x=65+i/Math.max(1,rows.length-1)*440;return <g key={r.period} tabIndex={0} aria-label={`${r.period}: ${r.approvals} approved, ${r.denials} denied`}><title>{`${r.period}: ${r.approvals} approved, ${r.denials} denied`}</title><rect x={x-18} y={96-r.approvals/max*80} width="36" height={r.approvals/max*80} fill={CHART_COLORS[0]}/><rect x={x-18} y={96-(r.approvals+r.denials)/max*80} width="36" height={r.denials/max*80} fill={CHART_COLORS[1]}/><text x={x} y="115" textAnchor="middle">{r.period}</text></g>})}
    <polyline points={rows.map((r,i)=>r.rate==null?null:`${65+i/Math.max(1,rows.length-1)*440},${96-r.rate*80}`).filter(Boolean).join(" ")} fill="none" stroke={CHART_COLORS[2]} strokeWidth="2.5"/>{rows.map((r,i)=>r.rate==null?null:<circle key={`rate-${r.period}`} cx={65+i/Math.max(1,rows.length-1)*440} cy={96-r.rate*80} r="4" fill={CHART_COLORS[2]} stroke="var(--surface-1)" strokeWidth="1.2"/>)}
  </svg></div>;
}
