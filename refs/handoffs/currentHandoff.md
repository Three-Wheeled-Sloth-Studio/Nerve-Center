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
- Application version is `0.12.26`.
- Agent Academy alignment baseline is `e4118f96cc0138490b950402ba711399580ee854`; bounded source discovery, handoff required reads, capability-aware sub-agent guidance, and source-modularity rules are now part of Nerve Center's engineering contract.
- The local-acquisition implementation checkpoint is `fa5cfd0f0558daab0b2a76a059679bf7db4c6b28`, with behavior through `708484842782fa91bc84a81fed6a72cec016e7a2`. CI run `35219112384` is green across Python, strict refs/source-catalog/agent-context validation, the full test suite, desktop web, and desktop Rust/Tauri.
- Issue #57 remains open. Do not close it until current-run evidence shows the local employer/alias acquisition path produces usable hypotheses that proceed through ordinary company/career discovery.
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
9. a reserved scheduler slot for both old and normalized civic attachment employer hypotheses;
10. employer deepening resolves the canonical career surface without a location term, while preserving civic location evidence for downstream validation;
11. direct-career and sitemap URL qualification uses discrete route evidence rather than substring matches such as `career-advice` or `job-interview`;
12. sitemap child registration defaults to 50 and is hard-capped at 250; source-only expansion without postings is down-weighted rather than rewarded;
13. durable search-cache rows are reclassified through current URL policy before use, so stale classifications cannot recreate rejected editorial sources;
14. employer-career resolution uses a bounded three-query sequence (`careers`, `official careers`, `employment opportunities`) only when earlier results contain no direct employer/ATS surface;
15. all public-search strategies are deduplicated by compiled `(source_path, query)` identity while their raw civic/OCR provenance rows remain durable;
16. tenant-keyed shared career-portal listing routes remain aggregator evidence, and aggregator-only companies are excluded from employer revisit scheduling;
17. regional alias probes receive protected scheduler capacity only for first-pass coverage. After a regional probe has executed once, it remains eligible through normal learned-weight, exploration-floor, and cooldown selection but no longer owns a guaranteed slot;
18. local-employer reference queries preserve exact discovery intent with quoted employer phrases, regional probes cover common public regional vocabulary, and the evidence extractors recognize broader generic regional-organization and employer-list heading forms without named-market exceptions.

OCR is generic and structural. It requires employer-list heading evidence plus monotonic ranked rows. OCR output becomes `local_employer_deepen` work; it does not directly create companies.

## Implementation and validation

- `7af8cbb2902141736c9b07a8d6c48b1e7ad0990e`: extensionless supported-document routing and bounded polling recovery (`0.12.16`).
- `e6c36488314874261e30c0db65712aae83fb2fd7`: bounded local OCR and packaged runtime support (`0.12.17`).
- `b3902c8`: civic-attachment scheduler compatibility (`0.12.18`).
- `e6aac49`: split civic authority from attachment medium.
- `4f2bceb`: bounded migration of persisted combined-authority hypotheses (`0.12.19`).
- `ef8d61b`: location-free canonical employer career resolution and OCR word-boundary repair (`0.12.20`).
- `bf461c2`: discrete job-route qualification, bounded sitemap expansion, and posting-conditioned learning (`0.12.21`).
- `8877970`: authoritative cached-result reclassification (`0.12.22`).
- `33f5d3e`: bounded canonical employer-career query failback (`0.12.23`).
- `a41dce0`: compiled civic-employer query deduplication (`0.12.24`).
- `c24b44b`: generic shared-portal classification and aggregator-only revisit exclusion (`0.12.25`).
- `12ed92d`: compiled-query deduplication across all public-search revisions and provenance (`0.12.26`).
- `12a566f2661beee677a125e1236487d62d922ed4`: first-pass-only protected capacity for `regional_alias_probe` strategies.
- `f1f144e07cfe2ccc170f78313607f5d8b2f41e8c`: regression coverage proving initial regional coverage remains protected but the slot is released after the first attempt.
- `a1632ff3e497b5c699eb5d4ca12609430d215ba6`: refreshed deterministic source-catalog shards for the regional-saturation implementation/test changes.
- `708484842782fa91bc84a81fed6a72cec016e7a2`: expanded generic regional-organization and employer-list evidence patterns with deterministic regression coverage.
- `fa5cfd0f0558daab0b2a76a059679bf7db4c6b28`: clean local-acquisition implementation checkpoint after temporary helper cleanup.
- CI `35219112384` is green: refs/tracked paths, agent context, Ruff, packaging command, full Python tests, desktop web, and desktop Rust/Tauri all passed.
- The self-contained Windows backend builds and passes health, workspace, and module-runtime smoke tests. OCR increases the backend executable to about 155.8 MiB.

## Runtime evidence

Run `efd30156-4156-48cc-a731-e357cc4bcb29` (`0.12.16`) reached planned `admission_draining`: 99 requests, 27 LLM calls, 27 successful searches, 269 returned results, 19/19 full scores, and current-run-only reference evidence. It routed three extensionless PDFs through the parser but extracted zero candidates because the documents lacked text layers.

Visual and parser inspection of the official High Point `2022 Largest Employers` PDF confirmed it is a one-page image-only employer table. The bounded OCR fallback extracted 12 hypotheses from that exact artifact, including `Volvo Group North America`, without a named-employer rule.

Run `48425240-38d6-431f-84b9-f92a57df5335` loaded `0.12.17`, created and persisted those 12 OCR employer hypotheses, and retained two roles with 10/10 successful full scores. A concurrent local validation process interrupted its managed API; the runner reported the failure truthfully. After resume it reached planned wind-down with 134 requests and 17 LLM calls. Treat it as acquisition evidence, not a clean end-to-end acceptance gate.

Run `d896ef7d-b671-4445-b02c-5f2a29e1488c` (`0.12.19`) proved scheduler reachability: three civic/OCR-derived `local_employer_deepen` attempts executed, 30/31 full scores completed with zero failures, and the run remained within budget. Location-heavy employer queries selected blocked aggregators, which led to the `0.12.20` canonical-career query correction.

Run `1c68afd8-26d1-4f40-9fee-bfe35e67cfef` (`0.12.20`) immediately exercised corrected queries such as `"High Point University" careers`. It was healthy through cycle 26 with 60 successful searches, 450 returned results, 12 companies, 36 career sources, five postings, one retained opportunity, and 26/26 successful scores. At cycle 27 a false company created from an editorial page expanded 250 sitemap article/image URLs and was incorrectly rewarded despite zero postings. The run was stopped at cycle 29.

The exact false RippleMatch graph was removed after a recoverable database backup: one company, 251 sources, 250 revisit strategies, two scans, and four evidence rows; it contained no jobs, provenance, or enrichment. A second evidence-defined quarantine disabled 746 historical sitemap-created JSON-LD sources that had neither discrete job-route evidence nor job provenance, and lowered their revisit strategies. No source with job provenance was touched.

Run `41270b53-6af3-475c-a528-5363016a1655` was the bounded `0.12.21` post-cleanup verification gate. It confirmed proportional source counts and posting-conditioned down-weighting, but also proved cached result classifications could bypass the new URL policy and recreate the rejected editorial company. It was stopped early; `0.12.22` made classification authoritative when cache rows are consumed.

Run `4633fbac-4c77-46cc-9411-cafd4b3915f8` (`0.12.22`) reached planned `admission_draining` with 50 requests, 13 LLM calls, 8/8 successful full scores, 16 searches, 132 results, two companies, two career sources, and four postings. Source growth stayed proportional and the stale RippleMatch result remained rejected. The result also identified weak chamber/directory identity resolution.

Run `1dc9b888-dfb7-4067-affe-b764446f5e0c` (`0.12.23`) reached planned wind-down with 47 requests, 24 LLM calls, 14/14 successful scores, 11 searches, 110 results, and no new companies or sources. Its 11 search attempts compiled to only eight unique queries, which led to compiled-query canonicalization.

Run `4d882157-ae48-477a-9139-aed0a2281816` (`0.12.24`) was stopped after a false shared career-portal company revisit expanded 50 sources with zero postings. Audit proved the full false graph had 304 sources, 303 revisit strategies, 46 scans, and zero jobs/provenance. It was removed after backup `nerve-center.pre-shared-portal-cleanup.20260915-154117.sqlite3`; foreign-key validation was clean. No named portal rule was added: `0.12.25` recognizes the generic tenant listing/print route shape and refuses employer revisit when a company's sources are aggregator-only.

Run `78b7e242-8aee-450f-a373-5f73600f8326` (`0.12.26`) is the final bounded pre-soak gate. It reached planned `admission_draining` with 59 requests, seven LLM calls, 5/5 successful full scores, 10 searches, 90 results, 38 successful source scans, 124 postings inspected, five retained roles, 12 evidence-backed employer hypotheses, and five career sources. All 10 public queries were unique, the shared-portal company remained absent, and source growth stayed proportional to posting yield.

The subsequent long soak was launched from pre-Agent-Academy-alignment head `ad34249`. The host rebooted during the run and Job Scout resumed correctly from durable state without requiring a restart. That is positive recovery evidence.

The completed long soak then reached planned wind-down cleanly at 10:52 PM EDT with no process or API listener left running. The exact run ID was not supplied with the final report, so none is inferred here. Final counts were:

- 1,574 / 3,000 requests;
- 159 / 500 LLM calls;
- 100 / 100 full scores, zero failures;
- 221 successful searches, zero failed;
- 674 search results returned;
- 732 postings inspected;
- six companies discovered;
- 18 retained opportunities;
- 87 requests per retained opportunity, improved from 365 in the previous soak;
- 102 intermittent monitoring timeouts, all recovered.

This clears general search reliability, scoring reliability, planned wind-down, and timeout recovery as active blockers. The remaining weakness is local acquisition: zero regional aliases and zero employer candidates. The location-family audit produced only two conditioned yields across 1,467 attempts while correctly down-weighting 200 poorly performing families.

## Regional saturation checkpoint

The scheduler previously reserved one `regional_alias_probe` slot whenever any such strategy was eligible. In a four-strategy wave, that could become a permanent 25 percent capacity reservation even after regional vocabulary had already been sampled and marginal yield had fallen.

The accepted correction is structural rather than threshold-based: each regional probe may use the protected slot until its first execution. After that, it competes through the same durable learned weight, exploration floor, and cooldown rules as other discovery strategies. This keeps regional coverage reachable without making it a perpetual fixed tax on later waves. No named market, static saturation count, or region-specific exception was introduced.

The regression test proves both sides of the invariant: a never-attempted regional probe is included in the initial protected portfolio, and after one attempt it is no longer forced into the next four-strategy wave.

## Local acquisition correction

The current bounded correction addresses the newly isolated acquisition weakness without increasing request caps or changing general scoring/scheduler weights:

1. local-employer reference queries preserve exact intent with quoted phrases such as `"major employers"`, `"largest employers"`, and `"employer directory"`;
2. regional probes search common public regional vocabulary: `regional council`, `regional partnership`, and `council of governments`;
3. regional title extraction recognizes generic `Council of Governments`, `Planning Commission`, and `Development District` forms in addition to the prior `Regional Council/Partnership/Commission/Authority/Planning` forms;
4. civic employer-list heading extraction accepts common variants such as `Top 25 Private Employers`, `Leading Employers`, `Employer Directory`, and `Employer List`;
5. deterministic tests cover the broadened regional and employer-list evidence while preserving the rule that extracted names are hypotheses only.

No named company, city, or region exception was added. No extra network path or request allowance was added.

## Next bounded slice

Run one isolated 30-minute local-acquisition gate. Do not run another long soak yet.

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 1800 `
  --max-requests 500 `
  --max-llm-calls 80 `
  --score-limit 25 `
  --score-failure-limit 5
```

Audit only the current run and answer these questions in order:

1. Did `regional_alias_probe` and `local_employer` strategies actually execute? If not, the next defect is allocation/cooldown/learned-weight starvation rather than acquisition syntax.
2. When regional probes execute, do the broadened queries return recognizable regional organization evidence and create any provenance-bearing aliases?
3. When local-employer strategies execute, do exact-intent queries reach employer-list/directory references, and do those references produce any employer candidates?
4. Do employer candidates become `local_employer_deepen` hypotheses and proceed through ordinary official-career discovery?
5. If high-intent references are inspected but candidate yield remains zero, improve HTML/table/list extraction next. Do not change general search or scoring.
6. If aliases/candidates appear, run a longer soak only after this short gate proves the acquisition path is alive.

Keep Issue #57 open until local acquisition produces real current-run evidence. Do not add named company, city, aggregator, or region exceptions. Preserve public-source safety boundaries and the rule that extracted employer names are hypotheses rather than company truth.

Code Shop Issue #54 remains staged behind this acceptance work. Its contract is `refs/planning/code-shop-foundation.md`.

## Required Reads For Next Slice

- `refs/handoffs/currentHandoff.md` - authoritative accepted baseline, completed long-soak evidence, local-acquisition correction, and current short-gate questions.
- `refs/handoffs/next-dev-prompt.md` - exact bounded execution/audit instructions for the next coding-agent session.
- Latest Issue #57 comments and the next current-head `run-*.json` - current-run evidence is authoritative for deciding the next behavior slice.
- `src/nerve_center/plugins/job_scout/query_portfolio.py` - only local-employer and regional-probe query compilation symbols returned by the source catalog.
- `src/nerve_center/plugins/job_scout/discovery_loop.py` - only regional-alias extraction, civic employer-landscape extraction, and employer-deepening symbols returned by the source catalog.
- `src/nerve_center/plugins/job_scout/discovery_learning.py` - only `select_strategies` and directly related scheduler/cooldown symbols if the short gate shows local strategies are not executing.
- `scripts/run_job_scout_live.py` - only report/audit collection symbols returned by the source catalog; use to interpret or improve reusable local-acquisition diagnostics.

## Re-entry

```powershell
python scripts/agent_context.py --focus "job scout local employer regional alias acquisition employer candidates" --issue 57
```

Start with the generated packet's required reads and source-catalog matches. Query the source catalog again before broader search if a concrete dependency remains unresolved.