// The old UI's icon set, drawn on a 16px grid with a 1.5 stroke.

const PATHS = {
  star: <path d="M8 2l1.8 3.9 4.2.5-3.1 2.9.8 4.2L8 11.5 4.3 13.5l.8-4.2L2 6.4l4.2-.5z" />,
  check: <path d="M3 8.5l3.2 3.2L13 5" />,
  x: <path d="M4 4l8 8M12 4l-8 8" />,
  ext: (
    <>
      <path d="M6 3h7v7M13 3L6.5 9.5" />
      <path d="M11 9.5V13H3V5h3.5" />
    </>
  ),
  left: <path d="M10 3L5 8l5 5" />,
  right: <path d="M6 3l5 5-5 5" />,
  search: (
    <>
      <circle cx="7.2" cy="7.2" r="4.2" />
      <path d="M10.4 10.4L13.5 13.5" />
    </>
  ),
  plus: <path d="M8 3.5v9M3.5 8h9" />,
  menu: <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />,
  queue: <path d="M2.5 4h11M2.5 8h11M2.5 12h7" />,
  feed: <path d="M3 12.5V7M8 12.5V3.5M13 12.5V9.5" />,
  doc: (
    <>
      <path d="M4 2h5l3 3v9H4z" />
      <path d="M9 2v3h3" />
    </>
  ),
  grid: <path d="M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z" />,
  sun: (
    <>
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1v1.6M8 13.4V15M15 8h-1.6M2.6 8H1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1M12.9 12.9l-1.1-1.1M4.2 4.2L3.1 3.1" />
    </>
  ),
  gear: (
    <>
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 1.5v1.8M8 12.7v1.8M14.5 8h-1.8M3.3 8H1.5M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3M12.6 12.6l-1.3-1.3M4.7 4.7L3.4 3.4" />
    </>
  ),
  briefcase: (
    <>
      <rect x="2" y="5" width="12" height="9" rx="1.5" />
      <path d="M6 5V3.5h4V5" />
    </>
  ),
  upload: (
    <>
      <path d="M8 11V3M5 6l3-3 3 3" />
      <path d="M2.5 11v2.5h11V11" />
    </>
  ),
  minus: <path d="M3.5 8h9" />,
  download: (
    <>
      <path d="M8 3v8M5 8l3 3 3-3" />
      <path d="M2.5 11v2.5h11V11" />
    </>
  ),
  copy: (
    <>
      <rect x="5.5" y="5.5" width="8" height="9" rx="1.5" />
      <path d="M10.5 5.5V2.5h-8v8h2" />
    </>
  ),
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
