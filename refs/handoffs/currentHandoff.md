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
- Application version is `0.12.19`.
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

OCR is generic and structural. It requires employer-list heading evidence plus monotonic ranked rows. OCR output becomes `local_employer_deepen` work; it does not directly create companies.

## Implementation and validation

- `7af8cbb2902141736c9b07a8d6c48b1e7ad0990e`: extensionless supported-document routing and bounded polling recovery (`0.12.16`).
- `e6c36488314874261e30c0db65712aae83fb2fd7`: bounded local OCR and packaged runtime support (`0.12.17`).
- `b3902c8`: civic-attachment scheduler compatibility (`0.12.18`).
- `e6aac49`: split civic authority from attachment medium.
- `4f2bceb`: bounded migration of persisted combined-authority hypotheses (`0.12.19`).
- CI `34914905154` is green for `e6c3648`, including Python, desktop web, and desktop Rust. Exact-head CI for the final integration commits must be green before the handoff is sealed.
- Local validation reached 250 Python tests before the migration regression; targeted migration/scheduler/attachment suites are green. Run complete required validation at final head.
- The self-contained Windows backend builds and passes health, workspace, and module-runtime smoke tests. OCR increases the backend executable to about 155.8 MiB.

## Runtime evidence

Run `efd30156-4156-48cc-a731-e357cc4bcb29` (`0.12.16`) reached planned `admission_draining`: 99 requests, 27 LLM calls, 27 successful searches, 269 returned results, 19/19 full scores, and current-run-only reference evidence. It routed three extensionless PDFs through the parser but extracted zero candidates because the documents lacked text layers.

Visual and parser inspection of the official High Point `2022 Largest Employers` PDF confirmed it is a one-page image-only employer table. The bounded OCR fallback extracted 12 hypotheses from that exact artifact, including `Volvo Group North America`, without a named-employer rule.

Run `48425240-38d6-431f-84b9-f92a57df5335` loaded `0.12.17`, created and persisted those 12 OCR employer hypotheses, and retained two roles with 10/10 successful full scores. A concurrent local validation process interrupted its managed API; the runner reported the failure truthfully. After resume it reached planned wind-down with 134 requests and 17 LLM calls. Treat it as acquisition evidence, not a clean end-to-end acceptance gate.

Short `0.12.18`/`0.12.19` gates confirmed clean startup, bounded migration, exact version reporting, status-timeout recovery, and durable employer hypotheses. Their windows ended before a newly recorded `local_employer_deepen` attempt. This remains the first overnight acceptance question.

## Overnight-ready checkpoint

The system is ready for a productive overnight run: candidate acquisition, OCR, persistence, budgets, scoring, polling recovery, and package construction are operational. Use explicit budgets:

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

Review the overnight report and Issue #57 audit before changing behavior:

1. Did at least one OCR/civic-derived `local_employer_deepen` strategy execute in the current run?
2. Did ordinary discovery resolve one to a plausible company and official career source?
3. Were false positives rejected or down-weighted through evidence/yield learning rather than named rules?
4. Did candidate/company/source counts grow across waves without accounting drift?
5. Did planned wind-down complete, with transient poll failures bounded and recovered?

If civic-derived strategies still do not execute, instrument current-run selected-strategy families and fix scheduler starvation generically. If they execute but fail to resolve valid employers, inspect their public-search query/result evidence before changing extraction. Do not tune scoring unless the report shows a scoring failure.

Code Shop Issue #54 remains staged behind this acceptance work. Its contract is `refs/planning/code-shop-foundation.md`.

## Re-entry

```powershell
python scripts/agent_context.py --focus "job scout overnight civic employer deepening audit" --issue 57
```

Read the generated packet, this handoff, the newest Issue #57 comments, the overnight report, and only directly relevant scheduler/reference files.
