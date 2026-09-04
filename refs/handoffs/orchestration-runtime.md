---
type: Implementation Handoff
title: Orchestration Runtime Handoff
description: Accepted durable run lifecycle, scheduling windows, restart recovery, resource budgets, and audit checkpoint.
status: stable
tags: [nerve-center, handoff, orchestration]
---
# Orchestration Runtime Handoff

## Accepted baseline

- Branch: `dev`.
- Accepted through commit: `1affa9c294dfebd712b27130a7d2c4b16b93aea9` plus this documentation commit.
- Visible version: `0.1.0`.
- Schema version: `2`.
- Python requirement: `3.12+`.
- Tracking issue: `#1`.

## Implemented

### Persisted run lifecycle

Runs persist their task identifier, window definition, concrete execution timestamps, status, cancellation flag, configuration, checkpoint, resource budget, resource usage, result summary, error code, and metrics.

Accepted states:

- `requested`
- `scheduled`
- `running`
- `cancelling`
- `interrupted`
- `succeeded`
- `partial`
- `cancelled`
- `failed`
- `missed`

Invalid transitions raise a domain error rather than silently rewriting state.

### Window behavior

Duration runs resolve their start and deadline when execution begins. Fixed-window runs remain scheduled until their start, launch automatically while the scheduler process is active, and become missed when the complete window passes before launch.

An interrupted duration run retains its original deadline. It does not receive a fresh full-duration allowance merely because the process restarted.

### Restart and shutdown behavior

On startup, persisted `running` and `cancelling` runs become `interrupted`. They retain checkpoints, budgets, usage, and original timing. They can be deliberately resumed while their window remains valid.

On shutdown, active runs receive a cancellation request and a bounded grace period. Tasks that do not stop within that period are cancelled by the process.

### Resource budgets

Each run persists:

- Maximum outbound requests.
- Maximum LLM calls.
- Maximum parallel work slots.
- Current request and LLM-call usage.

Elapsed time is enforced through the run deadline. Plugins consume request and LLM budgets explicitly and acquire bounded work slots through the shared task context. Budget exhaustion produces a `partial` result with a stable error code and preserved checkpoint.

### Events and audit

Run creation, transitions, cancellation requests, checkpoints, and restart recovery are stored as structured events. The API exposes a bounded event history. Event details are deliberately narrow and must not contain credentials, personal documents, full page bodies, or prompt bodies.

### API surface

- Create a run.
- List recent runs.
- Inspect one run.
- Inspect bounded run-event history.
- Start a run.
- Cancel a run.

The API uses an injectable application factory so tests and future desktop shells can isolate runtime data.

### Validation

Local validation passes 19 tests covering:

- Duration and fixed-window contracts.
- Scheduled and missed runs.
- Valid and invalid state transitions.
- Idempotent cancellation.
- Checkpoint persistence.
- Restart recovery.
- Synthetic task completion.
- Request-budget exhaustion.
- Parallel-work slot acquisition.
- Automatic scheduler launch.
- API creation, cancellation, inspection, events, and unknown-task rejection.

All database tests use temporary directories outside the checkout.

## Known limits

- The scheduler only runs while the Nerve Center process is active.
- The application does not wake a sleeping or powered-off computer.
- Windows startup and system-tray lifecycle belong to the desktop-shell increment.
- Event retention pruning is not implemented yet; API retrieval is bounded.
- The current migration layer is intentionally lightweight while the schema is young.
- Only the synthetic validation plugin is executable.

## Next increment

Proceed with Issue `#2`, Ollama provider and canonical career evidence profile.

Required sequence:

1. Extract provider-neutral interfaces and normalized errors.
2. Implement local Ollama model discovery and structured generation.
3. Add schema validation and deterministic cleanup.
4. Define read-only document references and local import records.
5. Add synthetic PDF, DOCX, Markdown, and text fixtures.
6. Build the evidence-backed canonical profile and user override model.
7. Generate learned positioning hypotheses without exposing multiple user-managed profiles.

Do not start job-source connectors inside the profile increment.
