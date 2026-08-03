# Nerve Center

Nerve Center is a local-first, single-user orchestration platform for scheduled desktop tasks that may use local tools and local language models.

The first task module is **Job Scout**, a job-discovery and decision-support workflow that searches public sources, evaluates opportunities against a user-controlled career profile, and prioritizes positions by both fit and likely employer response.

## Current status

The `dev` branch contains:

- Duration-based runs and fixed start/end windows.
- Automatic launch of due fixed-window runs while Nerve Center is active.
- Explicit persisted run states, transitions, checkpoints, results, budgets, and events.
- Restart recovery, idempotent cancellation, and graceful shutdown handling.
- A generic task-plugin registry and synthetic validation plugin.
- A provider-neutral structured LLM contract with local Ollama support.
- Schema-constrained Ollama generation and normalized provider errors.
- Local PDF, DOCX, Markdown, and text resume registration.
- One evidence-backed canonical career profile with durable user decisions.
- Persistent company, source, scan-health, job-opening, provenance, and search-cache records.
- Greenhouse, Lever, schema.org `JobPosting`, and sitemap connectors.
- Direct-employer-preferred cross-source deduplication.
- A scheduler-integrated `job_scout.discovery` task plugin.
- An optional cached Playwright broad-search proof of concept using a dedicated local profile.
- Public-repository privacy and security guardrails.

Opportunity scoring and the Tauri desktop shell are not implemented yet.

## Local development

Requirements:

- Python 3.12+
- Ollama for live local generation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check .
pytest
nerve-center-api
```

Optional Playwright search setup:

```powershell
python -m pip install -e ".[dev,search]"
playwright install chromium
```

The API defaults to `127.0.0.1:8765`. Runtime data is stored in the platform-specific user application-data directory, never in the checkout.

## Local API

### Runtime

- `GET /health`
- `POST /api/v1/runs`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/start`
- `POST /api/v1/runs/{run_id}/cancel`

### Ollama and career profile

- `GET /api/v1/providers/ollama/models`
- `POST /api/v1/profile/documents`
- `GET /api/v1/profile/documents`
- `GET /api/v1/profile`
- `POST /api/v1/profile/extract`
- `POST /api/v1/profile/claims/{claim_id}/decision`
- `PUT /api/v1/profile/claims/{claim_id}`
- `POST /api/v1/profile/hypotheses/{hypothesis_id}/decision`

### Job discovery

- `POST /api/v1/discovery/companies`
- `GET /api/v1/discovery/companies`
- `POST /api/v1/discovery/sources`
- `GET /api/v1/discovery/sources`
- `POST /api/v1/discovery/sources/{source_id}/scan`
- `GET /api/v1/discovery/sources/{source_id}/scans`
- `GET /api/v1/discovery/jobs`
- `POST /api/v1/discovery/search`

Scheduled discovery uses task identifier `job_scout.discovery`. A run may specify `configuration.source_ids`; otherwise it scans sources whose persisted cadence is due.

## Product boundaries

Nerve Center is designed to:

- Run tasks for a configured duration or within a configured start and end window.
- Discover information from public, policy-compatible sources.
- Use local Ollama models behind provider-neutral structured contracts.
- Persist durable local state outside the source repository.
- Explain recommendations and preserve an audit trail.
- Suggest user actions without performing consequential external actions automatically.

Nerve Center will not:

- Submit job applications or outreach.
- Change online profiles.
- Automate authenticated LinkedIn or job-board sessions.
- Provide cloud synchronization, hosted deployment, mobile access, or multi-user support.

## Repository branches

- `main`: stable public baseline.
- `dev`: accepted integration branch for active development.
- Feature work should branch from `dev` and return through pull requests when separate review is useful.

## Public repository safety

This repository must never contain resumes, career-history source documents, application records, browser profiles, cookies, authenticated session data, credentials, generated personalized documents, or local runtime logs. See `SECURITY.md` and `refs/planning/data-and-privacy-boundary.md`.

## Durable references

- `refs/planning/product-vision-and-architecture.md`
- `refs/planning/decision-register.md`
- `refs/planning/mvp-roadmap.md`
- `refs/handoffs/orchestration-runtime.md`
- `refs/handoffs/career-evidence-profile.md`
- `refs/handoffs/job-discovery-sources.md`

Nerve Center also follows the canonical principles in `Three-Wheeled-Sloth-Studio/TWS-Design-Principles`.

## License

License selection is pending. Until a license is added, no rights are granted beyond those provided by applicable law.
