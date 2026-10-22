import type { NavIconName } from "./NavIcon";

export interface NavItem {
  href: string;
  label: string;
  short: string;
  icon: NavIconName;
  /** Other routes that belong to this entry, so it stays selected there. */
  also?: string[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

// The order the owner works in: the daily loop first, then the tools,
// then the system pages. Answers belong with the extension that fills
// from them, Skills with Resume Studio; both keep their own routes.
export const NAV: NavGroup[] = [
  {
    label: "Daily workspace",
    items: [
      { href: "/app/pulls", label: "Pulls", short: "Pulls", icon: "pulls" },
      { href: "/app/opportunities", label: "Opportunities", short: "Jobs", icon: "briefcase", also: ["/app/jobs", "/app/saved"] },
      { href: "/app/applications", label: "Applications", short: "Applied", icon: "send" },
      { href: "/app/analytics", label: "Analytics", short: "Analytics", icon: "chart" },
      { href: "/app/dashboard", label: "Career Dashboard", short: "Dashboard", icon: "chart" },
      { href: "/app/applications/inbox", label: "Inbox Intelligence", short: "Inbox", icon: "send" },
    ],
  },
  {
    label: "Career tools",
    items: [
      { href: "/app/resume-studio", label: "Resume Studio", short: "Resume", icon: "file", also: ["/app/insights"] },
      { href: "/app/extension", label: "Autofill Extension", short: "Extension", icon: "puzzle", also: ["/app/answers"] },
      { href: "/app/archive", label: "Archive", short: "Archive", icon: "archive" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/app/coverage", label: "Coverage", short: "Coverage", icon: "globe" },
      { href: "/app/settings", label: "Settings", short: "Settings", icon: "settings" },
      { href: "/logout", label: "Sign out", short: "Sign out", icon: "signout" },
    ],
  },
];

export const ALL_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

const under = (path: string, href: string) => path === href || path.startsWith(`${href}/`);

export function isActive(item: NavItem, path: string): boolean {
  if (item.href === "/app/applications" && under(path, "/app/applications/inbox")) return false;
  return under(path, item.href) || (item.also ?? []).some((h) => under(path, h));
}

/** The entry a path belongs to, for the breadcrumb. */
export function activeItem(path: string): NavItem | null {
  return ALL_ITEMS.find((i) => isActive(i, path)) ?? null;
}
