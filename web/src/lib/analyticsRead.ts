import "server-only";
import { apiGetOr } from "./api";
import type { AnalyticsData, ApplicationAnalyticsRecords } from "./analytics";
import { calculateSupplement, type Interval, type SubmissionIdentity } from "./analyticsCalculations";

// Existing, authenticated GETs only. The compact identity ledger stays on the
// server. No mail bodies, syncs, new backend operation or application writes.
export async function readAnalyticsSupplement(d: AnalyticsData, interval: Interval, week?: string) {
  let identities: SubmissionIdentity[];
  if (!d.family) {
    const ledger = await apiGetOr<{ items: SubmissionIdentity[] } | null>("/api/inbox/applications", null);
    if (!ledger || ledger.items.length !== d.total_submitted) return null;
    identities = ledger.items;
  } else {
    // The compact ledger has no family. Reuse exact Analytics record keys;
    // never classify a historical role from a company or title in this UI.
    const params = { days: "all", family: d.family, tz: d.timezone, records: "1", limit: "100" };
    const first = await apiGetOr<ApplicationAnalyticsRecords | null>("/api/analytics", null, params);
    if (!first) return null;
    const records = [...first.records];
    for (let offset = 100; offset < first.record_total; offset += 100) {
      const next = await apiGetOr<ApplicationAnalyticsRecords | null>("/api/analytics", null, { ...params, offset: String(offset) });
      if (!next || next.record_total !== first.record_total || !next.records.length) return null;
      records.push(...next.records);
    }
    if (records.length !== first.record_total) return null;
    identities = records.map(row => ({ key: row.key, applied_at: row.submitted_at }));
  }
  return calculateSupplement(d, identities, interval, week);
}
