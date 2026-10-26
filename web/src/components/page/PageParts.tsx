import type { ReactNode } from "react";

// The page header and figure cards every new-style page shares, after the
// approved Pulls-first design. Server-safe: no hooks.

export function PageHero({
  eyebrow,
  title,
  subtitle,
  count,
  actions,
  leading,
}: {
  eyebrow: string;
  title: string;
  subtitle?: ReactNode;
  count?: string | null;
  actions?: ReactNode;
  leading?: ReactNode;
}) {
  const heading = <>
    <div className="eyebrow">{eyebrow}</div>
    <h1 className="h1">{title}{count ? <span className="h1-count">{count}</span> : null}</h1>
    {subtitle ? <p className="subtitle">{subtitle}</p> : null}
  </>;
  return (
    <div className="page-hero">
      {leading ? <div className="page-hero-identity">{leading}<div>{heading}</div></div> : <div>{heading}</div>}
      {actions ? <div className="btns">{actions}</div> : null}
    </div>
  );
}

export function Kpi({
  label,
  value,
  foot,
  tone,
  href,
}: {
  label: string;
  value: ReactNode;
  foot: ReactNode;
  tone?: "good" | "warn" | "bad";
  href?: string;
}) {
  const body = (
    <>
      <div className="kpi-l">{label}</div>
      <div className="kpi-n">{value}</div>
      <div className={`kpi-f${tone ? ` ${tone}` : ""}`}>{foot}</div>
    </>
  );
  return href ? (
    <a className="kpi kpi-link" href={href}>
      {body}
    </a>
  ) : (
    <div className="kpi">{body}</div>
  );
}

/** Horizontal bars for a few labelled counts, each optionally a link to
 *  the records behind it. */
export function Bars({ rows, empty }: { rows: { label: string; n: number; href?: string }[]; empty: string }) {
  if (!rows.length || rows.every((r) => !r.n)) return <p className="quiet-note">{empty}</p>;
  const max = Math.max(1, ...rows.map((r) => r.n));
  return (
    <div className="hbars">
      {rows.map((r) => {
        const inner = (
          <>
            <span className="hb-l">{r.label}</span>
            <span className="hb-t">
              <span className="hb-f" style={{ width: `${Math.max(r.n ? 3 : 0, Math.round((100 * r.n) / max))}%` }} />
            </span>
            <span className="hb-n">{r.n.toLocaleString("en-US")}</span>
          </>
        );
        return r.href ? (
          <a className="hb" key={r.label} href={r.href}>
            {inner}
          </a>
        ) : (
          <div className="hb" key={r.label}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}

/** Columns per day, the newest on the right, the count on hover. */
export function DayColumns({ days, label }: { days: { date: string; n: number }[]; label: string }) {
  const max = Math.max(1, ...days.map((d) => d.n));
  return (
    <div className="daycols" role="img" aria-label={label}>
      {days.map((d) => (
        <span className="dc" key={d.date} title={`${d.date}: ${d.n}`}>
          <span className="dc-n">{d.n || ""}</span>
          <span className="dc-bar" style={{ height: d.n ? `${Math.max(6, (d.n / max) * 100)}%` : 0 }} />
          <span className="dc-l">{Number(d.date.slice(8, 10))}</span>
        </span>
      ))}
    </div>
  );
}
