# Opportunity Scoring Handoff

## Accepted baseline

- Target branch: `dev`.
- Pull request: `#6`.
- Visible version: `0.4.0`.
- SQLite schema version: `5`.
- Tracking issue: `#4`.

## Implemented

Job Scout now records separate fit, response likelihood, opportunity value, confidence, and calculated priority scores. Priority weights, confidence bands, thresholds, and pursuit rules are configurable and versioned.

Fit analysis is constrained to verified canonical career claims. Qualification matches must cite exact job-description evidence and valid claim identifiers. Unverified required licenses and clearances remain explicit hard gates.

Location scoring implements the accepted ordering and constraints:

1. Local hybrid.
2. Local on-site.
3. Regional hybrid.
4. Regional remote.
5. Distant remote.

Local eligibility defaults to a 90-minute commute, with a continuous advantage for closer roles. A relevant nearby office can improve a remote role's response ranking. Distant remote opportunities receive an applicant-saturation penalty unless verified fit is exceptional. Relocation-required and distant in-person roles are excluded.

Every recommendation retains factor-level explanations, gates, contract and settings versions, job and profile snapshot hashes, and a calibration key. Fit analyses and scores are append-only. History ordering is deterministic even when two records share a timestamp.

## Local API

The service exposes scoring settings, location preferences, company and job enrichment, pursuit rules, fit analysis, scoring, and score history under `/api/v1/scoring`.

## Validation

The full Ruff and Pytest suite covers commute decay, nearby-office advantage, distant-remote saturation, missing dates, repost and evergreen signals, source conflicts, qualification evidence, required-license gates, configurable weights, append-only persistence, versioned history, and unknown entity handling.

## Known limits

- Geocoding and real route-time providers are not integrated yet.
- Coordinate-based commute estimates are approximate and remain visible as such.
- Company and job enrichment currently enters through local APIs.
- Response likelihood is an explainable ranking estimate, not yet a calibrated probability.
- A live Ollama smoke test was not available in the connector execution environment.

## Next increment

Proceed with Issue `#5`: desktop opportunity review and application tracking. Keep the Python service authoritative and retain the local-only, single-user boundary. Do not add automated applications, outreach, profile changes, authenticated job-board interaction, cloud sync, or multi-user behavior.
