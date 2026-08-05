# MVP Roadmap

## Increment 0: Foundation

- Establish public-safe repository boundaries.
- Create `dev` integration branch and CI.
- Define run-window and task-plugin contracts.
- Resolve runtime storage outside the checkout.
- Initialize SQLite with WAL.
- Add minimal local API and tests.
- Record accepted, deferred, and rejected decisions.

## Increment 1: Orchestration runtime

- Persist run requests, resolved windows, state transitions, checkpoints, and outcomes.
- Add task registry and plugin discovery.
- Add cancellation, deadline, retry, concurrency, and resource budgets.
- Add structured redacted event logging.
- Expose run controls and status through the local API.

## Increment 2: Ollama and profile foundation

- Implement provider-neutral model discovery and generation contracts based on Review Room patterns.
- Add structured schema validation and deterministic cleanup.
- Import PDF, DOCX, Markdown, and text resumes.
- Build a canonical evidence profile with source citations and user overrides.
- Generate and learn positioning hypotheses without exposing multiple user-managed profiles.

## Increment 3: Job discovery foundation

- Add source-compliance and source-health registry.
- Add Greenhouse and Lever connectors.
- Add generic `JobPosting` JSON-LD extraction.
- Add direct career-page discovery and company tracking.
- Add zero-cost Playwright web-search POC with dedicated unauthenticated browser data.
- Normalize provenance, dates, locations, content, and identifiers.
- Deduplicate postings across sources.

## Increment 4: Enrichment and scoring

- Add company and office enrichment.
- Add 90-minute commute and regional classification.
- Implement fit, response, value, confidence, and priority contracts.
- Add configurable weights, thresholds, gates, and rule overrides.
- Store factor-level explanations and version metadata.

## Increment 5: Review and application workflow

- Build the Tauri and React desktop shell.
- Present prioritized opportunities with progressive disclosure.
- Add company and title whitelist, blacklist, preference, and watch controls.
- Add application tracking and outcome history.
- Add manual original-listing and company-career-page actions.
- Add approve and disapprove feedback for positioning hypotheses.

## Increment 6: Windows packaging and runtime bootstrap

- Package the Python API as a self-contained Windows executable.
- Bundle the backend into an unsigned NSIS development package.
- Add desktop startup, health, port-conflict, and process-exit reporting.
- Preserve a Python fallback for source development.
- Add retry behavior and local diagnostic-log discovery.
- Add a Windows artifact workflow and real-machine smoke-test checklist.

## Deferred increments

- Code signing, automatic updates, and release channels.
- Remote LLM providers.
- Reviewable resume headline variants.
- Cover letters from immutable masters.
- Gmail-assisted status detection.
- Network and referral analysis.
- ComfyUI task plugins.
- Dedicated vector storage.
- Wake-from-sleep.
- Cross-platform packaging.

## Permanent non-goals

- Cloud synchronization.
- Hosted deployment.
- Mobile access.
- Multi-user support.
- Automated job applications.
- Automated outreach.
- Automated account or profile changes.
- Authenticated LinkedIn or job-board automation.
