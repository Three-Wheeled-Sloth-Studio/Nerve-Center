---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch.
- After merging a topic branch, switch the active checkout back to `dev`, update it to the accepted
  merge commit, and continue work there rather than remaining on the merged branch.
- Current application version on this documentation checkpoint is `0.12.4`.
- The latest accepted implementation checkpoint makes Job Scout scans scheduler-ready and includes the compact single-module workspace, resume/configuration cleanup, source discovery, provisional scoring, and provider-neutral manager runtime.
- Earlier accepted checkpoints cover module contracts, durable runs, child-process supervision, work sessions, durable shared work queues, provider-neutral local LLM support, career evidence, job discovery, scoring, application tracking, Tauri desktop review, and Windows packaging/runtime bootstrap.
- Nerve Center has adopted the Agent Academy OKF v0.2-compatible refs harness non-destructively. Existing Nerve Center planning and engineering documents remain authoritative; generated indexes are discovery surfaces only.
- Historical checkpoint detail remains in the sibling files under `refs/handoffs/`.

## Active product correction

Job Scout's current discovery behavior is materially too shallow for the intended product. The next implementation priority is not another board connector in isolation; it is the self-improving discovery loop defined in `refs/planning/job-scout-discovery-and-learning-contract.md`.

The accepted behavioral model is:

`expand -> converge -> deepen -> reflect -> expand again`

Job Scout should keep discovering while its authorized Nerve Center session remains open, explore liberally, focus more effort on strategies that produce useful signal, investigate promising companies deeply through their own career surfaces, and deliberately ideate on new search paths when marginal discovery falls.

There is no minimum job-count acceptance criterion. Coverage, useful market intelligence, and evidence that discovery actually searched broadly and deeply are the acceptance criteria.

The latest Job Scout live-quality slice resolves aggregator-listed openings to their actual hiring
companies, preserves corrected company identity during persistence, prevents board listing sources
from crowding out employer-owned deepening, and guarantees capacity for company-revisit strategies.
The manager can prefer `gemma3:4b` exclusively when configured, adapts Pydantic schemas to Ollama's
reliable structured-output subset, and retries one malformed same-model response with a bounded
repair request. Fit analysis now records contract/model provenance, validates job excerpts and claim
identifiers, caps unsupported scores, and retains a deterministic provisional fallback.

A bounded real run expanded the persisted market from one apparent aggregator company to dozens of
actual hiring-company identities and resolved employer career surfaces without allowing challenged
sources to stop the wider cycle. The remaining quality gap is ranking discrimination: current local
model analyses often find no defensible claim matches, leaving adjacent roles tied at conservative
scores. Continue by improving evidence matching and role relevance, refreshing current-contract
scores, and deepening healthy employer-owned sources into direct postings.

The follow-up hardening checkpoint makes preferred-model routing strict when fallback is disabled,
rejects weak social/job-board `sameAs` hints as employer domains, disambiguates same-name unresolved
employers when a stable organization hint exists, and makes the live runner consume the canonical
fit-analysis contract version. Coding-agent context conservation is now an explicit operating rule:
use the file map, targeted reads/searches, deterministic diagnostics, reusable tools, and durable
handoffs instead of repeatedly rediscovering unchanged state.

Fit intent is now explicit: listed titles are weak clues rather than gates. Job Scout should compare
actual responsibilities and requirements against verified experience, and domain relationship should
rank direct domain match above adjacent domain, transferable experience, and domain/skill mismatch.
The current scorer includes a model-produced domain component, but the reusable evidence-backed
domain-distance model/taxonomy is not implemented yet; treat it as part of the next ranking-quality
slice rather than assuming current `domain_score` provides that distinction.

## Immediate implementation slice

Implement the smallest coherent foundation that changes Job Scout from bounded querying into a persistent discovery engine:

1. Durable discovery-strategy identity and yield telemetry.
2. Company-first discovery and durable monitoring, including plausible employers with zero current relevant openings.
3. Cheap local-market expansion from the configured starting location using public geographic reference data and learned location aliases.
4. Iterative expand/converge/deepen/reflect orchestration during the existing manager-owned wall-clock session.
5. Transparent learned weighting with positive, deprioritized, and negative signals plus an exploration floor.
6. Session coverage metrics that show strategies attempted, results examined, companies/career sites discovered, postings inspected, opportunities retained, strategy changes, reflection hypotheses, and provider warnings.
7. Manager-routed LLM ideation only where deterministic expansion has reached diminishing returns.

Do not add people enrichment yet. Preserve a clean future seam for public person/contact references and a possible Farley File integration, but do not build a CRM inside Job Scout.

## Architectural constraints

- Keep all Job Scout discovery semantics inside the Job Scout module boundary.
- Do not add job-specific behavior to Nerve Center core schemas, navigation, scheduling, or provider policy.
- Modules remain model-blind and may not call Ollama or any other provider directly.
- Preserve the existing public-source safety boundary: no authenticated LinkedIn crawling, no CAPTCHA circumvention, no stealth browser automation, and no unattended outreach or application submission.
- Discovery should optimize recall; opportunity scoring and user feedback provide precision.
- User feedback must retain enough provenance to affect discovery allocation separately from opportunity ranking.
- A source challenge or throttle should cool that path down without ending the whole discovery cycle when other safe strategies remain.

## Read before implementation

1. `AGENTS.md`
2. `refs/README.md`
3. `refs/project.yaml`
4. `refs/handoffs/currentHandoff.md`
5. `refs/handoffs/next-dev-prompt.md`
6. `refs/planning/product-requirements-document.md`
7. `refs/planning/job-scout-discovery-and-learning-contract.md`
8. `refs/planning/job-scout-scoring-contract.md`
9. `refs/planning/module-package-contract.md`
10. `refs/research/search-source-strategy.md`
11. `refs/testing/validationCommands.yaml`

## Validation boundary

Before promotion, run the commands in `refs/testing/validationCommands.yaml`, including generated-index checks and the tracked-path case-collision guard, plus the existing Python, React/TypeScript, Rust/Tauri, and Windows packaging gates where applicable.

For discovery changes, add deterministic synthetic coverage around strategy weighting, company deepening, local-market expansion, diminishing-return/reflection transitions, provider cooldown isolation, and restart-safe persistence. Do not depend on live public sites for required CI.
