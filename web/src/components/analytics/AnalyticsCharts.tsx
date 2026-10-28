import Link from "next/link";
import { CHART_COLORS } from "@/lib/analytics";
import type { ChartPoint, Interval } from "@/lib/analyticsCalculations";

export function MiniBar({ value, max, color = CHART_COLORS[0] }: { value: number; max: number; color?: string }) {
  return <span className="an-mini-track" aria-hidden="true"><span style={{ width: `${max ? Math.min(100, value / max * 100) : 0}%`, background: color }} /></span>;
}
export function LineChart({ points, interval, href }: { points: ChartPoint[]; interval: Interval; href: (point: ChartPoint) => string }) {
  const id = `submissions-${interval}`;
  const maximum = Math.max(1, ...points.map(p => p.count));
  const step = Math.max(1, Math.ceil(maximum / 4));
  const top = step * 4;
  const plotted = points.map((point, i) => ({ ...point, x: 38 + i / Math.max(1, points.length - 1) * 704, y: 130 - point.count / top * 112 }));
  const line = plotted.map(p => `${p.x},${p.y}`).join(" ");
  const tick = (date: string) => new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", ...(interval === "monthly" ? { year: "2-digit" } : { day: "numeric" }), timeZone: "UTC" });
  return <div className="an-line-chart">
    <svg viewBox="0 0 760 166" role="img" aria-label={`Unique submissions by ${interval === "weekly" ? "calendar week" : interval === "monthly" ? "calendar month" : "submission date"}`}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".16" /><stop offset="100%" stopColor="var(--accent)" stopOpacity=".03" /></linearGradient></defs>
      {[0, 1, 2, 3, 4].map(i => <g key={i}><line x1="38" x2="748" y1={130 - i * 28} y2={130 - i * 28} stroke="var(--border-subtle)" /><text x="23" y={134 - i * 28} textAnchor="end">{step * i}</text></g>)}
      {plotted.length > 0 && <><polygon points={`38,130 ${line} ${plotted.at(-1)!.x},130`} fill={`url(#${id})`} /><polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="2.3" />{plotted.map((p, i) => <g key={p.date}>
        {plotted.length <= 100 && <a href={href(p)} aria-label={`${p.date}${p.end !== p.date ? ` through ${p.end}` : ""}: ${p.count} submissions. Open applications.`}><circle cx={p.x} cy={p.y} r="4" fill="var(--accent)" stroke="var(--surface-1)" strokeWidth="1.5"><title>{`${p.date}: ${p.count} submissions`}</title></circle></a>}
        {(i % Math.max(1, Math.ceil(plotted.length / 8)) === 0 || i === plotted.length - 1) && <text x={p.x} y="155" textAnchor="middle">{tick(p.date)}</text>}
      </g>)}</>}
    </svg>
    <details className="an-chart-details"><summary>View chart data</summary><div className="an-data-scroll"><table className="an-table"><thead><tr><th>Submission dates</th><th>Applications</th><th>Records</th></tr></thead><tbody>{points.map(p => <tr key={p.date}><th>{p.date}{p.end !== p.date && ` to ${p.end}`}</th><td>{p.count}</td><td><Link href={href(p)}>View applications</Link></td></tr>)}</tbody></table></div></details>
  </div>;
}
export function ColumnChart({ rows, label, weekly = false, percentages = false }: { rows: { label: string; count: number; detail?: string; href?: string; future?: boolean }[]; label: string; weekly?: boolean; percentages?: boolean }) {
  const max = Math.max(1, ...rows.map(r => r.count));
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  return <div className={`an-columns${weekly ? " an-weekly" : ""}`} aria-label={label}>
    {rows.map((r, i) => {
      const body = <><div className="an-column-plot"><i style={{ height: `${r.count / max * 100}%`, background: weekly ? `linear-gradient(180deg, ${CHART_COLORS[0]}, ${CHART_COLORS[1]})` : CHART_COLORS[i % CHART_COLORS.length] }}><span>{r.future ? "" : r.count}</span></i></div><span>{r.label}</span>{percentages && <strong>{total ? `${Math.round(r.count / total * 100)}%` : "No sample"}</strong>}</>;
      const description = `${r.detail ?? r.label}: ${r.future ? "future day" : `${r.count} applications`}`;
      return r.href && !r.future ? <Link className="an-column" key={r.label} href={r.href} aria-label={description}>{body}</Link> : <div className="an-column" key={r.label} tabIndex={0} aria-label={description}>{body}</div>;
    })}
  </div>;
}
export function Donut({ rows, label }: { rows: { label: string; count: number }[]; label: string }) {
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  let current = 0;
  const stops = rows.map((r, i) => { const start = current; current += total ? r.count / total * 100 : 0; return `${CHART_COLORS[i % CHART_COLORS.length]} ${start}% ${current}%`; });
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
