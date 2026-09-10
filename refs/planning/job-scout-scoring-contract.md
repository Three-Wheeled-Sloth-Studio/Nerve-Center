---
type: Scoring Contract
title: Job Scout Scoring Contract
description: Explainable fit, response-likelihood, opportunity-value, confidence, priority, location, and gating rules for Job Scout.
status: stable
tags: [nerve-center, planning, job-scout, scoring]
---
# Job Scout Scoring Contract

## Purpose

Job Scout ranks opportunities by practical pursuit value, not keyword similarity alone. Every score must retain factor-level evidence and confidence so the user can understand and tune the result.

## Score dimensions

### Fit, 0 to 100

Measures alignment between verified career evidence and the opening's required work, seniority, domain, methods, leadership scope, and outcomes. Preferred qualifications contribute less than required qualifications. Unsupported assumptions cannot count as evidence.

The listed job title is a weak discovery and seniority clue, not a fit gate. Fit evaluation must look past title wording and compare the actual responsibilities and requirements in the opening with verified candidate experience. A differently titled role can be a strong match when the work, scope, and evidence align; a familiar title can be a weak match when they do not.

Domain fit is a first-class part of fit and should distinguish, in descending order:

1. Direct domain match: verified experience in the same material business/problem domain.
2. Adjacent domain: materially related users, workflows, regulation, data, operating environment, or market context.
3. Transferable experience: the candidate has relevant methods, leadership, product, technical, or outcome evidence but must transfer it across a meaningfully different domain.
4. Domain or skill mismatch: the opening depends on domain knowledge or capabilities not supported by verified evidence.

Domain-distance evidence is explainable separately from title similarity and generic skill overlap. The scorer derives a structured `direct`, `adjacent`, `transferable`, or `mismatch` relationship from a reusable deterministic taxonomy, persists the supporting claim identifiers and evidence locators, and derives the numeric domain component from that relationship. Model-produced domain scalars are advisory and do not override the evidence-backed relationship. Extend the taxonomy only with observed, testable relationships rather than inventing candidate support.

## Qualification decision importance

Qualification category, employer-side decision importance, and candidate match strength are separate concepts.

- `required`, `responsibility`, and `preferred` describe the job-side category.
- `decision_weight` describes how central the item appears to employer screening or day-to-day role success.
- `full`, `partial`, `none`, and `unknown` describe candidate evidence strength.

Fit-analysis contract v7 may request a bounded model `decision_weight_hint`, but the hint is advisory. It must describe the job, not how well the candidate matches it. The scorer bounds model hints conservatively and may override them only from validated verbatim job excerpts. Explicit source language such as `must`, `minimum`, `essential`, `required`, or `core responsibility` can raise importance; `preferred`, `nice to have`, `bonus`, or equivalent optional language can lower it. Model-authored requirement labels cannot manufacture those deterministic cues.

Required, responsibility, and preferred coverage are weighted by normalized decision importance instead of simple equal averaging. The overall fit formula still keeps required qualifications and responsibilities materially stronger than preferred qualifications. Response likelihood consumes the same weighted required-coverage value.

Near-duplicate qualification phrasings remain visible for audit but only one representative receives coverage and domain-evidence credit. Representative selection favors explicit factual gates, then required over responsibility over preferred, then stronger job-side decision importance and evidence confidence. Duplicate factual gate copies are suppressed so repeated extraction cannot create repeated exclusion noise.

Decision importance remains soft unless an independent factual gate applies. Missing a high-importance ordinary requirement should reduce fit materially, but it does not become a hidden exclusion. Explicit licenses, clearances, configured minimums, and other factual/user gates remain separate.

Ranking engine v5 reconstructs decision weighting and duplicate suppression from persisted qualifications. Legacy v6 fit-analysis payloads remain loadable through neutral defaults and can be deterministically reinterpreted at score time. A ranking-only refresh therefore does not require another LLM fit-analysis call when the existing evidence remains valid.

### Response likelihood, 0 to 100

Estimates the chance of meaningful employer attention. Initial factors include listing freshness, direct-employer provenance, local or regional presence, work arrangement, commute time, weighted required-qualification coverage, applicant saturation signals, hiring activity, repost patterns, and application friction.

This is an estimate, not a calibrated probability, until sufficient application outcome data exists.

### Opportunity value, 0 to 100

Measures desirability based on scope, compensation when available, employment type, work arrangement, company and domain preferences, and explicit user rules.

### Confidence, 0 to 100

Measures source completeness, provenance quality, date reliability, location certainty, parsing confidence, and evidence coverage. Confidence reduces final priority rather than compensating for weak fit.

### Priority, 0 to 100

Default calculation:

```text
base priority = fit * 0.35
              + response likelihood * 0.45
              + opportunity value * 0.20

final priority = base priority * confidence multiplier
```

Initial confidence multipliers:

| Confidence | Multiplier |
|---|---:|
| 90 to 100 | 1.00 |
| 75 to 89 | 0.95 |
| 60 to 74 | 0.85 |
| 40 to 59 | 0.70 |
| Below 40 | 0.55 |

All weights, thresholds, gates, and multipliers are configurable.

## Location response order

1. Local hybrid.
2. Local on-site.
3. Regional hybrid.
4. Regional remote.
5. Distant remote.
6. Relocation required: excluded.

Local means an estimated drive of up to 90 minutes when coordinate or commute evidence exists. Commute contribution decays continuously with time. Remote jobs receive a presence adjustment based on the nearest relevant company office and evidence that the employer genuinely hires distributed teams.

When explicit structured job-location enrichment is absent, scoring must deterministically interpret the opening's persisted `location_text` and `locations` against configured local-market preferences. Exact configured-city evidence may establish local scope; a recognized configured region may establish regional scope; explicit foreign, out-of-region, or remote-only evidence may establish distant scope. Raw source text is preserved on the opening, and the scoring rationale retains the matched label plus its listing source so the classification remains reconstructable.

Structured job enrichment remains more authoritative than fallback listing-text interpretation. Listing location evidence and company-presence evidence are separate facts: a role being available in a market does not prove the employer has a physical office there, and an employer office does not rewrite the listing's stated location. Remote or multi-location strings such as `Remote - US`, mixed-country remote labels, and `City A OR City B` must be handled conservatively without substring-based state-code inference.

A scoring-engine version change that only changes deterministic interpretation may backfill existing score history from persisted opening, profile, fit, company, and job evidence. It must not require another LLM fit analysis when the existing fit evidence remains valid.

## Hard gates

Initial gates may exclude or explicitly flag:

- Relocation-required positions.
- Required licenses or clearances not held.
- Compensation below a configured minimum.
- Excluded employment types.
- Hard-excluded companies, domains, titles, industries, locations, or sources.

Geography must not be applied as an invisible pre-review deletion rule. Broadly discovered opportunities remain retained unless an explicit factual gate excludes pursuit. The review UI may filter by scored location scope, but filtering is a user-visible view operation rather than destructive discovery behavior.

## Explainability

Every score must provide:

- Positive factors.
- Negative factors.
- Missing or uncertain evidence.
- The contract and model versions used.
- Any user rule or learned positioning hypothesis that affected the result.
- The location rationale and source evidence used for local, regional, distant, or unknown classification.
- Weighted qualification coverage inputs, effective decision weights, rationale, duplicate linkage, and weighted contributions.
