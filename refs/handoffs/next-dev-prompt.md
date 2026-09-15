---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout overnight acceptance audit.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout overnight employer fallback official career audit" --issue 57
```

Use the packet-first/progressive-loading rules in `AGENTS.md`. Read `refs/handoffs/currentHandoff.md`, the newest Issue #57 comments, the latest live report, and only directly relevant query/learning files. Do not reread repository history.

Current application version is `0.12.26`. Civic/OCR employer hypotheses reach protected employer deepening; career resolution is location-free and has a bounded evidence-triggered failback sequence. Public searches deduplicate by compiled source path/query while raw provenance rows persist. Tenant-keyed shared career portals remain aggregator evidence and aggregator-only companies cannot enter employer revisit.

The final bounded gate is `78b7e242-8aee-450f-a373-5f73600f8326`: planned `admission_draining`, 59 requests, seven LLM calls, 5/5 successful full scores, 10 unique public queries, 90 search results, 38 successful scans, 124 postings inspected, five retained roles, 12 employer hypotheses, and five career sources. The rejected RippleMatch and shared-portal companies remained absent, and source growth was proportional.

Run the isolated overnight acceptance session:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --max-requests 3000 `
  --max-llm-calls 500 `
  --score-limit 100 `
  --score-failure-limit 20
```

Do not run process-level tests or packaging smoke concurrently with the soak.

Then audit only the current run. Confirm civic/OCR `local_employer_deepen` strategies execute after cooldown, inspect their query/failback telemetry, verify official employer or ATS career resolution, check that compiled queries remain unique, and confirm source growth tracks postings. Inspect the retained local roles and employer/location evidence without adding named rules.

Do not add named company, city, aggregator, or region exceptions. Let result classification, official-domain/career evidence, posting yield, and persisted learning reject or down-weight weak hypotheses. Do not retune scoring unless runtime evidence identifies scoring as the blocker.

Preserve all public-source safety boundaries, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted names are hypotheses rather than company truth.

Update both handoffs and Issue #57 with the exact overnight run ID, head SHA, CI run, budgets, counts, and next evidence-backed slice. Keep Issue #57 open until the current-run audit proves civic employer evidence reaches plausible official career sources without source amplification.
