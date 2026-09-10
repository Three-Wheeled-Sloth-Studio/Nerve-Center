import type {
  ApplicationRecord,
  ApplicationStatus,
  JobScoutConfiguration,
  JobScoutScanSummary,
  JobScoutWorkspace,
  ModuleLifecycleState,
  ModuleRecord,
  QueueStatusRecord,
  ReviewOpportunity,
  RunRecord,
  SessionRecord,
  ScoringRule,
  WorkRequestRecord,
} from "./types";

export interface DiscoveryAuditStrategy {
  id: string;
  hypothesis_family: string;
  anchor: string;
  location: string;
  source_domain: string;
  source_path: string;
  compiled_query: string;
  learned_weight: number;
  weight_before: number | null;
  weight_after: number | null;
  attempts: number;
  total_yield: number;
  conditioned_yield: number;
  warnings: string[];
  overlap_company_count: number;
  overlap_company_ids: string[];
  last_attempt_at: string | null;
}

export interface DiscoveryAudit {
  run_id: string | null;
  coverage_gaps: Record<string, string[]>;
  strategies: DiscoveryAuditStrategy[];
}

export interface ModelLabEvidence {
  provider: string;
  model: string;
  attempts: number;
  success_rate: number;
  schema_valid_rate: number;
  acceptance_rate: number | null;
  average_duration_ms: number;
}

export interface ModelLabOverview {
  settings: {
    enabled: boolean;
    capture_enabled: boolean;
    excluded_modules: string[];
    updated_at: string;
  };
  models: Array<{
    provider: string;
    model: string;
    label: string;
    family: string | null;
    parameter_size: string | null;
    quantization: string | null;
    installed: boolean;
    capabilities: Record<string, unknown>;
    hardware_fit: Record<string, unknown>;
    last_seen_at: string;
  }>;
  task_evidence: Record<string, ModelLabEvidence[]>;
  corpus_count: number;
  corpus: Array<{
    id: string;
    module_id: string;
    task_id: string;
    contract_version: string;
    production_provider: string | null;
    production_model: string | null;
    created_at: string;
  }>;
  exploration_session: {
    id: string;
    status: string;
    starts_at: string;
    ends_at: string;
    max_attempts: number;
    attempts_used: number;
    created_at: string;
    finished_at: string | null;
  } | null;
  benchmark_results: Array<{
    id: string;
    corpus_id: string;
    session_id: string;
    provider: string;
    model: string;
    status: string;
    schema_valid: boolean | null;
    duration_ms: number;
    output: Record<string, unknown> | unknown[] | null;
    error_code: string | null;
    provider_call_id: string | null;
    created_at: string;
  }>;
  production_queue: QueueStatusRecord;
}

const API_BASE = import.meta.env.VITE_NERVE_CENTER_API ?? "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const raw = await response.text();
    let message = raw || `${response.status} ${response.statusText}`;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      } else if (parsed.detail && typeof parsed.detail === "object" && "message" in parsed.detail) {
        message = String((parsed.detail as { message: unknown }).message);
      }
    } catch {
      // Keep the server response text when it is not JSON.
    }
    if (response.status === 404 && path.startsWith("/api/v1/modules/job_scout/")) {
      message =
        "The running Nerve Center service predates this Job Scout workspace. " +
        "Quit Nerve Center from the system tray, then relaunch it.";
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getOpportunities(sort: string, includeDismissed: boolean) {
  const query = new URLSearchParams({ sort, include_dismissed: String(includeDismissed) });
  return request<ReviewOpportunity[]>(`/api/v1/review/opportunities?${query}`);
}
export function updateApplication(jobId: string, status: ApplicationStatus) {
  return request<ApplicationRecord>(`/api/v1/applications/${jobId}`, {
    method: "PATCH", body: JSON.stringify({ status }),
  });
}
export function getRuns() { return request<RunRecord[]>("/api/v1/runs?limit=50"); }
export function getSessions() { return request<SessionRecord[]>("/api/v1/sessions?limit=50"); }
export function createDurationSession(minutes: number) {
  return request<SessionRecord>("/api/v1/sessions", {
    method: "POST", body: JSON.stringify({ duration_seconds: minutes * 60 }),
  });
}
export function createFixedSession(startsAt: string, endsAt: string) {
  return request<SessionRecord>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({ starts_at: new Date(startsAt).toISOString(), ends_at: new Date(endsAt).toISOString() }),
  });
}
export function createRecurringSession(input: { timezone: string; localStartTime: string; durationMinutes: number }) {
  return request<SessionRecord>("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      recurrence_timezone: input.timezone,
      recurrence_local_start_time: input.localStartTime,
      recurrence_duration_seconds: input.durationMinutes * 60,
      recurrence_weekdays: [0, 1, 2, 3, 4, 5, 6],
    }),
  });
}
export function emergencyStopSession(sessionId: string) {
  return request<SessionRecord>(`/api/v1/sessions/${sessionId}/emergency-stop`, { method: "POST" });
}
export function getWorkRequests() { return request<WorkRequestRecord[]>("/api/v1/work-requests?limit=200"); }
export function getQueueStatus() { return request<QueueStatusRecord>("/api/v1/work-requests/status"); }
export function cancelWorkRequest(id: string) { return request<WorkRequestRecord>(`/api/v1/work-requests/${id}/cancel`, { method: "POST" }); }
export function retryWorkRequest(id: string) { return request<WorkRequestRecord>(`/api/v1/work-requests/${id}/retry`, { method: "POST" }); }
export function reprioritizeWorkRequest(id: string, taskPriority: number) {
  return request<WorkRequestRecord>(`/api/v1/work-requests/${id}/priority`, {
    method: "PATCH", body: JSON.stringify({ task_priority: taskPriority }),
  });
}
export function getModules() { return request<ModuleRecord[]>("/api/v1/modules"); }
export function setModuleLifecycle(moduleId: string, lifecycleState: ModuleLifecycleState) {
  return request<ModuleRecord>(`/api/v1/modules/${moduleId}`, {
    method: "PATCH", body: JSON.stringify({ lifecycle_state: lifecycleState }),
  });
}
export function getRules() { return request<ScoringRule[]>("/api/v1/scoring/rules"); }
export function createRule(input: { target: string; action: string; pattern: string; note?: string }) {
  return request<ScoringRule>("/api/v1/scoring/rules", { method: "POST", body: JSON.stringify(input) });
}
export function deleteRule(id: string) { return request<void>(`/api/v1/scoring/rules/${id}`, { method: "DELETE" }); }
export function decideHypothesis(id: string, decision: "approved" | "disapproved") {
  return request<JobScoutWorkspace["profile"]>(`/api/v1/profile/hypotheses/${id}/decision`, {
    method: "POST", body: JSON.stringify({ decision }),
  });
}
export function getScoringSettings() { return request<Record<string, unknown>>("/api/v1/scoring/settings"); }
export function saveScoringSettings(settings: Record<string, unknown>) {
  return request<Record<string, unknown>>("/api/v1/scoring/settings", { method: "PUT", body: JSON.stringify(settings) });
}
export function getLocationPreferences() { return request<Record<string, unknown>>("/api/v1/scoring/location-preferences"); }
export function saveLocationPreferences(preferences: Record<string, unknown>) {
  return request<Record<string, unknown>>("/api/v1/scoring/location-preferences", { method: "PUT", body: JSON.stringify(preferences) });
}
export function getJobScoutWorkspace() {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/workspace");
}
export function getJobScoutDiscoveryAudit() {
  return request<DiscoveryAudit>("/api/v1/modules/job_scout/discovery/audit");
}
export function getModelLab() {
  return request<ModelLabOverview>("/api/v1/model-lab");
}
export function saveJobScoutConfiguration(configuration: JobScoutConfiguration) {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/config", {
    method: "PUT", body: JSON.stringify(configuration),
  });
}
export function loadJobScoutResume(path: string, analyzeResume: boolean) {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/resume", {
    method: "POST", body: JSON.stringify({ path, analyze_resume: analyzeResume }),
  });
}
export function uploadJobScoutResume(fileName: string, contentBase64: string, analyzeResume: boolean) {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/resume/upload", {
    method: "POST",
    body: JSON.stringify({
      file_name: fileName,
      content_base64: contentBase64,
      analyze_resume: analyzeResume,
    }),
  });
}
export function discoverJobScoutKeywords() {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/keywords/discover", { method: "POST" });
}
export function scanJobScout(discoverSources: boolean) {
  return request<JobScoutScanSummary>("/api/v1/modules/job_scout/scan", {
    method: "POST", body: JSON.stringify({ discover_sources: discoverSources }),
  });
}
