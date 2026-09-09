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
- Application version remains `0.12.4`.
- The manager/module boundary, durable work sessions and queue, provider-neutral LLM manager, Windows desktop/package baseline, career evidence profile, company-first Job Scout discovery, scoring, application tracking, and durable discovery learning are accepted foundations.
- Job Scout resolves aggregator-listed openings to actual hiring companies, protects employer-owned deepening from board-source crowding, persists strategy/yield learning, expands local markets, and implements the component phases of `expand -> converge -> deepen -> reflect`.
- Issue #34 is implemented and live-validated on PR #36: bounded discovery waves, durable revisit cooldowns, and interleaved active-window scoring replace early success after empty reflection.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output requests validate the result and may retry once on `qwen2.5:7b-instruct`; the next general request starts on Gemma again. Job Scout stays model-blind.
- Discovery includes direct Greenhouse, Lever, and Ashby board support, preserves the actual hiring-company identity while deepening ATS sources, and seeds all configured role families before repeating location/source combinations.
- Fit analysis contract v6 validates model-proposed claim links through a reusable semantic evidence matcher, retains claim/evidence provenance, and derives an explicit direct/adjacent/transferable/mismatch domain assessment instead of trusting an unexplained model scalar.
- Ranking engine v3 weights requirement and responsibility coverage directly, limits configured-title influence to a weak +/-3 point clue, and uses source-backed company hiring-location evidence to improve remote-role response ranking when a configured local market matches.
- Opportunity cards open HTTP(S) listings through the Tauri opener and expose the selected application/canonical URL for copying and manual QA.
- The source launcher initializes and validates a complete x64 Visual C++ environment before Tauri compilation. It skips incomplete Visual Studio installations and preserves an already valid developer shell.
- Employer identity resolution rejects weak social/job-board identity hints, preserves unresolved employers safely, and can disambiguate same-name unresolved companies when a stable organization hint exists.
- `scripts/run_job_scout_live.py` is the reusable real-run diagnostic. It reattaches to an actionable durable Job Scout session, records wave/scoring transitions, and returns when the module run terminates. Scoring happens inside the worker's active loop, not after manager shutdown. The runner closes its adopted/created session before stopping its API, including on Ctrl+C.
- Coding-agent context/token conservation is a primary engineering concern. `scripts/agent_context.py` generates a compact reset packet from authoritative refs and git state so agents can load context progressively instead of rereading large unchanged documents.

## Active product correction

Issue **#34: Keep Job Scout productive through the full work session and interleave scoring** is the active PR #36 validation checkpoint.

A live run launched with:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --score-limit 25
```

performed a small amount of discovery, then stopped useful work and waited for the eight-hour manager window to close. It did not fully score the retained candidates during the active window and did not re-enter discovery expansion as intended.

The accepted runtime behavior is:

`search -> identify companies/roles -> persist and score -> reflect/broaden -> search again`

repeating while manager admission remains open and resource budget remains, with bounded cooldown/backoff rather than a hot loop when no immediate work is productive.

### Before: confirmed control-flow causes

1. `scripts/run_job_scout_live.py::monitor_session()` first waits for the Job Scout run to become terminal and then waits for the **manager session** to become terminal before returning. `run()` only calls `score_candidates()` after `monitor_session()` returns, so an early-terminal discovery run can leave scoring deferred for hours.
2. `src/nerve_center/plugins/job_scout/worker.py::_execute_discovery_loop()` explicitly calls `_complete_from_summary(..., "succeeded")` when a manager-routed reflection produces zero new strategies. One empty reflection can therefore terminate the Job Scout run even though the fixed run deadline is the end of the multi-hour manager session.
3. `JobScoutDiscoveryRepository.select_strategies()` excludes every strategy already attempted anywhere in the same `run_id`. Simply removing the early completion would therefore not solve the problem; once the strategy set is exhausted it would repeatedly reach reflection with nothing newly eligible.
4. `WorkSessionService.start()` creates one fixed-window run per enabled module and does not replace an early-terminal Job Scout run with another run while the same manager session remains open.
5. `RunnerService` assigns the Job Scout fixed run the full manager-session deadline, confirming that the premature stop originates in Job Scout/runtime semantics rather than generic scheduler timeout.

These causes are addressed in the implementation below; they are retained here as the before/after evidence, not a description of current branch behavior.

## Implemented runtime semantics

- Each bounded discovery cycle persists discoveries, ensures provisional scores, and attempts at most one full fit analysis before reflection/refresh and another cycle. All retained roles remain discoverable regardless of rank. The durable per-run attempted-ID reservation enforces `--score-limit`, including failed analyses and restart; existing full scores are not needlessly repeated.
- Full analysis uses the existing manager-side `ScoringService` and provider routing through the scoped operation bridge. Reflection uses the manager work queue. No scheduler-specific Job Scout loop, provider change, or ranking-weight change was introduced.
- Known-company and due-source strategies are reseeded each cycle. A persisted public-search attempt cools down for 24 hours; company/source revisit strategies cool down for one hour, and source due timestamps must also permit a scan. New company/source IDs and changed search dimensions yield distinct eligible work. New waves never erase attempt history.
- An empty reflection advances to refresh, not success. LLM reflection is only requested when durable company/source/retained-role/full-score evidence changes. Three no-work backoffs of 30, 60, and 120 seconds each precede another eligibility refresh; continued exhaustion terminates explicitly as `no_work_after_three_refresh_backoffs`.
- Checkpoints expose wave, cycle, coverage, scoring reservations/completions, budget usage/remaining, reflection outcome, next-work decision, idle reason, and terminal reason. Stops distinguish cancellation, deadline, admission drain/close, request/LLM budget exhaustion, no configured evidence, bounded no-work, and reflection timeout.
- The final authorized reflection call can return and be harvested before LLM budget exhaustion prevents the next admission.

## Validation and remaining risks

- Local canonical validation passed: tracked-path guard, refs indexes/validation, context packet, Ruff, Python tests, desktop web build, and Rust test compilation. Deterministic tests use real SQLite discovery/scoring persistence plus fake public sources, clock, and provider; CI has no live-service dependency. The packaged empty-workspace smoke now requires the exact partial `no_configured_evidence_or_market` stop instead of the previous generic success.
- Regressions prove retained/scored wave 1 precedes empty reflection and useful company-revisit wave 2 while admission is open, paced exhaustion without unchanged repeated reflection, durable cooldowns across repository/run restart, scoring reservation cap on restart, final-call harvesting, explicit request-budget stop, and runner return without waiting for manager termination.
- Request accounting remains at discovery-batch granularity. A bounded batch can exceed the remaining request allowance; `requests_observed` and `request_batch_overrun` make that explicit while the reservation ledger remains capped. Per-fetch admission is a future hardening slice, not a strict per-HTTP ceiling claim.
- In-flight source/scoring operations may finish after admission changes; control is checked between bounded operations and during reflection/backoff waits. Full scoring reservations are conservative on crash: an interrupted attempt is not automatically retried in the same run.
- Hosted CI and Windows packaging pass. A 900-second live acceptance run completed all three allowed full analyses during the open session, continued through 20 waves, and stopped explicitly on request-budget exhaustion.

## Next slice

After merging PR #36 to `dev`, follow with per-fetch budget admission/recovery hardening if real evidence requires it; otherwise resume qualification-importance normalization and ranking-quality work.

The previous qualification-importance normalization/ranking-quality work remains valid but is deferred until this liveness defect is corrected. Do not tune ranking weights as a workaround for the control-loop problem.

## Latest live evidence

- The 8-hour run above is the pre-fix runtime failure: early discovery termination plus deferred scoring left most of the authorized window idle.
- The post-fix 900-second run (`da004e4a-8b1b-4723-8ea2-5dcdded6f724`) performed 89 cycles across 20 waves, attempted 356 strategies, discovered 49 companies and 70 career sources, retained 121 opportunities, and created 212 provisional plus 3/3 bounded full scores. It crossed added and empty reflection outcomes and kept discovering afterward. It stopped `partial` with `requests_budget_exhausted` after 500 reserved/502 observed requests; the two-request batch overrun was exposed. Two provider warnings recorded public-search cooldown/unavailability without failing the run.
- The durable inventory previously contained 151 roles across 96 companies and 579 sources; broad market state exists, so the failure is not simply lack of durable discovery material.
- A 20-role v6 sample previously completed 20/20 fit analyses on `gemma3:4b` with explicit domain results: 2 direct, 1 adjacent, 5 transferable, and 12 mismatch.
- Reflection evidence demonstrates the strict-schema fallback lane: Gemma remains primary, while failed reflection schemas can retry successfully on `qwen2.5:7b-instruct`.
- Direct-employer listing locations build durable company-presence evidence with source URLs; generic remote/nationwide labels and aggregator-only evidence do not establish local presence.

## Do not reopen without new evidence

- Company-first discovery as the product architecture and the double-diamond loop; PR #36 repairs its full-session liveness rather than changing the architecture.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Responsibility/requirement evidence is primary for fit; listed title is only a weak clue. Domain ordering remains direct > adjacent > transferable > mismatch.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or outreach.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.

## Coding-agent reset path

For issue #34, start with:

```powershell
python scripts/agent_context.py --focus "job scout continuous session discovery scoring reflection re-expansion" --issue 34
```

Use the generated packet, issue #34, and its file-map hints first. The highest-value code reads are expected to be:

- `scripts/run_job_scout_live.py`
- `src/nerve_center/plugins/job_scout/worker.py`
- `src/nerve_center/plugins/job_scout/discovery_learning.py`
- `src/nerve_center/plugins/job_scout/discovery_loop.py`
- `src/nerve_center/scheduler/sessions.py`
- `src/nerve_center/scheduler/runner.py`
- `src/nerve_center/scoring/service.py`
- `tests/test_job_scout_discovery_loop.py`
- `tests/test_job_scout_discovery_learning.py`
- `tests/test_live_runner_progress.py`
- `tests/test_sessions.py`

Read deeper architecture/history only if the packet or implementation evidence requires it. Do not re-derive accepted decisions.

## Validation boundary

Run required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites. The live 8-hour failure must gain deterministic control-flow regressions before promotion; a shorter real local run may then validate the repaired behavior without making live services a CI requirement.
