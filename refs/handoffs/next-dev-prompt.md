---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for continuing the Job Scout self-improving discovery implementation from the current Nerve Center dev baseline.
status: stable
tags: [nerve-center, handoff, job-scout, discovery]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch using normal issue -> branch -> implementation -> tests -> PR -> CI -> merge discipline.

The immediate tracking issue is **#34: Keep Job Scout productive through the full work session and interleave scoring**.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout continuous session discovery scoring reflection re-expansion" --issue 34
```

Treat that generated packet as the initial orientation. Read issue #34 and then only the code/docs identified by the packet or by direct implementation evidence. Do not re-derive accepted architecture decisions.

## Reproduction and observed failure

A real local run was launched with:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --score-limit 25
```

It performed a few minutes of discovery, then stopped useful Job Scout work and waited for the eight-hour manager window to close. Candidates found during discovery were not fully scored during the active window, and the expected search-expansion loop did not resume.

## Intended behavior

During an authorized work window Job Scout should continuously use available time and resource budget approximately as:

`search -> identify companies/roles -> persist and score -> reflect/broaden -> search again`

The exact implementation may batch those responsibilities, but the observable behavior must remain productive while manager admission is open. One empty reflection or one exhausted set of currently eligible strategies is not permission to sleep until the session ends.

The double-diamond product intent remains accepted:

`expand -> converge -> deepen -> reflect -> re-expand`

Discovery optimizes recall. Ranking/scoring provides precision. Listed title is only a weak fit clue; responsibility/requirement evidence and domain relationship remain authoritative for fit.

## Confirmed code findings

Do not spend a reset rediscovering these:

1. `scripts/run_job_scout_live.py::monitor_session()` waits for the Job Scout run to become terminal, then waits for the manager session itself to become terminal. `score_candidates()` is called only after `monitor_session()` returns. That directly defers scoring until the end of a long manager window when discovery ends early.
2. `src/nerve_center/plugins/job_scout/worker.py::_execute_discovery_loop()` completes the run as `succeeded` when a manager-routed reflection adds zero new strategies, even if hours remain in the run deadline.
3. `JobScoutDiscoveryRepository.select_strategies()` excludes every strategy already attempted under the same `run_id`. Therefore simply deleting the early-success branch will create repeated empty reflection/no-work behavior rather than a healthy second wave.
4. `WorkSessionService.start()` creates one fixed-window run per enabled module and does not replace an early-terminal Job Scout run during the same manager session.
5. `RunnerService` gives the Job Scout fixed run the full manager-session deadline. The premature stop is therefore Job Scout/runtime semantics, not generic scheduler timeout.

## Implementation objective

Implement the smallest coherent correction that preserves generic manager boundaries and makes Job Scout productive for the authorized session.

Expected shape:

- keep the Job Scout module run alive while manager admission is open unless a real terminal condition is reached;
- introduce bounded discovery waves/epochs or an equivalent attempt-eligibility model;
- prevent an identical strategy from hot-looping immediately, while allowing later reuse/revisit after materially new state, cooldown, changed dimensions, new reflection evidence, or appropriate source/company revisit eligibility;
- re-seed/refresh candidate work between waves from newly persisted companies, career sources, due sources, reflection hypotheses, and other durable market state;
- persist new openings promptly;
- perform deterministic/provisional scoring promptly and bounded full fit/scoring during the active session rather than only after shutdown;
- keep Job Scout model-blind: any LLM-backed reflection or fit/scoring must continue through manager-owned provider/scoring boundaries;
- preserve separate discovery-learning and ranking-feedback semantics;
- expose wave/cycle, newly retained jobs, newly scored jobs, reflection outcome, next-work decision, consumed/remaining request and LLM budget where available, idle/backoff reason, and terminal reason;
- stop on draining/closed admission, deadline, cancellation, request/LLM budget exhaustion, or a bounded explicit no-work decision after refresh/backoff attempts;
- use paced cooldown/backoff rather than a busy loop when no immediate productive work exists.

Prefer keeping the repeated-work semantics inside Job Scout rather than teaching generic Nerve Center scheduling about jobs. Change core scheduling only if a concrete generic lifecycle defect makes that necessary.

## Likely code surface

Start with targeted reads of:

- `scripts/run_job_scout_live.py`
- `src/nerve_center/plugins/job_scout/worker.py`
- `src/nerve_center/plugins/job_scout/discovery_learning.py`
- `src/nerve_center/plugins/job_scout/discovery_loop.py`
- `src/nerve_center/plugins/job_scout/runtime.py`
- `src/nerve_center/scheduler/sessions.py`
- `src/nerve_center/scheduler/runner.py`
- `src/nerve_center/scoring/service.py`

Then the directly relevant tests only.

## Deterministic acceptance test

Add a regression that simulates a long manager session and proves, without Ollama or live web access, that:

1. discovery wave 1 retains one or more opportunities;
2. those opportunities become scored before the manager session ends;
3. a deterministic and/or LLM reflection returning zero new strategies does not immediately mark the Job Scout run `succeeded` while admission is still open;
4. newly persisted state, bounded re-eligibility, revisit work, or a later reflection enables another productive wave;
5. a second discovery wave executes;
6. identical no-yield work does not spin in a hot loop;
7. final completion is attributable to drain/deadline/budget/cancellation or a bounded explicit no-work state;
8. checkpoint/coverage telemetry makes the sequence and stop reason inspectable.

Also add a focused live-runner regression proving that scoring is not structurally gated on manager-session termination.

## Constraints

- No authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.
- Do not add another provider as a workaround.
- Do not tune ranking weights as a workaround.
- Do not reopen the manager-owned provider/session/queue boundary without direct evidence.
- Keep CI deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites.
- Qualification-importance normalization remains valid follow-up work, but fix issue #34 first.
- Repeated diagnostics or manual inspection patterns should become reusable tools rather than consuming coding-agent tokens repeatedly.

## Validation

Run the commands in `refs/testing/validationCommands.yaml`. After deterministic CI is green, use a shorter real local Job Scout run to demonstrate at least two productive discovery/scoring waves before attempting another overnight evaluation.
