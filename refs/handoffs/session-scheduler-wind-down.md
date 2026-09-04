---
type: Implementation Handoff
title: Session Scheduler and Wind-Down Handoff
description: Archived durable work-session, recurring schedule, priority normalization, admission-phase, and wind-down checkpoint.
status: stable
tags: [nerve-center, handoff, scheduler]
---
# Session Scheduler and Wind-Down Handoff (Archived)

## Accepted baseline

- Branch: `dev`
- Version: `0.9.0`
- Superseded by: `refs/handoffs/durable-shared-work-queue.md`
- Product authority: `refs/planning/product-requirements-document.md`
- Roadmap authority: `refs/planning/mvp-roadmap.md`
- Module contract: `refs/planning/module-package-contract.md`

## Implemented

- Durable manager-owned work sessions with concrete wall-clock start and end.
- Duration, fixed-time, and IANA-timezone recurring session definitions.
- One session-entry run for every enabled module that declares a session entry task.
- Deterministic enabled-module priority normalization to exactly 100 points.
- Open, Constrained, Draining, and Closed admission phases derived from remaining
  wall-clock time and queue-clear estimates.
- Session control data delivered to supervised workers at checkpoint boundaries.
- Graceful discovery wind-down while admitted queued work is allowed to finish.
- Explicit Emergency Stop with run cancellation and bounded worker shutdown.
- Restart recovery that preserves the original end time.
- Missed recurring windows recorded without replay; the next future occurrence is
  scheduled instead.
- Desktop session creation, status, history, progressive module-run diagnostics,
  and Emergency Stop controls.
- Real-process integration coverage through the Job Scout managed worker.

## Deliberate boundaries

- The desktop recurring-session form currently schedules all seven weekdays. The
  API and domain contracts already support an explicit weekday subset.
- A module may declare one normal `session_entry_task_id`. Additional task graphs
  remain module-owned behind that entry point.
- A finite module pass may finish before the session closes; its supervised worker
  can remain available until normal wind-down or stop.
- Legacy direct run routes remain available for diagnostics and migration.
- Runs and sessions are durable, but request/result delivery between modules and
  the manager is not yet durable. That work belongs to Increment 10.

## Validation

```powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe -m pytest
cd desktop
npm run build
cd src-tauri
cargo check --tests
```

`tests/test_sessions.py` covers admission timing, queue-estimate wind-down, DST
recurrence, restart recovery, exact priority normalization, and missed recurrence.
`tests/test_module_runtime_integration.py` exercises a real manager session and
Job Scout child process through Emergency Stop.

## Next increment

Implement Increment 10 from `refs/planning/mvp-roadmap.md`:

1. Persist typed work requests before acknowledgement.
2. Add attempts, results, acknowledgements, idempotency, and redelivery.
3. Enforce global and per-module queue limits.
4. Derive queue wait and clear-time estimates from durable records.
5. Add queue inspection, cancellation, retry, and reprioritization controls.
