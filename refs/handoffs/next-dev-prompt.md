---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout regional saturation and employer-path acceptance audit.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout regional coverage diminishing returns saturation reallocation" --issue 57
```

Use the packet-first/progressive-loading rules in `AGENTS.md`. Read `refs/handoffs/currentHandoff.md`, the newest Issue #57 comments, the latest current-head live report, and only source-catalog matches directly relevant to the evidence. Do not reread repository history.

Current application version remains `0.12.26`. The validated regional-saturation implementation checkpoint is `a1632ff3e497b5c699eb5d4ca12609430d215ba6`, with CI run `35137884078` green across strict refs/source-catalog/agent-context validation, the full Python suite, desktop web, and desktop Rust/Tauri.

The scheduler now protects `regional_alias_probe` only for first-pass coverage. After a regional probe has executed once, it remains eligible through ordinary learned-weight, exploration-floor, and cooldown selection but no longer receives a guaranteed slot. This is intentionally structural: do not replace it with a named-market rule or an arbitrary saturation threshold unless current-run evidence demonstrates a general threshold is necessary.

The final bounded pre-soak gate remains `78b7e242-8aee-450f-a373-5f73600f8326`: planned `admission_draining`, 59 requests, seven LLM calls, 5/5 successful full scores, 10 unique public queries, 90 search results, 38 successful scans, 124 postings inspected, five retained roles, 12 employer hypotheses, and five career sources. The later long soak from pre-alignment head `ad34249` survived a host reboot and resumed from durable state, but its exact final report/counts were not present in the bounded repository/Issue #57 evidence used for this handoff. Do not treat that run as the acceptance artifact for the new scheduler behavior.

Run the isolated current-head long acceptance session:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --max-requests 3000 `
  --max-llm-calls 500 `
  --score-limit 100 `
  --score-failure-limit 20
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the soak.

Audit only the current run. Verify first-pass regional coverage, then show that attempted regional probes stop consuming guaranteed capacity. Confirm they can still reappear through normal portfolio selection when warranted. Compare regional-probe attempts against `regional_aliases_discovered` over time, and verify released slots move toward useful local-employer, employer-deepening, company-revisit, or other productive work instead of another low-yield family.

Continue the existing employer-path acceptance audit in the same artifact: civic/OCR `local_employer_deepen` strategies should execute after cooldown, official employer or ATS career resolution should remain plausible, compiled public queries should remain unique, and source growth should remain proportional to posting yield.

Do not add named company, city, aggregator, or region exceptions. Let result classification, official-domain/career evidence, posting yield, persisted learning, and generic scheduler rules reject or down-weight weak hypotheses. Do not retune scoring unless runtime evidence identifies scoring as the blocker.

Preserve all public-source safety boundaries, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted names are hypotheses rather than company truth.

If this audit requires the same diagnostic aggregation more than once, extend or add reusable reporting rather than repeating manual database archaeology.

Update both handoffs and Issue #57 with the exact current-head run ID, head SHA, CI run, budgets, counts, regional marginal-yield evidence, employer-path evidence, and next evidence-backed slice. Keep Issue #57 open until the current-head audit proves both capacity reallocation and plausible civic-employer career resolution without source amplification.
