import type { InboxCoverage } from "./inboxSync";
export const CHART_COLORS = ["var(--accent)", "#dd7b9e", "#b7a3cc", "#329477", "#f27b86", "#aaa2b0", "#dc9c37", "#8c739f"];
export interface AnalyticsGroup { submitted: number; eligible: number; responses: number; rejections: number; assessments: number; interviews: number; rate: number | null }
export interface AnalyticsCompany extends AnalyticsGroup { name: string; latest: string; latest_at: string | null }
export interface PetitionReport { entity: string; period: string; source: string; url: string; metric: string; version: string; checked_at: string; approvals: number | null; denials: number | null; rate: number | null }
export interface AnalyticsData {
  as_of: string; timezone: string; start: string; end: string; days: string; family: string | null;
  available_families: string[]; total_submitted: number; submitted: number; undated: number;
  week_total: number; positive: number; assessments: number; interviews: number; has_outcome_evidence: boolean;
  statuses: Record<string, number>; daily: { date: string; count: number }[]; granularity: string;
  week: { date: string; count: number }[];
  cohort: { eligible: number; positive: number; rejected: number; pending: number; unknown: number; rate: number | null; coverage: string };
  timing: { label: string; count: number }[]; median_days: number | null; timing_sample: number;
  evidence: { positive: number; rejected: number; manual: number; automatic: number; recorded_status?:number };
  review: { needs_review: number; exact_preview: number; ambiguous: number; deferred?:number; unlinked?:number };
  inbox_audit?: {stored_messages:number;recorded_messages:number;pending_messages:number;ignored_messages:number;stale_messages:number;pre_mark_email_outcomes:number;excluded_events:Record<string,number>;event_scope:string};
  roles: (AnalyticsGroup & { family: string })[];
  attribution: { resume: string; channel: string; combinations: unknown[] };
  companies: AnalyticsCompany[]; selected_company: string;
  rejected_companies: RejectedCompany[];
  rejection_summary: { applications: number; companies: number; dated: number; latest_at: string | null };
  company_rejections?: {company:string;messages:number;latest_at:string;message_ids:number[]}[];
  company_rejection_summary?: {companies:number;messages:number;latest_at:string|null;date_basis:"email_received";start:string|null;end:string;family_excluded_messages:number};
  verified_companies: (AnalyticsGroup & { name: string; reports: number })[];
  reports: PetitionReport[]; annual: { period: string; approvals: number; denials: number; rate: number | null }[];
}
/** An employer with a recorded rejection: newest dated rejection first. */
export interface RejectedCompany {
  name: string; rejections: number; applications: number; latest_at: string | null;
  dated: number; roles: string[]; in_progress: number;
}
export interface InboxConnection { connected: boolean; state: string; available: boolean; last_synced_at: string | null; coverage?:InboxCoverage|null }


export function applicationRecordsHref(data: Pick<AnalyticsData,"days"|"start"|"end"|"family"|"timezone">, filters: Record<string,string> = {}) {
  const query=new URLSearchParams({days:data.days, tz:data.timezone});
  if(data.days!=="all"){query.set("start",data.start);query.set("end",data.end);}
  if(data.family)query.set("family",data.family);
  for(const [key,value] of Object.entries(filters)) query.set(key,value);
  return `/app/applications/analytics?${query}`;
}
export interface ApplicationAnalyticsRecord {
  key:string; company:string; title:string; requisition_id:string|null; family:string; submitted_at:string|null;
  status:string; event_types:string[]; href:string|null;
  /** Each counted outcome, with its date and the email behind it when one exists. */
  evidence:{kind:string; at:string|null; message_id:number|null; predates_mark?:boolean}[];
  excluded_evidence?:{message_id:number;reason:string}[];
}
export interface ApplicationAnalyticsRecords extends AnalyticsData {
  not_listed?: {applications:{key:string;company:string;title:string;status:string;submitted_at:string|null;outside_range:boolean;href:string}[];
    emails:{id:number;subject:string;decision:string;classification:string;received_at:string}[];application_total:number;email_total:number};
  records:ApplicationAnalyticsRecord[]; record_total:number; record_offset:number; record_limit:number; record_query:string;
}
