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
export function discoverJobScoutKeywords() {
  return request<JobScoutWorkspace>("/api/v1/modules/job_scout/keywords/discover", { method: "POST" });
}
export function scanJobScout(discoverSources: boolean) {
  return request<JobScoutScanSummary>("/api/v1/modules/job_scout/scan", {
    method: "POST", body: JSON.stringify({ discover_sources: discoverSources }),
  });
}
