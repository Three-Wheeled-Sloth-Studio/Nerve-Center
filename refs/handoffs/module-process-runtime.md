# Module Process Runtime Handoff (Archived)

## Accepted baseline

- Branch: `dev`
- Version: `0.8.0`
- Superseded by: `refs/handoffs/session-scheduler-wind-down.md`
- Product authority: `refs/planning/product-requirements-document.md`
- Package contract: `refs/planning/module-package-contract.md`

## Implemented

- Generic supervised `managed_python` module launcher.
- Per-launch cryptographic bearer tokens and versioned loopback HTTP routes.
- One-time run assignment with run ID, task ID, deadline, priority, queue
  limits, resource policy, configuration, checkpoint, and assigned data path.
- Manager-owned checkpoint and resource-budget callbacks.
- Module-scoped operation bridges without shared database or credential access.
- Heartbeat, activity, backlog, queue-pressure, process ID, degraded, failed,
  stopping, and stopped runtime reporting.
- Graceful pause/shutdown with bounded terminate and kill fallback.
- Unexpected worker-exit propagation to the active run.
- Job Scout discovery orchestration moved into its child worker.
- Desktop module cards show live runtime status and poll it with run state.
- Source and packaged-executable worker entry paths.

## Deliberate migration boundary

The Job Scout worker owns its discovery loop but invokes registered operations
through `JobScoutOperationBridge`. Existing Job Scout persistence and connector
services remain manager-side until their records move behind durable generic
work/result contracts. This preserves the accepted shared-SQLite ownership
boundary and avoids exposing the database to child processes.

The current assignment queue is volatile. Runs remain durable and interrupted
runs are recovered, but durable request/result delivery belongs to Increment
10 after session scheduling in Increment 9.

## Validation

```powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe -m pytest
cd desktop
npm run build
cd src-tauri
cargo check --tests
```

`tests/test_module_runtime_integration.py` starts a real loopback API, launches
the Job Scout child process, completes a run, verifies runtime telemetry, and
pauses the module cleanly.

## Next increment

Implement Increment 9 from `refs/planning/mvp-roadmap.md`:

1. Introduce durable manager work sessions as the scheduling unit.
2. Resolve duration, fixed-time, and recurring wall-clock windows.
3. Launch all enabled modules with normalized priority allocations.
4. Implement Open, Constrained, Draining, and Closed admission phases.
5. Add graceful wind-down, Emergency Stop, and restart restoration against the
   original wall-clock end.
