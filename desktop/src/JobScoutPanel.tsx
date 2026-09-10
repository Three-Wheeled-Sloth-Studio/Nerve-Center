import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  Bookmark,
  BriefcaseBusiness,
  ClipboardCheck,
  Clock3,
  Copy,
  ExternalLink,
  FileText,
  FolderOpen,
  ListFilter,
  MapPin,
  Plus,
  ScanSearch,
  Settings2,
  Tags,
  X,
} from "lucide-react";

import {
  createRule,
  decideHypothesis,
  deleteRule,
  discoverJobScoutKeywords,
  saveJobScoutConfiguration,
  saveLocationPreferences,
  saveScoringSettings,
  scanJobScout,
  updateApplication,
  uploadJobScoutResume,
} from "./api";
import type {
  ApplicationStatus,
  JobScoutConfiguration,
  JobScoutScanSummary,
  JobScoutWorkspace,
  ReviewOpportunity,
  ScoringRule,
} from "./types";
import { messageOf, Metric, score, titleCase } from "./display";
import { formatMultivalueText, parseMultivalueText } from "./multivalue";

type SortKey = "priority" | "response" | "fit" | "freshness";
type LocationFilter = "all" | "local" | "local_or_regional";
type DraftField =
  | "target_titles"
  | "locations"
  | "source_urls"
  | "public_job_boards"
  | "allowed_domains"
  | "disallowed_domains"
  | "manual_keywords";
type ConfigurationDrafts = Record<DraftField, string>;

const MAX_RESUME_BYTES = 25 * 1024 * 1024;

function draftsFrom(configuration: JobScoutConfiguration): ConfigurationDrafts {
  return {
    target_titles: formatMultivalueText(configuration.target_titles),
    locations: formatMultivalueText(configuration.locations),
    source_urls: formatMultivalueText(configuration.source_urls),
    public_job_boards: formatMultivalueText(configuration.public_job_boards),
    allowed_domains: formatMultivalueText(configuration.allowed_domains),
    disallowed_domains: formatMultivalueText(configuration.disallowed_domains),
    manual_keywords: formatMultivalueText(configuration.manual_keywords),
  };
}

function fileToBase64(file: File): Promise<string> {
  return file.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
  });
}

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedResume, setSelectedResume] = useState<File | null>(null);
  const [activeDialog, setActiveDialog] = useState<"resume" | "search" | "keywords" | "scan" | null>(null);
  const [configuration, setConfiguration] = useState<JobScoutConfiguration>(workspace.configuration);
  const [drafts, setDrafts] = useState<ConfigurationDrafts>(() => draftsFrom(workspace.configuration));

  useEffect(() => {
    setConfiguration(workspace.configuration);
    setDrafts(draftsFrom(workspace.configuration));
  }, [workspace.configuration]);

  function updateDraft(field: DraftField, value: string) {
    setDrafts((current) => ({ ...current, [field]: value }));
  }
  function materializeConfiguration(): JobScoutConfiguration {
    const publicJobBoards = parseMultivalueText(drafts.public_job_boards);
    return {
      ...configuration,
      target_titles: parseMultivalueText(drafts.target_titles),
      locations: parseMultivalueText(drafts.locations),
      source_urls: parseMultivalueText(drafts.source_urls),
      public_job_boards: publicJobBoards,
      broad_search_enabled: publicJobBoards.length > 0,
      allowed_domains: parseMultivalueText(drafts.allowed_domains),
      disallowed_domains: parseMultivalueText(drafts.disallowed_domains),
      manual_keywords: parseMultivalueText(drafts.manual_keywords),
    };
  }
  async function perform(operation: () => Promise<unknown>): Promise<boolean> {
    onBusy(true);
    try { await operation(); await onRefresh(); return true; } catch (reason) { onError(messageOf(reason)); return false; } finally { onBusy(false); }
  }
  function addSuggestion(field: "target_titles" | "locations", value: string) {
    const values = parseMultivalueText(drafts[field]);
    if (!values.some((item) => item.toLocaleLowerCase() === value.toLocaleLowerCase())) {
      updateDraft(field, formatMultivalueText([...values, value]));
    }
  }
  function chooseResume(file: File | null) {
    if (file && file.size > MAX_RESUME_BYTES) {
      onError("Resume source files must be 25 MB or smaller.");
      setSelectedResume(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setSelectedResume(file);
  }
  async function uploadResume() {
    if (!selectedResume) return;
    const content = await fileToBase64(selectedResume);
    await uploadJobScoutResume(selectedResume.name, content, false);
    setSelectedResume(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }
  const sourceUrls = parseMultivalueText(drafts.source_urls);

  return (
    <div className="setup-compact">
      <div className="setup-toolbar" aria-label="Job Scout setup">
        <button type="button" className="setup-pill" title="Resume and career evidence" onClick={() => setActiveDialog("resume")}>
          <FileText aria-hidden="true" /><span><strong>Resume</strong><small>{workspace.configuration.resume_file_name ?? "Not loaded"}</small></span>
        </button>
        <button type="button" className="setup-pill" title="Search intent and sources" onClick={() => setActiveDialog("search")}>
          <Settings2 aria-hidden="true" /><span><strong>Search</strong><small>{configuration.target_titles.length} titles · {configuration.locations.length} locations</small></span>
        </button>
        <button type="button" className="setup-pill" title="Relevant search terms" onClick={() => setActiveDialog("keywords")}>
          <Tags aria-hidden="true" /><span><strong>Terms</strong><small>{workspace.keywords.keywords.length} selected</small></span>
        </button>
        <button type="button" className="setup-pill setup-pill-primary" title="Scan public job sources" onClick={() => setActiveDialog("scan")}>
          <ScanSearch aria-hidden="true" /><span><strong>Scan</strong><small>{workspace.sources.length} sources</small></span>
        </button>
      </div>

      <SetupDialog open={activeDialog === "resume"} title="Resume" icon={<FileText />} onClose={() => setActiveDialog(null)}>
        <p className="muted">PDF, DOCX, Markdown, and text are imported into local durable storage.</p>
        <p className="setup-current"><strong>Current</strong><span>{workspace.configuration.resume_file_name ?? "No resume loaded"}</span></p>
        <label htmlFor="resume-file-name">Resume file</label>
        <div className="file-picker">
          <input id="resume-file-name" readOnly value={selectedResume?.name ?? ""} placeholder="No file selected" />
          <button type="button" className="icon-button" aria-label="Browse for a resume file" title="Browse for a resume file" disabled={busy} onClick={() => fileInputRef.current?.click()}><FolderOpen aria-hidden="true" /></button>
          <input ref={fileInputRef} className="visually-hidden" type="file" accept=".pdf,.docx,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain" onChange={(event) => chooseResume(event.target.files?.[0] ?? null)} />
        </div>
        <div className="dialog-actions"><button type="button" onClick={() => setActiveDialog(null)}>Cancel</button><button type="button" className="primary" disabled={busy || !selectedResume} onClick={() => void perform(uploadResume).then((saved) => saved && setActiveDialog(null))}>Load resume</button></div>
      </SetupDialog>

      <SetupDialog open={activeDialog === "search"} title="Search setup" icon={<ListFilter />} size="wide" onClose={() => setActiveDialog(null)}>
        <div className="dialog-grid">
          <div>
            <label>Target titles<textarea value={drafts.target_titles} onChange={(event) => updateDraft("target_titles", event.target.value)} placeholder={"Director of Product\nPrincipal Product Manager"} /><small>One title per line.</small></label>
            <SuggestionList icon={<Plus />} label="Suggested from resume" values={workspace.suggestions.target_titles} onAdd={(value) => addSuggestion("target_titles", value)} />
          </div>
          <div>
            <label>Locations<textarea value={drafts.locations} onChange={(event) => updateDraft("locations", event.target.value)} placeholder={"Remote\nRaleigh, NC"} /><small>One location per line; commas remain part of the location.</small></label>
            <SuggestionList icon={<MapPin />} label="Suggested from resume" values={workspace.suggestions.locations} onAdd={(value) => addSuggestion("locations", value)} />
          </div>
        </div>
        <label>Work arrangement<select value={configuration.remote_preference} onChange={(event) => setConfiguration({ ...configuration, remote_preference: event.target.value as JobScoutConfiguration["remote_preference"] })}><option value="any">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on_site">On site</option></select></label>
        <label>Direct career or ATS URLs<textarea value={drafts.source_urls} onChange={(event) => updateDraft("source_urls", event.target.value)} placeholder={"https://boards.greenhouse.io/company\nhttps://jobs.lever.co/company"} /><small>Known employer pages, one URL per line.</small></label>
        <label>Public job boards<textarea value={drafts.public_job_boards} onChange={(event) => updateDraft("public_job_boards", event.target.value)} /><small>These domains are searched through an unauthenticated public provider. Remove all entries to disable public discovery.</small></label>
        <details><summary>Source policy and timing</summary><label>Allowed domains<textarea value={drafts.allowed_domains} onChange={(event) => updateDraft("allowed_domains", event.target.value)} placeholder="Leave empty to allow any public source" /></label><label>Disallowed domains<textarea value={drafts.disallowed_domains} onChange={(event) => updateDraft("disallowed_domains", event.target.value)} /></label><label>Source rescan interval, minutes<input type="number" min={5} max={10080} value={configuration.scan_interval_minutes} onChange={(event) => setConfiguration({ ...configuration, scan_interval_minutes: Number(event.target.value) })} /><small>Automatic scans run inside recurring work sessions configured in Schedule.</small></label></details>
        <div className="dialog-actions"><button type="button" onClick={() => setActiveDialog(null)}>Cancel</button><button type="button" className="primary" disabled={busy} onClick={() => { const next = materializeConfiguration(); setConfiguration(next); void perform(() => saveJobScoutConfiguration(next)).then((saved) => saved && setActiveDialog(null)); }}>Save</button></div>
      </SetupDialog>

      <SetupDialog open={activeDialog === "keywords"} title="Relevant terms" icon={<Tags />} size="wide" onClose={() => setActiveDialog(null)}>
        <div className="keyword-cloud">{workspace.keywords.keywords.length ? workspace.keywords.keywords.map((keyword) => <span key={keyword}>{keyword}</span>) : <p className="muted">Load a resume or add target titles to discover terms.</p>}</div>
        <label>Manual additions<textarea value={drafts.manual_keywords} onChange={(event) => updateDraft("manual_keywords", event.target.value)} /><small>One meaningful term or phrase per line.</small></label>
        {workspace.keywords.search_queries.length ? <details><summary>Search queries</summary><ul>{workspace.keywords.search_queries.map((query) => <li key={query}>{query}</li>)}</ul></details> : null}
        <div className="dialog-actions"><button type="button" onClick={() => setActiveDialog(null)}>Close</button><button type="button" className="primary" disabled={busy} onClick={() => { const next = materializeConfiguration(); setConfiguration(next); void perform(async () => { await saveJobScoutConfiguration(next); return discoverJobScoutKeywords(); }); }}>Rediscover</button></div>
      </SetupDialog>

      <SetupDialog open={activeDialog === "scan"} title="Scan public sources" icon={<ScanSearch />} onClose={() => setActiveDialog(null)}>
        <p className="muted">Scans configured direct sources. When public discovery is enabled, it also searches the configured public boards and registers supported result pages.</p>
        {scanSummary ? <div className="scan-summary"><strong>{scanSummary.openings_found} openings found</strong><span>{scanSummary.queries_run.length} public searches run</span><span>{scanSummary.search_results_seen} results reviewed</span><span>{scanSummary.sources_scanned} sources scanned</span><span>{scanSummary.sources_registered} sources added</span>{scanSummary.warnings.map((warning) => <small key={warning}>{warning}</small>)}</div> : null}
        {workspace.sources.length ? <ul className="source-list">{workspace.sources.map((source) => <li key={source.id}><span>{source.name}</span><small>{titleCase(source.kind)} · {titleCase(source.health)}</small></li>)}</ul> : <p className="muted">No registered sources yet.</p>}
        <div className="dialog-actions"><button type="button" onClick={() => setActiveDialog(null)}>Close</button><button type="button" className="primary" disabled={busy || (sourceUrls.length === 0 && workspace.sources.length === 0 && parseMultivalueText(drafts.public_job_boards).length === 0)} onClick={() => { const next = materializeConfiguration(); setConfiguration(next); onBusy(true); onScanSummary(null); void saveJobScoutConfiguration(next).then(() => scanJobScout(next.public_job_boards.length > 0)).then(onScanSummary).then(onRefresh).catch((reason: unknown) => onError(messageOf(reason))).finally(() => onBusy(false)); }}>{busy ? "Working…" : "Scan now"}</button></div>
      </SetupDialog>
    </div>
  );
}

function SetupDialog({ open, title, icon, size, onClose, children }: { open: boolean; title: string; icon: ReactNode; size?: "wide"; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return <dialog ref={ref} className={`setup-dialog${size === "wide" ? " setup-dialog-wide" : ""}`} onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="dialog-surface">
      <header><span className="dialog-title-icon">{icon}</span><h3>{title}</h3><button type="button" className="icon-button" aria-label={`Close ${title}`} title={`Close ${title}`} onClick={onClose}><X aria-hidden="true" /></button></header>
      <div className="dialog-body">{children}</div>
    </div>
  </dialog>;
}

function SuggestionList({ icon, label, values, onAdd }: { icon: ReactNode; label: string; values: string[]; onAdd: (value: string) => void }) {
  if (!values.length) return null;
  return <div className="suggestion-list"><small>{label}</small><div>{values.map((value) => <button type="button" key={value} title={`Add ${value}`} onClick={() => onAdd(value)}>{icon}<span>{value}</span></button>)}</div></div>;
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
  const [locationFilter, setLocationFilter] = useState<LocationFilter>("all");
  const locationCounts = useMemo(() => ({
    local: items.filter((item) => item.score?.location.scope === "local").length,
    regional: items.filter((item) => item.score?.location.scope === "regional").length,
  }), [items]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesQuery = !needle || `${item.opening.title} ${item.opening.company_name} ${item.opening.location_text ?? ""}`.toLowerCase().includes(needle);
      const scope = item.score?.location.scope ?? "unknown";
      const matchesLocation = locationFilter === "all"
        || (locationFilter === "local" && scope === "local")
        || (locationFilter === "local_or_regional" && ["local", "regional"].includes(scope));
      return matchesQuery && matchesLocation;
    });
  }, [items, locationFilter, query]);
  async function change(item: ReviewOpportunity, status: ApplicationStatus) {
    onBusy(true);
    try { await updateApplication(item.opening.id, status); await onRefresh(); } catch (reason) { onError(messageOf(reason)); } finally { onBusy(false); }
  }
  return <div className="embedded-panel">
    <div className="review-controls">
      <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title, company, location" /></label>
      <label>Sort<select value={sort} onChange={(event) => onSort(event.target.value as SortKey)}><option value="priority">Priority</option><option value="response">Response likelihood</option><option value="fit">Fit</option><option value="freshness">Freshness</option></select></label>
      <label>Location<select value={locationFilter} onChange={(event) => setLocationFilter(event.target.value as LocationFilter)}><option value="all">All locations ({items.length})</option><option value="local">Local ({locationCounts.local})</option><option value="local_or_regional">Local + regional ({locationCounts.local + locationCounts.regional})</option></select></label>
      <label className="checkbox"><input type="checkbox" checked={includeDismissed} onChange={(event) => onIncludeDismissed(event.target.checked)} />Show dismissed</label>
    </div>
    <div className="opportunity-list">{filtered.length === 0 ? <div className="empty-state">No opportunities match this view.</div> : filtered.map((item) => <OpportunityCard key={item.opening.id} item={item} busy={busy} onChange={change} onError={onError} />)}</div>
  </div>;
}

function OpportunityCard({ item, busy, onChange, onError }: {
  item: ReviewOpportunity;
  busy: boolean;
  onChange: (item: ReviewOpportunity, status: ApplicationStatus) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const listingUrl = item.opening.apply_url ?? item.opening.canonical_url;
  async function openListing() {
    try {
      const parsed = new URL(listingUrl);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Only HTTP job links can be opened.");
      await openUrl(parsed.toString());
    } catch (reason) {
      onError(`Could not open the original listing: ${messageOf(reason)}`);
    }
  }
  async function copyListing() {
    try {
      await navigator.clipboard.writeText(listingUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (reason) {
      onError(`Could not copy the listing URL: ${messageOf(reason)}`);
    }
  }
  return <article className="opportunity-card">
    <div className="opportunity-summary"><div className="priority-badge"><strong>{score(item.score?.priority)}</strong><span>priority</span></div><div className="opportunity-title"><h3>{item.opening.title}</h3><p><strong>{item.opening.company_name}</strong> · {item.opening.location_text ?? "Location unclear"}</p><div className="opportunity-meta"><span><BriefcaseBusiness aria-hidden="true" />{titleCase(item.opening.work_arrangement)}</span><span><MapPin aria-hidden="true" />{item.score ? titleCase(item.score.location.scope) : "Location unscored"}</span><span><Clock3 aria-hidden="true" />{freshness(item.opening.posted_at ?? item.opening.discovered_at)}</span><span>{item.score ? `${Math.round(item.score.confidence)}% confidence` : "Unscored"}</span></div></div><div className="score-strip"><Metric label="Fit" value={item.score?.fit} /><Metric label="Response" value={item.score?.response_likelihood} /><Metric label="Value" value={item.score?.opportunity_value} /></div><div className="opportunity-actions"><button className="icon-button" disabled={busy} title="Save" aria-label="Save" onClick={() => void onChange(item, "saved")}><Bookmark aria-hidden="true" /></button><button className="icon-button primary" disabled={busy} title="Plan to apply" aria-label="Plan to apply" onClick={() => void onChange(item, "planned_to_apply")}><ClipboardCheck aria-hidden="true" /></button><button className="icon-button" disabled={busy} title="Dismiss" aria-label="Dismiss" onClick={() => void onChange(item, "dismissed")}><X aria-hidden="true" /></button><button className="icon-button" type="button" title="Open original listing" aria-label="Open original listing" onClick={() => void openListing()}><ExternalLink aria-hidden="true" /></button></div></div>
    <details><summary>Listing details and description</summary><div className="listing-url"><code title={listingUrl}>{listingUrl}</code><button type="button" onClick={() => void copyListing()}><Copy aria-hidden="true" />{copied ? "Copied" : "Copy URL"}</button><button type="button" onClick={() => void openListing()}><ExternalLink aria-hidden="true" />Open listing</button></div><p>{item.opening.description}</p></details>
  </article>;
}

function freshness(value: string): string {
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000));
  if (days === 0) return "Today";
  if (days === 1) return "1 day old";
  return `${days} days old`;
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
