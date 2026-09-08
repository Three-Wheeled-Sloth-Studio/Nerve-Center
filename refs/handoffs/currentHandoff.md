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
- Manager-owned Ollama routing uses `gemma3:4b` as the primary general model. Strict structured-output requests validate the result and may retry once on `qwen2.5:7b-instruct`; the next general request starts on Gemma again. Job Scout stays model-blind.
- Discovery includes direct Greenhouse, Lever, and Ashby board support, preserves the actual hiring-company identity while deepening ATS sources, and seeds all configured role families before repeating location/source combinations.
- Fit analysis contract v6 validates model-proposed claim links through a reusable semantic evidence matcher, retains claim/evidence provenance, and derives an explicit direct/adjacent/transferable/mismatch domain assessment instead of trusting an unexplained model scalar.
- Ranking engine v2 weights requirement and responsibility coverage directly and limits configured-title influence to a weak +/-3 point clue rather than a role-family gate.
- Employer identity resolution rejects weak social/job-board identity hints, preserves unresolved employers safely, and can disambiguate same-name unresolved companies when a stable organization hint exists.
- `scripts/run_job_scout_live.py` is the reusable real-run discovery/scoring diagnostic. CI remains deterministic and does not require Ollama or live public sites.
- Coding-agent context/token conservation is a primary engineering concern. `scripts/agent_context.py` generates a compact reset packet from authoritative refs and git state so agents can load context progressively instead of rereading large unchanged documents.

## Active product correction

The evidence/domain ranking foundation is implemented. The next observed ranking-quality gap is qualification-importance normalization: some live model responses label every extracted item `preferred`, even when the posting language contains responsibilities or required qualifications. That leaves required coverage at its neutral default and reduces differentiation.

Continue treating titles as weak clues. Improve requirement/responsibility extraction and taxonomy coverage only from real, persisted examples with deterministic regressions. Never broaden an alias merely to raise a desired role; unsupported credentials, engineering depth, sales ownership, or domain experience must remain unsupported.

## Next implementation slice

1. Normalize qualification importance from explicit posting evidence/headings so model overuse of `preferred` cannot erase required/responsibility distinctions.
2. Expand semantic or domain aliases only when a live false negative/positive supplies a focused fixture; keep generic words such as `platform` from creating cross-role evidence.
3. Score more promising persisted product-family roles under v6 and compare top-rank evidence with user pursuit feedback.
4. Continue longer discovery sessions and company revisits when authorized; add another provider only if coverage telemetry, rather than ranking quality, becomes limiting.
5. Judge progress primarily by top-ranked opportunity quality, differentiation, and defensible evidence—not raw opening count.

## Latest live evidence

- The durable inventory contains 151 roles across 96 companies and 579 sources; broad discovery remains persisted while ranking iterates.
- A 20-role v6 sample completed 20/20 fit analyses on `gemma3:4b` with explicit domain results: 2 direct, 1 adjacent, 5 transferable, and 12 mismatch.
- A live false-positive fixture showed bare `platform` wording linking product evidence to software-engineering and sales roles. Requiring product-specific platform language reduced both roles to zero supported qualifications and domain mismatch.
- Reflection evidence demonstrates the strict-schema fallback lane: Gemma remains primary, while failed reflection schemas retry successfully on `qwen2.5:7b-instruct`.

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
