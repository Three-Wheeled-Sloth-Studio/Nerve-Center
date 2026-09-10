---
type: Roadmap
title: MVP Roadmap
description: Dependency-ordered implementation roadmap for the Nerve Center manager, module runtime, scheduling, queues, providers, and near-roadmap platform work.
status: stable
tags: [nerve-center, planning, roadmap]
---
# MVP Roadmap

> Product intent and non-negotiable boundaries are defined in `refs/planning/product-requirements-document.md`. This roadmap orders implementation; it does not redefine the product.

## Accepted baseline through 0.12.4

The repository contains a working local API, durable SQLite foundation, manager-owned scheduling and work queues, provider-neutral local LLM routing, the Job Scout reference workflow, a Tauri/React desktop shell, Windows packaging/runtime bootstrap, an iterative company-first discovery/scoring loop, and the first manager-owned Model Lab foundation.

The reusable manager/module boundary is established. Job Scout remains the reference module for validating those contracts. Model Lab now has its first durable local evaluation seams. The short real-world Job Scout acceptance run is complete; it exposed explicit-budget and local-discovery-learning work that must land before an unattended soak.

## Increment 7: Core and module boundary (implemented)

- Audit current schemas, services, API routes, UI surfaces, and storage for Job Scout entanglement.
- Define the versioned module manifest and compatibility contract.
- Define manager-owned versus module-owned configuration and storage.
- Define module permissions, package shape, UI contribution points, and migration boundaries.
- Move Job Scout-specific behavior behind the same contracts future modules will use.
- Preserve the accepted Windows package and startup-health baseline.

Implemented in `0.7.0`. The manager validates versioned manifests and task declarations, persists module lifecycle state, owns module storage roots, enforces pause state during run admission, and installs Job Scout through a module bootstrap adapter. The existing Job Scout tables retain their names for migration safety but have explicit module ownership.

## Increment 8: Module process runtime (implemented)

- Launch enabled modules as supervised child processes.
- Add scoped runtime tokens and a versioned loopback HTTP/event protocol.
- Provide run identity, window end, priority, queue limits, resource policy, and assigned data directory at launch.
- Add module heartbeat, lifecycle state, activity, backlog, queue-pressure, and degraded-state reporting.
- Support Enabled, Paused, and Not Installed lifecycle states.
- Add manager-rendered compact module cards and manager-owned module tabs.

Implemented in `0.8.0`. Job Scout task orchestration runs in a supervised managed-Python child process. The manager issues a per-launch scoped token, serves a versioned loopback protocol, delegates only registered module operations, and retains exclusive ownership of shared persistence and resource accounting.

## Increment 9: Session scheduler and wind-down (implemented)

- Make manager work sessions the primary scheduling unit.
- Support duration-based, fixed-time, and recurring wall-clock windows.
- Launch all enabled modules for a session.
- Add Open, Constrained, Draining, and Closed admission phases.
- Tell modules when remaining time and queue estimates no longer justify discovering new LLM-dependent work.
- Complete queued LLM work during normal graceful wind-down.
- Add explicit Emergency Stop.
- Restore active sessions after application or machine restart using the original wall-clock end.

Implemented in `0.9.0`. Durable manager work sessions own concrete wall-clock windows, enabled-module selection, normalized priority allocation, resource policy, module run IDs, and recurrence history. Restart recovery preserves the original end and missed recurrence windows are not replayed.

## Increment 10: Durable shared work queue (implemented)

- Add generic deterministic, network, LLM, human-review, and composite work classifications.
- Persist typed requests before acknowledgement.
- Add durable attempts, results, acknowledgements, redelivery, and idempotency keys.
- Enforce global and per-module soft and hard queue limits.
- Estimate each module's next-request wait and queue-clear time.
- Normalize enabled-module priorities to exactly 100 points.
- Order LLM work using module priority, request age, task priority, model suitability, and model-switch cost.
- Add progressively disclosed queue inspection, retry, cancellation, and reprioritization controls.

Implemented in `0.10.0`. The manager persists typed work requests before acknowledgement, records every claim as an attempt, retains results until module acknowledgement, and redelivers interrupted claims and unacknowledged results after restart. Module-scoped idempotency keys prevent duplicate admission and queue limits enforce backpressure.

## Increment 11: Provider-neutral LLM manager (implemented)

- Move every LLM invocation behind manager-owned provider adapters.
- Prohibit direct provider calls from modules.
- Define model-blind task requirements and structured result contracts.
- Add Ollama discovery and invocation as the first local runtime.
- Add capability, hardware-fit, performance, failure, retry, validation, and acceptance observations by task type.
- Add policy-driven retry and quality-tier escalation without exposing model names to modules.
- Preserve a cloud-provider abstraction with local-only as the default and bring-your-own credentials when enabled later.

Implemented in `0.11.0`. Production model calls pass through a manager-owned provider-neutral JSON contract. The manager discovers Ollama models, records durable task-specific outcome evidence, selects models without module-supplied identities, and validates structured outputs before delivery. Job Scout currently uses `gemma3:4b` as the primary general model with a bounded `qwen2.5:7b-instruct` strict-schema fallback while remaining model-blind.

## Job Scout reference-module foundation (implemented)

The self-improving discovery correction previously listed here is accepted implementation, primarily through Issues #18, #20, #22, #24, #26, #28, #30, #32, and #34.

Current accepted Job Scout behavior includes:

1. durable discovery-strategy identity, provenance, yield telemetry, learned influence, and an exploration floor;
2. companies as first-class durable discovery targets even when no current relevant opening exists;
3. company-first deepening into direct career pages, Greenhouse, Lever, Ashby, feeds, sitemaps, and other public employer surfaces;
4. cached local-market expansion from configured starting locations;
5. iterative `expand -> converge -> deepen -> reflect -> re-expand` execution across bounded waves;
6. prompt opportunity persistence plus provisional and bounded full scoring during the active manager window;
7. evidence-backed fit analysis where responsibilities/requirements and domain relationship dominate weak title clues;
8. explicit domain relationship ordering: `direct > adjacent > transferable > mismatch`;
9. manager-routed LLM reflection and scoring with modules remaining model-blind;
10. durable cooldown/revisit behavior, paced no-work handling, and attributable stop reasons;
11. reusable live-run diagnostics and compact coding-agent context generation.

PR #36 closed the major work-window liveness defect. A 900-second live acceptance run completed 89 cycles across 20 waves, retained 121 opportunities from 49 companies and 70 career sources, created 212 provisional scores, completed 3/3 bounded full analyses, and stopped explicitly on request-budget exhaustion after continuing through both added and empty reflection outcomes.

PR #39 hardened the Windows source launcher so ordinary PowerShell startup discovers and validates a complete x64 Visual C++ environment before Tauri compilation.

## Job Scout location-aware discovery and ranking (implemented)

Issue **#40: Make Job Scout location-aware in scoring, discovery learning, and UI** is implemented in PR #42.

Accepted behavior:

1. Persisted opening location text feeds deterministic, explainable classification using configured labor-market context while preserving raw source text and provenance.
2. Listing-location evidence, company-presence evidence, and discovery-strategy market evidence are separate concepts. A remote role available in a region does not establish a company office there, and employer discovery from a local query does not make every national opening local yield.
3. Ranking engine v4 invalidates stale pre-v4 scoring records for deterministic refresh while reusing valid full fit analysis; a location scoring change does not require another LLM fit pass.
4. Location-seeded strategy learning uses location-conditioned opening yield rather than all downstream employer openings. Total retained inventory remains visible as observability evidence.
5. Legacy location-strategy opening counts created under the old attribution semantics are neutralized so they can be relearned under the corrected contract.
6. Broad exploration and retention remain intact. Geography affects ranking, factual gates, and discovery allocation instead of silently hiding distant candidates before review.
7. Job Scout review exposes scored location scope, counts, filters, badges, and source-backed rationale.
8. Deterministic regression coverage includes local/regional evidence, generic remote, mixed-country, multi-location, state-only, and distant attribution cases.

Do not tune ranking weights to compensate for missing geography and do not add an LLM location classifier for evidence that can be derived deterministically. Query constraints are source capabilities, not universal syntax: structured ATS x-ray retrieval may intentionally omit geography when post-fetch location evidence is more authoritative, while local employer discovery and source-native search may still use geography directly.

## Job Scout source-aware discovery quality (implemented)

Issue **#43: Add source-aware query portfolios and gap-driven reflection** is implemented in PR #44.

Accepted behavior:

1. Search work is allocated across bounded materially different query families and source paths rather than superficial rewrites.
2. Public web, ordinary site search, and structured ATS x-ray strategies compile according to source capability.
3. Deterministic query linting rejects known self-defeating or unsupported structures before network spend.
4. Company/opening convergence is retained as discovery evidence and may affect deepening priority, but it never substitutes for fit scoring or creates duplicate score credit.
5. Coverage gaps are explicit across role, domain/capability, seniority, geography, work arrangement, employer archetype, source coverage, and query-family coverage.
6. Deterministic and manager-routed reflection receive the same bounded uncovered-space profile.
7. Healthy structured direct sources receive appropriate refresh preference after discovery without overriding source-health evidence.
8. The discovery audit exposes query family, compiled query/source path, total and location-conditioned yield, warnings, overlap, coverage gaps, and learned-weight changes without requiring approval for unattended work.

Preserve the local-first posture. Firecrawl is not a core dependency while local parsers/source health/caching cover the responsibility. Do not export career prompts or traces to LangSmith by default. A curated ATS-board catalog may be optional seed evidence but must never define market coverage.

## Job Scout qualification-importance ranking (implemented)

Issue **#45: Normalize qualification importance in Job Scout fit scoring** is implemented in PR #46.

Accepted behavior:

1. Fit-analysis contract v7 represents employer-side decision weight independently from broad qualification category and candidate match strength.
2. A bounded model centrality hint is advisory only; deterministic importance changes come from validated verbatim job excerpts, never model-authored requirement labels.
3. Explicit must/minimum/essential/core language can raise effective weight, while preferred/optional/nice-to-have language can lower it.
4. Required, responsibility, and preferred coverage use normalized weighted contributions rather than equal averaging.
5. Near-duplicate qualifications remain auditable but cannot manufacture repeated coverage, domain-evidence, or factual-gate credit.
6. Ordinary high-importance mismatches remain soft ranking evidence. Licenses, clearances, configured minimums, and other factual/user gates remain separate.
7. Ranking engine v5 exposes effective weight, rationale, duplicate linkage, counted status, match value, and weighted contribution for reconstruction.
8. Legacy v6 fit-analysis payloads remain loadable through neutral defaults and may be deterministically rescored without another LLM fit pass.

Calibration is intentionally bounded rather than nonlinear: central evidence should dominate a small set of peripheral bullets, but no single extracted item receives unlimited veto power unless an independent factual gate applies.

Per-fetch request-budget admission remains a possible Job Scout hardening follow-up if later live evidence shows batch-level overrun is operationally harmful. People enrichment remains deferred.

## Increment 12: Model Lab foundation (implemented)

Issue **#47: Add Model Lab foundation and local benchmark corpus** is implemented in PR #48.

The accepted provider-neutral manager remains the production authority. Model Lab extends those seams rather than creating a parallel provider stack.

Accepted foundation behavior:

1. Manager-owned Model Lab settings, benchmark corpus, exploration sessions, and benchmark results persist locally in additive schema v11.
2. Eligible completed model-blind requests/results can be harvested lazily and idempotently into a deduplicated local benchmark corpus, including after restart.
3. Corpus capture supports request-level and module-level opt-out and redacts credential-like retained values while preserving replay-critical schemas and provenance.
4. A benchmark item can be replayed against a selected installed model through a manager-owned exact-model experimental path.
5. Experimental benchmark outcomes are stored separately from production `TaskModelEvidence` and do not alter the production loaded-model state.
6. Exploration sessions are bounded by explicit duration and attempt ceilings.
7. Benchmark replay is refused while production LLM work is queued or claimed, preserving normal module precedence.
8. Read-only manager API/UI state exposes installed models, empirical production evidence, corpus state, exploration state, benchmark outcomes, and production queue state.
9. Model Lab remains local-first and deterministic CI does not require Ollama, GPUs, live models, cloud telemetry, or public benchmark scraping.

PR #48 exact head `8119e5cf577fa1f1d19ce8afe7fdbf4740ac864d` passed CI run `34502474954` / #250 with 192 Python tests and green desktop-web/desktop-rust jobs. Windows package run `34502474968` / #134 also passed packaged-backend health, Job Scout workspace and managed-runtime smoke, NSIS build, output verification, and artifact upload. PR #48 merged to `dev` as `fdca1c1075f3d1bfb2e8b79d7644abfa2fdbbed1`.

### Later Model Lab slices

- Enrich the model catalog with compatibility data and carefully sourced public benchmark/leaderboard evidence.
- Add policy-constrained automatic model installation and separately opt-in automatic removal.
- Add configurable exploration ceilings during contention and richer explicit exploration sessions.
- Reuse historical real requests for comparison across newly installed models.
- Add simple blinded pairwise A/B review using a Likert preference scale.
- Define evidence thresholds for when benchmark results may influence production routing; never promote a model from one experimental run.

## Job Scout explicit run budgets and convergent local learning (next slice)

Issue **#49: Run Job Scout short live acceptance before unattended soak** completed with useful blocking evidence. The valid run exited cleanly after about 21 minutes, completed 25/25 full scores, retained an inventory of 826 ranked opportunities, classified all of them as 34 regional and 792 distant, and preserved an explicit `requests_budget_exhausted` terminal reason. It did not complete the requested 30-minute observation window because `scripts/run_job_scout_live.py` submitted only the duration and silently inherited the platform default of 500 outbound requests and 100 LLM calls. The terminal discovery batch observed 515 requests against the capped 500-request ledger.

The run also confirmed that corrected location attribution is working: national openings were not credited as local yield and the Greensboro/Triad coverage gap remained open. However, 366 location-conditioned strategies retained zero location-conditioned openings, no directly local opening was found, and no unsuccessful strategy family reached a downweighted state during the run. Distinct query text currently fragments evidence enough that repeated zero-yield hypotheses do not converge quickly into a useful allocation correction.

Issue **#51: Make Job Scout run budgets explicit and local discovery learning converge** is the immediate implementation slice:

1. Expose `--max-requests` and `--max-llm-calls` in the live runner and persist them in the session resource policy.
2. Print and report the effective duration, request, LLM, and scoring ceilings before work starts; distinguish duration completion from budget exhaustion.
3. Admit requests before fetch execution, or otherwise eliminate the demonstrated batch-level overrun while retaining bounded concurrency.
4. Accumulate durable learning against a stable source/query/location hypothesis-family identity so superficial rewrites cannot reset evidence.
5. Reallocate effort after repeated zero local-opening yield while preserving bounded exploration and separately retaining useful employer/source discoveries.
6. Expose family-level attempts, yield, learned weight, and allocation evidence so self-correction is inspectable.

This correction must remain evidence-driven. Do not hard-code role, employer, city, or false-positive exclusion lists, and do not require a minimum local result count when the market evidence truthfully supports zero. Distant/national openings must remain separate from local-opening yield, while verified company/source evidence remains durable and useful.

After Issue #51 passes deterministic validation, rerun the 15-30 minute live gate with explicit resource ceilings. Proceed to a **4-8 hour unattended Job Scout soak** only when the full intended gate duration or its declared limiting budget is visible in advance, usage respects that declaration, and repeated unsuccessful location-conditioned families demonstrably affect subsequent allocation.

## Increment 13: Attention, safety, and connectors

- Add manager-owned Attention and Review queues.
- Let modules supply domain context, allowed dispositions, validation, and downstream meaning.
- Block only dependent workflow branches by default.
- Add morning summaries for completed, blocked, failed, degraded, and comparison work.
- Add install-time module permission review.
- Define public-read, authenticated-read, local-write, external-draft, and prohibited external-action classes.
- Allow authenticated read and non-public remote drafts only through explicit manager-owned connectors.
- Keep browser automation read-only for the initial product; defer form filling.

## Increment 14: Resource profiles, durability, and updates

- Add global resource defaults and per-session overrides for CPU, memory, GPU/VRAM, concurrency, queue depth, storage, network, exploration, and optional cloud spend.
- Add named reusable profiles such as Quiet, Balanced, Overnight, and Model Exploration.
- Add lightweight daily backups and pre-migration snapshots.
- Add compatibility-aware independent core and module updates.
- Support one global Stable or Development channel.
- Stage updates, drain active work, migrate, health-check, and roll back binaries when necessary.
- Apply staged updates on restart while preserving user and module data.

## Reference-module continuation

Job Scout remains the first reference module and should continue to improve when new evidence justifies it, but its domain roadmap is subordinate to the core boundary:

- resume and evidence-profile management remain module configuration;
- source policies and connectors remain module capabilities;
- discovery, normalization, scoring, application tracking, and review remain module-owned;
- Job Scout requests LLM work through the generic manager contract;
- Job Scout may not add domain-specific assumptions to core manager schemas or navigation.

A second substantially different module should be introduced early enough to validate that the contracts are truly generic rather than Job Scout with the labels filed off.

## Deferred increments

- Code signing and broad public distribution.
- Cross-platform packaging.
- Standalone or externally callable LLM router.
- Third-party and user-authored modules.
- Untrusted-module sandboxing and marketplace.
- Per-module update channels.
- Advanced staggered module schedules.
- Machine-idle, battery, metered-network, and active-user-sensitive scheduling.
- Automated form filling.
- Remote administration and headless workers.
- Multi-user or team support.
- Cloud synchronization and mobile access.

## Permanent non-goals

- Automated job applications.
- Automated outreach or email sending.
- Automated book, social-media, or website publishing.
- Purchases, acceptance of legal terms, or unattended external-account changes.
- Any module bypass of the manager-owned LLM boundary.
- Domain-specific reference-module logic embedded in the core manager.
- User data or credentials stored in the public source repository.
