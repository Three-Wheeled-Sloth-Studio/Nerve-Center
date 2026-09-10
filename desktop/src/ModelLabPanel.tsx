import { useCallback, useEffect, useState } from "react";

import { getModelLab, type ModelLabOverview } from "./api";
import { messageOf, titleCase } from "./display";

export function ModelLabPanel() {
  const [lab, setLab] = useState<ModelLabOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      setLab(await getModelLab());
    } catch (reason) {
      setError(messageOf(reason));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const session = lab?.exploration_session ?? null;
  const evidenceRows = Object.entries(lab?.task_evidence ?? {});

  return (
    <section aria-labelledby="model-lab-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Manager-owned local evaluation</p>
          <h2 id="model-lab-heading">Model Lab</h2>
        </div>
        <button type="button" onClick={() => void refresh()}>Refresh</button>
      </div>

      {error ? <div className="alert" role="alert">{error}</div> : null}

      <div className="queue-summary panel">
        <Metric label="Status" value={lab?.settings.enabled ? "Enabled" : "Disabled"} />
        <Metric label="Installed models" value={lab?.models.filter((item) => item.installed).length ?? 0} />
        <Metric label="Benchmark corpus" value={lab?.corpus_count ?? 0} />
        <Metric label="Production queue" value={lab?.production_queue.queued ?? 0} />
      </div>

      <div className="two-column">
        <div className="panel">
          <h3>Installed model evidence</h3>
          {lab?.models.length ? (
            <div className="run-list">
              {lab.models.map((model) => (
                <div className="run-row" key={`${model.provider}-${model.model}`}>
                  <div>
                    <strong>{model.label}</strong>
                    <span>{model.provider} · {model.parameter_size ?? "size unknown"} · {model.quantization ?? "quantization unknown"}</span>
                  </div>
                  <span>{model.installed ? "Installed" : "Not installed"}</span>
                </div>
              ))}
            </div>
          ) : <p className="muted">No local model catalog entries yet.</p>}

          <details>
            <summary>Task-specific production evidence</summary>
            {evidenceRows.length ? evidenceRows.map(([taskId, items]) => (
              <div key={taskId} className="queue-item">
                <strong>{taskId}</strong>
                {items.map((item) => (
                  <p key={`${item.provider}-${item.model}`}>
                    {item.provider}/{item.model}: {item.attempts} attempts, {Math.round(item.success_rate * 100)}% success, {Math.round(item.schema_valid_rate * 100)}% schema-valid
                  </p>
                ))}
              </div>
            )) : <p className="muted">No production routing observations yet.</p>}
          </details>
        </div>

        <div className="panel">
          <h3>Exploration state</h3>
          <p>
            {session
              ? `${titleCase(session.status)}: ${session.attempts_used}/${session.max_attempts} attempts used`
              : "No exploration session has been created."}
          </p>
          <p className="muted">
            Benchmarks are local-only and isolated from production routing evidence. Model Lab will not start a replay while production LLM work is queued or running.
          </p>
          <h3>Recent benchmark results</h3>
          {lab?.benchmark_results.length ? (
            <div className="run-list">
              {lab.benchmark_results.map((result) => (
                <div className="run-row" key={result.id}>
                  <div>
                    <strong>{result.provider}/{result.model}</strong>
                    <span>{result.duration_ms} ms · schema {result.schema_valid === null ? "unknown" : result.schema_valid ? "valid" : "invalid"}</span>
                  </div>
                  <span>{titleCase(result.status)}</span>
                </div>
              ))}
            </div>
          ) : <p className="muted">No benchmark attempts yet.</p>}
        </div>
      </div>

      <div className="panel">
        <h3>Local benchmark corpus</h3>
        <p className="muted">
          Eligible completed model-blind requests are harvested from durable local work history. Request-level and module-level opt-outs are respected, and obvious credential material is redacted before retention.
        </p>
        {lab?.corpus.length ? (
          <div className="run-list">
            {lab.corpus.map((item) => (
              <div className="run-row" key={item.id}>
                <div>
                  <strong>{item.task_id}</strong>
                  <span>{item.module_id} · {item.contract_version}</span>
                </div>
                <span>{item.production_model ?? "model unknown"}</span>
              </div>
            ))}
          </div>
        ) : <p className="muted">No eligible benchmark items captured yet.</p>}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}
