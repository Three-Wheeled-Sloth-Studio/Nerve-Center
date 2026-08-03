import type {
  ApplicationRecord,
  ApplicationStatus,
  CareerProfile,
  ReviewOpportunity,
  RunRecord,
  ScoringRule,
} from "./types";

const API_BASE =
  import.meta.env.VITE_NERVE_CENTER_API ?? "http://127.0.0.1:8123";

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

export function createDurationRun(minutes: number): Promise<RunRecord> {
  return request("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify({
      task_id: "job-discovery",
      duration_seconds: minutes * 60,
      configuration: {},
    }),
  });
}

export function createFixedRun(
  startsAt: string,
  endsAt: string,
): Promise<RunRecord> {
  return request("/api/v1/runs", {
    method: "POST",
    body: JSON.stringify({
      task_id: "job-discovery",
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
  decision: "approved" | "rejected",
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
