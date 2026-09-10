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
- Issue #40 location awareness is complete in PR #42. Raw opening locations now feed deterministic, explainable location classification; ranking engine v4 invalidates stale engine scores for deterministic refresh; location-seeded discovery learns from location-conditioned opening yield instead of all downstream company openings; legacy contaminated location yield is neutralized; and review exposes scope counts, filters, badges, and rationale without hiding distant retained candidates.
- Opening location, company-presence location, and discovery-strategy market evidence are separate concepts. A remote listing available in a region is not proof of a company office there, and an employer discovered by a local search does not make all of its national openings local yield.
- Fit analysis contract v6 remains responsibility/evidence-first and derives explicit `direct`, `adjacent`, `transferable`, or `mismatch` domain relationships. Listed title remains a weak clue, not a fit gate.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output work may retry once on `qwen2.5:7b-instruct`; Job Scout remains model-blind.
- The Windows source launcher validates a complete x64 Visual C++ environment before Tauri compilation and skips incomplete Visual Studio installations.
- `scripts/run_job_scout_live.py` remains the reusable real-run diagnostic.
- Coding-agent token conservation is a primary engineering concern. Use `scripts/agent_context.py` and progressive context loading instead of repository-wide rereads.

## Accepted Issue #40 behavior

Location awareness is now a first-class, deterministic product dimension:

- Persisted `location_text` and `locations` remain raw source truth and are interpreted against configured local/regional markets at score time.
- Direct local/regional listing evidence changes location scope and therefore practical response/value scoring with reconstructable source rationale.
- Ambiguous, nationwide, generic remote, mixed-country, and multi-location text does not manufacture false local certainty.
- Stale pre-v4 scores are refreshed through the normal scoring service while reusing the existing full fit analysis; review does not require a new LLM analysis merely because location scoring changed.
- Broad retention remains intact. Distant or unknown opportunities stay reviewable unless an explicit factual/user gate excludes them.
- Discovery-learning keeps total retained openings for observability but uses location-conditioned opening yield when a strategy carries a location dimension.
- Existing location-strategy opening counts created under the old attribution semantics are neutralized once so they can be relearned under the corrected contract.
- The UI defaults to all retained opportunities and provides explicit `local`, `regional`, `local + regional`, `distant`, and `unknown` audit views.

## Next implementation slice

Issue **#43: Add source-aware query portfolios and gap-driven reflection** is the next planned Job Scout slice.

The goal is to improve the information value of each discovery experiment without replacing company-first discovery, narrowing recall into title matching, or making the LLM the sole judge of search quality.

Implement as one coherent discovery-quality slice:

1. Compile bounded source-aware query portfolios rather than sending one universal query shape everywhere.
2. Generate materially different hypothesis families such as direct role/title family, adjacent role family, seniority variant, domain/capability angle, and employer-archetype angle.
3. Add deterministic query linting before network spend for self-defeating exclusions, catch-all title groups, invented constraints/technologies, duplicate constraints, and source-specific structures known to collapse recall.
4. Preserve cross-strategy overlap provenance. Convergence from distinct strategies should increase confidence that a company/source deserves deepening, not inflate opportunity fit or duplicate scoring credit.
5. Make coverage gaps first-class across role, domain, seniority, geography, work arrangement, employer archetype, and source coverage; feed that bounded gap profile into manager-routed reflection.
6. Prefer cheap authoritative structured refresh once a healthy direct Greenhouse, Lever, Ashby, sitemap, feed, or equivalent source is known, while broad search continues exploring unknown employers.
7. Expose strategy hypotheses, compiled queries, total/conditioned yield, warnings, overlap, coverage gaps, and weight changes for audit without requiring approval for normal unattended sessions.

## Deferred follow-up

- Per-fetch request-budget admission/recovery hardening remains available if later live evidence shows batch-level overrun is operationally harmful.
- Qualification-importance normalization and additional ranking-quality work remain valid after discovery-quality work is trustworthy.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.
- Firecrawl is not a core dependency while local parsing, caching, and source-health tracking cover the need.
- Do not export career prompts/traces to LangSmith by default.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond loop.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary; domain ordering remains `direct > adjacent > transferable > mismatch`.
- Deterministic, explainable location semantics from Issue #40.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.

## Coding-agent reset path

For Issue #43, start with:

```powershell
python scripts/agent_context.py --focus "job scout source aware query portfolio query lint coverage gaps reflection overlap structured refresh" --issue 43
```

Read the generated packet and Issue #43 first. Expand only to source/ref paths identified by the packet or direct implementation evidence. Do not reread repository history wholesale or re-derive accepted discovery, scoring, provider, scheduler, or location decisions.

## Validation boundary

Run the required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites. After deterministic validation is green, use the live runner for a short diagnostic to inspect query diversity, coverage gaps, structured-source refresh choices, overlap evidence, and strategy-yield telemetry before another long run.
