# Durable Shared Work Queue Handoff

## Accepted baseline

- Branch: `dev`
- Version: `0.10.0`
- Product authority: `refs/planning/product-requirements-document.md`
- Roadmap authority: `refs/planning/mvp-roadmap.md`
- Module contract: `refs/planning/module-package-contract.md`

## Implemented

- Generic deterministic, network, LLM, human-review, and composite work classes.
- Durable typed requests with module-scoped idempotency keys.
- Durable attempts, results, delivery counts, and acknowledgements.
- At-least-once result delivery until explicit module acknowledgement.
- Restart recovery that marks interrupted attempts and requeues their requests.
- Global and per-module soft and hard queue limits.
- Queue depth, pressure, next-request wait, and clear-time estimates.
- Initial ordering by normalized module priority, module-local task priority, and age.
- Authenticated module submit, result delivery, and acknowledgement routes.
- Manager inspection, claim, complete, fail, retry, cancel, and reprioritize routes.
- Desktop queue summary and progressively disclosed request intervention controls.

## Deliberate boundaries

- Provider execution is not part of this increment. Claims and attempt completion
  are generic contracts for the provider-neutral manager introduced next.
- Model suitability, loaded-model affinity, and model-switch cost are represented
  by request requirements but do not affect ordering until Increment 11.
- Exactly-once execution is not promised. Modules must safely tolerate duplicate
  result delivery and use idempotency keys for harmful duplicate work.
- Queue duration estimates start from a conservative default and improve from
  observed completed-attempt durations.
- The Job Scout discovery pass does not yet manufacture placeholder LLM work merely
  to exercise the queue. Its first real model-blind requests arrive with provider
  integration.

## Validation

```powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe -m pytest
cd desktop
npm run build
cd src-tauri
cargo check --tests
```

`tests/test_work_queue.py` covers idempotency, at-least-once delivery,
acknowledgement, retries, hard limits, ordering, telemetry, and restart recovery.
The API and supervisor suites cover manager and authenticated module boundaries.

## Next increment

Implement Increment 11 from `refs/planning/mvp-roadmap.md`:

1. Define provider-neutral model-blind invocation and result validation contracts.
2. Move provider selection and invocation behind the manager queue worker.
3. Add Ollama discovery and invocation as the first local provider.
4. Record task-level timing, validity, retry, failure, and acceptance evidence.
5. Activate model suitability and switch-cost queue-ordering terms.
