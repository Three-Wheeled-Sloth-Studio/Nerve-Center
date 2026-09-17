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
python scripts/agent_context.py --focus "job scout local employer regional alias acquisition employer candidates" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The local-acquisition implementation checkpoint is `fa5cfd0f0558daab0b2a76a059679bf7db4c6b28`, with behavior through `708484842782fa91bc84a81fed6a72cec016e7a2`. CI `35219112384` is green across strict refs/source-catalog/agent-context validation, Ruff, packaging validation, the full Python suite, desktop web, and Rust/Tauri.

The completed long soak established that general reliability is healthy: 1,574 requests, 159 LLM calls, 100/100 successful full scores, 221 successful searches with zero failures, 674 results, 732 postings inspected, six companies, and 18 retained opportunities. Efficiency improved to 87 requests per retained opportunity from 365. All 102 intermittent monitoring timeouts recovered. The run reached planned wind-down cleanly and left no process or API listener running.

The remaining defect is local acquisition: zero regional aliases, zero employer candidates, and only two conditioned location-family yields across 1,467 attempts, despite 200 low-performing families being correctly down-weighted. Do not change general search or scoring unless new evidence contradicts this diagnosis.

The current slice now uses exact quoted local-employer intent phrases, a broader regional-reference query (`regional council`, `regional partnership`, `council of governments`), broader regional organization-name recognition, and broader employer-list heading recognition such as `Top 25 Private Employers`, `Leading Employers`, and `Employer Directory`. Extracted names remain hypotheses only.

Run this isolated short gate, not another eight-hour soak:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 1800 `
  --max-requests 500 `
  --max-llm-calls 80 `
  --score-limit 25 `
  --score-failure-limit 5
```

Do not run process-level tests, packaging smoke, or another API-owning command concurrently with the gate.

Audit only the current run. First determine whether `regional_alias_probe` and `local_employer` strategies execute. If they do not, investigate learned-weight/cooldown allocation. If they execute, inspect query/result/reference evidence, `regional_aliases_discovered`, and `employer_candidates_discovered`. If high-intent references are inspected but candidate yield stays zero, the next slice is HTML/table/list extraction. If candidates appear, verify they become `local_employer_deepen` hypotheses and enter ordinary official-career resolution.

Do not add named company, city, aggregator, or region exceptions. Preserve request bounds, public-source safety, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names do not directly create company truth.

If this audit requires the same diagnostic aggregation more than once, extend or add reusable reporting rather than repeating manual database archaeology.

Update both handoffs and Issue #57 with the short-gate run ID, exact head/CI, local strategy attempts, alias/candidate counts, reference evidence, and the next evidence-backed slice. A longer soak is warranted only after this short gate proves the local acquisition path is producing evidence.