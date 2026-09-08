---
type: Handoff
title: Current Handoff
description: Active Nerve Center implementation state and the next context-heavy checkpoints.
status: stable
tags: [nerve-center, handoff]
---
# Current Handoff

## Current state

- `dev` is the accepted integration branch; return the active checkout to `dev` after merging a topic branch.
- Application version remains `0.12.4`.
- The manager/module boundary, durable work sessions and queue, provider-neutral LLM manager, Windows desktop/package baseline, career evidence profile, Job Scout discovery, scoring, application tracking, and self-improving discovery loop are accepted foundations.
- Job Scout discovery now resolves aggregator-listed openings to actual hiring companies, protects employer-owned deepening from board-source crowding, persists strategy/yield learning, expands local markets, and continues the `expand -> converge -> deepen -> reflect -> expand again` loop during an authorized session.
- Manager-owned Ollama routing can prefer `gemma3:4b` strictly. Structured-output adaptation/repair remains manager-owned; Job Scout stays model-blind.
- Employer identity resolution rejects weak social/job-board identity hints, preserves unresolved employers safely, and can disambiguate same-name unresolved companies when a stable organization hint exists.
- `scripts/run_job_scout_live.py` is the reusable real-run discovery/scoring diagnostic. CI remains deterministic and does not require Ollama or live public sites.
- Coding-agent context/token conservation is a primary engineering concern. `scripts/agent_context.py` generates a compact reset packet from authoritative refs and git state so agents can load context progressively instead of rereading large unchanged documents.

## Active product correction

The main Job Scout quality gap is now **ranking discrimination**, not basic discovery plumbing. Current fit analysis can still fail to connect differently worded job requirements to genuinely supporting career evidence, which causes plausible adjacent roles to collapse toward similar conservative scores.

Accepted fit semantics are responsibility- and evidence-first rather than title-driven. A listed title is a weak clue only; actual responsibilities and requirements must be compared with verified candidate experience. Domain relationship should distinguish, in descending fit value:

`direct domain match > adjacent domain > transferable experience > domain/skill mismatch`

The scorer currently contains a model-produced `domain_score`, but there is no reusable evidence-backed domain-distance classifier/taxonomy yet. Do not treat that scalar as satisfying the accepted domain-fit contract.

## Next implementation slice

1. Build a reusable career-claim ↔ job-requirement evidence matcher that can connect semantically equivalent or transferable experience without fabricating support.
2. Add an explicit evidence-backed domain relationship result: direct, adjacent, transferable, or mismatch, with confidence/provenance sufficient for explanation and tests.
3. Feed those structured results into fit scoring while keeping title influence weak and preserving required/preferred qualification evidence constraints.
4. Refresh stale/provisional scores under the current contract and rerun the durable live diagnostic against persisted opportunities.
5. Judge progress primarily by top-ranked opportunity quality, differentiation, and defensible evidence—not raw opening count.
6. Add another discovery provider only if live evidence shows discovery coverage, rather than ranking quality, is the limiting factor.

## Do not reopen without new evidence

- Company-first discovery and the double-diamond discovery loop.
- Manager-owned provider/session/queue boundaries; modules remain model-blind.
- `gemma3:4b` as the current Job Scout default local evaluator.
- Separate discovery-learning and opportunity-ranking feedback loops.
- Public-source safety: no authenticated LinkedIn/job-board crawling, CAPTCHA circumvention, stealth automation, unattended applications, or outreach.
- People enrichment remains deferred; preserve seams but do not build a CRM inside Job Scout.

## Coding-agent reset path

For routine continuation, start with:

```powershell
python scripts/agent_context.py --focus "job scout requirement evidence domain fit ranking" --issue <issue-number>
```

Use the generated packet, active issue, and its file-map hints first. Expand to full roadmap/decision/architecture documents only when needed. The packet is derived orientation and must never become a competing source of truth.

## Validation boundary

Run required commands in `refs/testing/validationCommands.yaml`. CI must remain deterministic and independent of Ollama, GPUs, live job boards, and mutable career sites. Bugs found during real Job Scout runs should gain deterministic fixtures/regressions when practical.
