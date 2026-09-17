---
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

Application version remains `0.12.26`. The latest implementation checkpoint is `1c50972bbd84d072c3c21fa63a163770d26638c5`. Targeted validation workflow `35262867619` passed Ruff, discovery-learning/connectors tests, the normalized-attachment-vs-legacy cooldown regression, both DuckDuckGo challenge/ordinary-empty regressions, and deterministic source-catalog validation. The handoff/OKF refresh is clean; after pulling, use the exact `git rev-parse HEAD` value as the runtime-identity target for the next gate.

The most recent live gate is run `6b582fdf-dba9-43fe-9929-576a97e6ffa8`. It ran the exact pulled checkout `267dd6c16cae70a942ca8e42131e8cf02604b41e` with `uses_checkout_source=true`, consumed 48 requests and seven LLM calls, completed five full scores with zero scoring failures, completed 31 source scans, and attempted 20 strategies across five cycles. The stale HTML/navigation hypotheses from the previous run were absent, proving the `employer_landscape_v2` exclusion works.

Two narrower defects remained. First, no `local_employer_deepen` strategy executed even though legitimate attachment/PDF-OCR hypotheses were durable. Equivalent normalized attachment and older PDF/OCR strategies were both considered current during canonical dedup, so oldest-first selection could retain the older row and inherit its 24-hour cooldown. Second, all eight public-search requests completed successfully but returned zero results, repeating the previous exact-runtime zero-result pattern. Audit isolated DuckDuckGo HTTP-200 bot/challenge HTML as a response class that was not trustworthy as a valid empty search.

Checkpoint `1c50972...` fixes those without changing scoring, query weights, scheduler capacity, request caps, or the cooldown. Equivalent employer-deepening strategies now compare evidence-semantics priority before age: normalized attachment/current-revision evidence outranks an older equivalent legacy PDF/OCR row, while legacy attachment evidence remains eligible when it is the best available equivalent. Shared HTTP acquisition also detects DuckDuckGo bot/challenge response language as `challenged`; an ordinary empty DuckDuckGo HTML response remains non-challenged.

After full clean-head CI is green, pull `dev` and run another isolated five-minute gate:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
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
