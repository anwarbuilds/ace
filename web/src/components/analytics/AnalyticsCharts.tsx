import Link from "next/link";
import { CHART_COLORS } from "@/lib/analytics";
import { AnalyticsTimeline } from "./AnalyticsTimeline";
import type { ChartPoint, Interval } from "@/lib/analyticsCalculations";

export function MiniBar({ value, max, color = CHART_COLORS[0] }: { value: number; max: number; color?: string }) {
  return <span className="an-mini-track" aria-hidden="true"><span style={{ width: `${max ? Math.min(100, value / max * 100) : 0}%`, background: color }} /></span>;
}
export function LineChart({ points, interval, href }: { points: ChartPoint[]; interval: Interval; href: (point: ChartPoint) => string }) {
  return <AnalyticsTimeline points={points.map(point=>({...point,href:href(point)}))} interval={interval}/>;
}

export function ColumnChart({ rows, label, weekly = false, percentages = false }: { rows: { label: string; count: number; detail?: string; href?: string; future?: boolean; color?: string }[]; label: string; weekly?: boolean; percentages?: boolean }) {
  const max = Math.max(1, ...rows.map(r => r.count));
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  return <div className={`an-columns${weekly ? " an-weekly" : ""}`} aria-label={label}>
    {rows.map((r, i) => {
      const body = <><div className="an-column-plot"><i style={{ height: `${r.count / max * 100}%`, background: weekly ? `linear-gradient(180deg, ${CHART_COLORS[0]}, ${CHART_COLORS[1]})` : r.color ?? CHART_COLORS[i % CHART_COLORS.length] }}><span>{r.future ? "" : r.count}</span></i></div><span>{r.label}</span>{percentages && <strong>{total ? `${Math.round(r.count / total * 100)}%` : "No sample"}</strong>}</>;
      const description = `${r.detail ?? r.label}: ${r.future ? "future day" : `${r.count} applications`}`;
      return r.href && !r.future ? <Link prefetch={false} className="an-column" key={r.label} href={r.href} aria-label={description}>{body}</Link> : <div className="an-column" key={r.label} data-future={r.future || undefined} tabIndex={0} title={r.future ? "Future day; activity is not yet known" : undefined} aria-label={description}>{body}</div>;
    })}
  </div>;
}
export function Donut({ rows, label }: { rows: { label: string; count: number; color?: string }[]; label: string }) {
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  let current = 0;
  const stops = rows.map((r, i) => { const start = current; current += total ? r.count / total * 100 : 0; return `${r.color ?? CHART_COLORS[i % CHART_COLORS.length]} ${start}% ${current}%`; });
  return <div className="an-donut" role="img" aria-label={`${label}. ${rows.map(r => `${r.label}: ${r.count}`).join("; ")}`} style={{ background: total ? `conic-gradient(${stops.join(",")})` : "var(--surface-2)" }}><div><strong>{total.toLocaleString("en-US")}</strong><span>{label}</span></div></div>;
}
export function PetitionChart({ rows }: { rows: { period: string; approvals: number; denials: number; rate: number | null }[] }) {
  const max = Math.max(1, ...rows.map(r => r.approvals + r.denials));
  const x = (i: number) => rows.length === 1 ? 294 : 70 + i / (rows.length - 1) * 448;
  return <div className="an-petition-chart"><div className="an-chart-key"><span><i style={{ background: CHART_COLORS[0] }} /> Approvals</span><span><i style={{ background: CHART_COLORS[1] }} /> Denials</span><span><i style={{ background: CHART_COLORS[0] }} /> Approval rate</span></div><svg viewBox="0 0 590 126" role="img" aria-label={`USCIS I-129 petition decisions. ${rows.map(r => `${r.period}: ${r.approvals} approvals, ${r.denials} denials, ${r.rate == null ? "rate unavailable" : `${Math.round(r.rate * 100)} percent approved`}`).join("; ")}`}>
    {[0, 1, 2, 3, 4].map(i => <g key={i}><line x1="42" x2="544" y1={96 - i * 20} y2={96 - i * 20} stroke="var(--border-subtle)" /><text x="35" y={100 - i * 20} textAnchor="end">{Math.round(max * i / 4).toLocaleString("en-US")}</text><text x="552" y={100 - i * 20}>{i * 25}%</text></g>)}
    {rows.map((r, i) => <g key={r.period} tabIndex={0} aria-label={`${r.period}: ${r.approvals} approved, ${r.denials} denied`}><title>{`${r.period}: ${r.approvals} approved, ${r.denials} denied`}</title><rect x={x(i) - 20} y={96 - r.approvals / max * 80} width="40" height={r.approvals / max * 80} fill={CHART_COLORS[0]} /><rect x={x(i) - 20} y={96 - (r.approvals + r.denials) / max * 80} width="40" height={r.denials / max * 80} fill={CHART_COLORS[1]} /><text x={x(i)} y="117" textAnchor="middle">{r.period}</text></g>)}
    {rows.map((r, i) => r.rate == null ? null : <g key={`rate-${r.period}`}>{i > 0 && rows[i - 1].rate != null && <line x1={x(i - 1)} y1={96 - rows[i - 1].rate! * 80} x2={x(i)} y2={96 - r.rate * 80} stroke={CHART_COLORS[0]} strokeWidth="2" />}<circle cx={x(i)} cy={96 - r.rate * 80} r="4" fill={CHART_COLORS[0]} stroke="var(--surface-1)" strokeWidth="1.2" /></g>)}
  </svg></div>;
}
