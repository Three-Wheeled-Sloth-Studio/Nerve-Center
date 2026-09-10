---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch; return the active checkout to `dev` after merging a topic branch.
- Accepted `dev` after PR #48 is `fdca1c1075f3d1bfb2e8b79d7644abfa2fdbbed1`.
- Application version remains `0.12.4`.
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

## Active gate: Issue #49

Issue **#49: Run Job Scout short live acceptance before unattended soak** is the next checkpoint.

This is intentionally an observation gate, not another feature slice. Run one 15-30 minute real-world Job Scout diagnostic against the accepted behavior using `scripts/run_job_scout_live.py`. Prefer the existing durable Job Scout workspace/configuration and local data directory rather than changing inputs merely to make the test easier.

The run should establish whether:

1. source-aware query portfolios remain materially different instead of collapsing into superficial rewrites;
2. explicit coverage gaps produce useful re-expansion without repetitive reflection churn;
3. known structured ATS sources receive sensible direct refresh/deepening treatment;
4. location-conditioned strategy yield remains truthful;
5. deterministic location/ranking reinterpretation avoids unnecessary LLM work when existing fit evidence is still valid;
6. qualification importance and duplicate-credit suppression remain reconstructable in real retained opportunities;
7. reflection stays bounded and evidence-triggered;
8. scoring throughput does not starve discovery or build an unhealthy queue;
9. request/resource accounting remains bounded with explicit reconstructable stop reasons;
10. source challenge/throttle/degradation and cooldown behavior remain observable and sane;
11. the durable diagnostic report is sufficient to explain a failure without rerunning blindly.

### Long-run decision rule

If Issue #49 has no blocking finding, proceed directly to a **4-8 hour unattended Job Scout soak** on the same accepted behavior. Do not insert another feature slice merely because the short run reveals optional tuning opportunities.

Block the soak only for demonstrated operational defects such as uncontrolled resource/request growth, queue deadlock or sustained unhealthy buildup, scoring starvation, premature unexplained discovery termination, materially wrong local-yield attribution, repetitive/unbounded reflection that prevents useful exploration, or diagnostics too weak to explain failure.

Expected source throttles/challenges with correct cooldown behavior, retained distant roles, individual low-yield query families, bounded fallback-model use, and ranking-quality tuning observations are not by themselves blockers.

## Deferred follow-up

- Per-fetch request-budget admission/recovery hardening remains evidence-triggered if Issue #49 or the later soak shows the known batch-level discrepancy is operationally harmful.
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

For Issue #49, start with:

```powershell
python scripts/agent_context.py --focus "job scout live acceptance long run soak query diversity coverage gaps queue accounting" --issue 49
```

Read the generated packet and Issue #49 first. This checkpoint should not require broad implementation rereads. Inspect `scripts/run_job_scout_live.py`, the current durable Job Scout configuration/report surfaces, and only the runtime/discovery/scoring code needed to explain observed evidence.

## Validation boundary

Issue #49 is intentionally outside deterministic CI because its purpose is to observe live public-source and local-model behavior. Do not weaken or replace ordinary deterministic tests. If the short run demonstrates a blocker requiring code changes, implement the smallest correction through normal issue -> branch -> tests -> PR -> CI -> merge discipline, then rerun the short live gate before the unattended soak.
