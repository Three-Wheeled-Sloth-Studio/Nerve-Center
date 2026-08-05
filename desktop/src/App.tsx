import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createDurationSession,
  createFixedSession,
  createRecurringSession,
  createRule,
  cancelWorkRequest,
  decideHypothesis,
  deleteRule,
  getLocationPreferences,
  getModules,
  getOpportunities,
  getProfile,
  getQueueStatus,
  getRules,
  getRuns,
  getSessions,
  getWorkRequests,
  getScoringSettings,
  saveLocationPreferences,
  saveScoringSettings,
  reprioritizeWorkRequest,
  retryWorkRequest,
  setModuleLifecycle,
  emergencyStopSession,
  updateApplication,
} from "./api";
import type {
  ApplicationStatus,
  CareerProfile,
  ModuleRecord,
  QueueStatusRecord,
  ReviewOpportunity,
  RunRecord,
  SessionRecord,
  ScoringRule,
  WorkRequestRecord,
} from "./types";

type Tab = "modules" | "review" | "sessions" | "queue" | "rules" | "profile" | "preferences";
type SortKey = "priority" | "response" | "fit" | "freshness";

const ACTIVE_RUN_STATUSES = new Set(["queued", "scheduled", "running", "cancelling"]);

export default function App() {
  const [tab, setTab] = useState<Tab>("review");
  const [opportunities, setOpportunities] = useState<ReviewOpportunity[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [workRequests, setWorkRequests] = useState<WorkRequestRecord[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatusRecord | null>(null);
  const [modules, setModules] = useState<ModuleRecord[]>([]);
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [profile, setProfile] = useState<CareerProfile | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [location, setLocation] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("priority");
  const [includeDismissed, setIncludeDismissed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [undo, setUndo] = useState<{
    jobId: string;
    prior: ApplicationStatus;
  } | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [
        nextOpportunities,
        nextRuns,
        nextRules,
        nextProfile,
        nextModules,
        nextSessions,
        nextWorkRequests,
        nextQueueStatus,
      ] =
        await Promise.all([
          getOpportunities(sort, includeDismissed),
          getRuns(),
          getRules(),
          getProfile(),
          getModules(),
          getSessions(),
          getWorkRequests(),
          getQueueStatus(),
        ]);
      setOpportunities(nextOpportunities);
      setRuns(nextRuns);
      setRules(nextRules);
      setProfile(nextProfile);
      setModules(nextModules);
      setSessions(nextSessions);
      setWorkRequests(nextWorkRequests);
      setQueueStatus(nextQueueStatus);
      const [nextSettings, nextLocation] = await Promise.all([
        getScoringSettings(),
        getLocationPreferences(),
      ]);
      setSettings(nextSettings);
      setLocation(nextLocation);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [includeDismissed, sort]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void Promise.all([
        getRuns(),
        getModules(),
        getSessions(),
        getWorkRequests(),
        getQueueStatus(),
      ])
        .then(([nextRuns, nextModules, nextSessions, nextWorkRequests, nextQueueStatus]) => {
          setRuns(nextRuns);
          setModules(nextModules);
          setSessions(nextSessions);
          setWorkRequests(nextWorkRequests);
          setQueueStatus(nextQueueStatus);
        })
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return opportunities;
    }
    return opportunities.filter((item) =>
      [
        item.opening.title,
        item.company.canonical_name,
        item.opening.location_text ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [opportunities, query]);

  const activeRun = runs.find((run) => ACTIVE_RUN_STATUSES.has(run.status));
  const activeSession = sessions.find((session) =>
    ["requested", "running", "interrupted", "draining"].includes(
      session.status,
    ),
  );
  const jobScout = modules.find((module) => module.manifest.module_id === "job_scout");

  async function changeStatus(
    item: ReviewOpportunity,
    status: ApplicationStatus,
  ) {
    setBusy(true);
    try {
      await updateApplication(item.opening.id, status);
      setUndo({ jobId: item.opening.id, prior: item.application.status });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function undoStatus() {
    if (!undo) {
      return;
    }
    setBusy(true);
    try {
      await updateApplication(undo.jobId, undo.prior);
      setUndo(null);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local orchestration manager</p>
          <h1>Nerve Center</h1>
        </div>
        <div className="runner-chip" aria-live="polite">
          <span className={activeRun ? "pulse" : "dot"} />
          {activeSession
            ? `${titleCase(activeSession.admission_phase)}: ${remaining(activeSession.ends_at)}`
            : activeRun
              ? `${activeRun.status}: ${remaining(activeRun.deadline)}`
              : "Manager idle"}
        </div>
      </header>

      <nav className="tabs" aria-label="Primary">
        {(["modules", "review", "sessions", "queue", "rules", "profile", "preferences"] as Tab[]).map(
          (item) => (
            <button
              key={item}
              type="button"
              className={tab === item ? "tab active" : "tab"}
              onClick={() => setTab(item)}
            >
              {titleCase(item)}
            </button>
          ),
        )}
      </nav>

      {error ? (
        <div className="alert" role="alert">
          <strong>Something went sideways.</strong> {error}
          <button type="button" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : null}

      {undo ? (
        <div className="undo" role="status">
          Status updated.
          <button type="button" disabled={busy} onClick={() => void undoStatus()}>
            Undo
          </button>
        </div>
      ) : null}

      <main>
        {tab === "modules" ? (
          <ModulesPanel modules={modules} onRefresh={refresh} onError={setError} />
        ) : null}
        {tab === "review" ? (
          <ReviewPanel
            items={filtered}
            query={query}
            sort={sort}
            includeDismissed={includeDismissed}
            busy={busy}
            onQuery={setQuery}
            onSort={setSort}
            onIncludeDismissed={setIncludeDismissed}
            onStatus={changeStatus}
          />
        ) : null}
        {tab === "sessions" ? (
          <SessionsPanel
            sessions={sessions}
            runs={runs}
            modules={modules}
            onRefresh={refresh}
            onError={setError}
          />
        ) : null}
        {tab === "queue" ? (
          <QueuePanel
            requests={workRequests}
            status={queueStatus}
            onRefresh={refresh}
            onError={setError}
          />
        ) : null}
        {tab === "rules" ? (
          <RulesPanel rules={rules} onRefresh={refresh} onError={setError} />
        ) : null}
        {tab === "profile" ? (
          <ProfilePanel profile={profile} onRefresh={refresh} onError={setError} />
        ) : null}
        {tab === "preferences" ? (
          <PreferencesPanel
            settings={settings}
            location={location}
            onRefresh={refresh}
            onError={setError}
          />
        ) : null}
      </main>

      <footer>
        Nerve Center suggests and tracks work. It never submits an application,
        contacts an employer, or changes your profile automatically.
      </footer>
    </div>
  );
}

function ModulesPanel({
  modules,
  onRefresh,
  onError,
}: {
  modules: ModuleRecord[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  async function changeLifecycle(module: ModuleRecord) {
    const target = module.lifecycle_state === "enabled" ? "paused" : "enabled";
    try {
      await setModuleLifecycle(module.manifest.module_id, target);
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <section aria-labelledby="modules-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Manager-owned inventory</p>
          <h2 id="modules-heading">Modules</h2>
        </div>
      </div>
      <div className="card-grid">
        {modules.map((module) => (
          <article className="panel module-card" key={module.manifest.module_id}>
            <div className="status-line">
              <span>{titleCase(module.lifecycle_state)}</span>
              <span>v{module.manifest.version}</span>
            </div>
            <h3>{module.manifest.display_name}</h3>
            <p>{module.manifest.description}</p>
            <dl className="module-facts">
              <div>
                <dt>Tasks</dt>
                <dd>{module.manifest.task_types.map((task) => task.display_name).join(", ")}</dd>
              </div>
              <div>
                <dt>Permissions</dt>
                <dd>{module.manifest.permissions.length}</dd>
              </div>
              <div>
                <dt>Storage</dt>
                <dd>{module.manifest.storage_namespace}</dd>
              </div>
              <div>
                <dt>Module API</dt>
                <dd>v{module.manifest.compatibility.module_api_version}</dd>
              </div>
              <div>
                <dt>Runtime</dt>
                <dd>{titleCase(module.runtime?.status ?? "stopped")}</dd>
              </div>
              <div>
                <dt>Activity</dt>
                <dd>{module.runtime?.activity ?? "Not running"}</dd>
              </div>
              <div>
                <dt>Backlog</dt>
                <dd>{module.runtime?.deterministic_backlog ?? 0}</dd>
              </div>
              <div>
                <dt>Queue pressure</dt>
                <dd>{Math.round((module.runtime?.queue_pressure ?? 0) * 100)}%</dd>
              </div>
            </dl>
            {module.lifecycle_state !== "not_installed" ? (
              <button type="button" onClick={() => void changeLifecycle(module)}>
                {module.lifecycle_state === "enabled" ? "Pause module" : "Enable module"}
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function ReviewPanel({
  items,
  query,
  sort,
  includeDismissed,
  busy,
  onQuery,
  onSort,
  onIncludeDismissed,
  onStatus,
}: {
  items: ReviewOpportunity[];
  query: string;
  sort: SortKey;
  includeDismissed: boolean;
  busy: boolean;
  onQuery: (value: string) => void;
  onSort: (value: SortKey) => void;
  onIncludeDismissed: (value: boolean) => void;
  onStatus: (item: ReviewOpportunity, status: ApplicationStatus) => Promise<void>;
}) {
  return (
    <section aria-labelledby="review-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Evidence before enthusiasm</p>
          <h2 id="review-heading">Opportunity review</h2>
        </div>
        <div className="review-controls">
          <label>
            Search
            <input
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              placeholder="Title, company, location"
            />
          </label>
          <label>
            Sort
            <select
              value={sort}
              onChange={(event) => onSort(event.target.value as SortKey)}
            >
              <option value="priority">Priority</option>
              <option value="response">Response likelihood</option>
              <option value="fit">Fit</option>
              <option value="freshness">Freshness</option>
            </select>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={includeDismissed}
              onChange={(event) => onIncludeDismissed(event.target.checked)}
            />
            Show dismissed
          </label>
        </div>
      </div>

      <div className="opportunity-list">
        {items.length === 0 ? (
          <div className="empty-state">
            No opportunities match the current view. The sloth has checked twice.
          </div>
        ) : null}
        {items.map((item) => (
          <article className="opportunity-card" key={item.opening.id}>
            <div className="opportunity-summary">
              <div className="priority-badge">
                <strong>{score(item.score?.priority)}</strong>
                <span>priority</span>
              </div>
              <div className="opportunity-title">
                <h3>{item.opening.title}</h3>
                <p>
                  {item.company.canonical_name} · {item.opening.location_text ?? "Location unclear"}
                  {item.opening.work_arrangement
                    ? ` · ${titleCase(item.opening.work_arrangement)}`
                    : ""}
                </p>
                <p className="next-action">Next: {item.next_action}</p>
              </div>
              <div className="score-strip" aria-label="Opportunity scores">
                <Metric label="Fit" value={item.score?.fit} />
                <Metric label="Response" value={item.score?.response_likelihood} />
                <Metric label="Value" value={item.score?.opportunity_value} />
                <Metric label="Confidence" value={item.score?.confidence} />
              </div>
            </div>

            <div className="actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onStatus(item, "saved")}
              >
                Save
              </button>
              <button
                type="button"
                className="primary"
                disabled={busy}
                onClick={() => void onStatus(item, "planned_to_apply")}
              >
                Plan to apply
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onStatus(item, "dismissed")}
              >
                Dismiss
              </button>
              <a href={item.opening.apply_url ?? item.opening.canonical_url} target="_blank">
                Original listing
              </a>
              {item.company.career_url ? (
                <a href={item.company.career_url} target="_blank">
                  Company careers
                </a>
              ) : null}
              <select
                aria-label={`Application status for ${item.opening.title}`}
                value={item.application.status}
                onChange={(event) =>
                  void onStatus(item, event.target.value as ApplicationStatus)
                }
              >
                {APPLICATION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {titleCase(status)}
                  </option>
                ))}
              </select>
            </div>

            <details>
              <summary>Evidence, gates, and provenance</summary>
              <div className="detail-grid">
                <section>
                  <h4>Why it scored this way</h4>
                  {item.score?.factors.length ? (
                    <ul>
                      {item.score.factors.map((factor) => (
                        <li key={`${factor.dimension}-${factor.code}`}>
                          <strong>{factor.label}</strong>
                          {factor.points ? ` (${factor.points > 0 ? "+" : ""}${factor.points.toFixed(1)})` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No score has been calculated yet.</p>
                  )}
                </section>
                <section>
                  <h4>Hard gates</h4>
                  {item.score?.gates.length ? (
                    <ul>
                      {item.score.gates.map((gate) => (
                        <li key={gate.code}>{gate.label}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No hard gates recorded.</p>
                  )}
                </section>
                <section>
                  <h4>Provenance</h4>
                  <ul>
                    {item.opening.provenance.map((source) => (
                      <li key={`${source.source_id}-${source.source_url}`}>
                        {source.connector}
                        {source.direct_employer_source ? " · direct employer" : ""}
                      </li>
                    ))}
                  </ul>
                </section>
                <section className="description">
                  <h4>Job description</h4>
                  <p>{item.opening.description}</p>
                </section>
              </div>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}

function SessionsPanel({
  sessions,
  runs,
  modules,
  onRefresh,
  onError,
}: {
  sessions: SessionRecord[];
  runs: RunRecord[];
  modules: ModuleRecord[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [mode, setMode] = useState<"duration" | "fixed" | "recurring">("duration");
  const [minutes, setMinutes] = useState(30);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [recurrenceTime, setRecurrenceTime] = useState("18:00");
  const [recurrenceMinutes, setRecurrenceMinutes] = useState(720);
  const active = sessions.find((session) =>
    ["requested", "running", "interrupted", "draining"].includes(
      session.status,
    ),
  );
  const enabledCount = modules.filter(
    (module) =>
      module.lifecycle_state === "enabled" && module.manifest.session_entry_task_id,
  ).length;

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (mode === "duration") {
        await createDurationSession(minutes);
      } else if (mode === "fixed") {
        await createFixedSession(startsAt, endsAt);
      } else {
        await createRecurringSession({
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          localStartTime: recurrenceTime,
          durationMinutes: recurrenceMinutes,
        });
      }
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <section aria-labelledby="sessions-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Bounded work, visible state</p>
          <h2 id="sessions-heading">Work sessions</h2>
        </div>
      </div>
      <div className="two-column">
        <form className="panel" onSubmit={(event) => void submit(event)}>
          <h3>Authorize work</h3>
          <div className="segmented" role="group" aria-label="Session window type">
            <button
              type="button"
              className={mode === "duration" ? "active" : ""}
              onClick={() => setMode("duration")}
            >
              Duration
            </button>
            <button
              type="button"
              className={mode === "fixed" ? "active" : ""}
              onClick={() => setMode("fixed")}
            >
              Fixed window
            </button>
            <button
              type="button"
              className={mode === "recurring" ? "active" : ""}
              onClick={() => setMode("recurring")}
            >
              Recurring
            </button>
          </div>
          {mode === "duration" ? (
            <label>
              Minutes
              <input
                type="number"
                min={1}
                max={1440}
                value={minutes}
                onChange={(event) => setMinutes(Number(event.target.value))}
              />
            </label>
          ) : mode === "fixed" ? (
            <>
              <label>
                Start
                <input
                  type="datetime-local"
                  required
                  value={startsAt}
                  onChange={(event) => setStartsAt(event.target.value)}
                />
              </label>
              <label>
                End
                <input
                  type="datetime-local"
                  required
                  value={endsAt}
                  onChange={(event) => setEndsAt(event.target.value)}
                />
              </label>
            </>
          ) : (
            <>
              <label>
                Daily start
                <input
                  type="time"
                  required
                  value={recurrenceTime}
                  onChange={(event) => setRecurrenceTime(event.target.value)}
                />
              </label>
              <label>
                Minutes
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={recurrenceMinutes}
                  onChange={(event) => setRecurrenceMinutes(Number(event.target.value))}
                />
              </label>
            </>
          )}
          <button
            className="primary"
            type="submit"
            disabled={Boolean(active) || enabledCount === 0}
          >
            {active
              ? "A session is already active"
              : enabledCount > 0
                ? `Start ${enabledCount} module${enabledCount === 1 ? "" : "s"}`
                : "Enable a module to run"}
          </button>
          {active ? (
            <button
              className="danger"
              type="button"
              onClick={() =>
                void emergencyStopSession(active.id).then(onRefresh).catch((reason: unknown) =>
                  onError(reason instanceof Error ? reason.message : String(reason)),
                )
              }
            >
              Emergency Stop
            </button>
          ) : null}
        </form>
        <div className="panel">
          <h3>Session history</h3>
          <div className="run-list">
            {sessions.map((session) => (
              <div className="run-row" key={session.id}>
                <div>
                  <strong>{titleCase(session.status)}</strong>
                  <span>{new Date(session.starts_at).toLocaleString()}</span>
                </div>
                <div>
                  <span>{titleCase(session.admission_phase)}</span>
                  <span>{remaining(session.ends_at)}</span>
                </div>
              </div>
            ))}
          </div>
          <details>
            <summary>Module run diagnostics</summary>
            <div className="run-list">
              {runs.map((run) => (
                <div className="run-row" key={run.id}>
                  <div>
                    <strong>{titleCase(run.status)}</strong>
                    <span>{run.task_id}</span>
                  </div>
                  <span>{run.result_summary ?? run.error_code ?? "No result yet"}</span>
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    </section>
  );
}

function QueuePanel({
  requests,
  status,
  onRefresh,
  onError,
}: {
  requests: WorkRequestRecord[];
  status: QueueStatusRecord | null;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  return (
    <section aria-labelledby="queue-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Durable delivery and backpressure</p>
          <h2 id="queue-heading">Work queue</h2>
        </div>
      </div>
      <div className="queue-summary panel">
        <QueueMetric label="Queued" value={status?.queued ?? 0} />
        <QueueMetric label="In progress" value={status?.claimed ?? 0} />
        <QueueMetric
          label="Awaiting acknowledgement"
          value={status?.awaiting_acknowledgement ?? 0}
        />
        <QueueMetric
          label="Pressure"
          value={`${Math.round((status?.pressure ?? 0) * 100)}%`}
        />
        <QueueMetric
          label="Estimated clear"
          value={formatDuration(status?.estimated_queue_clear_seconds ?? 0)}
        />
      </div>
      <div className="panel queue-list">
        {requests.length === 0 ? (
          <p className="muted">No durable work requests have been submitted.</p>
        ) : (
          requests.map((request) => (
            <QueueRequestRow
              key={request.id}
              request={request}
              onRefresh={onRefresh}
              onError={onError}
            />
          ))
        )}
      </div>
    </section>
  );
}

function QueueMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function QueueRequestRow({
  request,
  onRefresh,
  onError,
}: {
  request: WorkRequestRecord;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [priority, setPriority] = useState(request.task_priority);

  async function act(operation: () => Promise<unknown>) {
    try {
      await operation();
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <details className="queue-item">
      <summary>
        <span>
          <strong>{titleCase(request.status)}</strong>
          <small>{request.task_id}</small>
        </span>
        <span>
          {titleCase(request.work_class)} · priority {request.task_priority}
        </span>
      </summary>
      <dl className="queue-facts">
        <div><dt>Module</dt><dd>{request.module_id}</dd></div>
        <div><dt>Attempts</dt><dd>{request.attempt_count} / {request.max_retries + 1}</dd></div>
        <div><dt>Created</dt><dd>{new Date(request.created_at).toLocaleString()}</dd></div>
        <div><dt>Idempotency</dt><dd>{request.idempotency_key}</dd></div>
      </dl>
      <div className="queue-actions">
        {request.status === "queued" ? (
          <>
            <label>
              Task priority
              <input
                type="number"
                min={0}
                max={100}
                value={priority}
                onChange={(event) => setPriority(Number(event.target.value))}
              />
            </label>
            <button
              type="button"
              onClick={() => void act(() => reprioritizeWorkRequest(request.id, priority))}
            >
              Update priority
            </button>
            <button
              className="danger"
              type="button"
              onClick={() => void act(() => cancelWorkRequest(request.id))}
            >
              Cancel
            </button>
          </>
        ) : null}
        {["failed", "cancelled"].includes(request.status) ? (
          <button type="button" onClick={() => void act(() => retryWorkRequest(request.id))}>
            Retry
          </button>
        ) : null}
      </div>
      <details>
        <summary>Request contract</summary>
        <pre>{JSON.stringify({
          payload: request.payload,
          provenance: request.provenance,
          output_contract: request.output_contract,
          requirements: request.requirements,
        }, null, 2)}</pre>
      </details>
    </details>
  );
}

function RulesPanel({
  rules,
  onRefresh,
  onError,
}: {
  rules: ScoringRule[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [target, setTarget] = useState("company");
  const [action, setAction] = useState("prefer");
  const [pattern, setPattern] = useState("");
  const [note, setNote] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await createRule({ target, action, pattern, note: note || undefined });
      setPattern("");
      setNote("");
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <section aria-labelledby="rules-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Explicit preferences beat psychic software</p>
          <h2 id="rules-heading">Pursuit rules</h2>
        </div>
      </div>
      <div className="two-column">
        <form className="panel" onSubmit={(event) => void submit(event)}>
          <h3>Add a rule</h3>
          <label>
            Target
            <select value={target} onChange={(event) => setTarget(event.target.value)}>
              {[
                "company",
                "domain",
                "title",
                "industry",
                "location",
                "employment_type",
                "source",
              ].map((value) => (
                <option key={value} value={value}>
                  {titleCase(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Action
            <select value={action} onChange={(event) => setAction(event.target.value)}>
              {["hard_include", "hard_exclude", "prefer", "deprioritize", "watch"].map(
                (value) => (
                  <option key={value} value={value}>
                    {titleCase(value)}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            Pattern
            <input
              required
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
            />
          </label>
          <label>
            Note
            <textarea value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button className="primary" type="submit">
            Add rule
          </button>
        </form>
        <div className="panel">
          <h3>Current rules</h3>
          {rules.map((rule) => (
            <div className="rule-row" key={rule.id}>
              <div>
                <strong>{titleCase(rule.action)}</strong>
                <span>{titleCase(rule.target)} contains “{rule.pattern}”</span>
                {rule.note ? <small>{rule.note}</small> : null}
              </div>
              <button
                type="button"
                onClick={() =>
                  void deleteRule(rule.id).then(onRefresh).catch((reason: unknown) =>
                    onError(reason instanceof Error ? reason.message : String(reason)),
                  )
                }
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ProfilePanel({
  profile,
  onRefresh,
  onError,
}: {
  profile: CareerProfile | null;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  return (
    <section aria-labelledby="profile-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Positioning is proposed, never smuggled in</p>
          <h2 id="profile-heading">Positioning hypotheses</h2>
        </div>
      </div>
      <div className="card-grid">
        {profile?.hypotheses.map((hypothesis) => (
          <article className="panel" key={hypothesis.id}>
            <div className="status-line">
              <span>{titleCase(hypothesis.decision)}</span>
              <span>{Math.round(hypothesis.confidence * 100)}% confidence</span>
            </div>
            <h3>{hypothesis.label}</h3>
            <p>{hypothesis.summary}</p>
            <blockquote>{hypothesis.suggested_headline}</blockquote>
            <div className="actions">
              <button
                className="primary"
                type="button"
                onClick={() =>
                  void decideHypothesis(hypothesis.id, "approved")
                    .then(onRefresh)
                    .catch((reason: unknown) =>
                      onError(reason instanceof Error ? reason.message : String(reason)),
                    )
                }
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() =>
                  void decideHypothesis(hypothesis.id, "disapproved")
                    .then(onRefresh)
                    .catch((reason: unknown) =>
                      onError(reason instanceof Error ? reason.message : String(reason)),
                    )
                }
              >
                Disapprove
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function PreferencesPanel({
  settings,
  location,
  onRefresh,
  onError,
}: {
  settings: Record<string, unknown> | null;
  location: Record<string, unknown> | null;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const weights = (settings?.weights ?? {}) as Record<string, number>;

  async function saveLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await saveLocationPreferences({
        ...location,
        home_region: String(data.get("home_region") ?? "") || null,
        local_max_commute_minutes: Number(data.get("commute")),
      });
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function saveWeights(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await saveScoringSettings({
        ...settings,
        weights: {
          fit: Number(data.get("fit")),
          response_likelihood: Number(data.get("response")),
          opportunity_value: Number(data.get("value")),
        },
      });
      await onRefresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  return (
    <section aria-labelledby="preferences-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Tune the machine without teaching it astrology</p>
          <h2 id="preferences-heading">Preferences</h2>
        </div>
      </div>
      <div className="two-column">
        <form className="panel" onSubmit={(event) => void saveLocation(event)}>
          <h3>Location</h3>
          <label>
            Home region
            <input
              name="home_region"
              defaultValue={String(location?.home_region ?? "")}
              placeholder="NC"
            />
          </label>
          <label>
            Maximum local commute, minutes
            <input
              name="commute"
              type="number"
              min={1}
              max={300}
              defaultValue={Number(location?.local_max_commute_minutes ?? 90)}
            />
          </label>
          <button className="primary" type="submit">
            Save location preferences
          </button>
        </form>
        <form className="panel" onSubmit={(event) => void saveWeights(event)}>
          <h3>Priority weights</h3>
          <label>
            Fit
            <input name="fit" type="number" step="0.05" min={0} defaultValue={weights.fit ?? 0.35} />
          </label>
          <label>
            Response likelihood
            <input
              name="response"
              type="number"
              step="0.05"
              min={0}
              defaultValue={weights.response_likelihood ?? 0.45}
            />
          </label>
          <label>
            Opportunity value
            <input
              name="value"
              type="number"
              step="0.05"
              min={0}
              defaultValue={weights.opportunity_value ?? 0.2}
            />
          </label>
          <button className="primary" type="submit">
            Save scoring weights
          </button>
        </form>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{score(value)}</strong>
    </div>
  );
}

function score(value: number | undefined) {
  return value === undefined ? "--" : Math.round(value).toString();
}

function remaining(deadline: string | null) {
  if (!deadline) {
    return "No deadline";
  }
  const seconds = Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000));
  if (seconds < 60) {
    return `${seconds}s remaining`;
  }
  return `${Math.floor(seconds / 60)}m remaining`;
}

function formatDuration(seconds: number) {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `${minutes}m` : `${Math.round(minutes / 60)}h`;
}

function titleCase(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const APPLICATION_STATUSES: ApplicationStatus[] = [
  "discovered",
  "saved",
  "dismissed",
  "planned_to_apply",
  "applying",
  "applied",
  "recruiter_contact",
  "screening",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
  "closed_without_response",
];
