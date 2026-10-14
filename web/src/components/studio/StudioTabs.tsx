"use client";

import { usePathname } from "next/navigation";

import { Tabs } from "@/components/jobs/Tabs";

const TABS = [
  { key: "overview", label: "Overview", href: "/app/resume-studio" },
  { key: "facts", label: "Knowledge base", href: "/app/resume-studio/facts" },
  { key: "documents", label: "Documents and versions", href: "/app/resume-studio/documents" },
  { key: "check", label: "ATS checker", href: "/app/resume-studio/check" },
  { key: "history", label: "History", href: "/app/resume-studio/history" },
];

export function StudioTabs({ counts }: { counts: Partial<Record<string, number>> }) {
  const path = usePathname();
  const active = TABS.slice(1).find((t) => path.startsWith(t.href))?.key ?? "overview";
  return (
    <Tabs
      group="studio"
      active={active}
      tabs={TABS.map((t) => ({ ...t, count: counts[t.key] ?? null }))}
    />
  );
}
