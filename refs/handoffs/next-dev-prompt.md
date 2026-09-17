---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for the Job Scout provider/cache evidence acceptance gate.
status: stable
tags: [nerve-center, handoff, job-scout, discovery, live-test]
---
# Next Development Prompt

Continue Issue #60 directly on `dev`. Do not create a feature branch or PR. Issue #57 is closed as completed. Do not promote `qa` or `main`.

Start with:

```powershell
python scripts/agent_context.py --focus "job scout provider cache evidence DDG Bing fallback acceptance" --issue 60
```

Use packet-first/progressive loading. Read this handoff, `refs/handoffs/currentHandoff.md`, Issue #60, and only source-catalog matches needed for provider/cache evidence. Do not reread repository history.

The accepted source run is `8b646b11-d5ba-4725-991c-5eb2eb36c36a` from exact Git `5155a82099c516eb403630fa72d30b297062a154`. It completed planned `admission_draining` with 55 requests, five LLM calls, five successful full scores, 73 public-search results, three career sources, 319 postings inspected, and four retained opportunities. Six normalized attachment-backed employer hypotheses executed through ordinary career discovery, satisfying and closing Issue #57.

Issue #60 exists because that report could not distinguish provider cache reuse from network transport and the location-aware runtime cycle omitted the `search_provider_fallbacks` aggregate counter. The bounded fix records per-search provider/cache evidence and restores truthful fallback aggregation without changing provider policy.

After exact-head CI is green, run one isolated five-minute gate:

```powershell
git pull

.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 300 `
  --max-requests 150 `
  --max-llm-calls 30 `
  --score-limit 10 `
  --score-failure-limit 5
```

Audit `discovery_audit.public_search_attempt_evidence` for the new run. Verify runtime identity first. Then verify each actual public search records query, provider, fallback flag, transport (`cache`, `network`, or `cooldown`), status, and result count. After any DDG challenge, later searches must be explainable from those rows. If an uncached post-challenge call occurs, require Bing fallback and exact aggregate fallback accounting. If later calls are all reusable cache hits, accept that truthful outcome and do not force network work just to exercise Bing.

Do not change search semantics, extraction, scoring, scheduler weights, cooldown duration, request caps, or add a third provider from this gate. Keep Issue #60 open until live evidence is accepted. Code Shop Issue #54 is next after #60.
