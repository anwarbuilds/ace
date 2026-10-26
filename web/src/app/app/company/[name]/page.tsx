import { CompanyLogo } from "@/components/CompanyLogo";
import Link from "next/link";

import { PageHero } from "@/components/page/PageParts";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { clean } from "@/lib/format";

interface Report {
  legal_entity: string;
  source: string;
  source_uri: string;
  metric_definition: string;
  period: string;
  report_version: string;
  approvals: number | null;
  denials: number | null;
  approval_rate: number | null;
  last_checked_at: string;
}

interface Intelligence { company: string; petition_history: Report[]; hiring_sponsorship_rate: null; status: string }

export default async function CompanyPage({ params }: { params: Promise<{name: string}> }) {
  const { name } = await params;
  // This route receives escaped path segments. Decode once before identity
  // lookup and API queries; malformed legacy bookmarks still remain usable.
  let company = name;
  try { company = decodeURIComponent(name); } catch { /* Keep a literal malformed name. */ }
  const data = await apiGetOr<Intelligence | null>("/api/company-intelligence", null, { name: company });
  return <ScrollArea><div className="pg">
    <PageHero eyebrow="Company intelligence" leading={<CompanyLogo name={company} size="large" />} title={clean(company)} subtitle="Official employer evidence, with its legal entity and reporting period." actions={<Link className="btn" href={`/app/opportunities?company=${encodeURIComponent(company)}`}>View opportunities</Link>} />
    {!data ? <section className="panel"><p>Company evidence could not be loaded. Reload to try again.</p></section> :
      data.petition_history.length === 0 ? <section className="panel"><h2>H-1B petition history</h2><p>Not available. No verified official report has been connected to this company.</p><p>Company workforce sponsorship rate: Not available.</p></section> :
      <section className="panel"><h2>Verified petition history</h2><p>Petition decisions describe an employer and reporting period. They do not predict sponsorship for this job.</p>
        {data.petition_history.map((r) => <div className="company-report" key={`${r.source_uri}:${r.period}:${r.report_version}`}>
          <h3>{clean(r.legal_entity)} · {clean(r.period)}</h3>
          <p>{clean(r.metric_definition)}. Approved: {r.approvals ?? "Not available"}. Denied: {r.denials ?? "Not available"}. Approval rate: {r.approval_rate == null ? "Not available" : `${Math.round(r.approval_rate * 100)}%`}.</p>
          <p>Source: <a href={r.source_uri} target="_blank" rel="noreferrer">{clean(r.source)}</a>. Report version: {clean(r.report_version)}. Checked: {new Date(r.last_checked_at).toLocaleDateString("en-US")}.</p>
        </div>)}
        <p>Company workforce sponsorship rate: Not available.</p>
      </section>}
  </div></ScrollArea>;
}
