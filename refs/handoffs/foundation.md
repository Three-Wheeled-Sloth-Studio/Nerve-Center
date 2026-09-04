---
type: Implementation Handoff
title: Archived Foundation Handoff
description: Original 0.1.0 foundation checkpoint for Nerve Center core runtime and project boundaries.
status: stable
tags: [nerve-center, handoff, foundation]
---
# Archived Foundation Handoff

This document records the original `0.1.0` foundation and is no longer the
current implementation handoff. Continue from
`refs/handoffs/core-module-boundary.md` and the increment-specific handoffs.

## Accepted baseline

- Repository visibility: public.
- Stable branch: `main`.
- Integration branch: `dev`.
- Visible version: `0.1.0`.
- Python requirement: 3.12+.

## Implemented

- Public-safe README, security policy, and ignore rules.
- CI for Python lint and tests.
- Platform-specific external runtime data directory.
- Duration-based and fixed-time run-window domain contracts.
- Generic async task-plugin protocol.
- SQLite bootstrap with WAL, foreign keys, and busy timeout.
- Minimal FastAPI health endpoint.
- Job Scout plugin namespace placeholder.
- Durable product, privacy, scoring, source, and roadmap documentation.

## Not yet implemented

- Persisted run and task models.
- Scheduler service and background process lifecycle.
- Task registration or execution.
- Ollama provider.
- Resume ingestion or canonical profile.
- Any job-discovery connector.
- Tauri or React UI.

## Next increment

Implement the orchestration runtime:

1. Persist run requests and resolved windows.
2. Define explicit run-state transitions.
3. Register task plugins.
4. Execute tasks with deadline and cancellation handling.
5. Add resource budgets and checkpoint contracts.
6. Expose create, start, cancel, and inspect operations through the local API.
7. Add tests around deadline boundaries, restart recovery, and invalid transitions.

Do not begin job-source scraping inside the scheduler increment. Keep the core generic and prove it with a synthetic task plugin first.
