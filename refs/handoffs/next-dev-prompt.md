---
type: Development Prompt
title: Next Development Prompt
description: Ready-to-use prompt for continuing the Job Scout self-improving discovery implementation from the current Nerve Center dev baseline.
status: stable
tags: [nerve-center, handoff, job-scout, discovery]
---
# Next Development Prompt

Continue implementation in:

`https://github.com/Three-Wheeled-Sloth-Studio/Nerve-Center`

Work from the latest `dev` branch. Use the repository's Agent Academy workflow and branch/PR discipline rather than committing speculative intermediate states to `dev`.

The immediate tracking issue is **#18: Make Job Scout discovery iterative, company-first, and self-improving**.

Read these first:

1. `AGENTS.md`
2. `refs/README.md`
3. `refs/project.yaml`
4. `refs/handoffs/currentHandoff.md`
5. `refs/planning/product-requirements-document.md`
6. `refs/planning/job-scout-discovery-and-learning-contract.md`
7. `refs/planning/job-scout-scoring-contract.md`
8. `refs/planning/module-package-contract.md`
9. `refs/research/search-source-strategy.md`
10. `refs/testing/validationCommands.yaml`
11. GitHub issue `#18`

Before changing code, summarize:

- the current Job Scout discovery architecture and scheduler/module boundaries;
- why the existing behavior is still too bounded/shallow relative to the accepted discovery contract;
- the durable data additions you propose;
- the proposed expand -> converge -> deepen -> reflect loop and its stop/drain behavior;
- the local-market expansion approach and public geographic data source you intend to use;
- the smallest execution sequence that produces a testable end-to-end improvement without building people enrichment yet.

## Accepted behavior

Job Scout is a persistent market-research agent, not a fixed query runner.

During an authorized Nerve Center work session it should repeatedly:

1. **Expand** across plausible title families, meaningful terms, locations, employer archetypes, companies, boards, direct career sites, and source strategies.
2. **Converge** by allocating more effort to strategies that produce useful signal.
3. **Deepen** useful employers and sources by resolving career pages/ATS/feed/sitemap surfaces and examining broader openings there.
4. **Reflect** when marginal discovery falls, using deterministic evidence and occasional manager-routed LLM ideation to propose overlooked paths.
5. **Re-expand** with those hypotheses and continue until the manager-owned wall-clock session constrains or drains the work.

There is no minimum job-count target. Discovery should optimize recall; scoring and user feedback provide precision. The product must expose enough coverage telemetry to distinguish a genuinely thin market from a shallow search.

## Immediate implementation slice

Implement the smallest coherent foundation for Issue #18:

- durable discovery-strategy identity, provenance, attempts, yield telemetry, and learned weight;
- company-first durable discovery, including plausible local employers with zero current relevant openings;
- career-site/ATS/feed/sitemap deepening behind the existing public-source safety rules;
- cheap local-market expansion from the configured starting location, preferably from cached public geographic reference data for the U.S. MVP;
- iterative orchestration through expand, converge, deepen, and reflect phases during the existing manager-owned session;
- transparent explore/exploit weighting with an explicit exploration floor;
- contextual feedback so dismiss/save/apply/interview/response evidence can refine discovery allocation separately from opportunity ranking;
- session coverage metrics for strategies attempted, results examined, companies discovered, career sources resolved, postings inspected, opportunities retained, strategy changes, reflection hypotheses, and provider warnings;
- manager-routed LLM ideation only after deterministic discovery reaches diminishing returns.

## Constraints

- Keep Job Scout-specific concepts inside the Job Scout module boundary.
- Do not add job-search semantics to Nerve Center core scheduling, navigation, provider selection, or generic queue schemas.
- Modules remain model-blind and may never call Ollama or another provider directly.
- Preserve public-source safety: no authenticated LinkedIn crawling, no LinkedIn automation, no CAPTCHA circumvention, no stealth/fingerprint evasion, no automated outreach, and no automatic application submission.
- A throttled or challenged provider should cool down without ending the entire discovery cycle when other safe strategies remain.
- Do not build people enrichment yet. Preserve only a clean future seam for bounded public person/contact references and a possible Farley File integration.
- Do not use a hard minimum number of jobs as a success condition.
- Required CI must use deterministic synthetic fixtures; live public-site smoke may be supplemental but may not be a required gate.
- Preserve existing accepted Windows packaging/runtime behavior and manager/module contracts.

## Validation expectations

At minimum add deterministic coverage for:

- strategy persistence and weighting;
- exploration-floor behavior;
- company retention with zero current openings;
- company deepening into discovered career sources;
- local-market expansion and alias generation;
- diminishing-return transition into reflection;
- provider challenge/throttle isolation;
- feedback provenance affecting the correct discovery/ranking loop;
- restart-safe persistence and resumable session behavior;
- coverage-summary metrics.

Run the canonical validation commands from `refs/testing/validationCommands.yaml` before promotion, including refs/index validation, tracked-path case collision checks, Python tests/lint, desktop build, and Rust/Tauri checks. Run the Windows packaging gate when touched files require it.

Do not proceed into people enrichment, Farley File implementation, Model Lab expansion, or unrelated UI work until the discovery-loop foundation is green and reviewable.
