# Nerve Center

Nerve Center is a local-first, single-user orchestration platform for scheduled desktop tasks that may use local tools and local language models.

The first task module is **Job Scout**, a job-discovery and decision-support workflow that searches public sources, evaluates opportunities against a user-controlled career profile, and prioritizes positions by both fit and likely employer response.

## Current status

The `dev` branch contains the foundation increment:

- Duration-based and fixed-time run-window contracts.
- A generic task-plugin boundary.
- Externalized operating-system application-data paths.
- A minimal local FastAPI health surface.
- SQLite runtime initialization with WAL enabled.
- Public-repository privacy and security guardrails.
- Durable product, architecture, scoring, and roadmap decisions under `refs/`.

Job discovery connectors and the desktop shell are not implemented yet.

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

## Local development

Requirements:

- Python 3.12+

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
ruff check .
pytest
nerve-center-api
```

The API defaults to `127.0.0.1:8765` and stores runtime data in the platform-specific user application-data directory, never in the checkout.

## Repository branches

- `main`: stable public baseline.
- `dev`: accepted integration branch for active development.
- Feature work should branch from `dev` and return through pull requests.

## Public repository safety

This repository must never contain resumes, career-history source documents, application records, browser profiles, cookies, authenticated session data, credentials, generated personalized documents, or local runtime logs. See `SECURITY.md` and `refs/planning/data-and-privacy-boundary.md`.

## Shared design guidance

Nerve Center follows the canonical principles in `Three-Wheeled-Sloth-Studio/TWS-Design-Principles`. Project-specific decisions, implementation notes, and deliberate deviations remain here.

## License

License selection is pending. Until a license is added, no rights are granted beyond those provided by applicable law.
