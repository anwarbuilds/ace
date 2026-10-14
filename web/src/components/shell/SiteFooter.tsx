import Link from "next/link";

import { GROUPS } from "@/lib/browse";

const COLUMNS: { title: string; links: [string, string][] }[] = [
  {
    title: "Find roles",
    links: [
      ["/app/opportunities", "All opportunities"],
      ...GROUPS.slice(0, 5).map((g): [string, string] => [`/app/browse/${g.slug}`, g.title]),
      ["/app/companies", "Companies"],
    ],
  },
  {
    title: "Your pipeline",
    links: [
      ["/app/applications", "Applications"],
      ["/app/archive", "Archive"],
      ["/app/activity", "Discovery activity"],
    ],
  },
  {
    title: "Your profile",
    links: [
      ["/app/resume-studio", "Resume Studio"],
      ["/app/resume-studio/check", "ATS checker"],
      ["/app/answers", "Answer bank"],
      ["/app/insights/skills", "Skills"],
    ],
  },
  {
    title: "ace",
    links: [
      ["/app/coverage", "Coverage"],
      ["/app/settings", "Settings"],
      ["/app/settings#data", "Your data"],
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="foot">
      <div className="foot-cols">
        {COLUMNS.map((c) => (
          <div key={c.title} className="foot-col">
            <p className="eyebrow">{c.title}</p>
            {c.links.map(([href, label]) => (
              <Link key={href} href={href}>
                {label}
              </Link>
            ))}
          </div>
        ))}
      </div>
      <div className="foot-base">
        <span className="brand-name">ace</span>
        <span>Private to you. Every role links to the employer&rsquo;s own posting; ace never applies for you.</span>
      </div>
    </footer>
  );
}
