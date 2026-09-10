---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the next Job Scout source-aware discovery-quality slice.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, search]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch using normal issue -> branch -> implementation -> tests -> PR -> CI -> merge discipline.

The immediate tracking issue is **#43: Add source-aware query portfolios and gap-driven reflection**.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout source aware query portfolio query lint coverage gaps reflection overlap structured refresh" --issue 43
```

Treat that generated packet as the initial orientation. Read Issue #43 and only the code/docs identified by the packet or direct implementation evidence.

## Current accepted baseline

Issue #34 continuous discovery/liveness and Issue #40 location awareness are complete. Preserve:

- `expand -> converge -> deepen -> reflect -> re-expand`;
- company-first source deepening and durable discovery learning;
- broad opportunity retention with ranking providing precision;
- responsibility/requirement-first fit with title as a weak clue;
- explicit `direct > adjacent > transferable > mismatch` domain relationship;
- deterministic location scope from raw listing evidence and configured markets;
- separate opening-location, company-presence, and discovery-market evidence;
- location-conditioned yield for location-seeded strategies;
- manager-owned provider/session/queue boundaries and Job Scout model blindness;
- the exploration floor and durable revisit/cooldown behavior.

Do not reopen these without new evidence.

## Problem to solve

Current discovery can generate and execute useful strategies, but query construction is still too close to a universal search shape. That spends requests on queries that may be redundant, poorly matched to a source's retrieval capabilities, or aimed at dimensions already well covered. Reflection has durable evidence but needs a clearer deterministic statement of what remains uncovered.

The next improvement is not "more queries." It is a smaller set of materially different, source-appropriate experiments whose information gain can be inspected and learned from.

## Implementation objective

Implement the smallest coherent source-aware discovery-quality correction:

1. Model source/search-path retrieval capabilities sufficiently to compile source-appropriate queries rather than one universal query grammar.
2. Generate a bounded portfolio of materially different search hypotheses when applicable, including at least direct role/title family, adjacent role family, seniority variant, domain/capability angle, and employer-archetype angle.
3. Add deterministic preflight linting that rejects or repairs known self-defeating structures before network spend: contradictory exclusions, catch-all title groups, duplicated constraints, invented technologies/requirements, and source-specific syntax known to collapse recall.
4. Preserve provenance when materially different strategies converge on the same employer/opening. Use convergence to prioritize company/source deepening, not to inflate fit truth or duplicate opportunity score credit.
5. Compute a bounded coverage-gap profile from requested versus observed role, domain, seniority, geography, work arrangement, employer archetype, and source coverage. Feed explicit uncovered dimensions into manager-routed reflection.
6. Once a healthy authoritative direct source is known, prefer its cheapest structured recurring refresh path while broad public search continues exploring unknown employers and sources.
7. Add human-visible strategy audit data for hypothesis family, compiled query, source/path, total and conditioned yield, warnings, overlap evidence, coverage gaps, and learned weight changes. Ordinary unattended sessions must remain autonomous.

## Constraints

- Do not turn title matching into the primary fit/discovery truth.
- Do not collapse discovery-learning and opportunity-ranking feedback loops.
- Do not make an LLM the sole query-quality gate. Deterministic invalid structures may block; subjective evaluation is advisory.
- Keep manager-routed LLM calls bounded and Job Scout model-blind.
- Do not add Firecrawl as a core dependency while existing local parsing/caching/source-health infrastructure covers the responsibility.
- Do not export career prompts or traces to LangSmith by default.
- A curated ATS-board catalog may be optional seed evidence only, never authoritative market coverage.
- No authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.
- Keep CI deterministic and independent of live search providers, mutable career sites, Ollama, and GPUs.

## Deterministic acceptance tests

Add focused regressions proving that:

1. applicable search intent compiles at least three materially distinct query-angle families without superficial duplicate rewordings;
2. bad query structures are caught before any network request and covered by a regression corpus;
3. source capability differences produce meaningfully different compiled query forms where appropriate;
4. distinct discovery strategies converging on one employer/opening retain overlap provenance and can increase deepening priority without changing fit evidence or duplicating score credit;
5. coverage-gap output identifies genuinely uncovered requested dimensions and reflection receives that explicit bounded gap profile;
6. a healthy known direct structured source is preferred for refresh while broad exploration remains enabled;
7. audit/API/UI telemetry exposes hypotheses, queries, yield, warnings, overlap, gaps, and weight changes without creating an approval gate;
8. existing exploration-floor, cooldown, location-conditioned-yield, and broad-retention regressions remain green.

## Likely code surface

Use the generated packet first, but expect targeted reads around:

- Job Scout strategy generation and public-search execution;
- search-query compilation and source adapters/capabilities;
- discovery-learning strategy identity, attempts, yield, and provenance;
- reflection request construction and coverage snapshots;
- direct source resolution/refresh selection;
- Job Scout diagnostic/API telemetry and desktop audit UI;
- deterministic discovery-learning/search tests.

Prefer extending existing strategy and coverage contracts over creating a parallel planner.

## Validation

Run `refs/testing/validationCommands.yaml`. After deterministic CI and Windows packaging are green, use `scripts/run_job_scout_live.py` for a short diagnostic. Inspect whether query hypotheses are actually distinct, gap targeting makes sense, known structured sources are being refreshed cheaply, overlap is visible, and the system still explores beyond current winners.
