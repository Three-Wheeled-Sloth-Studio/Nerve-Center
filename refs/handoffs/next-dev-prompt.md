---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout v6 local acquisition acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout v6 local employer regional alias acquisition persistence" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the next current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The local-acquisition persistence implementation checkpoint is `5240bf5f820772277dfacba5a14c6ed6064c393a`. It advances durable market-reference identity to `market_reference_v6` and makes compiled-query canonicalization prefer the current revision for `local_employer` and `regional_alias_probe`, while preserving oldest-first canonicalization for unrelated searches and preserving the 24-hour cooldown. Targeted Ruff, discovery-learning tests, and deterministic source-catalog regeneration passed in workflow `35230212850`.

The prior 30-minute gate was run `2adf0558-f86f-4d03-8a8c-0a4477dd2dad`. It completed successfully at planned `admission_draining` with 139 requests, 43 LLM calls, 25/25 successful full scores, 25 successful public searches with zero failures, 58 completed source scans, 71 known-company revisits, 96 strategy attempts, 10 recovered polling timeouts, and three low-marginal-yield backoffs. However, all 25 searches returned zero results and the run produced zero companies, career sources, postings, retained opportunities, regional aliases, employer candidates, or inspected employer-reference pages.

The decisive evidence is strategy reachability: the run attempted 73 `legacy`, seven `employer_archetype`, seven `gap_reflection`, five `direct_role`, three `adjacent_role`, and one `domain_capability` strategies, but zero `local_employer` and zero `regional_alias_probe` strategies. The broadened local/regional acquisition behavior therefore was not exercised.

Repository audit showed this was a durable identity/canonicalization problem, not evidence that the regional reservation or general scheduler weights are wrong. The changed queries were still attached to `market_reference_v5`; recent v5 attempts remained inside the normal 24-hour cooldown, and equivalent compiled queries could still canonicalize to the older durable identity. The v6 checkpoint fixes both sides without weakening cooldowns or retuning scoring.

Pull the latest `dev` after the current full CI is green, then rerun the same isolated 30-minute gate. Do not run another long soak yet:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 1800 `
  --max-requests 500 `
  --max-llm-calls 80 `
  --score-limit 25 `
  --score-failure-limit 5
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the gate.

Audit only the new current run, in this order:

1. verify fresh `market_reference_v6` `local_employer` strategies execute despite recent v5 history;
2. verify fresh v6 `regional_alias_probe` strategies receive first-pass coverage;
3. inspect whether the broadened local/regional queries return search results and recognizable reference evidence;
4. if those targeted searches execute but still return zero results, investigate public-search provider/query behavior before changing extraction;
5. if high-intent references are inspected but aliases/employer candidates remain zero, improve HTML/table/list extraction next;
6. if aliases or employer candidates appear, verify employer candidates become `local_employer_deepen` hypotheses and enter ordinary official-career resolution;
7. only after the acquisition path is alive should another long soak be considered.

Do not add named company, city, aggregator, or region exceptions. Do not weaken the 24-hour cooldown or retune general scoring without new evidence. Preserve request bounds, public-source safety, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Update both handoffs and Issue #57 with the new gate run ID, exact head/CI, v6 local/regional attempts, search-result counts, alias/candidate counts, reference evidence, and the next evidence-backed slice. Keep Issue #57 open until the local acquisition path produces usable current-run evidence.