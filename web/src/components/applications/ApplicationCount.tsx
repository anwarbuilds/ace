"use client";

import { useApp } from "@/components/shell/AppProvider";
import type { ApplicationStatus } from "@/lib/types";

function statusTotal(statuses: ApplicationStatus[], counts: Partial<Record<ApplicationStatus, number>>): number {
  return statuses.reduce((total, status) => total + (counts[status] ?? 0), 0);
}

export function ApplicationCount() {
  const { marks } = useApp();
  return <>{marks.applications_total.toLocaleString("en-US")}</>;
}

export function ApplicationMetric() {
  const { marks } = useApp();
  return (
    <div className="kpi application-total" aria-live="polite">
      <div className="kpi-l">Total applications</div>
      <div className="kpi-n">{marks.applications_total.toLocaleString("en-US")}</div>
      <div className="kpi-f good">
        {marks.applications_without_posting
          ? `${marks.applications_with_posting.toLocaleString("en-US")} with a stored posting, ${marks.applications_without_posting.toLocaleString("en-US")} from history`
          : "Updates everywhere when you mark applied"}
      </div>
    </div>
  );
}

export function ApplicationStageCount({ statuses }: { statuses: ApplicationStatus[] }) {
  const { marks } = useApp();
  return <>{statusTotal(statuses, marks.application_by_status).toLocaleString("en-US")}</>;
}

export function ApplicationHeardBack() {
  const { marks } = useApp();
  const heard = statusTotal(
    ["screening", "interviewing", "offer", "accepted", "rejected"],
    marks.application_by_status,
  );
  const percent = marks.applications_total ? Math.round((100 * heard) / marks.applications_total) : 0;
  return <>{percent}%</>;
}

export function ApplicationHeardBackFoot() {
  const { marks } = useApp();
  const heard = statusTotal(
    ["screening", "interviewing", "offer", "accepted", "rejected"],
    marks.application_by_status,
  );
  return <>{heard.toLocaleString("en-US")} of {marks.applications_total.toLocaleString("en-US")} have an answer</>;
}

export function ApplicationInterviewFoot() {
  const { marks } = useApp();
  const total = marks.applications_total;
  const interviews = ["interviewing", "offer", "accepted"].reduce(
    (sum, status) => sum + (marks.application_by_status[status as ApplicationStatus] ?? 0),
    0,
  );
  if (!total) return <>None yet</>;
  return <>{Math.round((interviews / total) * 100)}% of applications, by current status</>;
}
