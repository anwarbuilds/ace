"use client";

import { Icon } from "@/components/Icon";

import { useApp } from "./AppProvider";

/** Shown below 1025px, where the sidebar becomes a drawer. */
export function Topbar() {
  const { setMenuOpen, setPaletteOpen } = useApp();
  return (
    <div className="topbar">
      <button className="iconbtn" onClick={() => setMenuOpen(true)} aria-label="Menu">
        <Icon name="menu" />
      </button>
      <span className="brand-name" style={{ fontSize: 18 }}>
        ace
      </span>
      <span className="spacer" />
      <button className="iconbtn" onClick={() => setPaletteOpen(true)} aria-label="Search">
        <Icon name="search" />
      </button>
    </div>
  );
}
