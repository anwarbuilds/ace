"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon, type IconName } from "@/components/Icon";

import { useApp } from "./AppProvider";
import { useLive } from "./Live";

function NavItem({
  href,
  label,
  count,
  icon,
  active,
}: {
  href: string;
  label: string;
  count?: number | null;
  icon: IconName;
  active: boolean;
}) {
  return (
    <Link className="nav-item" href={href} aria-current={active ? "page" : undefined}>
      <Icon name={icon} />
      <span className="nav-label">{label}</span>
      {count ? <span className="nav-count">{count.toLocaleString("en-US")}</span> : null}
    </Link>
  );
}

export function Sidebar({
  queueCount,
  externalCount,
  answersFilled,
  coverageGaps,
}: {
  queueCount: number;
  externalCount: number;
  answersFilled: number;
  coverageGaps: number;
}) {
  const path = usePathname();
  const { marks, cycleTheme, setPaletteOpen, menuOpen, setMenuOpen } = useApp();
  const { stale } = useLive();
  const [mac, setMac] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMac(/Mac|iPhone|iPad/.test(navigator.userAgent)), []);
  const on = (p: string) => path === p || path.startsWith(`${p}/`);

  return (
    <>
      <nav className={`side${menuOpen ? " open" : ""}`} aria-label="Main">
        <div className="brand">
          <span className="brand-name">ace</span>
        </div>
        <button className="jump" onClick={() => setPaletteOpen(true)} title="Command palette">
          <Icon name="search" size={14} />
          <span>Search or jump to</span>
          <span className="kbd">{mac ? "⌘K" : "Ctrl K"}</span>
        </button>
        <div className="nav">
          <NavItem href="/app/opportunities" label="Opportunities" count={queueCount} icon="queue" active={on("/app/opportunities")} />
          <NavItem href="/app/activity" label="Activity" icon="feed" active={on("/app/activity")} />
        </div>
        <div className="nav-rule" />
        <div className="nav-head">Pipeline</div>
        <div className="nav">
          <NavItem
            href="/app/applications"
            label="Applications"
            count={(marks.applied || 0) + externalCount}
            icon="briefcase"
            active={on("/app/applications")}
          />
          <NavItem href="/app/archive" label="Archive" count={marks.archived} icon="check" active={on("/app/archive")} />
        </div>
        <div className="nav-rule" />
        <div className="nav-head">Intelligence</div>
        <div className="nav">
          <NavItem href="/app/resume-studio" label="Resume Studio" icon="doc" active={on("/app/resume-studio")} />
          <NavItem href="/app/insights/skills" label="Skills" icon="grid" active={on("/app/insights/skills")} />
          <NavItem href="/app/answers" label="Answers" count={answersFilled} icon="copy" active={on("/app/answers")} />
          <NavItem href="/app/coverage" label="Coverage" count={coverageGaps} icon="grid" active={on("/app/coverage")} />
        </div>
        <div className="side-foot">
          <Link className="nav-item" href="/app/activity">
            <span className={`dot${stale ? " stale" : ""}`} />
            <span className="nav-label" style={stale ? { color: "var(--warning)" } : undefined}>
              {stale ? "Not updating" : "Live"}
            </span>
          </Link>
          <button className="nav-item" onClick={cycleTheme}>
            <Icon name="sun" />
            <span className="nav-label">Theme</span>
          </button>
          <NavItem href="/app/settings" label="Settings" icon="gear" active={on("/app/settings")} />
        </div>
      </nav>
      {menuOpen ? <div className="scrim" onClick={() => setMenuOpen(false)} /> : null}
    </>
  );
}
