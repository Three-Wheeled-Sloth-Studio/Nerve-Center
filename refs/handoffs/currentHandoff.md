---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next bounded checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- Work directly on `dev`; do not create a feature branch or PR unless explicitly requested.
- Application version is `0.12.22`.
- Issue #57 remains open. Do not close it until an overnight/current-run audit shows civic-derived employer deepening reaching normal company/career discovery.
- Job Scout remains an iterative market-research loop: `expand -> converge -> deepen -> reflect -> re-expand`. Discovery optimizes recall; ranking/scoring provides precision.
- Extracted employer names are hypotheses only. They must pass through ordinary public search and official-career resolution before becoming durable company/location evidence.
- No named employer, city, or region exception exists in production logic.

## Completed Issue #57 behavior

The accepted behavior now includes:

1. intent-pure, revisioned market queries and intent-aware civic-reference selection;
2. civic HR/self-employment exclusion unless employer-landscape evidence is also present;
3. a six-candidate ranked fallback pool with hard two-inspection and three-network-fetch ceilings;
4. current-run-scoped reference audit evidence;
5. extensionless PDF/XLSX routing by normalized response `Content-Type`, with requested/final redirect provenance and a four-megabyte response cap;
6. local OCR for image-only PDFs, limited to four pages and a 1,600-pixel long edge, followed by the existing ranked-employer structural parser and 12-candidate cap;
7. bounded runner tolerance for up to three consecutive status-poll timeouts;
8. normalized evidence semantics: `employer_evidence_authority=civic` and `employer_evidence_medium=attachment`, with a bounded migration for old `civic_attachment` hypotheses;
9. a reserved scheduler slot for both old and normalized civic attachment employer hypotheses.
10. employer deepening resolves the canonical career surface without a location term, while preserving civic location evidence for downstream validation;
11. direct-career and sitemap URL qualification uses discrete route evidence rather than substring matches such as `career-advice` or `job-interview`;
12. sitemap child registration defaults to 50 and is hard-capped at 250; source-only expansion without postings is down-weighted rather than rewarded.
13. durable search-cache rows are reclassified through current URL policy before use, so stale classifications cannot recreate rejected editorial sources.

OCR is generic and structural. It requires employer-list heading evidence plus monotonic ranked rows. OCR output becomes `local_employer_deepen` work; it does not directly create companies.

## Implementation and validation

- `7af8cbb2902141736c9b07a8d6c48b1e7ad0990e`: extensionless supported-document routing and bounded polling recovery (`0.12.16`).
- `e6c36488314874261e30c0db65712aae83fb2fd7`: bounded local OCR and packaged runtime support (`0.12.17`).
- `b3902c8`: civic-attachment scheduler compatibility (`0.12.18`).
- `e6aac49`: split civic authority from attachment medium.
- `4f2bceb`: bounded migration of persisted combined-authority hypotheses (`0.12.19`).
- `ef8d61b`: location-free canonical employer career resolution and OCR word-boundary repair (`0.12.20`).
- `bf461c2`: discrete job-route qualification, bounded sitemap expansion, and posting-conditioned learning (`0.12.21`).
- Current working slice: authoritative cache-result reclassification (`0.12.22`).
- CI `34984865125` is green for `bf461c2`, including Python, desktop web, and desktop Rust.
- Local validation is green: 255 Python tests, Ruff, case-collision, OKF index, refs, agent-context, and desktop web. Local Rust validation remains blocked by the machine's Visual Studio installation missing `excpt.h`; exact-head CI covers desktop Rust successfully.
- The self-contained Windows backend builds and passes health, workspace, and module-runtime smoke tests. OCR increases the backend executable to about 155.8 MiB.

## Runtime evidence

Run `efd30156-4156-48cc-a731-e357cc4bcb29` (`0.12.16`) reached planned `admission_draining`: 99 requests, 27 LLM calls, 27 successful searches, 269 returned results, 19/19 full scores, and current-run-only reference evidence. It routed three extensionless PDFs through the parser but extracted zero candidates because the documents lacked text layers.

Visual and parser inspection of the official High Point `2022 Largest Employers` PDF confirmed it is a one-page image-only employer table. The bounded OCR fallback extracted 12 hypotheses from that exact artifact, including `Volvo Group North America`, without a named-employer rule.

Run `48425240-38d6-431f-84b9-f92a57df5335` loaded `0.12.17`, created and persisted those 12 OCR employer hypotheses, and retained two roles with 10/10 successful full scores. A concurrent local validation process interrupted its managed API; the runner reported the failure truthfully. After resume it reached planned wind-down with 134 requests and 17 LLM calls. Treat it as acquisition evidence, not a clean end-to-end acceptance gate.

Run `d896ef7d-b671-4445-b02c-5f2a29e1488c` (`0.12.19`) proved scheduler reachability: three civic/OCR-derived `local_employer_deepen` attempts executed, 30/31 full scores completed with zero failures, and the run remained within budget. Location-heavy employer queries selected blocked aggregators, which led to the `0.12.20` canonical-career query correction.

Run `1c68afd8-26d1-4f40-9fee-bfe35e67cfef` (`0.12.20`) immediately exercised corrected queries such as `"High Point University" careers`. It was healthy through cycle 26 with 60 successful searches, 450 returned results, 12 companies, 36 career sources, five postings, one retained opportunity, and 26/26 successful scores. At cycle 27 a false company created from an editorial page expanded 250 sitemap article/image URLs and was incorrectly rewarded despite zero postings. The run was stopped at cycle 29.

The exact false RippleMatch graph was removed after a recoverable database backup: one company, 251 sources, 250 revisit strategies, two scans, and four evidence rows; it contained no jobs, provenance, or enrichment. A second evidence-defined quarantine disabled 746 historical sitemap-created JSON-LD sources that had neither discrete job-route evidence nor job provenance, and lowered their revisit strategies. No source with job provenance was touched.

Run `41270b53-6af3-475c-a528-5363016a1655` was the bounded `0.12.21` post-cleanup verification gate. It confirmed proportional source counts and posting-conditioned down-weighting, but also proved cached result classifications could bypass the new URL policy and recreate the rejected editorial company. It was stopped early; `0.12.22` makes classification authoritative when cache rows are consumed. Run a fresh bounded gate before another overnight soak.

## Overnight checkpoint

After a fresh `0.12.22` verification gate confirms proportional source growth, posting-conditioned down-weighting, and cache-policy enforcement, use these explicit overnight budgets:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --max-requests 3000 `
  --max-llm-calls 500 `
  --score-limit 100 `
  --score-failure-limit 20
```

The 500 LLM-call value is a run-specific safety ceiling, not a general product instruction. The request ceiling is higher than the short gates so company/career deepening is not starved after broad acquisition. Do not run the full test suite, packaging smoke, or another API-owning command concurrently with the soak.

## Next bounded slice

Review the `0.12.22` verification report and Issue #57 audit before changing behavior:

1. Did source counts remain proportional, with no sitemap article/image amplification?
2. Did source-only zero-posting attempts lose weight?
3. Did planned wind-down complete, with transient poll failures bounded and recovered?
4. Which civic-derived employer hypotheses returned only aggregators or duplicate location-free queries?
5. Can canonical employer identity/query failback improve official-career resolution without named employer rules?

The next quality slice is generic employer identity resolution: deduplicate civic hypotheses that compile to the same employer query across city/metro aliases, and add a bounded evidence-driven query failback when the first result set is aggregator-only or empty. Preserve raw civic/OCR provenance and downstream location validation. Do not tune scoring unless runtime evidence identifies scoring as the blocker.

Code Shop Issue #54 remains staged behind this acceptance work. Its contract is `refs/planning/code-shop-foundation.md`.

## Re-entry

```powershell
python scripts/agent_context.py --focus "job scout employer identity query failback deduplication" --issue 57
```

Read the generated packet, this handoff, the newest Issue #57 comments, the overnight report, and only directly relevant scheduler/reference files.
