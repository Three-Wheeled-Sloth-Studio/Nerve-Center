---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the bounded Job Scout employer-reference source-acquisition correction.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work directly on `dev`. Do not create a feature branch or PR unless explicitly requested.

Start from the latest clean `dev` head. The accepted green implementation baseline before the latest documentation-only refresh is:

`fd6bc92838999ff144d9f5ec7369995fb340de4a`

Nerve Center version is `0.12.14`.

The active tracking issue is **#57: Stratify Job Scout market exploration after regional live gate**. Leave it open until runtime acceptance is satisfied.

## Start with bounded re-entry

Do not reread repository history.

First run:

```powershell
python scripts/agent_context.py --focus "job scout local employer reference query intent fallback cooldown run scoped audit" --issue 57
```

Treat that generated packet as derived orientation, not source of truth. Read at minimum:

1. `refs/handoffs/currentHandoff.md`
2. Issue #57 and its newest runtime comment
3. `src/nerve_center/plugins/job_scout/query_portfolio.py`
4. `src/nerve_center/plugins/job_scout/attachment_discovery.py`
5. only the relevant reference-acquisition section of `src/nerve_center/plugins/job_scout/discovery_loop.py`
6. `src/nerve_center/plugins/job_scout/bootstrap.py`
7. directly relevant deterministic tests

Do not reload unrelated scoring, UI, Model Lab, packaging, or repository history unless a failing test makes it necessary.

## Latest runtime evidence

Authoritative live run:

`dcee77be-53c7-416a-be7c-b518f2240378`

Runtime was operationally healthy:

- version `0.12.14`;
- status `succeeded` via planned `admission_draining`;
- 92 requests and 30 LLM calls; neither budget exhausted;
- 20/20 full scores completed with zero failures;
- 20 public searches, 200 returned results, 56 eligible/registered sources;
- 15 civic reference pages inspected, 14 cache hits, 8 retry-deferred references;
- 2 cached attachment documents parsed, 0 invalid;
- 0 employer candidates and no current-run `local_employer_deepen` execution.

Filter live reference evidence to this run ID. The report currently includes 64 recent rows spanning three runs: 20 current rows plus 23 from `aa6a3579-6b34-4642-885e-20473a8270b3` and 21 from `4b5ad2ea-df90-4237-8d62-e45ec7f1216c`.

The 20 current-run local-employer attempts split evenly between `major employers` and `company headquarters` across Durham-Chapel Hill, Mount Airy, Danville, Sanford, Winston-Salem, and Martinsville market aliases/core places.

Current-run civic acquisition:

- 23 references selected;
- 15 inspected;
- 8 retry-deferred;
- `major employers`: 20 selected, 12 inspected, 8 deferred;
- `company headquarters`: 3 selected/inspected;
- zero extracted employer candidates.

## Diagnosis

The selector is now observable and the parser is behaving safely. The remaining blocker is generic source acquisition quality.

### Query dilution

`compile_strategy_query()` currently emits this local-employer query for the `major employers` anchor:

`<market> major employers chamber economic development`

The current run overwhelmingly returned generic economic-development/chamber pages, usually intent tier 3. Authority should remain a post-search ranking/provenance signal instead of mandatory query vocabulary.

Prior-run evidence proves the intent ranker works when a high-intent result exists: `Major Employers - Durham Economic Development` ranked at intent tier 0, but that source was `retry_deferred`.

### Poor civic references for `company headquarters`

Municipal `Employment Opportunities`/HR pages are being admitted as civic employer-landscape references. They are legitimate pages but not useful evidence about local companies. Direct employer career pages must remain untouched on the ordinary non-civic path.

### Deferred-reference fallback is artificially narrow

`_IntentAwareReferenceAdapter` returns only the top two civic candidates plus non-civic results. The base reference loop already skips `retry_deferred` references before incrementing `references_acquired`, but cannot inspect a third civic candidate because preselection removed it.

A bounded fallback pool can improve useful acquisition without increasing the acquired-reference cap, but add an explicit network-attempt ceiling so challenges/failures cannot create unbounded work.

### Audit needs run scoping

`_recent_reference_attempt_evidence()` is bounded by recency, not by `run_id`. Rows are attributable, but live acceptance should not require manual filtering across previous runs.

## Implement this bounded slice

### 1. Make local-employer queries intent-pure

For `major employers`, stop requiring generic authority terms like `chamber economic development` in the query.

Use a small deterministic employer-list vocabulary, for example concepts equivalent to:

- `major employers`
- `largest employers`
- `top employers`
- employer/business directory/list evidence

Keep variants bounded and attributable. If strategy dimensions/revision must change so durable learning does not conflate old and new query behavior, do that generically.

Authority remains part of reference rank/provenance after retrieval.

### 2. Harden civic-reference eligibility

For employer-landscape extraction, generically down-rank or exclude obvious civic self-employment/HR results such as municipal `Employment Opportunities`, jobs, or careers pages unless the result also carries clear employer/business landscape intent.

Do not suppress direct employer career results; those remain ordinary discovery inputs.

### 3. Add bounded fallback after deferred/invalid references

Preserve more than two ranked civic *candidates* while keeping hard execution bounds:

- maximum 2 successfully acquired/inspected references per attempt;
- explicit maximum network reference-fetch attempts per attempt;
- cached `retry_deferred`/invalid candidates do not consume the acquired-reference slot;
- fallback may continue to the next ranked eligible civic candidate only while caps allow.

Do not weaken cache/cooldown semantics and do not retry challenged sources early.

### 4. Run-scope reference attempt evidence

Make the live discovery audit expose current-run `reference_attempt_evidence` by default, or add/pass an explicit `run_id` filter.

Preserve bounded output and row-level `run_id` for auditability.

### 5. Add deterministic fictional tests

At minimum prove:

- employer-list query compilation does not require generic authority vocabulary;
- a generic government HR/employment page cannot outrank an actual employer-landscape reference;
- a retry-deferred first candidate falls through to a later eligible civic candidate without exceeding acquired-reference or network-attempt caps;
- run-scoped audit evidence excludes attempts from other runs;
- raw `search_results_returned` telemetry remains truthful;
- no named city/employer rule is introduced.

## Preserve these constraints

- No Wolfspeed, Volvo, Durham, Greensboro, or other named entity logic in production behavior.
- Responsibility/requirement-first opportunity fit and `direct > adjacent > transferable > mismatch` domain scoring remain untouched.
- Keep LinkedIn and authenticated job-board safety boundaries unchanged.
- Extracted employer names become `local_employer_deepen` hypotheses only; they never become company/location truth directly.
- Official-career resolution remains the path from employer hypothesis to durable company/source evidence.
- Do not retune scoring or model selection in this slice; the latest run had 20/20 successful full scores.
- Keep coding-agent context use bounded and token-efficient.

## Validation

Run normal repository verification and exact-head CI. Preserve generated OKF indexes when handoff metadata changes.

After deterministic validation, update:

- `refs/handoffs/currentHandoff.md`
- `refs/handoffs/next-dev-prompt.md`
- Issue #57 with exact commits/SHA, tests, and CI evidence

Do not close Issue #57 yet.

## Next live gate

After the code is green, request the same explicit-budget local rerun:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 900 `
  --max-requests 1000 `
  --max-llm-calls 150 `
  --score-limit 25 `
  --score-failure-limit 10
```

Acceptance should require the report itself to show:

1. current-run-only reference attempt evidence;
2. at least one high-intent employer-list/directory reference selected and inspected, or truthfully deferred with bounded fallback;
3. valid employer names create provenance-bearing `local_employer_deepen` hypotheses when the source actually contains such names;
4. at least one valid deepening hypothesis reaches ordinary official-career discovery when available;
5. request/LLM accounting and scoring remain healthy.

Representative companies remain observational probes only. Their individual presence or absence is not a production rule.
