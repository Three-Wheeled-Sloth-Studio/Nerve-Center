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
- Job Scout is now an iterative market-research loop rather than a bounded one-shot search. The accepted loop remains `expand -> converge -> deepen -> reflect -> re-expand`, with discovery optimized for recall and ranking/scoring providing precision.
- Issue #34 is complete and merged through PR #36. Job Scout now performs bounded discovery waves, persists opportunities promptly, interleaves provisional and bounded full scoring during the active manager window, refreshes companies and due sources between waves, and continues after empty reflections until a real stop condition is reached.
- A 900-second live acceptance run completed 89 cycles across 20 waves, retained 121 opportunities from 49 companies and 70 career sources, created 212 provisional scores, completed 3/3 allowed full analyses, continued after both added and empty reflection outcomes, and stopped explicitly on request-budget exhaustion.
- Request accounting is still admitted at discovery-batch granularity. The live acceptance run reserved 500 requests and observed 502, exposing a two-request batch overrun. Per-fetch admission remains a hardening option if future evidence makes strict request ceilings necessary.
- Job Scout resolves aggregator-listed openings to actual hiring companies, protects employer-owned deepening from board-source crowding, persists strategy/yield learning, expands configured markets, and supports direct Greenhouse, Lever, and Ashby discovery.
- Fit analysis contract v6 validates model-proposed career-claim evidence through the reusable semantic matcher and derives explicit `direct`, `adjacent`, `transferable`, or `mismatch` domain relationships.
- Ranking engine v3 is responsibility/evidence-first. Listed title is only a weak +/-3 point clue. Required and preferred qualification evidence, responsibility coverage, domain relationship, freshness, source quality, and location evidence are intended to drive practical pursuit priority.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output work validates results and may retry once on `qwen2.5:7b-instruct`; the next general request returns to Gemma. Job Scout remains model-blind.
- Opportunity cards open HTTP(S) listings through the Tauri opener and expose the selected application/canonical URL for copying and QA.
- The source launcher now discovers and validates a complete x64 Visual C++ environment before Tauri compilation, skips incomplete Visual Studio installations, preserves an already valid developer shell, and fails with an actionable setup message when no complete toolchain is available. PR #39 passed CI and Windows packaging.
- `scripts/run_job_scout_live.py` is the reusable real-run diagnostic. It reattaches to actionable durable sessions, reports discovery/scoring milestones and stop state, and closes its adopted or created session before shutting down the managed API.
- Coding-agent context/token conservation is a primary engineering concern. `scripts/agent_context.py` generates a bounded reset packet from authoritative refs and git state so agents can load context progressively rather than rereading large unchanged documents.

## Active product correction

Issue **#40: Make Job Scout location-aware in scoring, discovery learning, and UI** is the next recommended implementation slice.

The latest live inventory exposed a location-data gap rather than a general discovery-liveness problem:

- raw opening location text is persisted, but current score records frequently retain location scope as `unknown` because listing locations are not normalized into the structured location evidence expected by scoring;
- the current inventory contains no Greensboro/Triad postings and only one wider-region posting, so local discovery effectiveness cannot currently be audited well;
- a location-seeded search can discover a national employer and then receive credit for all downstream career-site openings, even when those openings are distant, which can falsely reinforce an unproductive local-market strategy;
- UI review does not yet expose enough location scope, counts, or filtering to distinguish local, regional, remote, and distant inventory cleanly.

## Recommended next slice

Implement Issue #40 as one coherent location-awareness slice across persistence, scoring, discovery learning, and review UI:

1. Normalize persisted opening location text into deterministic, explainable structured evidence using configured labor-market context. Preserve raw source text and provenance.
2. Classify meaningful scopes such as local, regional, remote, and distant without hard-coding one city, employer, or title. Treat ambiguous or conflicting evidence explicitly rather than forcing certainty.
3. Recompute or backfill existing opportunity scores from deterministic location evidence without requiring another LLM analysis when fit evidence is already valid.
4. Separate total discovery yield from location-conditioned yield. A location-seeded strategy may receive general discovery credit for finding a useful employer, but it must not be learned as locally productive solely because later company deepening returned distant jobs.
5. Preserve exploration and broad retention. Location relevance should influence ranking and discovery allocation, not become a premature hard filter that hides otherwise valuable remote or adjacent-market opportunities.
6. Surface location scope, local/regional counts, and useful filtering or audit controls in the Job Scout UI so live-market behavior can be inspected directly.
7. Add deterministic repository and UI regressions proving local/regional evidence changes classification and ranking, existing openings can be rescored, distant deepening does not falsely reward a local strategy, and broad discovery remains intact.

Use the existing scoring-location contracts and configured market data before introducing new abstractions. Keep geography deterministic and explainable; do not ask the LLM to solve location normalization that can be derived from persisted source evidence and public/cached geographic data.

## Deferred follow-up

- Per-fetch request-budget admission/recovery hardening remains available if additional live evidence shows batch-level overrun is operationally harmful.
- Qualification-importance normalization and additional ranking-quality work remain valid after location evidence is trustworthy. Do not tune ranking weights to compensate for unknown or misclassified geography.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.

## Latest live evidence

- Post-fix 900-second Job Scout acceptance run: 89 cycles, 20 waves, 356 strategies attempted, 49 companies discovered, 70 career sources discovered, 121 opportunities retained, 212 provisional scores, and 3/3 bounded full scores.
- The run crossed both added and empty reflection outcomes and continued discovering afterward, then stopped `partial` with `requests_budget_exhausted` after 500 reserved/502 observed requests.
- A 20-role fit-analysis v6 sample completed 20/20 analyses on `gemma3:4b` with explicit domain results: 2 direct, 1 adjacent, 5 transferable, and 12 mismatch.
- Direct-employer listing locations already build durable company-presence evidence with source URLs, while generic remote/nationwide labels and aggregator-only evidence do not establish local employer presence. Issue #40 should connect opening-level location evidence to the same explainable location intent rather than replace that existing company-presence logic.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond loop.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary for fit; listed title is only a weak clue. Domain ordering remains `direct > adjacent > transferable > mismatch`.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.

## Coding-agent reset path

For Issue #40, start with:

```powershell
python scripts/agent_context.py --focus "job scout location evidence scoring discovery learning UI" --issue 40
```

Use the generated packet and Issue #40 first. Expand only to source/ref paths identified by the packet or direct implementation evidence. Likely relevant surfaces include scoring location classification/enrichment, Job Scout opportunity persistence and discovery-learning attribution, review/workspace API aggregation, and the desktop opportunity list/filter UI.

Do not reread repository history wholesale and do not re-derive accepted discovery, scoring, provider, or scheduler decisions.

## Validation boundary

Run the required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites. After deterministic validation is green, use the reusable live runner for a short local-market diagnostic to verify that location scope and location-conditioned strategy telemetry are visible and plausible before another long run.
