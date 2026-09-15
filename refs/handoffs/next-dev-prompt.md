---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the next Job Scout employer-identity quality slice.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout employer identity query failback deduplication" --issue 57
```

Use the packet-first/progressive-loading rules in `AGENTS.md`. Read `refs/handoffs/currentHandoff.md`, the newest Issue #57 comments, the latest live report, and only directly relevant query/learning files. Do not reread repository history.

Current application version is `0.12.22`. Civic/OCR employer hypotheses now reach scheduled employer deepening. Career resolution defers location terms, job/career URL qualification requires discrete route evidence, sitemap child registration is bounded, source-only expansion without postings is down-weighted, and cached search results are reclassified by current URL policy before use.

Run `1c68afd8-26d1-4f40-9fee-bfe35e67cfef` exposed a generic source-amplification failure: an editorial page became false company `ripplematch.com`, then 250 article/image URLs were registered as career sources and rewarded without posting yield. `bf461c2` corrects the shared URL, sitemap, cap, and learning mechanisms; no named production rule was added. The false graph was removed from local runtime state after backup, and 746 equivalent historical no-provenance sitemap sources were reversibly quarantined.

Run a fresh bounded `0.12.22` verification gate. Confirm proportional source growth, down-weighting of zero-posting source expansion, rejection of the stale cached editorial result, zero scoring failures, and planned wind-down. If healthy, the overnight command remains:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --max-requests 3000 `
  --max-llm-calls 500 `
  --score-limit 100 `
  --score-failure-limit 20
```

Do not run process-level tests or packaging smoke concurrently with the soak.

Then implement one bounded employer-identity quality slice. Civic evidence currently creates separate city and metro hypotheses that can compile to the same location-free query, and first-pass career searches can return only aggregators or no results. Deduplicate equivalent compiled employer queries and add a small deterministic failback vocabulary for canonical official-career resolution. Keep civic evidence as provenance and downstream location evidence rather than company truth.

Do not add named company, city, aggregator, or region exceptions. Let result classification, official-domain/career evidence, posting yield, and persisted learning reject or down-weight weak hypotheses. Do not retune scoring unless runtime evidence identifies scoring as the blocker.

Preserve all public-source safety boundaries, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted names are hypotheses rather than company truth.

After the slice, update both handoffs and Issue #57 with the exact run ID, head SHA, CI run, budgets, counts, and next evidence-backed slice. Keep Issue #57 open until a current-run audit proves civic employer evidence reaches plausible official career sources without source amplification.
