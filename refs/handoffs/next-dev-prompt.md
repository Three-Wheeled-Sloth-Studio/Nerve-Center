---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for continuing Job Scout location-aware discovery and ranking from the current Nerve Center dev baseline.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, scoring, location]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch using normal issue -> branch -> implementation -> tests -> PR -> CI -> merge discipline.

The immediate tracking issue is **#40: Make Job Scout location-aware in scoring, discovery learning, and UI**.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout location evidence scoring discovery learning UI" --issue 40
```

Treat that generated packet as the initial orientation. Read Issue #40 and then only the code/docs identified by the packet or direct implementation evidence. Do not re-derive accepted architecture decisions.

## Current accepted baseline

Issue #34 is complete and merged through PR #36. Job Scout now remains productive through bounded discovery/scoring/reflection waves while manager admission and budget remain available. An empty reflection is not success; scoring occurs during the active work window; company/source revisit cooldowns persist across restarts; and terminal reasons are explicit.

A 900-second live validation completed 89 cycles across 20 waves, retained 121 opportunities from 49 companies and 70 career sources, created 212 provisional scores, completed 3/3 bounded full analyses, crossed both added and empty reflection outcomes, and stopped explicitly on request-budget exhaustion.

Fit analysis v6 and ranking engine v3 are also accepted. Responsibility and requirement evidence is primary, title influence is weak, and domain relationship is explicitly `direct > adjacent > transferable > mismatch`.

The Windows source launcher fix in PR #39 is merged and validated. It discovers a complete x64 Visual C++ environment, skips incomplete Visual Studio installations, and preserves an already valid developer shell.

Do not reopen those areas without new evidence.

## Observed location problem

The current live inventory exposed a geography-specific quality gap:

- opening records retain raw location text, but recent score records commonly persist location scope as `unknown` because opening locations are not normalized into the structured evidence used by scoring;
- the current inventory contains no Greensboro/Triad postings and only one wider-region posting, making local-market effectiveness difficult to audit;
- location-seeded discovery strategies can receive credit for distant roles found later while deepening a national employer, so a weak local search can look productive;
- the Job Scout UI does not yet make local/regional/remote/distant inventory easy to inspect or filter.

This is a data attribution and product-observability problem, not a reason to narrow discovery aggressively.

## Implementation objective

Implement the smallest coherent location-awareness correction across scoring, discovery learning, persistence, and review UI.

Expected shape:

- derive deterministic structured location evidence from persisted opening location text plus configured labor-market context;
- preserve raw source text, evidence provenance, uncertainty, and conflicting signals;
- classify useful location scope without hard-coded employer/title/city rules;
- reuse existing company-presence and scoring-location concepts where possible instead of creating a parallel geography model;
- allow existing opportunities to be backfilled/rescored from deterministic location evidence without requiring another LLM fit analysis when the existing fit analysis remains valid;
- distinguish total discovery yield from location-conditioned yield so a location-seeded strategy is not rewarded as locally productive solely because later employer deepening finds distant roles;
- preserve broad candidate retention and exploration, including useful remote and adjacent-market roles;
- expose location scope and useful local/regional counts or filters in the Job Scout UI;
- make location classification and strategy attribution inspectable in persisted factors/checkpoints where practical;
- keep Job Scout model-blind and keep deterministic geography outside the LLM.

## Deterministic acceptance tests

Add focused regressions proving that:

1. a direct local or regional listing location produces structured location evidence with provenance and changes scope/ranking appropriately;
2. ambiguous, nationwide, generic remote, or conflicting location text does not manufacture false local certainty;
3. existing persisted openings can be rescored/backfilled into meaningful location scopes without another LLM call when fit evidence is unchanged;
4. a location-seeded public search can receive general discovery credit for finding a useful employer, but distant jobs found later through company deepening do not count as local yield for that seed strategy;
5. location-conditioned learning still preserves an exploration floor and does not prevent broad opportunity persistence;
6. UI aggregation exposes useful location scope/count/filter behavior and does not hide otherwise eligible roles;
7. score explanations remain reconstructable and source-backed.

## Constraints

- No authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.
- Do not add an LLM geography classifier for evidence that can be derived deterministically.
- Do not tune ranking weights to mask missing location normalization.
- Do not collapse discovery-learning and opportunity-ranking feedback into one signal.
- Do not introduce Greensboro-specific production logic; configured markets must drive behavior generically.
- Keep CI deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites.
- Request-budget accounting remains batch-granular for now. Only pull per-fetch budget hardening into this slice if implementation evidence shows the two concerns are inseparable.
- Qualification-importance normalization remains a later ranking-quality slice after location evidence is trustworthy.

## Likely code surface

Use the packet first, but expect targeted reads around:

- scoring location classification/enrichment and score factor construction;
- Job Scout opening persistence and review aggregation;
- discovery strategy/yield persistence and attribution;
- configured market expansion/context;
- Job Scout workspace/review API models;
- desktop opportunity list, details, counts, and filters;
- existing tests for scoring location behavior, discovery learning, and workspace/review UI.

Prefer extending existing contracts over adding a second location taxonomy.

## Validation

Run the commands in `refs/testing/validationCommands.yaml`. After deterministic CI is green, run a short local Job Scout diagnostic and verify that local/regional/distant scope counts and location-conditioned discovery telemetry are plausible before another long-duration run.
