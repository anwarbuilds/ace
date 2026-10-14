// Resume Studio shapes, as /api/studio returns them.

export type FactStatus = "verified" | "suggested" | "deprecated" | "needs_clarification";
export type FactKind = "experience" | "education" | "project" | "skill" | "certification" | "summary" | "preference";

export interface Fact {
  id: number;
  kind: FactKind;
  title: string;
  organization: string;
  start_date: string;
  end_date: string;
  bullets: string[];
  skills: string[];
  evidence: string;
  status: FactStatus;
  origin: "parsed" | "user";
  source_document_id: number | null;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface StudioDocument {
  id: number;
  kind: "resume" | "template";
  filename: string;
  media_type: string;
  size_bytes: number;
  parser: string;
  report: {
    pages?: number | null;
    tables?: number;
    columns?: boolean;
    header_footer_contact?: boolean;
    characters?: number;
    error?: string;
    headings?: { kind: string; text: string; style: string }[];
  };
  created_at: string;
  extracted_text?: string;
  structure?: {
    sections: { kind: string; heading: string; line: number }[];
    emails: string[];
    phones: string[];
    links: string[];
    dates: { text: string; line: number }[];
    bullets: number;
  };
}

export interface Version {
  id: number;
  label: string;
  kind: "master" | "tailored";
  parent_id: number | null;
  document_id: number | null;
  job_id: number | null;
  status: "draft" | "approved" | "archived";
  is_primary: boolean;
  content_hash: string;
  created_at: string;
  approved_at: string | null;
  body_text?: string;
}

export type Component = "parseability" | "requirements" | "quality" | "fit";

export interface Evidence {
  skill: string;
  level: "required" | "preferred";
  state: "evidenced" | "listed_only" | "related" | "not_evidenced";
  quote: string;
  line: number | null;
  via: string;
}

export interface Finding {
  component: Component;
  severity: "blocker" | "high" | "medium" | "low" | "info";
  message: string;
}

export interface AssessmentSummary {
  id: number;
  version_id: number;
  job_id: number | null;
  job_source: "stored" | "pasted";
  job_title: string;
  job_company: string;
  algorithm_version: string;
  state: "scored" | "insufficient_job_data" | "unreadable_resume";
  aggregate: number | null;
  confidence: "high" | "medium" | "low";
  components: Partial<Record<Component, number | null>>;
  created_at: string;
}

export interface Assessment extends AssessmentSummary {
  result: {
    weights: Record<Component, number>;
    evidence: Evidence[];
    findings: Finding[];
    unknowns: string[];
    recommendations: Finding[];
    facts: { required?: string[]; preferred?: string[]; required_years?: number | null; your_years?: number | null };
  };
}

export interface StudioOverview {
  primary: Version | null;
  facts: { by_status: Partial<Record<FactStatus, number>>; by_kind: Partial<Record<FactKind, number>> };
  documents: StudioDocument[];
  versions: Version[];
  recent: AssessmentSummary[];
  checker: { algorithm_version: string; weights: Record<Component, number> };
}

export const KIND_LABEL: Record<FactKind, string> = {
  experience: "Experience",
  education: "Education",
  project: "Projects",
  skill: "Skills",
  certification: "Certifications",
  summary: "Summary",
  preference: "Preferences",
};

export const STATUS_LABEL: Record<FactStatus, string> = {
  verified: "Verified",
  suggested: "Suggested",
  needs_clarification: "Needs clarification",
  deprecated: "Retired",
};

export const COMPONENT_LABEL: Record<Component, string> = {
  parseability: "Parseability",
  requirements: "Requirement evidence",
  quality: "Content quality",
  fit: "Hard fit",
};

export const EVIDENCE_LABEL: Record<Evidence["state"], string> = {
  evidenced: "Evidenced",
  listed_only: "Listed only",
  related: "Related",
  not_evidenced: "Not evidenced",
};

export const STATE_LABEL: Record<AssessmentSummary["state"], string> = {
  scored: "Scored",
  insufficient_job_data: "Insufficient job data",
  unreadable_resume: "Resume unreadable",
};
