import { useEffect, useMemo, useState } from "react";

import { getJobScoutDiscoveryAudit, type DiscoveryAudit } from "./api";
import { titleCase } from "./display";

export function DiscoveryAuditPanel() {
  const [audit, setAudit] = useState<DiscoveryAudit | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      void getJobScoutDiscoveryAudit()
        .then((value) => {
          if (!cancelled) setAudit(value);
        })
        .catch(() => undefined);
    };
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const gaps = useMemo(
    () => Object.entries(audit?.coverage_gaps ?? {}).filter(([, values]) => values.length > 0),
    [audit],
  );
  const strategies = audit?.strategies.filter((item) => item.attempts > 0).slice(0, 24) ?? [];

  return (
    <details className="panel workspace-section">
      <summary>
        <strong>Discovery audit</strong>
        <span>{strategies.length} recent experiments</span>
      </summary>
      <div className="embedded-panel">
        <p className="muted">
          Read-only evidence for what Job Scout searched, what each path returned, and what remains uncovered.
        </p>
        {gaps.length ? (
          <div className="scan-summary">
            <strong>Coverage gaps</strong>
            {gaps.map(([dimension, values]) => (
              <span key={dimension}>
                {titleCase(dimension)}: {values.join(", ")}
              </span>
            ))}
          </div>
        ) : (
          <p className="muted">No explicit coverage gaps are recorded for the latest discovery session.</p>
        )}
        {strategies.length ? (
          <ul className="source-list">
            {strategies.map((strategy) => (
              <li key={strategy.id}>
                <span>
                  <strong>{titleCase(strategy.hypothesis_family)}</strong>
                  {strategy.anchor ? ` | ${strategy.anchor}` : ""}
                </span>
                <small>
                  {titleCase(strategy.source_path || "unknown path")} | weight {strategy.learned_weight.toFixed(2)}
                  {strategy.weight_before !== null && strategy.weight_after !== null
                    ? ` (${strategy.weight_before.toFixed(2)} -> ${strategy.weight_after.toFixed(2)})`
                    : ""}
                  {` | yield ${strategy.conditioned_yield}/${strategy.total_yield}`}
                  {strategy.overlap_company_count ? ` | ${strategy.overlap_company_count} overlap` : ""}
                </small>
                {strategy.compiled_query ? <code title={strategy.compiled_query}>{strategy.compiled_query}</code> : null}
                {strategy.warnings.length ? <small>Warnings: {strategy.warnings.join(", ")}</small> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No discovery experiments have been attempted yet.</p>
        )}
      </div>
    </details>
  );
}
