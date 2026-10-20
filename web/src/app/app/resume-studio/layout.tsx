import { StudioTabs } from "@/components/studio/StudioTabs";
import { StudioUpload } from "@/components/studio/StudioUpload";
import { apiGetOr } from "@/lib/api";
import type { StudioOverview } from "@/lib/studio";

export default async function StudioLayout({ children }: LayoutProps<"/app/resume-studio">) {
  const o = await apiGetOr<StudioOverview | null>("/api/studio", null);
  const review = (o?.facts.by_status.suggested ?? 0) + (o?.facts.by_status.needs_clarification ?? 0);
  return (
    <>
      <div className="head">
        <div className="eyebrow">Career tools</div>
        <div className="head-row">
          <div>
            <h1 className="h1">Resume Studio</h1>
            <p className="subtitle">
              Build a verified resume knowledge base and review job-specific tailoring suggestions before exporting.
            </p>
          </div>
          <span className="spacer" />
          <StudioUpload label="Add resume version" />
        </div>
        <StudioTabs counts={{ facts: review || undefined, history: o?.recent.length || undefined }} />
      </div>
      {children}
    </>
  );
}
