import Link from "next/link";

import { Icon } from "@/components/Icon";

/** Page numbers to show: the ends, and two either side of the current. */
export function pageWindow(current: number, last: number): (number | "gap")[] {
  const keep = new Set([1, last, current - 2, current - 1, current, current + 1, current + 2]);
  const out: (number | "gap")[] = [];
  let prev = 0;
  for (let p = 1; p <= last; p++) {
    if (!keep.has(p)) continue;
    if (p - prev > 1) out.push("gap");
    out.push(p);
    prev = p;
  }
  return out;
}

/** Numbered pages. Each is a URL, so a page can be bookmarked and Back
 *  returns to it. */
export function Pagination({
  current,
  total,
  pageSize,
  shown,
  href,
}: {
  current: number;
  total: number;
  pageSize: number;
  shown: number;
  href: (page: number) => string;
}) {
  const last = Math.max(1, Math.ceil(total / pageSize));
  const from = total ? (current - 1) * pageSize + 1 : 0;
  const to = (current - 1) * pageSize + shown;
  return (
    <nav className="pager" aria-label="Pages">
      <span className="pager-says">
        {total ? `${from.toLocaleString("en-US")} to ${to.toLocaleString("en-US")} of ${total.toLocaleString("en-US")}` : "Nothing to show"}
      </span>
      {last > 1 ? (
        <div className="pager-nums">
          {current > 1 ? (
            <Link className="pager-btn" href={href(current - 1)} aria-label="Previous page" scroll={false}>
              <Icon name="left" size={14} />
            </Link>
          ) : (
            <span className="pager-btn off" aria-hidden="true">
              <Icon name="left" size={14} />
            </span>
          )}
          {pageWindow(current, last).map((p, i) =>
            p === "gap" ? (
              <span key={`gap${i}`} className="pager-gap">
                &hellip;
              </span>
            ) : (
              <Link
                key={p}
                className="pager-btn"
                href={href(p)}
                aria-current={p === current ? "page" : undefined}
                scroll={false}
              >
                {p}
              </Link>
            ),
          )}
          {current < last ? (
            <Link className="pager-btn" href={href(current + 1)} aria-label="Next page" scroll={false}>
              <Icon name="right" size={14} />
            </Link>
          ) : (
            <span className="pager-btn off" aria-hidden="true">
              <Icon name="right" size={14} />
            </span>
          )}
        </div>
      ) : null}
    </nav>
  );
}
