import { LiveChip } from "@/components/shell/Live";
import { StudioTabs } from "@/components/studio/StudioTabs";
import { apiGetOr } from "@/lib/api";
import type { StudioOverview } from "@/lib/studio";

export default async function StudioLayout({ children }: LayoutProps<"/app/resume-studio">) {
  const o = await apiGetOr<StudioOverview | null>("/api/studio", null);
  const review = (o?.facts.by_status.suggested ?? 0) + (o?.facts.by_status.needs_clarification ?? 0);
  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Resume Studio</h1>
          <span className="spacer" />
          <LiveChip />
        </div>
        <StudioTabs counts={{ facts: review || undefined, history: o?.recent.length || undefined }} />
      </div>
      {children}
    </>
  );
}
