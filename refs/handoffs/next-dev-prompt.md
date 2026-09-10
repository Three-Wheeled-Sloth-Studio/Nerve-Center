---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the first bounded Model Lab and local benchmark-corpus slice.
status: stable
tags: [nerve-center, handoff, model-lab, providers, benchmarks]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch using normal issue -> branch -> implementation -> tests -> PR -> CI -> merge discipline.

The immediate tracking issue is **#47: Add Model Lab foundation and local benchmark corpus**.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "model lab local benchmark corpus provider model evidence exploration sessions" --issue 47
```

Treat that generated packet as the initial orientation. Read Issue #47 and only the code/docs identified by the packet or direct implementation evidence.

## Current accepted baseline

Issues #34, #40, #43, and #45 are complete. Preserve:

- manager-owned provider/session/queue boundaries and module model blindness;
- durable provider model catalog plus task-specific success, schema-validity, latency, and acceptance observations;
- provider-neutral model-blind request contracts;
- Job Scout `expand -> converge -> deepen -> reflect -> re-expand` behavior;
- company-first source deepening and durable discovery learning;
- source-aware bounded query portfolios and deterministic pre-request query linting;
- explicit discovery coverage gaps and gap-driven reflection;
- convergence provenance affecting company/source deepening, never opportunity fit truth;
- broad opportunity retention with ranking providing precision;
- responsibility/requirement-first fit with title as a weak clue;
- explicit `direct > adjacent > transferable > mismatch` domain relationship;
- deterministic location scope from raw listing evidence and configured markets;
- fit-analysis v7 employer-side decision weighting independent of candidate match strength;
- ranking v5 weighted qualification coverage with duplicate-credit suppression and reconstructable factors;
- factual license/clearance gates remaining separate from soft weighted mismatches.

Do not reopen these without new evidence.

## Problem to solve

The provider-neutral LLM manager already contains most of the raw evidence needed for a Model Lab: installed-model discovery, durable model metadata, production task observations, manager-owned selection, schema validation, and request/result metadata.

What is missing is an explicit manager-owned evaluation subsystem. Today there is no durable privacy-safe corpus of eligible real requests, no isolated benchmark-result history, no bounded way to replay the same request across models, and no exploration-session contract that keeps experimental work separate from production routing evidence and module priority.

The first Model Lab slice should establish those seams without jumping ahead to automatic model installation/removal or external benchmark ingestion.

## Implementation objective

Implement the smallest coherent Model Lab foundation:

1. Add a manager-owned, toggleable Model Lab service/API contract over the existing model catalog and task evidence.
2. Add a durable benchmark-corpus record for eligible completed model-blind requests/results. Preserve task, module, contract, schema, and provenance needed for replay while avoiding credentials, provider secrets, and unrelated runtime state.
3. Make corpus capture deduplicated and opt-out capable at the module/request level.
4. Support bounded replay of one corpus item against a selected installed model through a manager-owned experimental provider path. A module still cannot select a production model.
5. Persist benchmark attempts/results separately from production `TaskModelEvidence`. Experimental success or failure must not silently change ordinary routing.
6. Add an explicit exploration-session budget/window outside module priority. Exploration may use otherwise idle capacity but cannot preempt higher-priority normal module work.
7. Expose a minimal read-only desktop/API surface for installed models, empirical production evidence, corpus size/eligibility, exploration state, and benchmark outcomes.
8. Keep all corpus and benchmark data local by default.

## Constraints

- Model Lab belongs to the manager/core, not Job Scout.
- Modules remain model-blind in production.
- Do not create a second provider manager or duplicate the accepted model catalog.
- Production task evidence and experimental benchmark evidence must remain distinguishable and independently queryable.
- Do not add automatic model installation or removal in this slice.
- Do not add external tracing, cloud telemetry, or public benchmark scraping as a release dependency.
- Do not persist credentials, authorization headers, provider secrets, or unrelated user data in benchmark records.
- Disabled Model Lab state must admit no experimental work while ordinary provider routing continues unchanged.
- Model Lab exploration cannot consume module priority or silently delay admitted higher-priority module work.
- CI must be deterministic and independent of Ollama, GPUs, the network, or live models.

## Deterministic acceptance tests

Add focused regressions proving that:

1. the existing discovered model catalog and production task evidence are available through the Model Lab read contract;
2. one eligible completed model-blind request creates one deduplicated corpus item;
3. an opted-out module/request creates no corpus item;
4. corpus records preserve replay-critical task/module/contract/schema provenance without credentials or unrelated runtime secrets;
5. benchmark replay against a deterministic provider fixture persists an experimental result;
6. benchmark replay does not update production `TaskModelEvidence` or alter normal candidate ranking;
7. disabled Model Lab state admits no benchmark/exploration work;
8. exploration admission stops at its explicit budget/window and does not preempt higher-priority normal work;
9. restart/reload preserves corpus and benchmark history;
10. read-only API/UI state reconstructs model metadata, production evidence, corpus counts/eligibility, exploration state, and benchmark outcomes;
11. existing provider, queue, session, Job Scout, desktop, and Windows-package regressions remain green.

## Likely code surface

Use the generated packet first, but expect targeted reads around:

- `src/nerve_center/providers/manager.py`;
- `src/nerve_center/providers/base.py`;
- `src/nerve_center/persistence/providers.py` and provider/model persistence schemas;
- manager queue/session admission and resource-policy code;
- manager API routes and desktop manager-owned navigation/state;
- provider and queue/session deterministic fixtures.

Prefer extending the existing provider evidence and shared scheduling contracts over introducing parallel Model Lab-only infrastructure.

## Explicitly deferred from Issue #47

- policy-driven automatic model installation;
- automatic model removal;
- external/public benchmark and leaderboard ingestion;
- blinded pairwise human A/B review beyond any minimal persistence seam needed now;
- automatic production-router promotion based on benchmark results;
- cross-machine or headless Model Lab workers.

## Validation

Run `refs/testing/validationCommands.yaml`. Full CI and Windows packaging must be green on the exact PR head before merge.

No live Ollama run is required for CI acceptance. A later local manual diagnostic may exercise the Model Lab against installed models, but deterministic provider fixtures are the release gate for this slice.
