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
- Opening location, company-presence location, and discovery-strategy market evidence remain separate concepts. A remote listing available in a region is not proof of a company office there, and an employer discovered by a local search does not make all of its national openings local yield.
- Fit analysis contract v6 remains responsibility/evidence-first and derives explicit `direct`, `adjacent`, `transferable`, or `mismatch` domain relationships. Listed title remains a weak clue, not a fit gate.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output work may retry once on `qwen2.5:7b-instruct`; Job Scout remains model-blind.
- The Windows source launcher validates a complete x64 Visual C++ environment before Tauri compilation and skips incomplete Visual Studio installations.
- `scripts/run_job_scout_live.py` remains the reusable real-run diagnostic.
- Coding-agent token conservation is a primary engineering concern. Use `scripts/agent_context.py` and progressive context loading instead of repository-wide rereads.

## Accepted Issue #43 behavior

Source-aware discovery quality is now part of the durable Job Scout contract:

- Query portfolios are bounded and allocated across materially different families and source paths rather than multiplying superficial rewrites.
- Initial hypothesis families include direct role, adjacent role, seniority variant, domain/capability, and employer archetype.
- Broad web, ordinary site search, and structured ATS x-ray paths compile differently according to retrieval capability.
- Greenhouse/Lever/Ashby-style x-ray strategies may defer geography to post-fetch structured evidence instead of wasting low-recall duplicate queries.
- Deterministic query linting rejects missing/catch-all anchors, contradictory exclusions, unsupported invented technologies/requirements, and other known bad structures before network spend.
- Company convergence from distinct strategies can raise company-revisit priority, but never alters opportunity fit. Opening convergence is retained for audit through existing source/job provenance and does not create duplicate score credit.
- Coverage gaps are explicit across role, domain/capability, seniority, geography, work arrangement, employer archetype, source coverage, and query-family coverage.
- Deterministic reflection targets those gaps first; manager-routed reflection receives the same bounded uncovered-space profile and proposed strategies still pass deterministic compilation before execution.
- Direct structured source revisits receive a one-time initial preference only when source health is unknown and needs first verification or is known healthy. Known degraded, challenged, or blocked sources do not get a bonus merely because they are structured.
- The discovery audit exposes hypothesis family, compiled query/source path, total and location-conditioned yield, warnings, overlap, coverage gaps, and before/after learned weight without creating an approval gate.
- Issue #40 location-conditioned yield and broad-retention semantics remain intact because the location-aware loop extends the source-aware loop rather than replacing it.

## Next implementation slice

Issue **#45: Normalize qualification importance in Job Scout fit scoring** is the next planned Job Scout slice.

The current analyzer selects up to eight decision-relevant job requirements/responsibilities and validates matches against persisted career evidence, but coverage still averages items equally within the broad `required`, `responsibility`, and `preferred` buckets. That can let several peripheral matches offset a missed central requirement too easily.

Implement as one coherent ranking-quality slice:

1. Represent job-side decision importance separately from candidate match strength and from the factual required/responsibility/preferred category.
2. Derive importance conservatively from explicit job language and bounded structured analysis, with deterministic normalization and no candidate-strength feedback loop.
3. Weight required and responsibility coverage by normalized decision importance; preferred items remain lower influence.
4. Deduplicate materially equivalent qualification phrasings so repeated bullets cannot manufacture fit.
5. Preserve explicit license/clearance gates as gates rather than turning ordinary weighted mismatches into hidden exclusions.
6. Expose weighted coverage inputs and rationale in score factors and version contracts as needed.
7. Add realistic ordering regressions where central evidence beats many peripheral matches while title weakness and domain ordering remain unchanged.

## Deferred follow-up

- Per-fetch request-budget admission/recovery hardening remains evidence-triggered if later live runs show batch-level overrun is operationally harmful.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.
- Firecrawl is not a core dependency while local parsing, caching, and source-health tracking cover the need.
- Do not export career prompts/traces to LangSmith by default.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond loop.
- Source-aware query portfolios, query linting, explicit coverage gaps, and convergence semantics from Issue #43.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary; domain ordering remains `direct > adjacent > transferable > mismatch`.
- Deterministic, explainable location semantics from Issue #40.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.

## Coding-agent reset path

For Issue #45, start with:

```powershell
python scripts/agent_context.py --focus "job scout qualification importance weighted required responsibility coverage dedup fit response scoring" --issue 45
```

Read the generated packet and Issue #45 first. Expand only to source/ref paths identified by the packet or direct implementation evidence. Do not reread repository history wholesale or re-derive accepted discovery, provider, scheduler, domain, or location decisions.

## Validation boundary

Run the required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites.

The Issue #43 closeout did not use a local live market run from the GitHub-connected environment. Before another long discovery run, a short local `scripts/run_job_scout_live.py` diagnostic remains useful to inspect real query diversity, gap targeting, overlap telemetry, and structured-source refresh choices; treat it as runtime observation, not permission to retune ranking without evidence.
