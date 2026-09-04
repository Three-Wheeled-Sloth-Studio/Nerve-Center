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

### Response likelihood, 0 to 100

Estimates the chance of meaningful employer attention. Initial factors include listing freshness, direct-employer provenance, local or regional presence, work arrangement, commute time, required-qualification coverage, applicant saturation signals, hiring activity, repost patterns, and application friction.

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

Local means an estimated drive of up to 90 minutes. Commute contribution decays continuously with time. Remote jobs receive a presence adjustment based on the nearest relevant company office and evidence that the employer genuinely hires distributed teams.

## Hard gates

Initial gates may exclude or explicitly flag:

- Relocation-required positions.
- Required licenses or clearances not held.
- Compensation below a configured minimum.
- Excluded employment types.
- Hard-excluded companies, domains, titles, industries, locations, or sources.

## Explainability

Every score must provide:

- Positive factors.
- Negative factors.
- Missing or uncertain evidence.
- The contract and model versions used.
- Any user rule or learned positioning hypothesis that affected the result.
