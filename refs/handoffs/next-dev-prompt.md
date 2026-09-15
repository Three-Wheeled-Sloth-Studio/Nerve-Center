---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout overnight employer-deepening audit.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout overnight civic employer deepening audit" --issue 57
```

Use the packet-first/progressive-loading rules in `AGENTS.md`. Read `refs/handoffs/currentHandoff.md`, the newest Issue #57 comments, the overnight report, and only directly relevant scheduler/reference files. Do not reread repository history.

Current application version is `0.12.19`. The completed implementation routes extensionless supported documents, performs bounded local OCR for image-only ranked employer PDFs, persists extracted names as hypotheses only, normalizes civic authority versus attachment medium, migrates old combined evidence rows, and reserves scheduler capacity for those hypotheses.

The official High Point image-only employer PDF produced 12 durable hypotheses through generic OCR structure, including `Volvo Group North America`. No named employer or location production rule was added.

Run or review this explicit overnight soak:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 28800 `
  --max-requests 3000 `
  --max-llm-calls 500 `
  --score-limit 100 `
  --score-failure-limit 20
```

Do not run process-level tests or packaging smoke concurrently with the soak.

Audit current-run evidence for civic/OCR extraction and provenance; `local_employer_deepen` execution; ordinary public-search and official-career resolution; evidence-driven correction of weak hypotheses; wave-to-wave growth; exact budgets; scoring health; polling recovery; and planned wind-down.

If no civic-derived deepening attempt executes, add bounded selected-strategy-family telemetry and correct scheduler starvation generically. If attempts execute but valid employers do not resolve, inspect their query/result evidence and improve the generic employer-deepening path. Do not retune scoring unless runtime evidence identifies scoring as the blocker.

Preserve all public-source safety boundaries, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted names are hypotheses rather than company truth.

After the audit, update both handoffs and Issue #57 with the exact run ID, head SHA, CI run, budgets, counts, and next evidence-backed slice.
