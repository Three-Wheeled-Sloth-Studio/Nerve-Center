---
type: Implementation Handoff
title: Provider-Neutral LLM Manager Handoff
description: Accepted model-blind manager routing, Ollama adapter, empirical selection, evidence, and local provider checkpoint.
status: stable
tags: [nerve-center, handoff, llm, providers]
---
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

### Real-machine source smoke (2026-08-05)

The `dev` checkout at baseline commit `d8f1314` plus the root source-launcher
addition was exercised on Windows x64 with Python 3.12, Node.js 24, Rust 1.95,
and a live local Ollama service.

- `launch.bat` started the Tauri shell and its manager-owned API.
- `GET /health` returned HTTP 200 with version `0.11.0`.
- `GET /api/v1/providers/models` returned five installed Ollama models:
  `codellama:latest`, `gemma4:latest`, `gpt-oss:latest`,
  `qwen2.5-coder:latest`, and `qwen2.5:7b-instruct`.
- Catalog entries included family, parameter size, quantization, structured-output
  capability, host operating system, architecture, and logical CPU count.
- Memory fit, accelerator identity, GPU/VRAM fit, and active throughput remain
  explicitly `unmeasured` and belong to Increment 12 Model Lab.

The smoke exposed a stale repository virtual environment containing Nerve Center
`0.8.0` without `pip`. The source launcher now restores `pip` when needed, compares
the installed package version with `pyproject.toml`, and refreshes the editable
install before launch. This prevents a stale environment from silently starting an
older or incomplete API.

The API is lifecycle-owned by the desktop shell. It is available on
`127.0.0.1:8765` only while Nerve Center is running; choosing **Quit** stops the
managed API. See `refs/testing/source-launcher-and-ollama-smoke.md` for the exact
repeatable procedure.

## Next increment

Implement Increment 12, Model Lab:

1. Add active hardware-fit probes and model lifecycle/install policy.
2. Build the replay-eligibility and privacy contract for retained requests.
3. Add bounded exploration scheduling outside module priority.
4. Add historical request replay and blinded pairwise review.
5. Surface catalog, evidence, and exploration controls in a manager-owned Model Lab UI.
