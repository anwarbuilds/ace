"use client";

import { useApp } from "@/components/shell/AppProvider";

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
