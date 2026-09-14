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
- Application version is `0.12.15`.
- Accepted green implementation baseline: `66e41e7dc9557a2f1f0e5cb8f977578abc1c9586`.
- CI run `34888748787` is green: refs/OKF, agent context, Ruff, packaging dry-run, 244 Python tests, desktop-web, and desktop-rust/Tauri shell.
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
6. Reference ranking is intent-aware: explicit `major/top/largest/leading employers`, employer/business/company directory/list signals, and supported employer documents rank ahead of generic civic authority. The acquired-reference bound remains two.
7. `0.12.14` exposes bounded reference-attempt evidence in the discovery audit so live reports can explain selection, inspection, cooldown, attachment parsing, and candidate extraction without SQLite archaeology.
8. No named city or employer production rule has been added. Volvo Group and Wolfspeed are representative runtime probes only.
9. `0.12.15` makes local-employer queries intent-pure, excludes civic self-employment pages that lack employer-landscape evidence, preserves a six-candidate ranked civic fallback pool behind hard two-inspection/three-network-fetch caps, and scopes live reference-attempt evidence by `run_id`.

## Latest runtime gate: 0.12.14

Run `dcee77be-53c7-416a-be7c-b518f2240378` is the authoritative latest live acceptance artifact.

Operational result:

- runtime version `0.12.14`;
- status `succeeded`, terminal reason `admission_draining`, planned wind-down reached;
- 92 requests and 30 LLM calls consumed without budget exhaustion;
- 20/20 full-score attempts completed with zero failures; the configured target of 25 was not reached before wind-down, but structured scoring is healthy;
- 20 public searches completed, 200 results returned, 56 eligible/registered sources, 100 source scans attempted, and 44 completed;
- 15 civic reference pages inspected, 14 reference cache hits, and 8 retry-deferred references;
- two cached attachment documents were parsed, both valid, with zero invalid/unsupported documents;
- zero employer candidates were extracted and no current-run `local_employer_deepen` hypothesis was created or executed.

Filter `discovery_audit.reference_attempt_evidence` by this run ID before drawing conclusions. The current-run subset contains exactly 20 local-employer attempts: 10 `major employers` and 10 `company headquarters`, spanning Durham-Chapel Hill, Mount Airy, Danville, Sanford, Winston-Salem, and Martinsville market aliases/core places.

Current-run reference behavior:

- 23 civic references were selected for acquisition;
- 15 were inspected and 8 were retry-deferred;
- `major employers`: 20 selected, 12 inspected, 8 deferred, zero employer candidates;
- `company headquarters`: 3 selected/inspected, zero employer candidates; seven attempts found no civic reference worth selecting;
- the cached Danville Economic Development PDF was parsed twice and correctly yielded zero candidates again;
- Wolfspeed and Volvo are absent from this report. This is evidence, not a reason for named production logic.

## Diagnosis

The remaining blocker is now **reference-source acquisition quality**, not parser correctness, source-ranking observability, or scoring.

### 1. Query intent is being diluted before ranking

When a high-intent result exists, the `0.12.13` ranker behaves correctly. Prior-run evidence in the audit shows `Major Employers - Durham Economic Development` at intent tier 0 ahead of generic civic pages; that source was `retry_deferred`, not starved by `.gov` authority.

In the latest current-run evidence, however, almost every `major employers` search returned only generic economic-development/chamber material. The query compiler currently emits:

`<market> major employers chamber economic development`

Authority is already represented in post-search ranking. Including `chamber economic development` in the query appears to bias retrieval toward generic pages and away from explicit employer lists/directories. Treat this as a generic query-capability defect.

### 2. `company headquarters` civic references admit self-employment/HR pages

Current-run examples include municipal `Employment Opportunities` pages. Those are legitimate public pages but poor employer-landscape evidence. Direct company career pages must remain available to ordinary non-civic discovery; civic-reference extraction should prefer evidence about companies/businesses/headquarters/existing industry, not a municipality's own HR page.

### 3. Retry-deferred top references need bounded fallback

`_IntentAwareReferenceAdapter` currently returns only the top two civic candidates plus non-civic results. The base acquisition loop already skips `retry_deferred` references without incrementing `references_acquired`, but it cannot fall through to the third civic candidate because preselection removed it.

Preserve a small ranked fallback pool while maintaining explicit hard caps on acquired references and network fetch attempts. A zero-cost cooldown/invalid result should not consume the opportunity to inspect another already-ranked civic candidate, but the correction must not create unbounded network work.

### 4. The new audit is attributable but not run-scoped

The latest report's bounded `reference_attempt_evidence` contains 64 rows: 20 from the current run, 23 from `aa6a3579-6b34-4642-885e-20473a8270b3`, and 21 from `4b5ad2ea-df90-4237-8d62-e45ec7f1216c`.

Each row carries `run_id`, so the data is not corrupt, but a live-run report should expose the current run directly or accept an explicit run filter. Do not make future acceptance reviewers manually separate recent historical rows.

## Completed implementation slice: 0.12.15

The generic, bounded source-acquisition correction is implemented. No named employer/city exceptions were added.

1. **Intent-pure local-employer queries**
   - Authority terms are no longer mandatory query tails for `major employers`.
   - The deterministic vocabulary is `major employers`, `largest employers`, `top employers`, `employer directory`, and `company headquarters`.
   - Authority remains a post-search rank/provenance dimension, not a required search term.
   - If multiple query variants are added, keep them deterministic, bounded, and represented in strategy identity/revision so learning stays attributable.

2. **Civic-reference eligibility/ranking hardening**
   - Obvious civic self-employment/HR pages are excluded when they do not also contain business/employer-landscape signals.
   - Preserve direct employer career results on the normal discovery path.

3. **Bounded fallback after deferred/invalid references**
   - The selector preserves up to six ranked civic candidates.
   - The loop preserves `<=2` successfully acquired/inspected references and `<=3` network fetch attempts per attempt.
   - Cached `retry_deferred`/invalid candidates may fall through without consuming an acquired-reference slot.

4. **Run-scoped live reference evidence**
   - The discovery-audit endpoint accepts `run_id`, and the live runner always passes its current run ID.
   - Preserve the bounded diagnostic shape and row-level run identity.

5. **Deterministic regression coverage**
   - Query intent, civic eligibility, truthful raw result telemetry, deferred/invalid fallback, acquired/network caps, and cross-run audit exclusion are covered.

The validation baseline is 244 passing Python tests plus clean Ruff, refs, diff, desktop-web, and GitHub desktop-rust checks. The runtime gate remains to be recorded.

## Next action: runtime acceptance

Use the standard explicit-budget 15-minute run:

```powershell
.\.venv\Scripts\python.exe scripts\run_job_scout_live.py `
  --duration-seconds 900 `
  --max-requests 1000 `
  --max-llm-calls 150 `
  --score-limit 25 `
  --score-failure-limit 10
```

The next gate should require:

1. the live report's reference evidence is scoped to the current run;
2. at least one current-run high-intent employer-list/directory reference is selected and inspected, or is truthfully retry-deferred with bounded fallback to another eligible reference;
3. if a source actually contains employer names, extraction creates provenance-bearing `local_employer_deepen` hypotheses without section-heading false positives;
4. at least one resulting deepening hypothesis proceeds through ordinary official-career discovery when valid candidates exist;
5. request/LLM accounting remains exact and scoring remains healthy;
6. Volvo Group/Wolfspeed remain observational probes only. Their individual presence is not a production acceptance rule.

Do not close Issue #57 until runtime evidence shows the generic employer-reference path can turn a real public employer-list/directory source into a normal company/career discovery attempt, or until the evidence demonstrates a different generic blocker that requires a separately justified slice.

## Known follow-up evidence

- Persisted historical `local_employer_deepen` strategies include some weak HTML-extraction artifacts that look like section headings rather than employer names. Do not mix that debt into the current source-acquisition correction unless fresh current-run extraction reproduces it; if reproduced, harden candidate structure generically with fictional tests.
- The earlier planned-wind-down durability note remains open: the durable discovery-session aggregate can trail the final attempt ledger by one terminal cycle. The attempt ledger preserves the event, but final-cycle aggregate coverage should eventually flush before termination.
- The latest report demonstrates that scoring is not the current blocker; do not spend this slice retuning scoring or model choice.

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

For the active Issue #57 source-acquisition slice:

```powershell
python scripts/agent_context.py --focus "job scout 0.12.15 employer reference live acceptance" --issue 57
```

Read the generated packet, Issue #57, this handoff, and only the directly relevant query/reference files. Do not reread repository history. The authoritative runtime evidence is run `dcee77be-53c7-416a-be7c-b518f2240378`; the local report itself remains outside the public repository.
