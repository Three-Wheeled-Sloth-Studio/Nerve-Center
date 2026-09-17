---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout employer-evidence revision acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #57 directly on `dev`. Do not create a feature branch or PR, and do not close the issue yet.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout employer evidence revision exact runtime local acquisition" --issue 57
```

Use packet-first/progressive loading. Read `refs/handoffs/currentHandoff.md`, the latest Issue #57 comments, the next current-run live report, and only source-catalog matches needed for the evidence. Do not reread repository history.

Application version remains `0.12.26`. The latest implementation checkpoint is `8d7f9477caec1874d8cd5f81d1f6b709100f073d`. Targeted validation workflow `35256387208` passed Ruff, discovery-learning/loop tests, the existing v6 revision/cooldown regression, and deterministic source-catalog validation.

The exact-runtime diagnostic gate is run `7e9184d1-30d7-4d25-8379-852b613d112f`. It reached planned `admission_draining` with 46 requests, seven LLM calls, four successful full scores, 25 completed searches, 16 completed source scans, five revisits, and 20 strategy attempts. Runtime identity proved the exact pulled checkout executed: Git `8c61f2c75b69b39ec6a6eb7d121a8807f802de00`, `uses_checkout_source=true`, and both the imported `nerve_center` module and managed API resolved the repository `src` tree.

The scheduler is now accepted. Each of the five cycles selected exactly one legacy/revisit, one fresh v6 `regional_alias_probe`, one `local_employer_deepen`, and one v6 `local_employer`. Do not reopen scheduler weighting/cooldown tuning from this evidence.

The gate instead exposed durable stale employer evidence. Its five deepening slots were consumed by old HTML-derived false hypotheses created before the current extractor precision fix: `In this section`, `Strategic Location`, `Transportation Infrastructure`, `Innovation & Research`, and `Vibrant Businesses Major Employers`. The current extractor would not create those rows, but persistence still made them schedulable.

Checkpoint `8d7f947...` adds `EMPLOYER_LANDSCAPE_EVIDENCE_REVISION = "employer_landscape_v2"`. New HTML/structured employer hypotheses carry that revision. Unversioned non-attachment `local_employer_deepen` rows remain durable audit history but are excluded from selection. Existing legacy `civic_attachment` and normalized `civic` + `attachment` PDF/OCR evidence remains eligible. Canonical public-search dedup prefers current evidence semantics over equivalent stale deepening identities. No named company, location, page, or heading exception was added.

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

1. verify `runtime_identity.uses_checkout_source` is true and `runtime_identity.git_commit` equals the exact pulled `dev` head;
2. verify fresh `regional_alias_probe` and `local_employer` lanes remain reachable with one revisit preserved;
3. verify none of the stale unversioned HTML/navigation deepening hypotheses execute;
4. if `local_employer_deepen` executes, verify its provenance is either current `employer_landscape_v2` HTML/structured evidence or legitimate legacy/normalized attachment/PDF-OCR evidence;
5. if a current employer reference produces a candidate, verify `employer_evidence_revision=employer_landscape_v2` and ordinary location-free employer-career resolution;
6. note that the previous exact-runtime gate completed 25 public searches with zero results. If this repeats, investigate public-search provider/cache/query behavior before changing extraction, scoring, scheduler allocation, cooldowns, or request caps;
7. only return to a longer gate after the current evidence path is clean and producing usable reference results.

Preserve public-source safety, the `gemma3:4b` general model with schema-failure fallback to `qwen2.5:7b-instruct`, and the rule that extracted employer names remain hypotheses until ordinary public company/career validation succeeds.

Update both handoffs and Issue #57 with the next run ID, exact runtime identity, strategy mix, evidence provenance, search-result eligibility, exact head/CI, and the next evidence-backed slice. Keep Issue #57 open until usable current-run employer/alias evidence proceeds through ordinary company/career discovery.
