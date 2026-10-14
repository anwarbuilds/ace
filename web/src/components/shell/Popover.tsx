"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** A frosted popover placed under its anchor, flipped above when there
 *  is no room. Closes on an outside click or Escape. */
export function Popover({
  anchor,
  onClose,
  children,
  className = "",
}: {
  anchor: HTMLElement | null;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (!anchor || !ref.current) return;
    const r = anchor.getBoundingClientRect();
    const w = ref.current.offsetWidth;
    const h = ref.current.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    setPos({
      left: Math.max(8, Math.min(vw - w - 8, r.left)),
      top: r.bottom + 6 + h > vh ? Math.max(8, r.top - h - 6) : r.bottom + 6,
    });
  }, [anchor]);

  useEffect(() => {
    // Only while open: a closed popover that still swallowed Escape
    // stopped Escape from leaving the job page.
    if (!anchor) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || anchor?.contains(t)) return;
      onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [anchor, onClose]);

  if (!anchor) return null;
  return createPortal(
    <div
      ref={ref}
      className={`pop ${className}`}
      style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: -9999 }}
    >
      {children}
    </div>,
    document.body,
  );
}

/** Anchor state for a popover: the element it opens from, or null. */
export function usePopover() {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  return {
    anchor,
    open: (el: HTMLElement) => setAnchor((a) => (a === el ? null : el)),
    close: () => setAnchor(null),
  };
}
