# Nerve Center

Nerve Center is a local-first, single-user orchestration platform for scheduled desktop tasks that may use local tools and local language models.

The first task module is **Job Scout**, a job-discovery and decision-support workflow that searches public sources, evaluates opportunities against a user-controlled career profile, and prioritizes positions by fit, likely employer response, and practical pursuit value.

## Current status

The `dev` line now includes:

- A versioned module manifest, compatibility, permission, storage, task, launch, and UI-contribution contract.
- Durable manager-owned module inventory with Enabled, Paused, and Not Installed lifecycle state.
- Run-admission enforcement that prevents paused modules from starting new work.
- Job Scout composition behind the same module bootstrap and task-registration boundary intended for future modules.
- Duration-based runs and fixed start/end windows.
- Automatic launch of due fixed-window runs while Nerve Center is active.
- Explicit persisted run states, transitions, checkpoints, results, budgets, and events.
- Restart recovery, idempotent cancellation, and graceful shutdown handling.
- A generic task-plugin registry.
- A provider-neutral structured LLM contract with local Ollama support.
- Schema-constrained Ollama generation and normalized provider errors.
- Local PDF, DOCX, Markdown, and text resume registration.
- One evidence-backed canonical career profile with durable user decisions.
- Persistent company, source, scan-health, job-opening, provenance, and search-cache records.
- Greenhouse, Lever, schema.org `JobPosting`, and sitemap connectors.
- Direct-employer-preferred cross-source deduplication.
- A scheduler-integrated `job_scout.discovery` task plugin.
- Explainable, configurable opportunity scoring with deterministic location logic and append-only history.
- Durable application tracking and outcome history.
- A React review client and Tauri v2 desktop shell with close-to-tray behavior.
- Windows runtime bootstrap with packaged-backend supervision and startup-health reporting.
- A repeatable unsigned NSIS development-package workflow.
- Public-repository privacy and security guardrails.

## Local development

### Windows launcher

From the repository root, run `launch.bat` to bootstrap missing local dependencies and start the Tauri desktop shell with its managed Python API:

```powershell
.\launch.bat
```

The launcher uses `.venv\Scripts\python.exe` for the API, installs the editable Python package and desktop dependencies when needed, and reports missing Python, Node.js, or Rust prerequisites. Ollama is optional for launching the application but required for live local-model work. After the desktop shell starts, the API is available at `http://127.0.0.1:8765`.

### Python service

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

### React client

Requirements:

- Node.js 22+

```powershell
cd desktop
npm install
npm run build
npm run dev
```

The Vite development server uses `127.0.0.1:1420` and connects to the local API on port `8765`.

### Tauri desktop shell

Requirements for source development:

- Rust stable toolchain.
- Tauri v2 platform prerequisites.
- The Python package installed in an environment available to the desktop process.

```powershell
cd desktop
npm install
npm run tauri dev
```

Source development falls back to a Python-managed local API. Set `NERVE_CENTER_PYTHON` to an explicit interpreter when the desired environment is not on `PATH`. Set `NERVE_CENTER_API_EXECUTABLE` to test a specific packaged backend. Set `NERVE_CENTER_API_MANAGED=0` to use a service started separately.

The shell probes the local health endpoint before launching a child process, adopts an existing healthy Nerve Center service without taking ownership, reports unrelated port conflicts, hides the main window to the system tray, and stops its managed backend only when the user chooses Quit.

### Windows development package

The Windows package bundles a PyInstaller-built `nerve-center-api.exe`; users of the assembled artifact do not need to install Python, Node.js, Rust, or the repository package.

Build the backend on Windows:

```powershell
python -m pip install -e ".[packaging]"
python scripts/build_windows_backend.py
python scripts/smoke_packaged_backend.py
```

Build the unsigned per-user NSIS installer:

```powershell
cd desktop
npm install
npm run tauri build -- --config src-tauri/tauri.package.conf.json --bundles nsis
```

The packaging-only Tauri config is deliberately not auto-loaded during source development. The draft-aware `Windows package` GitHub Actions workflow performs the same backend smoke test and uploads the installer as a short-lived workflow artifact. Code signing, automatic updates, release channels, and public distribution remain deferred.

## Local API

### Runtime

- `GET /health`
- `GET /api/v1/modules`
- `GET /api/v1/modules/{module_id}`
- `PATCH /api/v1/modules/{module_id}`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/start`
- `POST /api/v1/sessions/{session_id}/emergency-stop`
- `GET /api/v1/work-requests/status`
- `POST /api/v1/work-requests`
- `GET /api/v1/work-requests`
- `GET /api/v1/work-requests/{request_id}`
- `GET /api/v1/work-requests/{request_id}/attempts`
- `POST /api/v1/work-requests/claim`
- `POST /api/v1/work-attempts/{attempt_id}/complete`
- `POST /api/v1/work-attempts/{attempt_id}/fail`
- `POST /api/v1/work-requests/{request_id}/cancel`
- `POST /api/v1/work-requests/{request_id}/retry`
- `PATCH /api/v1/work-requests/{request_id}/priority`
- authenticated `/runtime/v1/modules/{module_id}/*` worker protocol
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

### Opportunity scoring

- `GET /api/v1/scoring/settings`
- `PUT /api/v1/scoring/settings`
- `GET /api/v1/scoring/location-preferences`
- `PUT /api/v1/scoring/location-preferences`
- `GET|PUT /api/v1/scoring/companies/{company_id}/enrichment`
- `GET|PUT /api/v1/scoring/jobs/{job_id}/enrichment`
- `GET|POST /api/v1/scoring/rules`
- `DELETE /api/v1/scoring/rules/{rule_id}`
- `GET|POST /api/v1/scoring/jobs/{job_id}/fit`
- `GET|POST /api/v1/scoring/jobs/{job_id}/scores`

### Review and application tracking

- `GET /api/v1/review/opportunities`
- `GET /api/v1/applications`
- `GET /api/v1/applications/{job_id}`
- `PATCH /api/v1/applications/{job_id}`
- `GET /api/v1/applications/{job_id}/events`

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

This repository must never contain resumes, career-history source documents, application records, browser profiles, cookies, authenticated session data, credentials, generated personalized documents, or local runtime logs. The generated packaged backend is build output and is not committed. See `SECURITY.md` and `refs/planning/data-and-privacy-boundary.md`.

## Durable references

- `refs/planning/product-vision-and-architecture.md`
- `refs/planning/decision-register.md`
- `refs/planning/mvp-roadmap.md`
- `refs/engineering/ci-and-agent-workflow.md`
- `refs/handoffs/orchestration-runtime.md`
- `refs/handoffs/career-evidence-profile.md`
- `refs/handoffs/job-discovery-sources.md`
- `refs/handoffs/opportunity-scoring.md`
- `refs/handoffs/desktop-review-application-tracking.md`
- `refs/handoffs/windows-packaging-runtime-bootstrap.md`
- `refs/handoffs/provider-neutral-llm-manager.md`
- `refs/testing/windows-desktop-smoke.md`
- `refs/testing/source-launcher-and-ollama-smoke.md`

Nerve Center also follows the canonical principles in `Three-Wheeled-Sloth-Studio/TWS-Design-Principles`, including `engineering/CI-Signal-Discipline.md`.

## License

License selection is pending. Until a license is added, no rights are granted beyond those provided by applicable law.
