// Shapes the FastAPI backend returns. Hand-written from
// backend/app/api/main.py, because its OpenAPI bodies are untyped.

export type Tier = "BIG_TECH" | "TOP_TIER" | "ESTABLISHED" | "OTHER";

export type ApplicationStatus =
  | "applied"
  | "screening"
  | "interviewing"
  | "offer"
  | "accepted"
  | "rejected"
  | "withdrawn"
  | "ghosted";

export type ReviewState = "reviewed" | "dismissed";

export interface AppliedBefore {
  job_id: number;
  title: string;
  location: string | null;
  applied_at: string;
  is_active: boolean;
  requisition_id: string | null;
  count: number;
}

export interface Job {
  id: number;
  company: string;
  title: string;
  location: string;
  official_url: string;
  source: string;
  source_account: string;
  external_id: string;
  requisition_id: string | null;
  eligibility_status: string;
  role_family: string;
  role_priority: string;
  reasons: string[];
  required_experience_years: number | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  is_active: boolean;
  closed_at: string | null;
  posting_age_days: number | null;
  first_seen_session_id: number | null;
  is_early_career: boolean;
  requirements_verified: boolean;
  match_score: number | null;
  is_scored?: boolean;
  matched_skills: string[];
  missing_skills: string[];
  related_skills: string[];
  related_evidence: { skill: string; via: string }[];
  previous_match_score: number | null;
  score_changed_at: string | null;
  is_saved: boolean;
  review_state: ReviewState | null;
  company_tier: Tier;
  application_status: ApplicationStatus | null;
  status_changed_at: string | null;
  status_note: string | null;
  applied_at: string | null;
  applied_before: AppliedBefore | null;
}

export interface JobPage {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  sort: string;
  resume_id: number | null;
}

export interface Stats {
  posted_today?: number;
  posted_last_7_days?: number;
  labelled_new_grad?: number;
  verified_jobs?: number;
  qualifying_active_jobs?: number;
  match_high?: number;
  match_medium?: number;
  match_minimal?: number;
  match_unscored?: number;
  corpus_started_at?: string | null;
  sources_enabled?: number;
  sources_polled?: number;
  generated_at?: string;
  last_poll_at: string | null;
}

export interface Facet {
  value: string;
  count: number;
}

export interface Facets {
  companies: Facet[];
  sources: Facet[];
  families: Facet[];
  priorities: Facet[];
  statuses: string[];
  sorts: string[];
}

export interface Pull {
  id: number;
  started_at: string;
  finished_at: string | null;
  jobs_discovered: number;
  qualifying_discovered: number;
  boards_checked: number | null;
  postings_checked: number | null;
  qualifying_open_now: number;
  age_seconds: number;
  jobs: Job[];
}

export interface PullsResponse {
  last_poll_at: string | null;
  sessions: Pull[];
}

export interface MarkCounts {
  saved: number;
  archived: number;
  applied: number;
  open_applications: number;
  by_status: Partial<Record<ApplicationStatus, number>>;
}

export interface MarkResult {
  job_id: number;
  is_saved: boolean;
  review_state: ReviewState | null;
  applied_at: string | null;
  application_status: ApplicationStatus | null;
  status_changed_at: string | null;
  status_note: string | null;
}

export interface Resume {
  id: number;
  label: string;
  filename: string;
  skills: string[];
  uploaded_at: string;
}

export interface SkillGap {
  skill: string;
  count: number;
  share: number;
}

export interface ResumeResponse {
  resume: Resume | null;
  skills_gap: SkillGap[];
}

export interface Answer {
  id: number;
  label: string;
  value: string;
  kind: "text" | "boolean" | "choice";
  options: string[];
  hint: string;
  known: boolean;
  aliases: string[];
}

export interface HistoryEntry {
  id?: number;
  employer: string;
  job_title: string;
  location: string;
  is_current: boolean;
  start_month: number | null;
  start_year: number | null;
  end_month: number | null;
  end_year: number | null;
  description: string;
}

export interface ExternalApplication {
  id: number;
  company: string;
  title: string;
  applied_at: string | null;
  application_status: ApplicationStatus | null;
  url: string | null;
}

export interface CoverageGap {
  company: string;
  outcome: string;
  detail: string;
  checked_at: string | null;
}

export interface Coverage {
  total: number;
  reached: number;
  unreached: CoverageGap[];
  sources: number;
  sponsorship: { company: string; refusing: number; readable: number; share: number }[];
  caught_late: {
    count: number;
    board_added_later: number;
    seen_late: number;
    republished?: number;
    rows: { company: string; title: string; cause: string; lag_hours: number }[];
  } | null;
  feed_only: { company: string; passing: number; board_read: boolean }[];
  dark: {
    company: string;
    source_type: string;
    source_account: string;
    last_success_at: string | null;
    dark_since: string;
  }[];
}

export interface SourceResult {
  status: string;
  company: string | null;
  source_type: string | null;
  source_account: string | null;
  job_count: number | null;
  evidence: string | null;
  detail: string | null;
}
