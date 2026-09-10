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

The repository contains a working local API, durable SQLite foundation, manager-owned scheduling and work queues, provider-neutral local LLM routing, the Job Scout reference workflow, a Tauri/React desktop shell, Windows packaging/runtime bootstrap, and an iterative company-first discovery/scoring loop.

The reusable manager/module boundary is established. Job Scout remains the reference module for validating those contracts while its domain behavior continues to mature.

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

The self-improving discovery correction previously listed here is now accepted implementation, primarily through Issues #18, #20, #22, #24, #26, #28, #30, #32, and #34.

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

## Immediate Job Scout correction: location-aware discovery and ranking

Issue **#40: Make Job Scout location-aware in scoring, discovery learning, and UI** is the immediate reference-module priority before returning attention to the next core increment.

The latest live inventory shows that opening location text is persisted but not consistently normalized into the structured location evidence used by scoring. Recent scores therefore retain `unknown` location scope too often. Location-seeded strategies can also receive credit for distant openings found later while deepening national employers, making weak local search paths appear more productive than they are.

Required sequence:

1. Normalize persisted opening location text into deterministic, explainable evidence using configured labor-market context while preserving raw source text and provenance.
2. Classify useful local, regional, remote, distant, and uncertain scopes without hard-coded employer, title, or city rules.
3. Backfill or rescore existing opportunities from deterministic location evidence without another LLM fit analysis when existing fit evidence remains valid.
4. Separate total discovery yield from location-conditioned yield. A location-seeded strategy may receive general credit for discovering an employer, but distant openings found during later company deepening must not count as local yield.
5. Preserve broad exploration and candidate retention. Geography should guide discovery allocation and ranking rather than become a hidden hard filter.
6. Expose location scope, local/regional counts, and useful audit/filter controls in the Job Scout UI.
7. Add deterministic backend/UI regressions and validate the behavior with a short local-market live diagnostic.

Do not tune ranking weights to compensate for missing geography and do not add an LLM location classifier for evidence that can be derived deterministically.

Per-fetch request-budget admission remains a possible hardening follow-up if later evidence shows batch-level overrun is operationally harmful. Qualification-importance normalization remains a ranking-quality follow-up after location evidence is trustworthy.

## Increment 12: Model Lab

- Add a manager-owned, toggleable Model Lab subsystem outside module priority.
- Maintain a model catalog seeded by Ollama metadata, compatibility data, and relevant public benchmarks or leaderboards.
- Add policy-constrained automatic model installation and separate opt-in automatic removal.
- Retain eligible real requests as a local benchmark corpus by default, with user and module opt-out.
- Reserve a configurable 5-10% exploration ceiling during contention while freely using otherwise idle compute.
- Add explicit exploration sessions such as `Explore models for four hours.`
- Reuse historical real requests for comparison.
- Add simple blinded pairwise A/B review using a Likert preference scale.

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

Job Scout remains the first reference module and should continue to improve, but its domain roadmap is subordinate to the core boundary:

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
