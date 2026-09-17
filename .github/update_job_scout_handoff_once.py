from pathlib import Path

current_path = Path("refs/handoffs/currentHandoff.md")
current = current_path.read_text(encoding="utf-8")

old_state = "- The current local-acquisition checkpoint is `8d7f9477caec1874d8cd5f81d1f6b709100f073d`. The live gate now pins the checkout source and reports exact runtime identity; reserved regional/local/deepening lanes are proven reachable under that exact runtime; stale pre-fix non-attachment employer hypotheses are excluded unless they carry current `employer_landscape_v2` evidence semantics, while legacy/normalized PDF-OCR attachment evidence remains eligible. Targeted validation passed in workflow `35256387208`; full clean-head CI is required before the next live gate."
new_state = "- The current local-acquisition checkpoint is `1c50972bbd84d072c3c21fa63a163770d26638c5`. Exact-runtime gates are pinned to the checkout source; regional/local/deepening reservations are proven reachable; canonical deepening now prefers normalized attachment/current-revision evidence over older equivalent legacy rows; and DuckDuckGo bot/challenge HTML is classified as challenged instead of a valid zero-result search. Targeted validation passed in workflow `35262867619`; full clean-head CI is required before the next live gate."
if old_state not in current:
    raise SystemExit("current-state checkpoint line not found")
current = current.replace(old_state, new_state, 1)

old_behavior = "22. persisted non-attachment `local_employer_deepen` strategies are schedulable only when they carry the current `employer_landscape_v2` evidence revision; legacy and normalized attachment/PDF-OCR evidence remains eligible, and current evidence wins canonical identity over stale equivalents."
new_behavior = "22. persisted non-attachment `local_employer_deepen` strategies are schedulable only when they carry the current `employer_landscape_v2` evidence revision; legacy and normalized attachment/PDF-OCR evidence remains eligible.\n23. canonical deepening resolves equivalent durable employer hypotheses by evidence-semantics priority so normalized attachment/current-revision evidence outranks older legacy PDF/OCR rows before cooldown is applied; DuckDuckGo bot/challenge HTML is reported as challenged rather than cached as a legitimate zero-result search, while ordinary empty HTML remains non-challenged."
if old_behavior not in current:
    raise SystemExit("accepted behavior checkpoint not found")
current = current.replace(old_behavior, new_behavior, 1)

implementation_anchor = "- `8d7f9477caec1874d8cd5f81d1f6b709100f073d`: durable employer-landscape evidence revisioning; stale unversioned non-attachment deepening rows are excluded from scheduling, current evidence is preferred during canonical dedup, and legacy/normalized attachment/PDF-OCR evidence remains eligible. Targeted validation workflow `35256387208` passed Ruff, discovery-learning/loop tests, and deterministic source-catalog validation."
implementation_addition = implementation_anchor + "\n- `1c50972bbd84d072c3c21fa63a163770d26638c5`: equivalent `local_employer_deepen` strategies now use evidence-semantics priority during canonical public-search dedup, allowing normalized attachment/current evidence to bypass an older equivalent row's cooldown. `HttpFetcher` also detects DuckDuckGo bot/challenge response language without treating an ordinary empty DuckDuckGo HTML page as challenged. Targeted validation workflow `35262867619` passed Ruff, discovery-learning/connectors tests, and deterministic source-catalog validation."
if implementation_anchor not in current:
    raise SystemExit("implementation anchor not found")
current = current.replace(implementation_anchor, implementation_addition, 1)

insert_anchor = "\n## Regional saturation checkpoint\n"
latest_section = '''

## Post-evidence-revision five-minute gate

Run `6b582fdf-dba9-43fe-9929-576a97e6ffa8` completed the requested five-minute gate from exact checkout `267dd6c16cae70a942ca8e42131e8cf02604b41e`: `runtime_identity.uses_checkout_source=true`, the imported module resolved `D:\\Apps\\Nerve-Center\\src`, and the managed API used that same source root. The run consumed 48 requests and seven LLM calls, completed five full scores with zero scoring failures, completed 31 source scans, and attempted 20 strategies across five cycles.

The stale HTML/navigation hypotheses were absent from current-run execution, confirming the `employer_landscape_v2` exclusion worked. However, no `local_employer_deepen` strategy executed even though the durable inventory still contained legitimate attachment/PDF-OCR employer hypotheses. Audit showed normalized attachment rows were being canonicalized against older equivalent PDF/OCR rows that were also considered current. Oldest-first tie resolution therefore retained the legacy row, and its prior attempt could place the canonical identity inside the 24-hour cooldown. This was a canonical persistence defect, not a scheduler-capacity defect.

The same run repeated the public-search anomaly: eight search requests completed, zero failed, and all eight returned zero results. With two consecutive exact-runtime short gates showing this pattern, provider handling became the next bounded investigation. DuckDuckGo bot/challenge HTML can return HTTP 200 and was previously indistinguishable from a valid empty result page in coverage accounting.

Checkpoint `1c50972...` addresses both findings without retuning scoring, query weights, scheduler allocation, cooldown duration, or request caps. Equivalent deepening strategies now compare evidence-semantics priority before age, so normalized attachment/current-revision evidence wins over an older equivalent legacy PDF/OCR row. Legacy attachment evidence remains eligible when no higher-priority equivalent exists. Shared HTTP acquisition now marks DuckDuckGo bot/challenge response language as challenged while a regression proves an ordinary empty DuckDuckGo HTML page remains non-challenged.
'''
if "## Post-evidence-revision five-minute gate" not in current:
    if insert_anchor not in current:
        raise SystemExit("runtime section insertion anchor not found")
    current = current.replace(insert_anchor, latest_section + insert_anchor, 1)

next_start = current.index("## Next bounded slice")
required_start = current.index("## Required Reads For Next Slice", next_start)
new_next = '''## Next bounded slice

Pull `dev` after full clean-head CI is green, then run one isolated five-minute exact-runtime gate. Do not run a 30-minute or long soak yet.

```powershell
.\\.venv\\Scripts\\python.exe scripts\\run_job_scout_live.py `
  --duration-seconds 300 `
  --max-requests 150 `
  --max-llm-calls 30 `
  --score-limit 10 `
  --score-failure-limit 5
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the gate. Audit only the new current run:

1. verify `runtime_identity.uses_checkout_source` is true and `runtime_identity.git_commit` equals the exact pulled `dev` head;
2. verify fresh `regional_alias_probe` and `local_employer` strategies remain reachable while one revisit is preserved;
3. verify a clean normalized attachment/current-revision `local_employer_deepen` strategy can execute despite an older equivalent legacy row inside cooldown, and verify stale HTML/navigation hypotheses remain absent;
4. if deepening executes, verify it proceeds through ordinary location-free employer-career resolution and remains hypothesis-first until official career evidence succeeds;
5. inspect provider warnings and search failure/challenge counts. A DuckDuckGo bot/challenge response must no longer appear as a successful zero-result search;
6. an ordinary non-challenge empty result page may still legitimately report zero results; do not convert all empty search responses into failures;
7. if DuckDuckGo challenge responses dominate the gate, investigate bounded provider fallback/transport behavior next rather than changing extraction, scoring, scheduler weights, cooldowns, or request caps;
8. return to a 30-minute gate only after clean deepening execution and trustworthy public-search result accounting are proven.

Keep Issue #57 open. Do not add named company, city, aggregator, page-heading, provider-result, or region exceptions. Preserve public-source safety, the 24-hour cooldown, existing request bounds, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Code Shop Issue #54 remains staged behind this acceptance work. Its contract is `refs/planning/code-shop-foundation.md`.

'''
current = current[:next_start] + new_next + current[required_start:]

current = current.replace(
    'python scripts/agent_context.py --focus "job scout employer evidence revision exact runtime local acquisition" --issue 57',
    'python scripts/agent_context.py --focus "job scout deepening canonical evidence DDG challenge accounting" --issue 57',
)
current_path.write_text(current, encoding="utf-8")

next_prompt = '''---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout deepening-canonicalization and provider-challenge acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout deepening canonical evidence DDG challenge accounting" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the next current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The latest implementation checkpoint is `1c50972bbd84d072c3c21fa63a163770d26638c5`. Targeted validation workflow `35262867619` passed Ruff, discovery-learning/connectors tests, the normalized-attachment-vs-legacy cooldown regression, both DuckDuckGo challenge/ordinary-empty regressions, and deterministic source-catalog validation.

The most recent live gate is run `6b582fdf-dba9-43fe-9929-576a97e6ffa8`. It ran the exact pulled checkout `267dd6c16cae70a942ca8e42131e8cf02604b41e` with `uses_checkout_source=true`, consumed 48 requests and seven LLM calls, completed five full scores with zero scoring failures, completed 31 source scans, and attempted 20 strategies across five cycles. The stale HTML/navigation hypotheses from the previous run were absent, proving the `employer_landscape_v2` exclusion works.

Two narrower defects remained. First, no `local_employer_deepen` strategy executed even though legitimate attachment/PDF-OCR hypotheses were durable. Equivalent normalized attachment and older PDF/OCR strategies were both considered current during canonical dedup, so oldest-first selection could retain the older row and inherit its 24-hour cooldown. Second, all eight public-search requests completed successfully but returned zero results, repeating the previous exact-runtime zero-result pattern. Audit isolated DuckDuckGo HTTP-200 bot/challenge HTML as a response class that was not trustworthy as a valid empty search.

Checkpoint `1c50972...` fixes those without changing scoring, query weights, scheduler capacity, request caps, or the cooldown. Equivalent employer-deepening strategies now compare evidence-semantics priority before age: normalized attachment/current-revision evidence outranks an older equivalent legacy PDF/OCR row, while legacy attachment evidence remains eligible when it is the best available equivalent. Shared HTTP acquisition also detects DuckDuckGo bot/challenge response language as `challenged`; an ordinary empty DuckDuckGo HTML response remains non-challenged.

After full clean-head CI is green, pull `dev` and run another isolated five-minute gate:

```powershell
.\\.venv\\Scripts\\python.exe scripts\\run_job_scout_live.py `
  --duration-seconds 300 `
  --max-requests 150 `
  --max-llm-calls 30 `
  --score-limit 10 `
  --score-failure-limit 5
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the gate. Audit only the new run, in this order:

1. verify exact runtime identity against the pulled `dev` head;
2. verify regional and local-employer acquisition lanes remain reachable with one revisit preserved;
3. verify clean normalized attachment/current-revision `local_employer_deepen` work executes despite older equivalent legacy strategy history, and stale HTML/navigation hypotheses remain absent;
4. verify any clean deepening attempt uses ordinary location-free employer-career resolution and stays hypothesis-first until official career evidence succeeds;
5. verify DuckDuckGo bot/challenge responses surface as challenged/search-failure/provider-warning evidence rather than successful zero-result searches;
6. do not treat an ordinary non-challenge empty response as a challenge;
7. if provider challenge dominates, investigate bounded provider fallback/transport behavior before changing query semantics, extraction, scoring, scheduler allocation, cooldowns, or request caps;
8. only return to a longer gate after clean deepening execution and trustworthy public-search accounting are proven.

Preserve public-source safety, the `gemma3:4b` general model with schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Update both handoffs and Issue #57 with the next run ID, exact runtime identity, strategy mix, evidence provenance, provider challenge/search-result evidence, exact head/CI, and the next evidence-backed slice. Keep Issue #57 open until usable current-run employer/alias evidence proceeds through ordinary company/career discovery.
'''
Path("refs/handoffs/next-dev-prompt.md").write_text(next_prompt, encoding="utf-8")
