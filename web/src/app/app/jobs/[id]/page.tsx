import { notFound } from "next/navigation";

import { JobDetail } from "@/components/jobs/JobDetail";
import { ApiError, apiGet, apiGetOr } from "@/lib/api";
import { clean } from "@/lib/format";
import type { Job, ResumeResponse } from "@/lib/types";

async function loadJob(id: string): Promise<Job> {
  if (!/^\d+$/.test(id)) notFound();
  try {
    return await apiGet<Job>(`/api/jobs/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata(props: PageProps<"/app/jobs/[id]">) {
  const { id } = await props.params;
  try {
    const job = await apiGet<Job>(`/api/jobs/${id}`);
    return { title: `${clean(job.title)}, ${job.company} · ace` };
  } catch {
    return { title: "ace" };
  }
}

// A link to a posting resolves even after it closes or the rules change.
export default async function JobPage(props: PageProps<"/app/jobs/[id]">) {
  const { id } = await props.params;
  const [job, resume] = await Promise.all([
    loadJob(id),
    apiGetOr<ResumeResponse>("/api/resume", { resume: null, skills_gap: [] }),
  ]);
  return <JobDetail job={job} resumeLabel={resume.resume?.label ?? null} />;
}
