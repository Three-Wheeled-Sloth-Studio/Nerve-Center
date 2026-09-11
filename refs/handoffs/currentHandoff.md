---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch. The current user directive is to work directly on `dev` and not create feature branches.
- Accepted `dev` entering Issue #53 is `151843c02024c079e0a8735b3e6fbcc829474c15`.
- Application version is `0.12.6`.
- The manager/module boundary, durable work sessions and queue, provider-neutral LLM manager, Windows desktop/package baseline, career evidence profile, company-first Job Scout discovery, scoring, application tracking, durable discovery learning, and first Model Lab foundation are accepted.
- Job Scout remains an iterative market-research loop: `expand -> converge -> deepen -> reflect -> re-expand`. Discovery optimizes recall; ranking/scoring provides precision.
- Issue #34 continuous-work/liveness is complete. The accepted 900-second run completed 89 cycles across 20 waves, retained 121 opportunities from 49 companies and 70 career sources, created 212 provisional scores, completed 3/3 bounded full analyses, continued through added and empty reflections, and stopped explicitly on request-budget exhaustion.
- Issue #40 location awareness is complete in PR #42. Raw opening locations feed deterministic, explainable location classification; ranking engine v4 refreshes stale deterministic scores; location-seeded discovery learns from location-conditioned opening yield; and review exposes scope counts, filters, badges, and rationale without hiding distant retained candidates.
- Issue #43 source-aware discovery quality is complete in PR #44. Job Scout compiles bounded materially distinct query families by source capability, lints invalid search structures before request spend, tracks company/opening convergence separately from fit, computes explicit coverage gaps for reflection, prefers eligible structured refresh paths, and exposes a read-only discovery audit.
- Issue #45 qualification importance is complete in PR #46. Fit-analysis v7 separates employer-side decision weight from candidate match strength, ranking v5 uses deterministic weighted coverage, near-duplicate qualifications cannot manufacture repeated fit/domain/gate credit, and old v6 analyses remain loadable for deterministic rescoring without another LLM pass.
- Issue #47 Model Lab foundation is complete in PR #48. Model Lab now has local persistent settings, a deduplicated real-request benchmark corpus, request/module capture opt-outs, credential redaction, isolated benchmark results, bounded exploration sessions, exact-model replay through the manager provider boundary, production-queue precedence, and a read-only manager UI.
- Experimental Model Lab results are structurally separate from production `TaskModelEvidence`; benchmark replay does not change production model-selection evidence or production loaded-model state.
- Opening location, company-presence location, and discovery-strategy market evidence remain separate concepts. A remote listing available in a region is not proof of a company office there, and an employer discovered by a local search does not make all of its national openings local yield.
- Fit analysis remains responsibility/evidence-first and derives explicit `direct`, `adjacent`, `transferable`, or `mismatch` domain relationships. Listed title remains a weak clue, not a fit gate.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output work may retry once on `qwen2.5:7b-instruct`; modules remain model-blind.
- The Windows source launcher validates a complete x64 Visual C++ environment before Tauri compilation and skips incomplete Visual Studio installations.
- `scripts/run_job_scout_live.py` remains the reusable real-run diagnostic and continuously writes a durable local report/checkpoint history.
- Issue #49's short live gate is complete. The valid run stopped cleanly on the inherited 500-request limit after about 21 minutes rather than completing the requested 30-minute window; it completed 25/25 full scores and captured 826 ranked opportunities, 199 companies, 1,170 sources, and 1,389 strategies.
- The run classified every ranked opportunity (34 regional, 792 distant, 0 unknown) and did not falsely credit national openings as local yield. It found zero directly local Greensboro/Triad openings; 366 location-conditioned strategies retained zero conditioned openings and none reached a downweighted state.
- Issue #51 is implemented on `dev`. Live-run duration, request, LLM, and full-score ceilings are explicit in stdout and the durable report; the session receives the requested resource policy; each cycle receives its remaining request allowance; network fetches reserve from that allowance before execution; and an invariant rejects any overrun.
- Public-search strategies now share durable evidence at a stable hypothesis-family/source/location identity. Location-family exploitation uses conditioned opening yield rather than employer/source discoveries, while individual strategy provenance and the exploration floor remain intact. The discovery API/audit and live report expose family attempts, yield, influence, and before/after weight evidence.
- The first four-hour soak completed 641 cycles across 584 waves and stopped cleanly at planned manager wind-down after 3 hours 36 minutes. It used 1,726/5,000 requests and 203/1,000 LLM calls with exact request accounting, retained 74 opportunity observations, and completed 94 of 100 reserved score attempts. It also exposed excessive late low-yield strategy churn, ambiguous completion semantics, and missing effective configuration in the report.
- Issue #53 is implemented on `dev`: planned wind-down is a successful active-work terminal state with separate deadline evidence; scoring targets successes with a bounded failure ceiling; eight-cycle zero-marginal-yield windows cause exponential backoff; evidence-derived `local_employer` searches find nearby companies before roles; and the live report records effective configuration, efficiency, scoring failures, and grouped location-family evidence.
- Coding-agent token conservation is a primary engineering concern. Use `scripts/agent_context.py` and progressive context loading instead of repository-wide rereads.

## Accepted Issue #47 behavior

The first manager-owned Model Lab slice is now accepted:

- Schema v11 adds local Model Lab settings, benchmark corpus, exploration-session history, and benchmark-result history without replacing production provider evidence.
- Eligible completed model-blind request/result pairs can be harvested lazily and idempotently from durable queue history, including after restart.
- Capture is opt-out capable at both request and module level. Retained prompts/results redact credential-like values while preserving replay-critical JSON schemas and task/contract provenance.
- A selected installed model can be exercised through an explicit manager-owned experimental execution path.
- Experimental execution bypasses production `TaskModelEvidence` recording and does not alter the manager's production loaded-model state.
- Exploration is bounded by explicit wall-clock duration and attempt budget.
- Replay refuses admission while production LLM work is queued or claimed, so Model Lab cannot preempt normal module work.
- The manager API/UI exposes installed models, empirical production task evidence, corpus state, exploration state, benchmark outcomes, and production queue state.
- Automatic model installation/removal, external benchmark ingestion, pairwise review, and automatic production-router promotion remain deferred.

PR #48 exact-head validation before merge:

- head `8119e5cf577fa1f1d19ce8afe7fdbf4740ac864d`;
- CI run `34502474954` / #250: green;
- Python: 192 passed, 0 failed;
- desktop-web: green;
- desktop-rust: green;
- Windows package run `34502474968` / #134: green;
- packaged backend health, Job Scout workspace route, managed module runtime smoke, NSIS build, output verification, and artifact upload: green.

## Completed slice: Issue #51

Issue **#51: Make Job Scout run budgets explicit and local discovery learning converge** is implemented in `0.12.5`.

The Issue #49 observation demonstrated two related blockers to a trustworthy unattended soak:

1. A duration-only live-run request silently inherits the generic manager defaults of 500 outbound requests and 100 LLM calls. The 30-minute test therefore stopped after about 21 minutes on request-budget exhaustion, and its terminal batch observed 515 requests against the capped 500-request ledger.
2. Location attribution is truthful, but learning is not converging quickly enough. All 366 location-conditioned strategies retained zero conditioned openings, yet distinct strategy/query identities prevented that repeated evidence from producing a downweighted family or visible reallocation during the run.

Implemented correction:

1. Add `--max-requests` and `--max-llm-calls` to `scripts/run_job_scout_live.py` and send them in the session `resource_policy`.
2. Echo and persist every effective run ceiling at startup: duration, outbound requests, LLM calls, and full-score limit.
3. Make terminal output/reporting distinguish duration completion, request exhaustion, and LLM exhaustion without requiring checkpoint archaeology.
4. Move request admission ahead of fetch execution, or provide equivalent accounting that never exceeds the declared request ceiling under bounded concurrency.
5. Define a stable, durable source/query/location hypothesis-family identity and accumulate equivalent-strategy evidence there.
6. Let repeated zero local-opening yield lower future family allocation while maintaining bounded exploration and separately preserving employer/source discovery value.
7. Surface family attempts, conditioned yield, learned weight, and allocation changes in the discovery audit and durable report.

Do not encode Greensboro, particular roles, employers, or observed false positives as correction rules. The tool must generalize from outcome evidence. A truthful zero-result market remains acceptable; the required behavior is inspectable convergence and reallocation, not a manufactured minimum count.

### Live-gate evidence

The rerun declared 900 seconds, 1,000 requests, 100 LLM calls, and 25 full scores before work started. It completed 43 cycles across 25 waves, consumed and observed exactly 157 requests with zero overrun, used 41 LLM calls, completed 25 full and 58 provisional scores, and retained 58 additional opportunity observations. Manager wind-down began normally near the end of the window and the module stopped explicitly on `admission_draining`.

All 169 attempted location-conditioned families still had zero conditioned opening yield. Eighty-seven were now durably `deprioritized` or `negative`, including the repeatedly attempted Greensboro/source families. The Greensboro coverage gap remained open, confirming that self-correction changed allocation evidence without manufacturing a local success.

## Completed slice: Issue #53

Issue **#53: Make Job Scout soak completion and convergence truthful** is implemented in `0.12.6` from the evidence produced by run `646a7392-9f77-4420-b9b9-842173473b1e`.

The correction remains general and evidence-driven:

1. `admission_draining` and `admission_closed` mean the module completed its authorized active-work phase successfully; the report separately records `planned_wind_down_reached` and `session_deadline_reached`.
2. `full_score_limit` is a success target. `full_score_failure_limit` bounds failed provider/schema attempts, and checkpoints/reporting preserve attempts, successes, failures, and whether the target was met.
3. Discovery accumulates durable eight-cycle marginal-yield windows. A request-spending window with no new company, career source, or opportunity increments a consecutive low-yield counter and triggers exponential backoff capped at 15 minutes. Any material durable yield resets the consecutive counter; normal exploration selection remains unchanged.
4. The query portfolio adds `local_employer` experiments using evidence-derived company archetypes and configured local-market aliases on broad public web search. These persist companies and career surfaces without making a local opening claim.
5. Live reports retain effective configuration even when inherited from the workspace, summarize request/result/opportunity efficiency, and group local evidence by location, source domain, and hypothesis family.

## Live acceptance evidence

The 15-minute live acceptance ran as:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 900 `
  --max-requests 1000 `
  --max-llm-calls 150 `
  --score-limit 25 `
  --score-failure-limit 10
```

Run `f0214cd8-0151-4f38-bbdb-cc5f4096bd79` passed the Issue #53 gate:

- status `succeeded`, terminal reason `admission_draining`, `duration_completed=true`, `planned_wind_down_reached=true`, and `session_deadline_reached=false`;
- 48 requests consumed and observed, zero request overrun, and 24 LLM calls;
- 15 cycles and 15 waves with one 30-second `low_marginal_yield` backoff, supported by an eight-cycle window containing 29 requests, 32 attempts, and zero new companies, career sources, or opportunities;
- 10 successful full scores from 15 attempts, five failures, target 25, failure ceiling 10, and truthful `target_met=false` at wind-down;
- effective configuration persisted with Greensboro, NC, six target titles, the public-board set, work-arrangement preference, score target, and failure ceiling;
- 213 location families summarized across 793 attempts with zero conditioned yield and 139 downweighted families; three `local_employer` groups were attempted once each and retained as neutral evidence.

No local opening was manufactured, and the short run found no additional opportunity. That is a truthful saturated-market result, not a gate failure.

## Next gate: repeat unattended soak

Run a second four-hour soak with the default 25-failure allowance:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 14400 `
  --max-requests 5000 `
  --max-llm-calls 1000 `
  --score-limit 100 `
  --score-failure-limit 25
```

Validate exact resource accounting, multiple low-yield backoff windows and their reset after any durable yield, successful-score target/failure-ceiling semantics, and accumulated local-employer family evidence. A truthful zero local-opening count remains acceptable.

## Deferred follow-up

- Automatic model installation and separately opt-in automatic removal belong to later Model Lab slices.
- External/public benchmark ingestion and blinded pairwise A/B review remain later Model Lab work.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.
- Firecrawl is not a core dependency while local parsing, caching, and source-health tracking cover the need.
- Do not export career prompts, benchmark prompts, results, or traces to LangSmith by default.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond loop.
- Source-aware query portfolios, query linting, explicit coverage gaps, and convergence semantics from Issue #43.
- Qualification-importance semantics from Issue #45: employer-side weight is independent of candidate fit, duplicates cannot inflate evidence, and factual gates remain separate.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- Model Lab production/experimental evidence isolation from Issue #47.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary; domain ordering remains `direct > adjacent > transferable > mismatch`.
- Deterministic, explainable location semantics from Issue #40.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.

## Coding-agent reset path

For Issue #53 continuation, start with:

```powershell
python scripts/agent_context.py --focus "job scout soak completion convergence local auditability" --issue 53
```

Read the generated packet and Issue #53 first. Use `scripts/run_job_scout_live.py` with explicit ceilings and inspect its durable report before changing behavior. Preserve the accepted manager/module boundary, exploration floor, and location-evidence separation.

## Validation boundary

Issue #53 has deterministic coverage for successful-score replacement and failure ceilings, planned wind-down completion semantics, marginal-yield backoff, evidence-derived local-employer queries, effective configuration propagation, efficiency summaries, and grouped location-family audit evidence. Its short live gate passed; the repeat unattended soak is operational follow-up rather than a blocker to merging the slice.
