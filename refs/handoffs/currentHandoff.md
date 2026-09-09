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
- **Full-session discovery liveness is not currently implemented correctly.** An 8-hour live run demonstrated that Job Scout can finish its module run after only a few minutes and leave the manager session idle for the remainder of the window.
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output requests validate the result and may retry once on `qwen2.5:7b-instruct`; the next general request starts on Gemma again. Job Scout stays model-blind.
- Discovery includes direct Greenhouse, Lever, and Ashby board support, preserves the actual hiring-company identity while deepening ATS sources, and seeds all configured role families before repeating location/source combinations.
- Fit analysis contract v6 validates model-proposed claim links through a reusable semantic evidence matcher, retains claim/evidence provenance, and derives an explicit direct/adjacent/transferable/mismatch domain assessment instead of trusting an unexplained model scalar.
- Ranking engine v3 weights requirement and responsibility coverage directly, limits configured-title influence to a weak +/-3 point clue, and uses source-backed company hiring-location evidence to improve remote-role response ranking when a configured local market matches.
- Opportunity cards open HTTP(S) listings through the Tauri opener and expose the selected application/canonical URL for copying and manual QA.
- Employer identity resolution rejects weak social/job-board identity hints, preserves unresolved employers safely, and can disambiguate same-name unresolved companies when a stable organization hint exists.
- `scripts/run_job_scout_live.py` is the reusable real-run diagnostic. It reattaches to an actionable durable Job Scout session after manager restart and continuously checkpoints JSON, but its current sequencing defers `score_candidates()` until after the manager session itself closes.
- Coding-agent context/token conservation is a primary engineering concern. `scripts/agent_context.py` generates a compact reset packet from authoritative refs and git state so agents can load context progressively instead of rereading large unchanged documents.

## Active product correction

Issue **#34: Keep Job Scout productive through the full work session and interleave scoring** is now the immediate priority.

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

### Confirmed control-flow causes

1. `scripts/run_job_scout_live.py::monitor_session()` first waits for the Job Scout run to become terminal and then waits for the **manager session** to become terminal before returning. `run()` only calls `score_candidates()` after `monitor_session()` returns, so an early-terminal discovery run can leave scoring deferred for hours.
2. `src/nerve_center/plugins/job_scout/worker.py::_execute_discovery_loop()` explicitly calls `_complete_from_summary(..., "succeeded")` when a manager-routed reflection produces zero new strategies. One empty reflection can therefore terminate the Job Scout run even though the fixed run deadline is the end of the multi-hour manager session.
3. `JobScoutDiscoveryRepository.select_strategies()` excludes every strategy already attempted anywhere in the same `run_id`. Simply removing the early completion would therefore not solve the problem; once the strategy set is exhausted it would repeatedly reach reflection with nothing newly eligible.
4. `WorkSessionService.start()` creates one fixed-window run per enabled module and does not replace an early-terminal Job Scout run with another run while the same manager session remains open.
5. `RunnerService` assigns the Job Scout fixed run the full manager-session deadline, confirming that the premature stop originates in Job Scout/runtime semantics rather than generic scheduler timeout.

This is therefore not a one-line runner fix. The implementation needs bounded repeated discovery waves/epochs or an equivalent re-eligibility model, plus active-window scoring.

## Next implementation slice

1. Start from issue #34 and preserve the generic manager/module boundary; do not add Job Scout-specific loop logic to core scheduling unless evidence proves the module cannot own it.
2. Keep the Job Scout run alive and productive while admission is open. One empty reflection is a next-work signal, not successful completion.
3. Add a bounded wave/epoch or equivalent strategy-attempt scope so strategies are not immediately repeated with identical inputs but can become eligible after new company/source state, materially changed dimensions, cooldown, or deliberate revisit conditions.
4. Re-seed/refresh strategy candidates at wave boundaries using newly persisted companies, sources, due revisits, reflection hypotheses, and other durable market state.
5. Interleave persistence and scoring of newly retained opportunities during the active window. Deterministic/provisional scoring should be prompt; bounded full fit/scoring should use existing manager-owned provider/scoring boundaries and must keep Job Scout model-blind.
6. Make live-runner monitoring report productive waves and scoring as they happen rather than waiting for wall-clock shutdown before scoring.
7. Add deterministic regression coverage for a long session in which wave 1 finds jobs, scoring completes before session end, an empty reflection does not terminate the run, a later wave executes, and final completion is attributable to drain/deadline/budget/cancel or a bounded explicit no-work condition.
8. Prevent busy loops: repeated no-work/reflection outcomes must back off or cooldown and expose the next-work reason instead of rapidly consuming requests or LLM budget.
9. Preserve request/LLM budget accounting and expose wave, scoring, remaining-budget, reflection, idle, and stop telemetry.

The previous qualification-importance normalization/ranking-quality work remains valid but is deferred until this liveness defect is corrected. Do not tune ranking weights as a workaround for the control-loop problem.

## Latest live evidence

- The 8-hour run above is the authoritative current runtime failure: early discovery termination plus deferred scoring left most of the authorized window idle.
- The durable inventory previously contained 151 roles across 96 companies and 579 sources; broad market state exists, so the failure is not simply lack of durable discovery material.
- A 20-role v6 sample previously completed 20/20 fit analyses on `gemma3:4b` with explicit domain results: 2 direct, 1 adjacent, 5 transferable, and 12 mismatch.
- Reflection evidence demonstrates the strict-schema fallback lane: Gemma remains primary, while failed reflection schemas can retry successfully on `qwen2.5:7b-instruct`.
- Direct-employer listing locations build durable company-presence evidence with source URLs; generic remote/nationwide labels and aggregator-only evidence do not establish local presence.

## Do not reopen without new evidence

- Company-first discovery as the product architecture. The **intent** of the double-diamond loop is accepted; its current full-session liveness implementation is not.
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
