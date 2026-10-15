import { ScrollArea } from "@/components/shell/ScrollArea";
import { Checker } from "@/components/studio/Checker";
import { apiGetOr } from "@/lib/api";
import type { StudioOverview } from "@/lib/studio";
import type { Job } from "@/lib/types";

export const metadata = { title: "ATS checker · ace" };

export default async function CheckPage({ searchParams }: PageProps<"/app/resume-studio/check">) {
  const sp = await searchParams;
  const jobId = Number(Array.isArray(sp.job) ? sp.job[0] : sp.job) || null;
  const [o, job] = await Promise.all([
    apiGetOr<StudioOverview | null>("/api/studio", null),
    jobId ? apiGetOr<Job | null>(`/api/jobs/${jobId}`, null) : Promise.resolve(null),
  ]);
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <Checker
            versions={(o?.versions ?? []).filter((v) => v.status === "approved")}
            primaryId={o?.primary?.id ?? null}
            initialJob={job ? { id: job.id, company: job.company, title: job.title } : null}
          />
        </div>
      </div>
    </ScrollArea>
  );
}
