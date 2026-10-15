// The navigation's icons, drawn on a 24px grid with a 1.75 stroke, as
// in the approved Pulls-first design.

const PATHS = {
  pulls: <path d="M3 12h2l3-7 4 14 3-8 2 3h4" />,
  briefcase: (
    <>
      <rect x="3" y="7" width="18" height="14" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
    </>
  ),
  chart: <path d="M4 20V9M10 20V4M16 20v-7M22 20v-11" />,
  send: <path d="m22 2-7 20-4-9-9-4zM22 2 11 13" />,
  file: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8" />,
  puzzle: (
    <path d="M12 3H8v4a2 2 0 1 1-4 0V3H2v7h4a2 2 0 1 1 0 4H2v7h7v-4a2 2 0 1 1 4 0v4h9v-7h-4a2 2 0 1 1 0-4h4V3h-7v4a2 2 0 1 1-4 0V3z" />
  ),
  archive: (
    <>
      <rect x="3" y="3" width="18" height="5" rx="1" />
      <path d="M5 8v13h14V8M10 12h4" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c4 4 4 14 0 18M12 3c-4 4-4 14 0 18" />
    </>
  ),
  settings: (
    <>
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
      <circle cx="12" cy="12" r="5" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" />
    </>
  ),
  moon: <path d="M21 13A9 9 0 0 1 11 3 9 9 0 1 0 21 13Z" />,
  system: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </>
  ),
  chevron: <path d="m6 9 6 6 6-6" />,
  right: <path d="M5 12h14m-7-7 7 7-7 7" />,
  left: <path d="M19 12H5m7 7-7-7 7-7" />,
  external: (
    <>
      <path d="M13 5h6v6M19 5 10 14" />
      <path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" />
    </>
  ),
  check: <path d="m4 12 5 5L20 6" />,
  x: <path d="M18 6 6 18M6 6l12 12" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l4 2" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 7h.01" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2 4 5v7c0 5 3 8 8 10 5-2 8-5 8-10V5z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  signout: (
    <>
      <path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5" />
      <path d="m16 8 4 4-4 4M20 12H9" />
    </>
  ),
} as const;

export type NavIconName = keyof typeof PATHS;

export function NavIcon({ name, size = "md" }: { name: NavIconName; size?: "sm" | "md" | "lg" }) {
  return (
    <svg className={`nic nic-${size}`} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
