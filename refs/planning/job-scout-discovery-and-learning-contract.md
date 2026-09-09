---
type: Product Contract
title: Job Scout Discovery and Learning Contract
description: Accepted Job Scout behavior for continuous job-market discovery, company-first research, strategy learning, local-market expansion, and future people enrichment.
status: stable
tags: [nerve-center, job-scout, discovery, learning, planning]
---
# Job Scout Discovery and Learning Contract

## Authority and scope

This document refines Job Scout behavior under the manager/module boundary defined in `refs/planning/product-requirements-document.md` and `refs/planning/module-package-contract.md`.

Nerve Center core continues to own scheduling, process supervision, resource budgets, durable queues, LLM routing, storage services, and global UX. Job Scout owns job-market discovery, employer research, career-site discovery, opportunity ranking inputs, discovery feedback, and future people-targeting intelligence.

Where older Job Scout discovery documentation describes a bounded proof of concept or a small fixed query pass, this contract controls current product intent.

## Product intent

Job Scout is a persistent job-market research agent, not a scheduled search form.

During an authorized Nerve Center work session it should aggressively seek plausible opportunities while manager admission remains open and usable resource budget remains. A discovery wave exhausting its currently eligible strategies, or one deterministic/LLM reflection producing no new strategy, is not by itself successful session completion. Those conditions trigger bounded refresh, scoring, revisit, cooldown, or another deliberate next-work decision. The run may finish early only for cancellation, budget exhaustion, an explicit bounded no-work state after refresh/backoff attempts, or another attributable terminal condition.

Finding a small number of jobs is not itself evidence that discovery succeeded. Success is defined by useful market coverage, retained intelligence, and learning quality rather than by any minimum job count. A thin market may legitimately produce few strong opportunities; the user must still be able to see that Job Scout looked broadly and deeply before reaching that conclusion.

Discovery should optimize recall. Ranking and user feedback provide precision.

## Continuous double-diamond discovery loop

Job Scout repeatedly performs an expand, converge, deepen, reflect cycle.

### 1. Expand

Generate a portfolio of plausible discovery strategies from:

- the canonical career evidence profile;
- configured target-title families and adjacent titles;
- meaningful skills, domains, methods, industries, and outcomes;
- configured and derived local labor markets;
- remote-work eligibility;
- known employers and employer archetypes;
- public job boards and aggregators;
- direct employer career sites and ATS platforms;
- search terms that have produced useful signal before;
- new hypotheses produced by prior reflection cycles.

Expansion should be deliberately liberal. False positives are acceptable at this stage because downstream normalization, filtering, scoring, and user feedback exist to reduce noise.

### 2. Converge

Measure which strategies are producing useful signal and allocate more effort to them.

Useful signal includes more than a raw result count. It may include:

- new employers discovered;
- career sites or ATS endpoints resolved;
- new and non-duplicate openings found;
- openings retained after basic eligibility checks;
- high-ranking opportunities;
- user saves, dismissals, applications, recruiter responses, interviews, or later outcomes;
- low duplicate and low-noise rates;
- healthy source behavior without repeated throttling or challenges.

Convergence changes search effort, not permanent truth. Productive strategies should receive more work while an exploration floor preserves the ability to discover surprising new paths.

### 3. Deepen

When a search exposes a useful employer or source, Job Scout should investigate it rather than stopping at the first posting.

For a plausible employer, attempt to:

1. resolve its canonical domain and career page;
2. identify a supported ATS, public API, feed, sitemap, or structured job surface;
3. register those surfaces as durable discovery sources;
4. inspect the employer's available openings for relevant roles;
5. retain the employer even if no current opening qualifies;
6. revisit the employer on an appropriate future cadence.

A job-board result is often a clue to an employer, not the end of discovery.

### 4. Reflect and re-expand

When marginal discovery falls, Job Scout should spend a bounded cycle asking what useful avenue has not yet been tried.

Reflection may use deterministic heuristics and occasional manager-routed LLM work. The reflection input should be structured evidence about what has and has not worked, not an unbounded dump of the user's history.

Reflection may propose:

- adjacent titles or seniority labels;
- alternative terminology for the same work;
- overlooked industries or employer archetypes;
- nearby cities or labor markets;
- different combinations of terms and locations;
- new public discovery sources;
- deeper paths within already productive employers;
- strategies that were previously weak but have not been tried recently.

New hypotheses enter the strategy portfolio and are tested. If reflection adds no new hypothesis, Job Scout must still make an explicit next-work decision from newly persisted companies/sources, due revisits, scoring backlog, cooldown eligibility, and remaining budget. One empty reflection must not silently convert an otherwise open multi-hour work window into idle time.

The loop repeats until the manager's wall-clock session transitions to draining/closed behavior, the authorized resource budget is exhausted, cancellation is requested, or Job Scout records an explicit bounded no-work terminal reason.

## Work-window liveness and interleaved scoring

The authorized manager window is a work budget, not a sleep-until-deadline timer. While admission remains open, Job Scout should alternate among productive discovery, persistence, bounded scoring, and re-expansion work rather than leave a terminal module run attached to a still-running session.

A practical implementation may organize the session into waves or epochs. Whatever representation is used, it must preserve these semantics:

1. **Attempt eligibility is bounded, not permanent for the whole session.** A strategy attempted in one wave should not be reissued immediately with identical cached inputs, but whole-run exclusion must not prevent later revisits after new companies/sources appear, cooldown expires, search dimensions change, or reflection produces materially different context.
2. **New opportunities are persisted promptly.** Discovery output becomes durable before the next wave so later deepening and scoring can consume it.
3. **Scoring occurs during the active window.** Newly retained promising opportunities should receive deterministic/provisional ranking promptly and bounded full fit/scoring work while the session is active. Full scoring must not be deferred solely until the manager session closes.
4. **Scoring and discovery remain distinct feedback loops.** Ranking evidence may inform which companies, domains, or strategy families deserve more attention, but it must not collapse discovery recall into title matching or otherwise turn ranking precision into a hard discovery gate.
5. **New durable state feeds re-expansion.** Newly discovered companies, career surfaces, source health, posting evidence, and eligible scoring outcomes should be available to the next strategy-allocation decision.
6. **Idle behavior is explicit and paced.** If no immediate work is productive, use a bounded cooldown/backoff and record why. Do not hot-loop identical strategies, repeatedly spend LLM calls asking the same reflection question, or quietly wait for hours with an unexplained terminal Job Scout run.
7. **Stop reasons are attributable.** Draining/closed admission, run deadline, cancellation, request budget exhaustion, LLM budget exhaustion, or a bounded no-work conclusion must be distinguishable in checkpoints and final telemetry.

The live diagnostic runner should exercise these same semantics. A `--duration-seconds` value describes the authorized evaluation window; it must not delay scoring until the end of that window after discovery has already stopped.

## Durable discovery strategies

A discovery strategy is a first-class durable Job Scout concept. It should be representable by dimensions such as:

- title or title family;
- geography or labor market;
- domain, industry, or employer archetype;
- source or acquisition path;
- keyword or phrase family;
- remote, hybrid, or on-site context;
- origin, such as user rule, profile evidence, learned strategy, or reflection hypothesis.

The implementation may normalize these dimensions differently, but it must retain enough provenance to explain why work was attempted and why its future weight changed.

For each strategy, retain bounded telemetry such as:

- attempts and searches performed;
- results examined;
- employers discovered;
- career sources resolved;
- postings inspected;
- unique openings retained;
- relevant or high-ranking opportunities yielded;
- user feedback and pursuit outcomes attributable to the strategy;
- duplicate/noise rate;
- challenge, throttle, and failure rate;
- last attempted and last productive time;
- current learned weight and the evidence affecting it.

Strategy weighting may begin as a transparent heuristic. A bandit or more sophisticated allocator is optional later. The important behavior is evidence-driven explore/exploit allocation with recency and an explicit exploration floor.

## User feedback and learning

Job Scout should learn both where to search and how to rank what it finds.

These are related but distinct loops:

- **Discovery learning** asks where the next search effort should go.
- **Opportunity ranking** asks which of the already discovered opportunities the user should inspect first.

User actions may affect both, but their meaning must be contextual.

Examples:

- Repeatedly dismissing irrelevant jobs from one domain is evidence to down-weight that domain or strategy.
- Dismissing one job because it requires relocation should primarily affect location/ranking logic, not necessarily the employer or source.
- Saving, applying to, interviewing for, or receiving recruiter response from jobs found through a strategy provides increasingly strong positive evidence.
- Explicit user rules such as hard exclusions remain authoritative and stronger than learned weights.

Learned weights should support positive, neutral, deprioritized, and negative influence. Learned negatives should reduce effort or ranking without silently becoming hard exclusions unless the user explicitly asks for one.

## Companies as durable market intelligence

Companies are first-class objects of interest, not incidental metadata attached to postings.

Job Scout should deliberately discover plausible local employers even when it has not yet seen a matching opening from them. A company with zero relevant openings today may still be valuable because its career site can be revisited cheaply tomorrow.

The retained market map should be able to connect:

`company -> domains -> offices/locations -> career page -> ATS/feed/sitemap -> posting history -> discovery-strategy evidence`

Local employer discovery should be liberal. The system should prefer building a broad durable employer universe and let later scoring, source health, and user feedback decide where to spend repeated effort.

## Local-market expansion

A configured starting location represents a labor market to investigate, not merely a literal query string.

Job Scout should derive useful nearby search locations cheaply and retain which names actually produce signal. Initial U.S. implementation should favor cached public reference data over per-query paid services. U.S. Census Places, Core Based Statistical Areas, counties, urban areas, and related Gazetteer-style datasets are strong candidates and should be validated during implementation.

The initial location-expansion approach should be able to:

1. resolve or accept the user's starting place;
2. identify the containing metro/labor-market context where possible;
3. enumerate significant nearby places and useful geographic aliases;
4. generate bounded candidate search locations;
5. learn which city, metro, county, and regional labels return useful employers or openings;
6. expand into adjacent markets only when distance and user preference make them plausible.

Broad discovery does not require exact drive-time routing for every candidate place. Geometry, metro membership, and simple distance are sufficient starting priors. More expensive commute or route enrichment belongs on promising opportunities, not every exploratory query.

International expansion may later use other public geographic datasets behind the same conceptual contract.

## Source portfolio and failure behavior

No single job board, search engine, or public source is authoritative enough to end discovery.

Job Scout should use a portfolio of public acquisition paths and continue with other strategies when one source throttles, challenges, or yields little signal. Existing restrictions remain:

- do not defeat CAPTCHAs or explicit blocking;
- do not use stealth browser fingerprinting;
- do not reuse authenticated personal LinkedIn or job-board sessions;
- cache and pace public searches responsibly;
- prefer direct employer sources over copied aggregator records when both describe the same opening.

A provider failure should reduce that provider's current usefulness, not terminate the entire discovery cycle when other safe paths remain.

## Coverage and observability

The user must be able to distinguish a genuinely thin result set from a shallow search.

A scan/session summary should report useful coverage signals, for example:

- discovery waves/epochs and cycles completed;
- discovery strategies attempted;
- public searches executed;
- results examined;
- companies discovered;
- career sites or ATS endpoints resolved;
- known company sources revisited;
- postings inspected;
- unique opportunities retained;
- opportunities provisionally and fully scored during the window;
- high-priority opportunities surfaced;
- strategies promoted or down-weighted;
- new reflection hypotheses created and empty-reflection outcomes;
- source warnings, throttles, or challenges;
- current/terminal next-work decision and stop reason;
- consumed and remaining request/LLM budget where available.

These are observability metrics, not minimum quotas. The system should not manufacture low-quality jobs to satisfy a count.

## Future people enrichment

People enrichment is desirable but deferred from the immediate discovery MVP.

For a promising company or opportunity, a future Job Scout capability may identify relevant public people such as:

- probable functional leaders;
- likely hiring managers, with uncertainty clearly labeled;
- recruiters or talent partners associated with the domain;
- adjacent leaders or peers useful for manual follow-up.

Discovery may use ordinary public web search, public company pages, conference pages, press releases, and search-engine-indexed LinkedIn profile pages. It must not crawl authenticated LinkedIn, automate LinkedIn interactions, defeat access controls, or send outreach.

Job Scout should retain only bounded public identity/contact references needed to support follow-up. It should not grow into a general CRM. The data model should leave room for external `person_ref` or `relationship_ref` identifiers so a future dedicated Farley File product can own richer people and relationship intelligence and be consumed by Job Scout.

## Immediate implementation priority

The durable strategy/company/deepening foundation exists. The immediate correction is to make its runtime behavior honor the full authorized work window and interleave scoring with discovery.

1. keep Job Scout productive while manager admission remains open instead of completing after the first exhausted reflection;
2. introduce bounded wave/epoch or equivalent strategy re-eligibility so new durable state can drive later work without hot-looping identical searches;
3. persist and score newly retained opportunities during the active session;
4. re-seed/revisit from newly discovered companies, sources, cooldowns, and bounded reflection hypotheses;
5. preserve the exploration floor and separate discovery-learning from ranking feedback;
6. expose wave/scoring/next-work/stop telemetry sufficient to diagnose idle time;
7. retain manager-owned scheduling, provider routing, resource budgets, and module model-blindness.

Qualification-importance normalization and further ranking refinements remain important but are secondary until the continuous work-session loop is reliable. People enrichment, richer contact storage, and Farley File integration remain later work.
