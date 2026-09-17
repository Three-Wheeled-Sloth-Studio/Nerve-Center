---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout reserved acquisition-lane acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout local employer deepening regional alias reserved acquisition lanes" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the next current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The latest bounded implementation checkpoint is `857bbfae2a2822039956ffabcb336dac3b400a2c`. Targeted validation workflow `35243110817` passed the touched discovery-learning and discovery-loop tests, Ruff, and deterministic source-catalog regeneration.

The completed v6 gate is run `14011cec-0ee2-4d63-b593-0dc7f318c832`. It reached planned `admission_draining` successfully with 133 requests and 43 LLM calls. The decisive result is that `market_reference_v6` `local_employer` discovery is now alive: 21 current-run local-employer reference attempts returned search evidence across the bounded market family, inspected employer-reference pages, and produced employer hypotheses. High Point's civic `2022 Largest Employers` PDF was parsed through the existing bounded OCR path and yielded 12 employer-name hypotheses.

The same gate exposed two narrower defects. All eight fresh v6 `regional_alias_probe` strategies remained unattempted, and newly produced `local_employer_deepen` hypotheses did not receive a current-run attempt. Scheduler audit showed why: reserved non-company lanes could replace ordinary non-company work but could not displace any `company_revisit`, so multiple high-weight revisits could consume the remaining four-slot wave. Separately, one HTML Major Employers page produced 12 false employer hypotheses from subordinate navigation/section labels such as `Strategic Location`, `Higher Education`, `Facebook`, and `LinkedIn`.

The bounded correction at `857bbfae...` does not retune general scoring, cooldowns, or request caps. It allows a reserved non-company acquisition lane to displace an excess company revisit only when more than one revisit is already selected, preserving one company-revisit slot. Regression coverage proves a four-slot portfolio can contain exactly one company revisit plus `local_employer`, evidence-backed `local_employer_deepen`, and first-pass `regional_alias_probe`. HTML employer-list extraction now rejects shallow subordinate headings and generic social-navigation labels while leaving structured JSON and PDF/OCR extraction unchanged.

After full CI is green, pull `dev` and rerun the same isolated 30-minute gate:

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

1. verify at least one fresh `regional_alias_probe` executes through its first-pass protected lane;
2. verify at least one evidence-backed `local_employer_deepen` hypothesis executes while a company revisit is still preserved;
3. verify HTML employer-list extraction no longer promotes shallow section/navigation/social labels as employer hypotheses;
4. verify the working PDF/OCR employer path remains intact;
5. if employer deepening executes, verify it enters the ordinary location-free official-career resolution path and records truthful company/source/posting evidence;
6. if regional and deepening lanes execute but produce no usable downstream evidence, diagnose those acquisition/deepening paths next rather than retuning general scoring or search allocation;
7. consider another long soak only after the regional and employer-deepening paths are proven alive.

Do not add named company, city, aggregator, or region exceptions. Do not weaken the 24-hour cooldown or retune general scoring without new evidence. Preserve request bounds, public-source safety, the `gemma3:4b` general model plus schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Update both handoffs and Issue #57 with the next gate run ID, exact head/CI, regional/deepening attempts, candidate quality, reference evidence, and the next evidence-backed slice. Keep Issue #57 open until usable current-run employer/alias evidence proceeds through ordinary company/career discovery.
