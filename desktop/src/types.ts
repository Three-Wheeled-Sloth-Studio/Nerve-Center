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
  session_id: string | null;
  module_priority: number;
}

export interface SessionRecord {
  id: string;
  status: string;
  admission_phase: "open" | "constrained" | "draining" | "closed";
  starts_at: string;
  ends_at: string;
  requested_at: string;
  updated_at: string;
  finished_at: string | null;
  recurrence: {
    timezone: string;
    local_start_time: string;
    duration_seconds: number;
    weekdays: number[];
  } | null;
  recurrence_parent_id: string | null;
  module_run_ids: Record<string, string>;
  module_priorities: Record<string, number>;
  resource_policy: Record<string, number>;
  emergency_stop: boolean;
  result_summary: string | null;
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

export type ModuleLifecycleState = "enabled" | "paused" | "not_installed";

export interface ModuleRecord {
  manifest: {
    manifest_version: number;
    module_id: string;
    display_name: string;
    description: string;
    version: string;
    storage_namespace: string;
    compatibility: {
      module_api_version: number;
      minimum_core_version: string;
      maximum_tested_core_version: string;
      data_schema_version: number;
    };
    launch: {
      runtime: string;
      entrypoint: string;
      arguments: string[];
    };
    permissions: Array<{
      kind: string;
      scopes: string[];
      rationale: string;
      required: boolean;
    }>;
    task_types: Array<{
      task_id: string;
      display_name: string;
      work_classes: string[];
    }>;
    ui_contributions: Array<{
      slot: string;
      renderer_key: string;
    }>;
    configuration_schema: Record<string, unknown>;
    session_entry_task_id: string | null;
  };
  lifecycle_state: ModuleLifecycleState;
  saved_priority: number;
  runtime: {
    module_id: string;
    status: string;
    activity: string;
    process_id: number | null;
    last_heartbeat_at: string | null;
    work_items_processed: number;
    deterministic_backlog: number;
    pending_llm_requests: number;
    estimated_next_request_wait_seconds: number | null;
    estimated_queue_clear_seconds: number | null;
    queue_pressure: number;
    reason: string | null;
  } | null;
}
