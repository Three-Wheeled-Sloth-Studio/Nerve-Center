---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next bounded checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- Work directly on `dev`; do not create a feature branch or PR unless explicitly requested.
- Application version is `0.12.14`.
- Implementation checkpoint before this handoff refresh: `ca24a9e6d9855791674a0e02f8d5055d57adf379`.
- The manager/module boundary, durable work sessions/queue, provider-neutral local LLM routing, Windows desktop/package baseline, career-evidence profile, company-first Job Scout discovery, scoring/application tracking, durable discovery learning, and Model Lab foundation are accepted.
- Job Scout remains an iterative market-research loop: `expand -> converge -> deepen -> reflect -> re-expand`. Discovery optimizes recall; ranking/scoring provides precision.
- Responsibility/requirement evidence is primary. Listed title is a weak clue. Domain relationship remains `direct > adjacent > transferable > mismatch`.
- Opening location, company-presence evidence, and discovery-strategy market evidence remain separate concepts.
- Public-source safety remains unchanged: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or automated outreach.
- Coding-agent token conservation is a primary engineering concern. Use `scripts/agent_context.py` and progressive context loading instead of repository-wide rereads.

## Active slice: Issue #57

Issue **#57: Stratify Job Scout market exploration after regional live gate** remains open on runtime evidence, not CI alone.

Accepted behavior accumulated through this slice:

1. Current market-query revisions are preferred over stale persisted variants when eligible, and distinct markets are sampled before repeating another angle for the same market.
2. Regional-reference capacity and company deepening remain bounded protected paths.
3. Public civic reference pages are cacheable/retry-aware; success, challenge, transient failure, and invalid evidence have distinct cooldown behavior.
4. Bounded employer extraction supports accountable HTML/JSON evidence and public PDF/CSV/TSV/JSON/XLSX directory attachments.
5. Extracted names become provenance-bearing `local_employer_deepen` hypotheses only. They do not become company/location truth until ordinary official-career discovery resolves them.
6. Reference selection is intent-aware: explicit `major/top/largest/leading employers`, employer/business/company directory/list signals, and supported employer documents compete before generic civic authority. The two-reference acquisition bound remains unchanged.
7. No named city or employer production rule has been added. Volvo Group and Wolfspeed are representative runtime probes only.

### Runtime evidence to date

The `0.12.12` gate proved the attachment path itself is safe and bounded: Durham/core-market discovery executed, regional-alias evidence executed, PDFs were fetched/parsed/reused from cache, and scoring stayed healthy. The parsed Chapel Hill policy PDF and Danville economic-development budget PDF correctly yielded zero employer candidates because neither was an employer directory. Volvo Group had already been reached through the ordinary official-career path; Wolfspeed remained absent.

SQLite inspection of that gate exposed a general source-selection defect: generic `.gov` pages could consume both civic-reference slots while an explicit employer-list result in the same result set was skipped. `0.12.13` corrected selection generically by ranking employer-directory intent before authority and added deterministic fictional tests.

The next 15-minute run, `aa6a3579-6b34-4642-885e-20473a8270b3`, executed on `0.12.13` and was operationally healthy:

- status `succeeded`, terminal reason `admission_draining`, planned wind-down reached;
- 155 requests and 30 LLM calls, without budget exhaustion;
- 23/23 full-score attempts succeeded with zero failures;
- 23 current-window `local_employer` strategies executed, including Durham-Chapel Hill market work;
- 16 civic references were inspected, with 16 cache hits and 12 retry-deferred references;
- zero employer candidates were created;
- all attachment counters were zero;
- no `local_employer_deepen` strategy executed during that run.

That report could not diagnose the source-selection result because per-attempt `reference_selection_evidence`, `employer_reference_evidence`, and `attachment_reference_evidence` were durable in the attempt ledger but absent from the final live report. Another manual SQLite inspection would have been required.

### 0.12.14 diagnostic hardening

`0.12.14` fixes that observability gap without changing acquisition behavior:

- the discovery audit exposes a bounded recent `reference_attempt_evidence` stream;
- each row carries run/attempt/strategy/cycle identity, hypothesis family, location, anchor, status, relevant acquisition counters, reference-selection ranking, employer-reference evidence, and attachment evidence;
- only attempts containing reference evidence are included;
- output is bounded, and the live runner already embeds the discovery audit;
- deterministic fictional coverage proves run attribution, evidence retention, bounded output, and omission of unrelated attempts.

Implementation commits:

- `80a107d0f4cbeb3dd9a5e3def43faeb173778443` — expose bounded reference-attempt evidence;
- `a3d621079d29286441bd06e38eb34107db494786` — deterministic audit regression test;
- `ca24a9e6d9855791674a0e02f8d5055d57adf379` — align version to `0.12.14`.

## Next gate

After exact-head CI is green, rerun the standard explicit-budget acceptance:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 900 `
  --max-requests 1000 `
  --max-llm-calls 150 `
  --score-limit 25 `
  --score-failure-limit 10
```

The next uploaded `run-*.json` should be sufficient by itself. Inspect `discovery_audit.reference_attempt_evidence` filtered to the current run ID and answer, in order:

1. Which civic references ranked highest and were selected?
2. Were selected references inspected, cache hits, challenged, or retry-deferred?
3. Did a selected page expose supported directory attachments?
4. Did HTML/JSON/attachment parsing produce valid employer candidates with provenance?
5. Did any resulting `local_employer_deepen` hypothesis execute and resolve an ordinary official career surface?
6. Did discovery/scoring remain productive and request/LLM accounting remain exact?

If no valid directory-derived employer is produced, treat the evidence as a general source-capability or extraction-quality diagnosis. Do not add Wolfspeed, Durham, Volvo, or any other named production rule.

## Known follow-up evidence

Persisted historical `local_employer_deepen` strategies include some weak HTML-extraction artifacts that look like section headings rather than employer names. They predate the current run and were not exercised by the `0.12.13` acceptance. Do not mix that debt into the current selector diagnosis without fresh current-run evidence. If the new audit proves high-intent pages are selected and inspected but base HTML extraction creates structural headings, harden candidate structure generically with fictional tests.

The earlier planned-wind-down durability note also remains open: the durable discovery-session aggregate can trail the final attempt ledger by one terminal cycle. The attempt ledger preserves the event, but final-cycle aggregate coverage should eventually flush before termination.

## Staged next slice: Issue #54 Code Shop foundation

Code Shop remains staged behind the active Job Scout acceptance work. The accepted architecture contract is `refs/planning/code-shop-foundation.md`. GitHub remains project identity/metadata authority; local checkout access must stay inside approved roots and match the selected repository remote; unattended engineering authority is capability-specific and manager-owned; user-supplied modules never receive generic autonomous shell/filesystem authority.

For Code Shop re-entry when explicitly resumed:

```powershell
python scripts/agent_context.py --focus "code shop project registry authority execution host escalation" --issue 54
```

## Deferred follow-up

- automatic model installation and separately opt-in removal belong to later Model Lab slices;
- external/public benchmark ingestion and blinded pairwise A/B review remain later Model Lab work;
- people enrichment remains deferred;
- Firecrawl is not a core dependency while local parsing/caching/source-health tracking cover the responsibility;
- do not export career prompts, benchmark prompts, results, or traces to LangSmith by default.

## Re-entry

For the active Issue #57 runtime gate:

```powershell
python scripts/agent_context.py --focus "job scout intent-aware civic references attachment provenance live acceptance" --issue 57
```

Read the generated packet and Issue #57 first. Do not reread repository history. The runtime report, current handoff, and directly relevant discovery files are the authoritative starting set.
