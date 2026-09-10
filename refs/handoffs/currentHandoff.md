---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch; return the active checkout to `dev` after merging a topic branch.
- Application version remains `0.12.4`.
- The manager/module boundary, durable work sessions and queue, provider-neutral LLM manager, Windows desktop/package baseline, career evidence profile, company-first Job Scout discovery, scoring, application tracking, and durable discovery learning are accepted foundations.
- Job Scout remains an iterative market-research loop: `expand -> converge -> deepen -> reflect -> re-expand`. Discovery optimizes recall; ranking/scoring provides precision.
- Issue #34 continuous-work/liveness is complete. The accepted 900-second run completed 89 cycles across 20 waves, retained 121 opportunities from 49 companies and 70 career sources, created 212 provisional scores, completed 3/3 bounded full analyses, continued through added and empty reflections, and stopped explicitly on request-budget exhaustion.
- Issue #40 location awareness is complete in PR #42. Raw opening locations feed deterministic, explainable location classification; ranking engine v4 refreshes stale deterministic scores; location-seeded discovery learns from location-conditioned opening yield; and review exposes scope counts, filters, badges, and rationale without hiding distant retained candidates.
- Issue #43 source-aware discovery quality is complete in PR #44. Job Scout compiles bounded materially distinct query families by source capability, lints invalid search structures before request spend, tracks company/opening convergence separately from fit, computes explicit coverage gaps for reflection, prefers eligible structured refresh paths, and exposes a read-only discovery audit.
- Issue #45 qualification importance is implemented in PR #46. Fit-analysis v7 separates employer-side decision weight from candidate match strength, ranking v5 uses deterministic weighted coverage, near-duplicate qualifications cannot manufacture repeated fit/domain/gate credit, and old v6 analyses remain loadable for deterministic rescoring without another LLM pass.
- Opening location, company-presence location, and discovery-strategy market evidence remain separate concepts. A remote listing available in a region is not proof of a company office there, and an employer discovered by a local search does not make all of its national openings local yield.
- Fit analysis remains responsibility/evidence-first and derives explicit `direct`, `adjacent`, `transferable`, or `mismatch` domain relationships. Listed title remains a weak clue, not a fit gate.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output work may retry once on `qwen2.5:7b-instruct`; modules remain model-blind.
- The provider layer already persists discovered model metadata plus task-specific success, schema-validity, latency, and acceptance observations. Those are the accepted seams for the next manager-owned Model Lab slice.
- The Windows source launcher validates a complete x64 Visual C++ environment before Tauri compilation and skips incomplete Visual Studio installations.
- `scripts/run_job_scout_live.py` remains the reusable real-run diagnostic.
- Coding-agent token conservation is a primary engineering concern. Use `scripts/agent_context.py` and progressive context loading instead of repository-wide rereads.

## Accepted Issue #45 behavior

Qualification importance is now part of the durable Job Scout scoring contract:

- Fit-analysis contract v7 may return a bounded `decision_weight_hint`, but that hint describes employer-side screening or role centrality only. Candidate match strength may not raise or lower importance.
- Deterministic importance cues are read only from the validated verbatim job excerpt. A model-authored requirement label cannot manufacture words such as `critical`, `required`, or `must` and influence its own weight.
- Model hints are conservatively bounded. Explicit must/minimum/essential/core language can raise effective weight; explicit optional/preferred/nice-to-have language can lower it.
- Required, responsibility, and preferred coverage use weighted match contributions instead of equal averaging within each bucket.
- Near-duplicate qualifications remain persisted for audit but link to one representative and do not receive repeated coverage credit.
- Duplicate qualification evidence is excluded from domain aggregation, and duplicate factual gate copies cannot emit repeated license/clearance exclusions.
- Factual gates remain separate from soft importance weighting. A high-importance ordinary mismatch can lower ranking but cannot silently become a hard exclusion.
- Ranking engine v5 exposes per-qualification match value, effective decision weight, rationale, duplicate linkage, counted status, and weighted contribution so fit remains reconstructable.
- Existing v6 fit payloads load with neutral defaults and can be deterministically reinterpreted by ranking v5 without forcing another LLM fit analysis.
- Calibration remains intentionally conservative: central evidence should outrank a small set of peripheral bullets, but the implementation does not add arbitrary nonlinear rules making one item overpower unlimited contrary evidence.

## Next implementation slice

Issue **#47: Add Model Lab foundation and local benchmark corpus** is the next manager-roadmap slice.

The accepted provider-neutral LLM manager already discovers local models, persists model metadata, records task-specific success/schema/latency/acceptance evidence, and keeps modules model-blind. The next step is to turn those seams into a manager-owned evaluation subsystem without changing production routing policy or adding automatic model management yet.

Implement as one bounded foundation slice:

1. Add a toggleable manager-owned Model Lab service/API contract over the existing model catalog and task evidence.
2. Persist deduplicated, privacy-safe benchmark-corpus records for eligible completed model-blind requests/results, with explicit module/request opt-out.
3. Replay a bounded benchmark item against a selected installed model through the manager-owned provider boundary.
4. Persist experimental benchmark attempts/results separately from production `TaskModelEvidence` so experiments cannot silently bias ordinary model selection.
5. Add an explicit exploration-session budget/window outside module priority; normal module work keeps precedence.
6. Expose read-only Model Lab UI state for installed models, empirical task evidence, corpus eligibility/counts, and benchmark outcomes.
7. Keep benchmark prompts/results local by default and do not add automatic installation/removal, cloud telemetry, or public benchmark scraping in this slice.

## Deferred follow-up

- Automatic model installation and separately opt-in automatic removal belong to later Model Lab slices.
- External/public benchmark ingestion and blinded pairwise A/B review remain later Model Lab work.
- Per-fetch request-budget admission/recovery hardening remains evidence-triggered if later live Job Scout runs show batch-level overrun is operationally harmful.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.
- Firecrawl is not a core dependency while local parsing, caching, and source-health tracking cover the need.
- Do not export career prompts, benchmark prompts, results, or traces to LangSmith by default.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond loop.
- Source-aware query portfolios, query linting, explicit coverage gaps, and convergence semantics from Issue #43.
- Qualification-importance semantics from Issue #45: employer-side weight is independent of candidate fit, duplicates cannot inflate evidence, and factual gates remain separate.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary; domain ordering remains `direct > adjacent > transferable > mismatch`.
- Deterministic, explainable location semantics from Issue #40.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.

## Coding-agent reset path

For Issue #47, start with:

```powershell
python scripts/agent_context.py --focus "model lab local benchmark corpus provider model evidence exploration sessions" --issue 47
```

Read the generated packet and Issue #47 first. Expand only to source/ref paths identified by the packet or direct implementation evidence. In particular, inspect the existing provider manager, provider persistence, shared queue/session contracts, and manager API/UI seams before introducing new abstractions. Do not reread repository history wholesale.

## Validation boundary

Run the required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, network model catalogs, live job boards, and mutable career sites. Full CI and Windows packaging must be green on the exact PR head before merge.

Before another long Job Scout market run, a short local `scripts/run_job_scout_live.py` diagnostic remains useful to inspect real query diversity, gap targeting, overlap telemetry, and structured-source refresh choices. That observation is independent of Model Lab work and should not trigger ranking retuning without evidence.
