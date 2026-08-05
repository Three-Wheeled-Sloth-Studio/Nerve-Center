import { type FormEvent, useState } from "react";

import {
  cancelWorkRequest,
  createDurationSession,
  createFixedSession,
  createRecurringSession,
  emergencyStopSession,
  reprioritizeWorkRequest,
  retryWorkRequest,
  setModuleLifecycle,
} from "./api";
import type {
  ModuleRecord,
  QueueStatusRecord,
  RunRecord,
  SessionRecord,
  WorkRequestRecord,
} from "./types";
import { formatDuration, messageOf, remaining, titleCase } from "./display";

export function HomePanel({ modules, activeSession, queueStatus, onOpen, onRefresh, onError }: {
  modules: ModuleRecord[];
  activeSession: SessionRecord | undefined;
  queueStatus: QueueStatusRecord | null;
  onOpen: (moduleId: string) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  return (
    <section aria-labelledby="home-heading">
      <div className="section-heading">
        <div><p className="eyebrow">Manager-owned status</p><h2 id="home-heading">Home</h2></div>
      </div>
      <div className="queue-summary panel home-summary">
        <QueueMetric label="Session" value={activeSession ? titleCase(activeSession.admission_phase) : "Idle"} />
        <QueueMetric label="Time remaining" value={activeSession ? remaining(activeSession.ends_at) : "—"} />
        <QueueMetric label="Queued work" value={queueStatus?.global_queued ?? 0} />
        <QueueMetric label="Queue pressure" value={`${Math.round((queueStatus?.pressure ?? 0) * 100)}%`} />
      </div>
      <div className="card-grid">
        {modules.map((module) => (
          <ModuleCard key={module.manifest.module_id} module={module} onOpen={onOpen} onRefresh={onRefresh} onError={onError} />
        ))}
      </div>
    </section>
  );
}

function ModuleCard({ module, onOpen, onRefresh, onError }: {
  module: ModuleRecord;
  onOpen: (moduleId: string) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  async function toggle() {
    try {
      await setModuleLifecycle(module.manifest.module_id, module.lifecycle_state === "enabled" ? "paused" : "enabled");
      await onRefresh();
    } catch (reason) { onError(messageOf(reason)); }
  }
  return (
    <article className="panel module-card compact-module-card">
      <div className="status-line"><span>{titleCase(module.lifecycle_state)}</span><span>v{module.manifest.version}</span></div>
      <h3>{module.manifest.display_name}</h3>
      <p>{module.runtime?.activity ?? module.manifest.description}</p>
      <dl className="module-facts compact-facts">
        <div><dt>Runtime</dt><dd>{titleCase(module.runtime?.status ?? "stopped")}</dd></div>
        <div><dt>Backlog</dt><dd>{module.runtime?.deterministic_backlog ?? 0}</dd></div>
        <div><dt>LLM queue</dt><dd>{module.runtime?.pending_llm_requests ?? 0}</dd></div>
        <div><dt>Pressure</dt><dd>{Math.round((module.runtime?.queue_pressure ?? 0) * 100)}%</dd></div>
      </dl>
      <div className="actions">
        <button type="button" className="primary" onClick={() => onOpen(module.manifest.module_id)}>Open module</button>
        {module.lifecycle_state !== "not_installed" ? (
          <button type="button" onClick={() => void toggle()}>{module.lifecycle_state === "enabled" ? "Pause" : "Enable"}</button>
        ) : null}
      </div>
    </article>
  );
}

export function SchedulePanel({ sessions, runs, modules, onRefresh, onError }: { sessions: SessionRecord[]; runs: RunRecord[]; modules: ModuleRecord[]; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  const [mode, setMode] = useState<"duration" | "fixed" | "recurring">("duration"); const [minutes, setMinutes] = useState(60); const [startsAt, setStartsAt] = useState(""); const [endsAt, setEndsAt] = useState(""); const [time, setTime] = useState("18:00"); const [recurringMinutes, setRecurringMinutes] = useState(720);
  const active = sessions.find((session) => ["requested", "running", "interrupted", "draining"].includes(session.status));
  const enabled = modules.filter((module) => module.lifecycle_state === "enabled" && module.manifest.session_entry_task_id).length;
  async function submit(event: FormEvent) { event.preventDefault(); try { if (mode === "duration") await createDurationSession(minutes); else if (mode === "fixed") await createFixedSession(startsAt, endsAt); else await createRecurringSession({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, localStartTime: time, durationMinutes: recurringMinutes }); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } }
  return <section><div className="section-heading"><div><p className="eyebrow">Wall-clock authorization</p><h2>Schedule</h2></div></div><div className="two-column"><form className="panel" onSubmit={(event) => void submit(event)}><div className="segmented">{(["duration", "fixed", "recurring"] as const).map((item) => <button type="button" className={mode === item ? "active" : ""} onClick={() => setMode(item)} key={item}>{titleCase(item)}</button>)}</div>{mode === "duration" ? <label>Minutes<input type="number" min={1} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label> : mode === "fixed" ? <><label>Start<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label><label>End<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label></> : <><label>Daily start<input type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label><label>Minutes<input type="number" value={recurringMinutes} onChange={(event) => setRecurringMinutes(Number(event.target.value))} /></label></>}<button className="primary" disabled={Boolean(active) || enabled === 0}>{active ? "Session active" : `Start ${enabled} module${enabled === 1 ? "" : "s"}`}</button>{active ? <button type="button" className="danger" onClick={() => void emergencyStopSession(active.id).then(onRefresh).catch((reason: unknown) => onError(messageOf(reason)))}>Emergency Stop</button> : null}</form><div className="panel"><h3>Session history</h3><div className="run-list">{sessions.map((session) => <div className="run-row" key={session.id}><div><strong>{titleCase(session.status)}</strong><span>{new Date(session.starts_at).toLocaleString()}</span></div><span>{remaining(session.ends_at)}</span></div>)}</div><details><summary>Module run diagnostics</summary>{runs.map((run) => <p key={run.id}><strong>{titleCase(run.status)}</strong> · {run.task_id} · {run.result_summary ?? run.error_code ?? "Pending"}</p>)}</details></div></div></section>;
}

export function QueuePanel({ requests, status, onRefresh, onError }: { requests: WorkRequestRecord[]; status: QueueStatusRecord | null; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  return <section><div className="section-heading"><div><p className="eyebrow">Manager-owned durable work</p><h2>Queue</h2></div></div><div className="queue-summary panel"><QueueMetric label="Queued" value={status?.queued ?? 0} /><QueueMetric label="In progress" value={status?.claimed ?? 0} /><QueueMetric label="Awaiting acknowledgement" value={status?.awaiting_acknowledgement ?? 0} /><QueueMetric label="Estimated clear" value={formatDuration(status?.estimated_queue_clear_seconds ?? 0)} /></div><div className="panel queue-list">{requests.length ? requests.map((request) => <QueueRequestRow key={request.id} request={request} onRefresh={onRefresh} onError={onError} />) : <p className="muted">No durable work requests.</p>}</div></section>;
}

function QueueRequestRow({ request, onRefresh, onError }: { request: WorkRequestRecord; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  const [priority, setPriority] = useState(request.task_priority);
  async function act(operation: () => Promise<unknown>) { try { await operation(); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } }
  return <details className="queue-item"><summary><span><strong>{titleCase(request.status)}</strong><small>{request.task_id}</small></span><span>{titleCase(request.work_class)} · {request.module_id}</span></summary><div className="queue-actions">{request.status === "queued" ? <><label>Priority<input type="number" min={0} max={100} value={priority} onChange={(event) => setPriority(Number(event.target.value))} /></label><button onClick={() => void act(() => reprioritizeWorkRequest(request.id, priority))}>Update</button><button className="danger" onClick={() => void act(() => cancelWorkRequest(request.id))}>Cancel</button></> : null}{["failed", "cancelled"].includes(request.status) ? <button onClick={() => void act(() => retryWorkRequest(request.id))}>Retry</button> : null}</div></details>;
}

export function ManagerSettings({ modules }: { modules: ModuleRecord[] }) {
  return <section><div className="section-heading"><div><p className="eyebrow">Core settings only</p><h2>Settings</h2></div></div><div className="panel"><h3>Module boundary</h3><p>Domain configuration lives inside each module workspace. Nerve Center owns scheduling, shared resources, provider access, lifecycle, permissions, and updates.</p>{modules.map((module) => <details key={module.manifest.module_id}><summary>{module.manifest.display_name} permissions</summary><ul>{module.manifest.permissions.map((permission) => <li key={`${permission.kind}-${permission.scopes.join("-")}`}><strong>{titleCase(permission.kind)}</strong>: {permission.rationale}</li>)}</ul></details>)}</div></section>;
}


function QueueMetric({ label, value }: { label: string; value: string | number }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
