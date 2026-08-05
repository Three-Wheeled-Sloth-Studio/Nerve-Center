import type {
  ApplicationRecord,
  ApplicationStatus,
  CareerProfile,
  ModuleLifecycleState,
  ModuleRecord,
  ReviewOpportunity,
  RunRecord,
  SessionRecord,
  ScoringRule,
} from "./types";

const API_BASE =
  import.meta.env.VITE_NERVE_CENTER_API ?? "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getOpportunities(
  sort: string,
  includeDismissed: boolean,
): Promise<ReviewOpportunity[]> {
  const query = new URLSearchParams({
    sort,
    include_dismissed: String(includeDismissed),
  });
  return request(`/api/v1/review/opportunities?${query.toString()}`);
}

export function updateApplication(
  jobId: string,
  status: ApplicationStatus,
): Promise<ApplicationRecord> {
  return request(`/api/v1/applications/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getRuns(): Promise<RunRecord[]> {
  return request("/api/v1/runs?limit=50");
}

export function getSessions(): Promise<SessionRecord[]> {
  return request("/api/v1/sessions?limit=50");
}

export function createDurationSession(minutes: number): Promise<SessionRecord> {
  return request("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({ duration_seconds: minutes * 60 }),
  });
}

export function createFixedSession(startsAt: string, endsAt: string): Promise<SessionRecord> {
  return request("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
    }),
  });
}

export function createRecurringSession(input: {
  timezone: string;
  localStartTime: string;
  durationMinutes: number;
}): Promise<SessionRecord> {
  return request("/api/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      recurrence_timezone: input.timezone,
      recurrence_local_start_time: input.localStartTime,
      recurrence_duration_seconds: input.durationMinutes * 60,
      recurrence_weekdays: [0, 1, 2, 3, 4, 5, 6],
    }),
  });
}

export function emergencyStopSession(sessionId: string): Promise<SessionRecord> {
  return request(`/api/v1/sessions/${sessionId}/emergency-stop`, { method: "POST" });
}

export function getModules(): Promise<ModuleRecord[]> {
  return request("/api/v1/modules");
}

export function setModuleLifecycle(
  moduleId: string,
  lifecycleState: ModuleLifecycleState,
): Promise<ModuleRecord> {
  return request(`/api/v1/modules/${moduleId}`, {
    method: "PATCH",
    body: JSON.stringify({ lifecycle_state: lifecycleState }),
  });
}

export function createDurationRun(taskId: string, minutes: number): Promise<RunRecord> {
  return request("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify({
      task_id: taskId,
      duration_seconds: minutes * 60,
      configuration: {},
    }),
  });
}

export function createFixedRun(
  taskId: string,
  startsAt: string,
  endsAt: string,
): Promise<RunRecord> {
  return request("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify({
      task_id: taskId,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
      configuration: {},
    }),
  });
}

export function startRun(runId: string): Promise<RunRecord> {
  return request(`/api/v1/runs/${runId}/start`, { method: "POST" });
}

export function cancelRun(runId: string): Promise<RunRecord> {
  return request(`/api/v1/runs/${runId}/cancel`, { method: "POST" });
}

export function getRules(): Promise<ScoringRule[]> {
  return request("/api/v1/scoring/rules");
}

export function createRule(input: {
  target: string;
  action: string;
  pattern: string;
  note?: string;
}): Promise<ScoringRule> {
  return request("/api/v1/scoring/rules", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteRule(ruleId: string): Promise<void> {
  return request(`/api/v1/scoring/rules/${ruleId}`, { method: "DELETE" });
}

export function getProfile(): Promise<CareerProfile> {
  return request("/api/v1/profile");
}

export function decideHypothesis(
  hypothesisId: string,
  decision: "approved" | "disapproved",
): Promise<CareerProfile> {
  return request(`/api/v1/profile/hypotheses/${hypothesisId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}

export function getScoringSettings(): Promise<Record<string, unknown>> {
  return request("/api/v1/scoring/settings");
}

export function saveScoringSettings(
  settings: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request("/api/v1/scoring/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export function getLocationPreferences(): Promise<Record<string, unknown>> {
  return request("/api/v1/scoring/location-preferences");
}

export function saveLocationPreferences(
  preferences: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request("/api/v1/scoring/location-preferences", {
    method: "PUT",
    body: JSON.stringify(preferences),
  });
}
