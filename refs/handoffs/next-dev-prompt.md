---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the next Job Scout qualification-importance ranking slice.
status: stable
tags: [nerve-center, handoff, job-scout, scoring, fit]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch using normal issue -> branch -> implementation -> tests -> PR -> CI -> merge discipline.

The immediate tracking issue is **#45: Normalize qualification importance in Job Scout fit scoring**.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout qualification importance weighted required responsibility coverage dedup fit response scoring" --issue 45
```

Treat that generated packet as the initial orientation. Read Issue #45 and only the code/docs identified by the packet or direct implementation evidence.

## Current accepted baseline

Issues #34, #40, and #43 are complete. Preserve:

- `expand -> converge -> deepen -> reflect -> re-expand`;
- company-first source deepening and durable discovery learning;
- source-aware bounded query portfolios and deterministic pre-request query linting;
- explicit discovery coverage gaps and gap-driven reflection;
- convergence provenance affecting company/source deepening, never opportunity fit truth;
- broad opportunity retention with ranking providing precision;
- responsibility/requirement-first fit with title as a weak clue;
- explicit `direct > adjacent > transferable > mismatch` domain relationship;
- deterministic location scope from raw listing evidence and configured markets;
- separate opening-location, company-presence, and discovery-market evidence;
- location-conditioned yield for location-seeded strategies;
- manager-owned provider/session/queue boundaries and Job Scout model blindness;
- exploration-floor and durable revisit/cooldown behavior.

Do not reopen these without new evidence.

## Problem to solve

The fit analyzer already selects up to eight decision-relevant requirements or responsibilities and validates every positive match against persisted career claims. Scoring, however, still treats items equally within the broad `required`, `responsibility`, and `preferred` categories.

That loses job-side decision importance. A central must-have requirement can carry the same within-bucket weight as a marginal required bullet, and a role-defining responsibility can carry the same weight as a supporting responsibility. Several peripheral matches can therefore offset one central miss too easily.

Importance must describe the job, not how strong the candidate happens to be.

## Implementation objective

Implement the smallest coherent qualification-importance correction:

1. Represent normalized job-side decision importance separately from match level and separately from the factual required/responsibility/preferred category.
2. Derive importance conservatively from explicit job language and bounded structured fit analysis, then validate/normalize it deterministically.
3. Keep explicit cues such as `must`, `required`, `minimum`, and `essential` stronger than vague supporting language; keep preferred/nice-to-have items lower influence.
4. Weight required and responsibility coverage by normalized importance instead of simple equal averaging.
5. Prevent duplicate or near-duplicate qualification phrasings from gaining repeated score weight.
6. Keep licenses/clearances and other explicit factual gates separate from soft weighted mismatches.
7. Expose normalized importance, weighted coverage, and rationale in persisted analysis/score factors sufficiently for audit.
8. Version the fit/scoring contract as needed and reuse existing validated evidence for deterministic refresh when safe instead of forcing unnecessary LLM reruns.

## Constraints

- Do not make title similarity a substitute for qualification evidence.
- Do not infer job importance from candidate match strength.
- Do not let a model invent qualifications or unsupported importance rationales; job excerpts and evidence validation remain mandatory.
- Preserve the existing direct/adjacent/transferable/mismatch domain relationship and its evidence provenance.
- Preserve manager-owned provider boundaries and Job Scout model blindness.
- Preserve Issue #40 location behavior and Issue #43 discovery-learning behavior.
- Ordinary weighted mismatches must not silently become hard exclusions.
- Keep CI deterministic and independent of live search providers, mutable career sites, Ollama, and GPUs.

## Deterministic acceptance tests

Add focused regressions proving that:

1. normalized importance is distinct from both broad qualification category and candidate match level;
2. one high-importance required miss matters more than a low-importance required miss, all else equal;
3. strong evidence for a central responsibility matters more than equivalent evidence for a peripheral responsibility;
4. preferred qualifications remain materially lower influence than required qualifications/core responsibilities;
5. duplicate or near-duplicate qualification wording cannot inflate weighted coverage;
6. explicit license/clearance gate behavior remains a gate and ordinary importance weighting remains soft;
7. a candidate satisfying central requirements/responsibilities outranks one matching many peripheral bullets while missing a central item, all else equal;
8. listed title remains a weak clue and cannot rescue weak requirement evidence;
9. domain ordering, location scoring, evidence validation, broad retention, and discovery regressions remain green;
10. score factors make the weighted inputs reconstructable.

## Likely code surface

Use the generated packet first, but expect targeted reads around:

- `src/nerve_center/scoring/models.py` qualification contracts;
- `src/nerve_center/scoring/fit.py` extraction validation and coverage helpers;
- `src/nerve_center/scoring/engine.py` fit/response coverage use and score factors;
- scoring persistence/version refresh behavior;
- fit-analysis response schema/prompt validation;
- deterministic fit/evidence/scoring regressions.

Prefer extending the accepted qualification/evidence contract over introducing a parallel ranking model.

## Validation

Run `refs/testing/validationCommands.yaml`. Full CI and Windows packaging must be green on the exact PR head before merge.

A short local Job Scout live diagnostic remains useful before another long market run to observe the newly accepted Issue #43 query diversity, gap targeting, overlap telemetry, and structured refresh behavior. That runtime observation is independent of the Issue #45 deterministic ranking implementation and should not trigger weight tuning without evidence.
