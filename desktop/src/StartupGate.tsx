import { invoke } from "@tauri-apps/api/core";
import { type ReactNode, useEffect, useState } from "react";

import "./startup.css";

const API_BASE =
  import.meta.env.VITE_NERVE_CENTER_API ?? "http://127.0.0.1:8765";

interface StartupStatus {
  phase: string;
  message: string;
  detail: string | null;
  backendSource: string | null;
  logPath: string | null;
  pid: number | null;
  updatedAtMs: number;
}

function runningInTauri(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

async function browserHealth(): Promise<StartupStatus> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const payload = (await response.json()) as { status?: string };
    if (payload.status !== "ok") {
      throw new Error("The health endpoint returned an unexpected response.");
    }
    return {
      phase: "ready",
      message: "Connected to the local development service.",
      detail: null,
      backendSource: "browser development service",
      logPath: null,
      pid: null,
      updatedAtMs: Date.now(),
    };
  } catch (reason) {
    return {
      phase: "failed",
      message: "The local development service is unavailable.",
      detail: reason instanceof Error ? reason.message : String(reason),
      backendSource: "browser development service",
      logPath: null,
      pid: null,
      updatedAtMs: Date.now(),
    };
  }
}

async function readStartupStatus(): Promise<StartupStatus> {
  if (runningInTauri()) {
    return invoke<StartupStatus>("startup_status");
  }
  return browserHealth();
}

export default function StartupGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<StartupStatus | null>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const next = await readStartupStatus();
        if (!cancelled) {
          setStatus(next);
        }
      } catch (reason) {
        if (!cancelled) {
          setStatus({
            phase: "failed",
            message: "Desktop startup status could not be read.",
            detail: reason instanceof Error ? reason.message : String(reason),
            backendSource: "Tauri shell",
            logPath: null,
            pid: null,
            updatedAtMs: Date.now(),
          });
        }
      }
    }

    void refresh();
    const timer = window.setInterval(() => void refresh(), 750);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  async function retry() {
    setRetrying(true);
    try {
      if (runningInTauri()) {
        await invoke("restart_api");
      }
      setStatus(await readStartupStatus());
    } finally {
      setRetrying(false);
    }
  }

  if (status?.phase === "ready") {
    return <>{children}</>;
  }

  const failed = status?.phase === "failed";
  return (
    <main className="startup-shell" aria-live="polite">
      <section className="startup-card">
        <div className={failed ? "startup-mark failed" : "startup-mark"}>
          <span />
        </div>
        <p className="startup-eyebrow">Local runtime bootstrap</p>
        <h1>{failed ? "Nerve Center could not start" : "Starting Nerve Center"}</h1>
        <p className="startup-message">
          {status?.message ?? "Preparing the desktop and local service."}
        </p>

        {status?.detail ? (
          <pre className="startup-detail">{status.detail}</pre>
        ) : null}

        <dl className="startup-facts">
          {status?.backendSource ? (
            <>
              <dt>Backend</dt>
              <dd>{status.backendSource}</dd>
            </>
          ) : null}
          {status?.pid ? (
            <>
              <dt>Process</dt>
              <dd>{status.pid}</dd>
            </>
          ) : null}
          {status?.logPath ? (
            <>
              <dt>Local diagnostics</dt>
              <dd>{status.logPath}</dd>
            </>
          ) : null}
        </dl>

        {failed ? (
          <button
            type="button"
            className="startup-retry"
            disabled={retrying}
            onClick={() => void retry()}
          >
            {retrying ? "Restarting…" : "Retry local service"}
          </button>
        ) : (
          <div className="startup-progress" aria-hidden="true">
            <span />
          </div>
        )}

        <p className="startup-note">
          Runtime data and diagnostics remain on this machine, outside the source
          checkout.
        </p>
      </section>
    </main>
  );
}
