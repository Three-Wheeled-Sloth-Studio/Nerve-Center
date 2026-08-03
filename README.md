# Nerve Center

Nerve Center is a local-first, single-user orchestration platform for scheduled desktop tasks that may use local tools and local language models.

The first task module is **Job Scout**, a job-discovery and decision-support workflow that searches public sources, evaluates opportunities against a user-controlled career profile, and prioritizes positions by both fit and likely employer response.

## Product boundaries

Nerve Center is designed to:

- Run tasks for a configured duration or within a configured start and end window.
- Discover information from public, policy-compatible sources.
- Use local Ollama models behind provider-neutral structured contracts.
- Persist durable local state outside the source repository.
- Explain recommendations and preserve an audit trail.
- Suggest user actions without performing consequential external actions automatically.

Nerve Center will not:

- Submit job applications.
- Send outreach or messages.
- Change online profiles.
- Automate authenticated LinkedIn or job-board sessions.
- Provide cloud synchronization, hosted deployment, mobile access, or multi-user support.

## Repository status

Early architecture and implementation work is performed on the `dev` branch. The `main` branch is the stable public baseline.

## Public repository safety

This repository must never contain:

- Resumes or career-history source documents.
- Application records or discovered-job databases.
- Browser profiles, cookies, or authenticated session data.
- API keys, tokens, passwords, or generated credentials.
- Generated cover letters or tailored resume copies containing personal information.
- Local runtime logs containing personal or company-specific search history.

Runtime data and secrets will be stored outside the checkout using operating-system-appropriate application data and credential storage.

## Shared design guidance

Nerve Center follows the canonical principles in:

- `Three-Wheeled-Sloth-Studio/TWS-Design-Principles`

Project-specific decisions, implementation notes, and deliberate deviations remain in this repository.

## License

License selection is pending. Until a license is added, no rights are granted beyond those provided by applicable law.
