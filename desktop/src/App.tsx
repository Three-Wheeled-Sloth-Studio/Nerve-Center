import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  cancelWorkRequest,
  createDurationSession,
  createFixedSession,
  createRecurringSession,
  createRule,
  decideHypothesis,
  deleteRule,
  discoverJobScoutKeywords,
  emergencyStopSession,
  getJobScoutWorkspace,
  getLocationPreferences,
  getModules,
  getOpportunities,
  getQueueStatus,
  getRules,
  getRuns,
  getScoringSettings,
  getSessions,
  getWorkRequests,
  loadJobScoutResume,
  reprioritizeWorkRequest,
  retryWorkRequest,
  saveJobScoutConfiguration,
  saveLocationPreferences,
  saveScoringSettings,
  scanJobScout,
  setModuleLifecycle,
  updateApplication,
} from "./api";
import type {
  ApplicationStatus,
  JobScoutConfiguration,
  JobScoutScanSummary,
  JobScoutWorkspace,
  ModuleRecord,
  QueueStatusRecord,
  ReviewOpportunity,
  RunRecord,
  ScoringRule,
  SessionRecord,
  WorkRequestRecord,
} from "./types";
import { HomePanel, ManagerSettings, QueuePanel, SchedulePanel } from "./CorePanels";
import { DiscoveryAuditPanel } from "./DiscoveryAuditPanel";
import { JobScoutPanel } from "./JobScoutPanel";
import { messageOf, remaining, titleCase } from "./display";
import "./module.css";

type CoreTab = "home" | "schedule" | "queue" | "settings";
type View = { kind: "core"; tab: CoreTab } | { kind: "module"; moduleId: string };
type SortKey = "priority" | "response" | "fit" | "freshness";

const ACTIVE_RUN_STATUSES = new Set(["queued", "scheduled", "running", "cancelling"]);

export default function App() {
  const [view, setView] = useState<View>({ kind: "core", tab: "home" });
  const [openModuleId, setOpenModuleId] = useState<string | null>(null);
  const [modules, setModules] = useState<ModuleRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [requests, setRequests] = useState<WorkRequestRecord[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatusRecord | null>(null);
  const [jobScout, setJobScout] = useState<JobScoutWorkspace | null>(null);
  const [opportunities, setOpportunities] = useState<ReviewOpportunity[]>([]);
  const [rules, setRules] = useState<ScoringRule[]>([]);
  const [scoringSettings, setScoringSettings] = useState<Record<string, unknown> | null>(null);
  const [location, setLocation] = useState<Record<string, unknown> | null>(null);
  const [sort, setSort] = useState<SortKey>("priority");
  const [includeDismissed, setIncludeDismissed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scanSummary, setScanSummary] = useState<JobScoutScanSummary | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const [nextModules, nextSessions, nextRuns, nextRequests, nextQueue] = await Promise.all([
        getModules(), getSessions(), getRuns(), getWorkRequests(), getQueueStatus(),
      ]);
      setModules(nextModules);
      setSessions(nextSessions);
      setRuns(nextRuns);
      setRequests(nextRequests);
      setQueueStatus(nextQueue);
      if (nextModules.some((item) => item.manifest.module_id === "job_scout")) {
        const [workspace, nextOpportunities, nextRules, nextSettings, nextLocation] = await Promise.all([
          getJobScoutWorkspace(),
          getOpportunities(sort, includeDismissed),
          getRules(),
          getScoringSettings(),
          getLocationPreferences(),
        ]);
        setJobScout(workspace);
        setOpportunities(nextOpportunities);
        setRules(nextRules);
        setScoringSettings(nextSettings);
        setLocation(nextLocation);
      }
    } catch (reason) {
      setError(messageOf(reason));
    }
  }, [includeDismissed, sort]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void Promise.all([getModules(), getSessions(), getRuns(), getWorkRequests(), getQueueStatus()])
        .then(([nextModules, nextSessions, nextRuns, nextRequests, nextQueue]) => {
          setModules(nextModules);
          setSessions(nextSessions);
          setRuns(nextRuns);
          setRequests(nextRequests);
          setQueueStatus(nextQueue);
        })
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const activeRun = runs.find((run) => ACTIVE_RUN_STATUSES.has(run.status));
  const activeSession = sessions.find((session) =>
    ["requested", "running", "interrupted", "draining"].includes(session.status),
  );
  const selectedModule = modules.find((item) => item.manifest.module_id === openModuleId) ?? null;

  function openModule(moduleId: string) {
    setOpenModuleId(moduleId);
    setView({ kind: "module", moduleId });
  }

  function closeModule() {
    setOpenModuleId(null);
    setView({ kind: "core", tab: "home" });
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
              ? `${titleCase(activeRun.status)}: ${remaining(activeRun.deadline)}`
              : "Manager idle"}
        </div>
      </header>

      <nav className="tabs" aria-label="Primary">
        {(["home", "schedule", "queue", "settings"] as CoreTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            className={view.kind === "core" && view.tab === tab ? "tab active" : "tab"}
            onClick={() => setView({ kind: "core", tab })}
          >
            {titleCase(tab)}
          </button>
        ))}
        {selectedModule ? (
          <span className="module-tab-wrap">
            <button
              type="button"
              className={view.kind === "module" ? "tab active module-tab" : "tab module-tab"}
              onClick={() => setView({ kind: "module", moduleId: selectedModule.manifest.module_id })}
            >
              {selectedModule.manifest.display_name}
            </button>
            <button type="button" className="module-tab-close" aria-label="Close module tab" onClick={closeModule}>
              ×
            </button>
          </span>
        ) : null}
      </nav>

      {error ? (
        <div className="alert" role="alert">
          <strong>Something went sideways.</strong> {error}
          <button type="button" onClick={() => void refresh()}>Retry</button>
        </div>
      ) : null}

      <main>
        {view.kind === "core" && view.tab === "home" ? (
          <HomePanel modules={modules} activeSession={activeSession} queueStatus={queueStatus} onOpen={openModule} onRefresh={refresh} onError={setError} />
        ) : null}
        {view.kind === "core" && view.tab === "schedule" ? (
          <SchedulePanel sessions={sessions} runs={runs} modules={modules} onRefresh={refresh} onError={setError} />
        ) : null}
        {view.kind === "core" && view.tab === "queue" ? (
          <QueuePanel requests={requests} status={queueStatus} onRefresh={refresh} onError={setError} />
        ) : null}
        {view.kind === "core" && view.tab === "settings" ? (
          <ManagerSettings modules={modules} />
        ) : null}
        {view.kind === "module" && view.moduleId === "job_scout" ? (
          <>
            <JobScoutPanel
              workspace={jobScout}
              opportunities={opportunities}
              rules={rules}
              scoringSettings={scoringSettings}
              location={location}
              sort={sort}
              includeDismissed={includeDismissed}
              scanSummary={scanSummary}
              busy={busy}
              onBusy={setBusy}
              onSort={setSort}
              onIncludeDismissed={setIncludeDismissed}
              onScanSummary={setScanSummary}
              onRefresh={refresh}
              onError={setError}
            />
            <DiscoveryAuditPanel />
          </>
        ) : null}
      </main>

      <footer>
        Nerve Center prepares and stages work. It never submits an application or takes another consequential external action without you.
      </footer>
    </div>
  );
}
