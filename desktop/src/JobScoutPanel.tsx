import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  createRule,
  decideHypothesis,
  deleteRule,
  discoverJobScoutKeywords,
  loadJobScoutResume,
  saveJobScoutConfiguration,
  saveLocationPreferences,
  saveScoringSettings,
  scanJobScout,
  updateApplication,
} from "./api";
import type {
  ApplicationStatus,
  JobScoutConfiguration,
  JobScoutScanSummary,
  JobScoutWorkspace,
  ReviewOpportunity,
  ScoringRule,
} from "./types";
import { lines, messageOf, Metric, score, titleCase } from "./display";

type SortKey = "priority" | "response" | "fit" | "freshness";

export function JobScoutPanel({ workspace, opportunities, rules, scoringSettings, location, sort, includeDismissed, scanSummary, busy, onBusy, onSort, onIncludeDismissed, onScanSummary, onRefresh, onError }: {
  workspace: JobScoutWorkspace | null;
  opportunities: ReviewOpportunity[];
  rules: ScoringRule[];
  scoringSettings: Record<string, unknown> | null;
  location: Record<string, unknown> | null;
  sort: SortKey;
  includeDismissed: boolean;
  scanSummary: JobScoutScanSummary | null;
  busy: boolean;
  onBusy: (value: boolean) => void;
  onSort: (value: SortKey) => void;
  onIncludeDismissed: (value: boolean) => void;
  onScanSummary: (summary: JobScoutScanSummary | null) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  if (!workspace) return <div className="empty-state">Loading Job Scout…</div>;
  return (
    <section aria-labelledby="job-scout-heading" className="module-workspace">
      <div className="section-heading module-heading">
        <div><p className="eyebrow">Module workspace</p><h2 id="job-scout-heading">Job Scout</h2></div>
        <div className="workspace-stats">
          <span>{workspace.sources.length} sources</span><span>{workspace.opening_count} openings</span><span>{workspace.keywords.keywords.length} keywords</span>
        </div>
      </div>
      <JobScoutSetup workspace={workspace} scanSummary={scanSummary} busy={busy} onBusy={onBusy} onScanSummary={onScanSummary} onRefresh={onRefresh} onError={onError} />
      <details className="panel workspace-section" open>
        <summary><strong>Opportunities</strong><span>{opportunities.length} in current view</span></summary>
        <ReviewPanel items={opportunities} sort={sort} includeDismissed={includeDismissed} busy={busy} onBusy={onBusy} onSort={onSort} onIncludeDismissed={onIncludeDismissed} onRefresh={onRefresh} onError={onError} />
      </details>
      <details className="panel workspace-section">
        <summary><strong>Pursuit rules</strong><span>{rules.length} configured</span></summary>
        <RulesPanel rules={rules} onRefresh={onRefresh} onError={onError} />
      </details>
      <details className="panel workspace-section">
        <summary><strong>Career evidence</strong><span>{workspace.profile.claims.length} claims</span></summary>
        <ProfilePanel workspace={workspace} onRefresh={onRefresh} onError={onError} />
      </details>
      <details className="panel workspace-section">
        <summary><strong>Scoring and location</strong><span>Module-owned preferences</span></summary>
        <PreferencesPanel settings={scoringSettings} location={location} onRefresh={onRefresh} onError={onError} />
      </details>
    </section>
  );
}

function JobScoutSetup({ workspace, scanSummary, busy, onBusy, onScanSummary, onRefresh, onError }: {
  workspace: JobScoutWorkspace;
  scanSummary: JobScoutScanSummary | null;
  busy: boolean;
  onBusy: (value: boolean) => void;
  onScanSummary: (summary: JobScoutScanSummary | null) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [resumePath, setResumePath] = useState("");
  const [configuration, setConfiguration] = useState<JobScoutConfiguration>(workspace.configuration);

  useEffect(() => setConfiguration(workspace.configuration), [workspace.configuration]);

  function setLines(field: keyof JobScoutConfiguration, value: string) {
    setConfiguration((current) => ({ ...current, [field]: lines(value) }));
  }
  async function perform(operation: () => Promise<unknown>) {
    onBusy(true);
    try { await operation(); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } finally { onBusy(false); }
  }
  return (
    <div className="setup-grid">
      <section className="panel setup-card">
        <p className="eyebrow">1 · Career evidence</p>
        <h3>Load a resume</h3>
        <p className="muted">PDF, DOCX, Markdown, and text are imported into local durable storage. Model analysis is optional; keyword discovery also has a deterministic fallback.</p>
        <label>Resume path<input value={resumePath} onChange={(event) => setResumePath(event.target.value)} placeholder="C:\\Users\\you\\Documents\\resume.docx" /></label>
        <button type="button" className="primary" disabled={busy || !resumePath.trim()} onClick={() => void perform(() => loadJobScoutResume(resumePath, false))}>Load resume</button>
        <p className="setup-result">Current: {workspace.configuration.resume_file_name ?? "No resume loaded"}</p>
      </section>

      <section className="panel setup-card">
        <p className="eyebrow">2 · Search intent</p>
        <h3>Basic configuration</h3>
        <label>Target titles<textarea value={configuration.target_titles.join("\n")} onChange={(event) => setLines("target_titles", event.target.value)} placeholder="Director of Product\nPrincipal Product Manager" /></label>
        <label>Locations<textarea value={configuration.locations.join("\n")} onChange={(event) => setLines("locations", event.target.value)} placeholder="Remote\nRaleigh, NC" /></label>
        <label>Work arrangement<select value={configuration.remote_preference} onChange={(event) => setConfiguration({ ...configuration, remote_preference: event.target.value as JobScoutConfiguration["remote_preference"] })}><option value="any">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on_site">On site</option></select></label>
        <label>Public career or ATS URLs<textarea value={configuration.source_urls.join("\n")} onChange={(event) => setLines("source_urls", event.target.value)} placeholder="https://boards.greenhouse.io/company\nhttps://jobs.lever.co/company" /></label>
        <label className="checkbox"><input type="checkbox" checked={configuration.broad_search_enabled} onChange={(event) => setConfiguration({ ...configuration, broad_search_enabled: event.target.checked })} />Use public browser search to discover additional direct sources</label>
        <details><summary>Source policy and timing</summary><label>Allowed domains, one per line<textarea value={configuration.allowed_domains.join("\n")} onChange={(event) => setLines("allowed_domains", event.target.value)} placeholder="Leave empty to allow any public source" /></label><label>Disallowed domains, one per line<textarea value={configuration.disallowed_domains.join("\n")} onChange={(event) => setLines("disallowed_domains", event.target.value)} /></label><label>Scheduled rescan interval, minutes<input type="number" min={5} max={10080} value={configuration.scan_interval_minutes} onChange={(event) => setConfiguration({ ...configuration, scan_interval_minutes: Number(event.target.value) })} /></label></details>
        <button type="button" className="primary" disabled={busy} onClick={() => void perform(() => saveJobScoutConfiguration(configuration))}>Save configuration</button>
      </section>

      <section className="panel setup-card">
        <p className="eyebrow">3 · Keywords</p>
        <h3>Relevant terms</h3>
        <div className="keyword-cloud">{workspace.keywords.keywords.length ? workspace.keywords.keywords.map((keyword) => <span key={keyword}>{keyword}</span>) : <p className="muted">Load a resume or add target titles to discover terms.</p>}</div>
        <label>Manual additions<textarea value={configuration.keywords.join("\n")} onChange={(event) => setLines("keywords", event.target.value)} /></label>
        <button type="button" disabled={busy} onClick={() => void perform(discoverJobScoutKeywords)}>Rediscover keywords</button>
        {workspace.keywords.search_queries.length ? <details><summary>Search queries</summary><ul>{workspace.keywords.search_queries.map((query) => <li key={query}>{query}</li>)}</ul></details> : null}
      </section>

      <section className="panel setup-card scan-card">
        <p className="eyebrow">4 · Scan</p>
        <h3>Run the basic scanner</h3>
        <p className="muted">Scans configured Greenhouse, Lever, and structured career pages now. Public browser discovery is used only when enabled.</p>
        <button type="button" className="primary" disabled={busy || (configuration.source_urls.length === 0 && workspace.sources.length === 0 && !configuration.broad_search_enabled)} onClick={() => {
          onBusy(true); onScanSummary(null);
          void saveJobScoutConfiguration(configuration)
            .then(() => scanJobScout(configuration.broad_search_enabled))
            .then(onScanSummary)
            .then(onRefresh)
            .catch((reason: unknown) => onError(messageOf(reason)))
            .finally(() => onBusy(false));
        }}>{busy ? "Working…" : "Scan now"}</button>
        {scanSummary ? <div className="scan-summary"><strong>{scanSummary.openings_found} openings found</strong><span>{scanSummary.sources_scanned} sources scanned</span><span>{scanSummary.sources_registered} sources added</span>{scanSummary.warnings.map((warning) => <small key={warning}>{warning}</small>)}</div> : null}
        {workspace.sources.length ? <ul className="source-list">{workspace.sources.map((source) => <li key={source.id}><span>{source.name}</span><small>{titleCase(source.kind)} · {titleCase(source.health)}</small></li>)}</ul> : null}
      </section>
    </div>
  );
}

function ReviewPanel({ items, sort, includeDismissed, busy, onBusy, onSort, onIncludeDismissed, onRefresh, onError }: {
  items: ReviewOpportunity[];
  sort: SortKey;
  includeDismissed: boolean;
  busy: boolean;
  onBusy: (value: boolean) => void;
  onSort: (value: SortKey) => void;
  onIncludeDismissed: (value: boolean) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? items.filter((item) => `${item.opening.title} ${item.company.canonical_name} ${item.opening.location_text ?? ""}`.toLowerCase().includes(needle)) : items;
  }, [items, query]);
  async function change(item: ReviewOpportunity, status: ApplicationStatus) {
    onBusy(true);
    try { await updateApplication(item.opening.id, status); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } finally { onBusy(false); }
  }
  return <div className="embedded-panel">
    <div className="review-controls">
      <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title, company, location" /></label>
      <label>Sort<select value={sort} onChange={(event) => onSort(event.target.value as SortKey)}><option value="priority">Priority</option><option value="response">Response likelihood</option><option value="fit">Fit</option><option value="freshness">Freshness</option></select></label>
      <label className="checkbox"><input type="checkbox" checked={includeDismissed} onChange={(event) => onIncludeDismissed(event.target.checked)} />Show dismissed</label>
    </div>
    <div className="opportunity-list">{filtered.length === 0 ? <div className="empty-state">No opportunities match this view.</div> : filtered.map((item) => <article className="opportunity-card" key={item.opening.id}>
      <div className="opportunity-summary"><div className="priority-badge"><strong>{score(item.score?.priority)}</strong><span>priority</span></div><div className="opportunity-title"><h3>{item.opening.title}</h3><p>{item.company.canonical_name} · {item.opening.location_text ?? "Location unclear"}</p><p className="next-action">Next: {item.next_action}</p></div><div className="score-strip"><Metric label="Fit" value={item.score?.fit} /><Metric label="Response" value={item.score?.response_likelihood} /><Metric label="Value" value={item.score?.opportunity_value} /></div></div>
      <div className="actions"><button disabled={busy} onClick={() => void change(item, "saved")}>Save</button><button className="primary" disabled={busy} onClick={() => void change(item, "planned_to_apply")}>Plan to apply</button><button disabled={busy} onClick={() => void change(item, "dismissed")}>Dismiss</button><a href={item.opening.apply_url ?? item.opening.canonical_url} target="_blank">Original listing</a></div>
      <details><summary>Evidence and description</summary><p>{item.opening.description}</p></details>
    </article>)}</div>
  </div>;
}

function RulesPanel({ rules, onRefresh, onError }: { rules: ScoringRule[]; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  const [target, setTarget] = useState("company"); const [action, setAction] = useState("prefer"); const [pattern, setPattern] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); try { await createRule({ target, action, pattern }); setPattern(""); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } }
  return <div className="two-column embedded-panel"><form onSubmit={(event) => void submit(event)}><label>Target<select value={target} onChange={(event) => setTarget(event.target.value)}>{["company", "domain", "title", "industry", "location", "source"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Action<select value={action} onChange={(event) => setAction(event.target.value)}>{["hard_include", "hard_exclude", "prefer", "deprioritize", "watch"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Pattern<input required value={pattern} onChange={(event) => setPattern(event.target.value)} /></label><button className="primary">Add rule</button></form><div>{rules.length ? rules.map((rule) => <div className="rule-row" key={rule.id}><div><strong>{titleCase(rule.action)}</strong><span>{titleCase(rule.target)} contains “{rule.pattern}”</span></div><button onClick={() => void deleteRule(rule.id).then(onRefresh).catch((reason: unknown) => onError(messageOf(reason)))}>Remove</button></div>) : <p className="muted">No pursuit rules yet.</p>}</div></div>;
}

function ProfilePanel({ workspace, onRefresh, onError }: { workspace: JobScoutWorkspace; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  return <div className="embedded-panel"><p>{workspace.profile.claims.length} evidence claims extracted from {workspace.documents.length} document{workspace.documents.length === 1 ? "" : "s"}.</p><div className="card-grid">{workspace.profile.hypotheses.map((hypothesis) => <article className="subcard" key={hypothesis.id}><div className="status-line"><span>{titleCase(hypothesis.decision)}</span><span>{Math.round(hypothesis.confidence * 100)}%</span></div><h3>{hypothesis.label}</h3><p>{hypothesis.summary}</p><blockquote>{hypothesis.suggested_headline}</blockquote><div className="actions"><button className="primary" onClick={() => void decideHypothesis(hypothesis.id, "approved").then(onRefresh).catch((reason: unknown) => onError(messageOf(reason)))}>Approve</button><button onClick={() => void decideHypothesis(hypothesis.id, "disapproved").then(onRefresh).catch((reason: unknown) => onError(messageOf(reason)))}>Disapprove</button></div></article>)}</div></div>;
}

function PreferencesPanel({ settings, location, onRefresh, onError }: { settings: Record<string, unknown> | null; location: Record<string, unknown> | null; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  const weights = (settings?.weights ?? {}) as Record<string, number>;
  async function saveLocation(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); try { await saveLocationPreferences({ ...location, home_region: String(data.get("home_region") ?? "") || null, local_max_commute_minutes: Number(data.get("commute")) }); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } }
  async function saveWeights(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); try { await saveScoringSettings({ ...settings, weights: { fit: Number(data.get("fit")), response_likelihood: Number(data.get("response")), opportunity_value: Number(data.get("value")) } }); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } }
  return <div className="two-column embedded-panel"><form onSubmit={(event) => void saveLocation(event)}><h3>Location</h3><label>Home region<input name="home_region" defaultValue={String(location?.home_region ?? "")} /></label><label>Maximum commute<input name="commute" type="number" defaultValue={Number(location?.local_max_commute_minutes ?? 90)} /></label><button className="primary">Save</button></form><form onSubmit={(event) => void saveWeights(event)}><h3>Priority weights</h3><label>Fit<input name="fit" type="number" step="0.05" defaultValue={weights.fit ?? 0.35} /></label><label>Response likelihood<input name="response" type="number" step="0.05" defaultValue={weights.response_likelihood ?? 0.45} /></label><label>Opportunity value<input name="value" type="number" step="0.05" defaultValue={weights.opportunity_value ?? 0.2} /></label><button className="primary">Save</button></form></div>;
}

