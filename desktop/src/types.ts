export type ApplicationStatus =
  | "discovered"
  | "saved"
  | "dismissed"
  | "planned_to_apply"
  | "applying"
  | "applied"
  | "recruiter_contact"
  | "screening"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn"
  | "closed_without_response";

export interface ApplicationRecord {
  job_id: string;
  status: ApplicationStatus;
  application_date: string | null;
  source: string | null;
  resume_variant_reference: string | null;
  referral_status: string;
  response_date: string | null;
  disposition_reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobOpening {
  id: string;
  company_id: string;
  company_name: string;
  title: string;
  description: string;
  location_text: string | null;
  work_arrangement: string;
  canonical_url: string;
  apply_url: string | null;
  posted_at: string | null;
  discovered_at: string;
  provenance: Array<{
    source_id: string;
    connector: string;
    source_url: string;
    direct_employer_source: boolean;
  }>;
}

export interface Company {
  id: string;
  canonical_name: string;
  domain: string;
  career_url: string | null;
}

export interface ScoreFactor {
  dimension: string;
  code: string;
  label: string;
  kind: string;
  points: number;
  evidence: string[];
}

export interface OpportunityScore {
  fit: number;
  response_likelihood: number;
  opportunity_value: number;
  confidence: number;
  priority: number;
  excluded: boolean;
  retained: boolean;
  gates: Array<{ code: string; label: string; evidence: string[] }>;
  factors: ScoreFactor[];
  location: {
    scope: string;
    commute_minutes: number | null;
    nearest_office_minutes: number | null;
    rationale: string[];
  };
}

export interface ReviewOpportunity {
  opening: JobOpening;
  company: Company;
  score: OpportunityScore | null;
  application: ApplicationRecord;
  next_action: string;
}

export interface RunRecord {
  id: string;
  task_id: string;
  status: string;
  window_kind: string;
  duration_seconds: number | null;
  starts_at: string | null;
  deadline: string | null;
  requested_at: string;
  updated_at: string;
  finished_at: string | null;
  checkpoint: Record<string, unknown>;
  result_summary: string | null;
  error_code: string | null;
}

export interface ScoringRule {
  id: string;
  target: string;
  action: string;
  pattern: string;
  enabled: boolean;
  note: string | null;
}

export interface CareerProfile {
  hypotheses: Array<{
    id: string;
    label: string;
    summary: string;
    suggested_headline: string;
    decision: string;
    confidence: number;
  }>;
}
