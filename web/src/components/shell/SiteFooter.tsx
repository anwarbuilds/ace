import Link from "next/link";

const LINKS: [string, string][] = [
  ["/app", "Pulls"],
  ["/app/opportunities", "Opportunities"],
  ["/app/applications", "Applications"],
  ["/app/dashboard", "Dashboard"],
  ["/app/resume-studio", "Resume Studio"],
  ["/app/answers", "Answers"],
  ["/app/coverage", "Coverage"],
  ["/app/settings", "Settings"],
];

export function SiteFooter() {
  return (
    <footer className="foot">
      <nav className="foot-links" aria-label="Site">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href}>
            {label}
          </Link>
        ))}
      </nav>
      <div className="foot-base">
        <span className="brand-name">ace</span>
        <span>Private to you. Every role links to the employer&rsquo;s own posting; ace never applies for you.</span>
      </div>
    </footer>
  );
}
