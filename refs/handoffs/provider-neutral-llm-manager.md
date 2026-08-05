# Provider-Neutral LLM Manager Handoff

## Accepted baseline

- Branch: `dev`
- Version: `0.11.0`
- Product authority: `refs/planning/product-requirements-document.md`
- Roadmap authority: `refs/planning/mvp-roadmap.md`
- Queue handoff: `refs/handoffs/durable-shared-work-queue.md`

## Implemented

- Manager-owned model-blind JSON request and structured result contracts.
- Ollama discovery and JSON-schema invocation behind the provider-neutral adapter.
- Production profile and fit calls routed through manager selection; incoming model
  fields remain optional compatibility inputs and do not control production routing.
- Durable LLM queue worker with manager-side JSON Schema validation.
- Alternate-model fallback after provider failure and evidence-driven escalation
  after schema-invalid results.
- Durable installed-model catalog with provider metadata, declared capabilities,
  and observed host architecture/CPU context.
- Per-task timing, failure, provider retry, schema-validity, and explicit module
  acceptance/rejection observations.
- Conservative empirical selection with deterministic cold-start ordering and a
  bounded loaded-model preference only when prior outcomes remain credible.
- Queue ordering applies a bounded empirical suitability adjustment after module
  priority, allowing evidence and model-switch cost to outweigh small task-priority
  differences without starving a higher-priority module.
- Read-only manager endpoints for the installed catalog and task evidence.

## Deliberate boundaries

- Ollama is the only active adapter. Cloud providers and credential handling remain
  disabled and local-only remains the routing policy.
- GPU, VRAM, and memory fit are explicitly `unmeasured`; Model Lab should add active
  probes rather than guessing from model names.
- Delivery acknowledgement without a disposition remains valid and does not count as
  model acceptance. Modules should send `accepted` and an optional reason when they
  have completed domain validation.
- Numeric quality scoring and user ratings are deferred to Model Lab. Initial routing
  uses manager validation, module disposition, reliability, duration, and loaded-model
  affinity.
- Provider execution is serial in the initial local runtime. Resource-profile work
  will own concurrency and model lifecycle limits.

## Validation

Run from the repository root:

```powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe -m pytest
cd desktop
npm run build
cd src-tauri
cargo check --tests
```

The packaged Windows executable must also pass `/health` and a real managed-worker
smoke before promotion.

## Next increment

Implement Increment 12, Model Lab:

1. Add active hardware-fit probes and model lifecycle/install policy.
2. Build the replay-eligibility and privacy contract for retained requests.
3. Add bounded exploration scheduling outside module priority.
4. Add historical request replay and blinded pairwise review.
5. Surface catalog, evidence, and exploration controls in a manager-owned Model Lab UI.
