---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the bounded Job Scout live acceptance gate before an unattended soak.
status: stable
tags: [nerve-center, handoff, job-scout, live-test, soak]
---
# Next Development Prompt

Continue work in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch. The accepted baseline after Model Lab PR #48 is:

`fdca1c1075f3d1bfb2e8b79d7644abfa2fdbbed1`

The immediate tracking issue is **#49: Run Job Scout short live acceptance before unattended soak**.

This is a bounded real-world acceptance checkpoint, not a new feature slice.

## Bounded re-entry

Do not reread repository history or all planning documents.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout live acceptance long run soak query diversity coverage gaps queue accounting" --issue 49
```

Treat that generated packet plus Issue #49 as the initial orientation. Inspect `scripts/run_job_scout_live.py`, the current durable Job Scout workspace/configuration, and only the source paths needed to interpret observed behavior.

## Current accepted baseline

Issues #34, #40, #43, #45, and #47 are complete. Preserve:

- manager-owned provider/session/queue boundaries and module model blindness;
- durable provider model catalog plus task-specific success, schema-validity, latency, and acceptance observations;
- Model Lab benchmark evidence isolated from production routing evidence;
- Job Scout `expand -> converge -> deepen -> reflect -> re-expand` behavior;
- company-first source deepening and durable discovery learning;
- source-aware bounded query portfolios and deterministic pre-request query linting;
- explicit discovery coverage gaps and gap-driven reflection;
- convergence provenance affecting company/source deepening, never opportunity fit truth;
- broad opportunity retention with ranking providing precision;
- responsibility/requirement-first fit with title as a weak clue;
- explicit `direct > adjacent > transferable > mismatch` domain relationship;
- deterministic location scope from raw listing evidence and configured markets;
- fit-analysis v7 employer-side decision weighting independent of candidate match strength;
- ranking v5 weighted qualification coverage with duplicate-credit suppression and reconstructable factors;
- factual license/clearance gates remaining separate from soft weighted mismatches.

Do not reopen these without evidence from the live run.

## Accepted validation entering this checkpoint

PR #48 exact head `8119e5cf577fa1f1d19ce8afe7fdbf4740ac864d` passed:

- CI `34502474954` / #250;
- 192 Python tests, 0 failures;
- desktop-web and desktop-rust;
- Windows package `34502474968` / #134;
- packaged backend health, Job Scout workspace route, managed runtime smoke, NSIS bundle, and artifact upload.

The short live gate exists because deterministic CI cannot establish real search-source behavior, local-model throughput, cooldown interactions, long-enough reflection behavior, or real resource-accounting stability.

## Execution objective

Run one **15-30 minute** real-world Job Scout diagnostic using the accepted reusable runner. The runner defaults to 1800 seconds, so the ordinary path is:

```powershell
python scripts/run_job_scout_live.py --duration-seconds 1800
```

Prefer the existing durable Job Scout workspace and configured local data directory. Add `--report`, `--resume`, `--target-title`, or `--location` only when the local environment actually requires them. Do not rewrite good durable configuration just to produce a cleaner test.

The runner already owns a loopback API when needed, resumes actionable Job Scout sessions, checkpoints progress, records transition history, interleaves scoring, and writes a durable local report.

## Acceptance questions

Use the run evidence to answer all of these:

1. Are materially different query families actually being attempted, or are they collapsing into trivial rewrites?
2. Do uncovered role/domain/location/work-arrangement/source gaps lead to useful re-expansion?
3. Does reflection stay bounded and evidence-triggered rather than repetitive?
4. Are known healthy structured ATS sources refreshed/deepened sensibly?
5. Is location-conditioned yield truthful, with distant/national openings excluded from local productivity credit?
6. Are deterministic location/ranking reinterpretations reusing existing fit evidence rather than needlessly creating new LLM work?
7. Do qualification-importance and duplicate-credit rules remain reconstructable on real opportunities?
8. Does scoring progress without starving discovery or causing sustained queue growth?
9. Are request/resource counts bounded and stop reasons explicit?
10. Are source challenges, throttles, degradation, cooldowns, and revisits visible and sane?
11. Is the generated report sufficient to explain a bad outcome without immediately rerunning the workload?

## Soak blocker definition

Block a 4-8 hour unattended run only if this diagnostic demonstrates one of these operational defects:

- uncontrolled request/resource growth or materially unsafe budget overrun;
- queue deadlock, sustained unhealthy buildup, or scoring starvation;
- premature discovery termination without a justified explicit stop reason;
- materially incorrect local-yield attribution;
- repetitive/unbounded reflection or strategy collapse that prevents useful re-expansion;
- diagnostics too weak to reconstruct why the run failed or stopped.

Do **not** block merely for expected throttles/challenges with correct cooldown behavior, retained distant roles, one low-yield query family, bounded fallback-model use, or ranking-quality tuning opportunities that do not threaten liveness/accounting/explainability.

The previously observed roughly two-request batch-level discrepancy is not automatically a blocker. Escalate it only if the new live evidence shows operationally harmful or unbounded behavior.

## Decision rule

- If the short run has **no blocker**, proceed directly to a **4-8 hour unattended Job Scout soak** on the same accepted code/configuration. Do not insert another feature slice first.
- If the short run has a **blocker**, identify the smallest demonstrated cause, implement only that correction using normal issue -> branch -> tests -> PR -> CI -> merge discipline, then rerun Issue #49 before soaking.

## Evidence to preserve

Keep the runner's durable report and record at minimum:

- accepted `dev` SHA;
- session/run IDs and duration;
- terminal status and reason;
- cycles/waves and strategies attempted;
- companies, career sources, postings, and retained opportunities;
- provisional/full score counts;
- request and LLM budget/accounting totals;
- reflection transitions/outcomes;
- source warnings/challenges/throttles;
- coverage-gap and query-family observations;
- queue behavior;
- explicit pass/fail decision for the unattended soak.

Do not commit private resume content, local reports containing personal data, or provider/runtime secrets to the public repository. Summarize privacy-safe acceptance evidence in Issue #49.
