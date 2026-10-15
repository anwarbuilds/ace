import Link from "next/link";
import { notFound } from "next/navigation";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { AssessmentView } from "@/components/studio/AssessmentView";
import { apiGetOr } from "@/lib/api";
import type { Assessment, StudioOverview } from "@/lib/studio";

export const metadata = { title: "Check result · ace" };

export default async function AssessmentPage({ params }: PageProps<"/app/resume-studio/history/[id]">) {
  const { id } = await params;
  const [a, o] = await Promise.all([
    apiGetOr<Assessment | null>(`/api/studio/assessments/${encodeURIComponent(id)}`, null),
    apiGetOr<StudioOverview | null>("/api/studio", null),
  ]);
  if (!a) notFound();
  const label = o?.versions.find((v) => v.id === a.version_id)?.label;
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <div className="controls" style={{ paddingLeft: 0, marginBottom: 16 }}>
            <Link className="link-btn" href="/app/resume-studio/history">
              Back to history
            </Link>
            {a.job_id ? (
              <Link className="btn btn-secondary btn-sm" href={`/app/resume-studio/check?job=${a.job_id}`}>
                Check again
              </Link>
            ) : null}
          </div>
          <AssessmentView a={a} versionLabel={label} />
        </div>
      </div>
    </ScrollArea>
  );
}
