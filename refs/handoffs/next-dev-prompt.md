---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout bounded public-search fallback acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout public search provider fallback DDG Bing acceptance" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the next current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The bounded provider-fallback implementation checkpoint is `fe1608e5e7bc4f309d8a823340f78200a9886ba6`. Targeted workflow `35270065108` passed Ruff, 67 focused tests, deterministic source-catalog validation, and OKF validation. After pulling, use the exact `git rev-parse HEAD` value as the runtime-identity target for the gate.

The latest accepted live evidence is run `e107e4a4-5f1c-4cd0-806e-001b4c97fd3a`. It reached planned `admission_draining` with 51 / 150 requests, 6 / 30 LLM calls, four full scores with zero scoring failures, and 31 / 31 source scans completed. Clean `local_employer_deepen` work executed for `Volvo Group North America` with four public results and `HAECO Americas` with eight public results, proving the deepening canonicalization/cooldown correction. DuckDuckGo bot/challenge responses surfaced as `challenged` for Durham-Chapel Hill, Mount Airy, and Danville, proving truthful challenge accounting.

That gate isolated the remaining blocker to public-search transport. Nine public-search attempts produced four completed searches, six failed/challenged attempts, and 15 returned results, with no new companies, career sources, postings, regional aliases, or employer candidates. Do not use that evidence to retune scoring, query semantics, extraction rules, scheduler allocation, cooldown duration, or request caps.

Checkpoint `fe1608e5...` adds bounded ordinary-public provider fallback only:

- DuckDuckGo remains primary.
- A challenge stores one-hour provider-health/circuit-breaker state.
- The current challenged strategy ends without retry; one search request per strategy remains the budget contract.
- Later public-search strategies use Bing public HTML while DuckDuckGo cools.
- Successful non-empty cached results remain usable; ordinary empty DuckDuckGo HTML does not trigger fallback.
- Bing parsing is limited to the normal result list, and Bing tracking URLs are normalized back to public targets.
- Attempt detail records `search_provider` and `search_provider_fallback_used`; aggregate coverage records `search_provider_fallbacks`.
- If Bing also challenges, it receives its own cooldown. Do not automatically add a third provider.

After full helper-free exact-head CI is green, pull `dev` and run another isolated five-minute gate:

```powershell
git pull

.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 300 `
  --max-requests 150 `
  --max-llm-calls 30 `
  --score-limit 10 `
  --score-failure-limit 5
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the gate. Audit only the new run, in this order:

1. verify exact runtime identity against the pulled `dev` head and `uses_checkout_source=true`;
2. verify any DuckDuckGo challenge is still reported as challenged rather than as a successful zero-result search;
3. after a DuckDuckGo challenge, verify a later public-search strategy can execute through `bing_html` with `search_provider_fallback_used=true`;
4. if DuckDuckGo challenges during the run, require aggregate `search_provider_fallbacks > 0` unless no later public-search strategy receives a slot;
5. verify each strategy still consumes only one search request; there must be no hidden same-strategy retry;
6. verify an ordinary non-challenge empty DuckDuckGo response does not rotate providers;
7. verify clean normalized attachment/current-revision `local_employer_deepen` work remains reachable and stays hypothesis-first until ordinary official-career evidence succeeds;
8. verify protected local-employer/regional acquisition lanes remain reachable while one company revisit is preserved;
9. if Bing also challenges or returns unusable transport evidence, diagnose that bounded provider path before adding another provider or changing query/scoring/scheduler/cooldown/cap policy;
10. only return to a longer gate after provider fallback produces trustworthy usable public-search results and downstream acquisition remains healthy.

Preserve public-source safety, the `gemma3:4b` general model with schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Update both handoffs and Issue #57 with the next run ID, exact runtime identity, provider mix, fallback count, strategy mix, evidence provenance, downstream acquisition evidence, exact head/CI, and the next evidence-backed slice. Keep Issue #57 open until usable current-run employer/alias evidence proceeds through ordinary company/career discovery.