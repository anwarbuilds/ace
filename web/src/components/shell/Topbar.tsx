"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ago } from "@/lib/format";
import { ApplicationCount } from "@/components/applications/ApplicationCount";

import { THEME_LABEL, useApp, useNow } from "./AppProvider";
import { LIVE_LABEL, liveState } from "./liveState";
import { activeItem } from "./nav";
import { NavIcon } from "./NavIcon";

/** The page header every route shares: where you are, whether ace is
 *  checking, and the theme. */
export function Topbar() {
  const path = usePathname();
  const { lastPoll, theme, cycleTheme } = useApp();
  const now = useNow();
  const state = liveState(lastPoll, now);
  const item = activeItem(path);
  const since = lastPoll ? ago(lastPoll, now) : "";
  const when = !lastPoll ? "" : since === "just now" ? "checked just now" : `checked ${since} ago`;

  return (
    <header className="tb">
      <div className="tb-crumb">
        <Link href="/app/pulls" className="tb-ace">
          <span>a</span>ce
        </Link>
        <span className="tb-sep" aria-hidden="true">
          /
        </span>
        <strong>{item?.label ?? "ace"}</strong>
      </div>
      <div className="tb-actions">
        <Link href="/app/pulls" className={`tb-live s-${state}`} suppressHydrationWarning title="When a source last answered">
          <i className="pulse" aria-hidden="true" />
          <span suppressHydrationWarning>{LIVE_LABEL[state]}</span>
          <span className="tb-when" suppressHydrationWarning>
            {when}
          </span>
        </Link>
        <button
          className="tb-icon"
          onClick={cycleTheme}
          title={`Theme: ${THEME_LABEL[theme]}. Switch theme`}
          aria-label={`Theme: ${THEME_LABEL[theme]}. Switch theme`}
        >
          <NavIcon name={theme === "dark" ? "moon" : theme === "light" ? "sun" : "system"} />
        </button>
        <Link className="tb-applied" href="/app/applications" aria-label="Open tracked applications">
          <NavIcon name="send" size="sm" />
          <span>Applied</span>
          <strong><ApplicationCount /></strong>
        </Link>
      </div>
    </header>
  );
}

/** Five destinations at the bottom of a phone screen; the rest are a
 *  tap away on Settings and the pages themselves. */
export function MobileBar() {
  const path = usePathname();
  const items = [
    { href: "/app/pulls", label: "Pulls", icon: "pulls" as const },
    { href: "/app/opportunities", label: "Jobs", icon: "briefcase" as const, also: ["/app/jobs"] },
    { href: "/app/applications", label: "Applied", icon: "send" as const },
    { href: "/app/analytics", label: "Analytics", icon: "chart" as const },
    { href: "/app/more", label: "More", icon: "settings" as const, also: ["/app/resume-studio", "/app/extension", "/app/archive", "/app/coverage", "/app/settings", "/app/answers", "/app/insights"] },
  ];
  const under = (h: string) => path === h || path.startsWith(`${h}/`);
  return (
    <nav className="mb" aria-label="Main">
      {items.map((i) => {
        const on = under(i.href) || (i.also ?? []).some(under);
        return (
          <Link key={i.href} href={i.href} className={on ? "on" : undefined} aria-current={on ? "page" : undefined}>
            <NavIcon name={i.icon} />
            {i.label}
          </Link>
        );
      })}
    </nav>
  );
}
