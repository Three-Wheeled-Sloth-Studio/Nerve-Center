---
type: Product Contract
title: Job Scout Discovery and Learning Contract
description: Accepted Job Scout behavior for continuous job-market discovery, company-first research, strategy learning, location-aware market coverage, and future people enrichment.
status: stable
tags: [nerve-center, job-scout, discovery, learning, planning]
---
# Job Scout Discovery and Learning Contract

## Authority and scope

This document defines current Job Scout discovery behavior under the manager/module boundary in `refs/planning/product-requirements-document.md` and `refs/planning/module-package-contract.md`.

Nerve Center core owns scheduling, process supervision, resource budgets, durable queues, LLM routing, storage services, and global UX. Job Scout owns job-market discovery, employer research, career-site discovery, opportunity-ranking inputs, discovery feedback, and future people-targeting intelligence.

Where older Job Scout documentation describes a bounded proof of concept, a one-pass search, or Issue #34 as future work, this contract controls current product intent.

## Product intent

Job Scout is a persistent job-market research agent, not a scheduled search form.

During an authorized work session it should seek plausible opportunities while manager admission remains open and usable resource budget remains. Discovery optimizes recall. Ranking and scoring provide precision. A thin result set may be legitimate, but the system must make broad and deep market coverage inspectable before concluding that the market is thin.

The accepted discovery loop is:

`expand -> converge -> deepen -> reflect -> re-expand`

Issue #34 and PR #36 established the current runtime semantics: bounded discovery waves, prompt persistence, interleaved provisional and bounded full scoring, safe revisit cooldowns, paced no-work backoff, and explicit stop reasons. One empty reflection or one exhausted wave is not successful completion while productive work remains eligible.

Issue #40 and PR #42 established deterministic location awareness while preserving broad retention. Issue #43 and PR #44 established source-aware search portfolios, deterministic query linting, cross-strategy convergence, explicit coverage gaps, structured-source refresh preference, and a human-visible discovery audit. Issue #51 established explicit live-run resource policies, pre-fetch request admission, and durable hypothesis-family learning.

## Expand

Generate a portfolio of plausible strategies from:

- canonical career evidence;
- configured target-title families and adjacent titles;
- meaningful skills, domains, methods, industries, and outcomes;
- configured and derived labor markets;
- remote-work eligibility;
- known employers and employer archetypes;
- direct ATS and employer sources;
- public search and secondary board sources;
- previously productive terms and source paths;
- new hypotheses produced by reflection.

Expansion should be deliberately liberal. False positives are acceptable because downstream normalization, scoring, and user feedback exist to reduce noise.

Search constraints must be source-aware. Do not mechanically put every user preference into every search query. A constraint that is reliable after retrieval but destructive to search recall should be applied to normalized results instead. Location, compensation, seniority, and technology terms may therefore be retrieval dimensions for some source types and post-retrieval evidence for others.

Source-aware portfolio compilation must preserve materially different hypothesis families rather than superficial query rewrites. The accepted initial families are direct role, adjacent role, seniority variant, domain/capability, and employer archetype. Portfolio allocation is bounded and should give multiple source paths a chance to participate rather than allowing one broad-search family to consume the request budget first.

Before network spend, deterministic query linting rejects structurally bad experiments such as contradictory exclusions, catch-all anchors, unsupported invented technologies or requirements, and other source-specific combinations known to collapse recall. Subjective LLM judgment is not a single-run execution gate.

For structured ATS x-ray paths such as Greenhouse, Lever, and Ashby, reliable post-fetch fields may replace destructive query constraints. In particular, geography may be deferred to normalized opening evidence instead of being repeated in every x-ray query.

## Converge

Allocate more effort to strategies that produce useful signal while preserving an exploration floor.

Materially equivalent public-search strategies share a stable evidence family based on hypothesis family, source domain, and location. Query wording and anchor variants remain independently auditable, but they may not reset accumulated family evidence. Repeated zero location-conditioned opening yield lowers exploitation priority at the family level while the exploration floor continues to sample alternatives.

Useful signal includes:

- new employers discovered;
- career sites or ATS endpoints resolved;
- new non-duplicate openings retained;
- useful local or regional coverage for a location-targeted strategy;
- high-ranking opportunities;
- user saves, applications, recruiter responses, interviews, and later outcomes;
- low duplicate/noise rates;
- healthy source behavior without repeated throttling or challenges.

Raw result count alone is not enough. A strategy can be broadly productive but locally unproductive, or can discover a valuable employer even when the first listing itself is not a fit. Persist enough provenance to keep those distinctions available.

When materially different strategies converge on the same employer, that convergence may raise the priority of employer/source deepening. When they converge on the same opening, retain the multi-strategy provenance for audit. Neither form of convergence changes opportunity fit truth or creates duplicate scoring credit.

## Deepen

A board or search result is often evidence about an employer, not the end of discovery.

For a plausible employer, attempt to:

1. resolve its canonical domain and career page;
2. identify supported ATS, public API, feed, sitemap, or structured job surfaces;
3. register those surfaces as durable discovery sources;
4. inspect the employer's available openings;
5. retain the employer even when no current opening qualifies;
6. revisit the employer on an evidence-based cadence.

Direct employer evidence should supersede copied aggregator evidence when both describe the same opening.

Once a direct structured source is known, prefer a cheap authoritative refresh path without ending broad exploration of unknown employers. A newly discovered source with unknown health may receive one initial verification preference; a known healthy structured source remains eligible for preference. Known degraded, challenged, or blocked sources do not receive a discovery-quality bonus merely because they are structured. After the initial preference, observed source yield and health control normal learning.

## Reflect and re-expand

When marginal discovery falls, Job Scout should ask what useful avenue has not yet been tried.

Reflection may use deterministic heuristics and occasional manager-routed LLM work. It must consume bounded structured evidence rather than an unbounded career-history dump.

Reflection evidence includes explicit requested-vs-observed coverage gaps across role/title family, responsibility or skill family, domain/capability, employer archetype, location/labor market, work arrangement, seniority, source/ATS coverage, and query-family coverage.

Deterministic reflection should first propose bounded strategies targeted at actual gaps. Manager-routed reflection receives the same explicit uncovered-space profile and may propose additional materially different strategies. Proposed LLM strategies still pass deterministic query compilation/linting before execution.

An empty reflection still triggers a deliberate next-work decision from newly persisted companies/sources, due revisits, scoring backlog, cooldown eligibility, remaining budget, and explicit coverage gaps.

## Durable discovery strategies

A strategy is a first-class durable Job Scout concept. It may include dimensions such as:

- title or title family;
- keyword/phrase or responsibility family;
- geography/labor market;
- domain, industry, or employer archetype;
- source/acquisition path;
- work arrangement;
- origin, such as profile evidence, user rule, learned strategy, or reflection hypothesis.

Strategy provenance must be strong enough to explain why work was attempted and why its future weight changed.

Strategy identity preserves the complete experiment dimensions. Family identity deliberately omits superficial query wording while retaining the hypothesis family, source, and location needed to interpret yield. Company and source evidence remains durable and visible but does not offset zero location-conditioned opening yield when allocating a location-targeted public-search family.

Retain bounded telemetry such as attempts, results examined, employers discovered, sources resolved, postings inspected, unique openings retained, location-conditioned yield, relevant/high-ranking opportunities, user/outcome feedback, duplicate/noise rate, challenge/failure rate, last attempted/productive time, current learned influence, and before/after weight movement where available.

A bandit or more sophisticated allocator is optional. Evidence-driven explore/exploit allocation with recency and an explicit exploration floor is required.

## Search-portfolio quality

One logical search intent may be represented by several materially different query angles when the source supports it. Useful angles can include obvious titles, adjacent titles, seniority variants, domain/capability terms, and employer archetypes.

The strategy system should prefer diversity over superficial rewording. If two query strategies retrieve substantially the same result set, that is duplicate search effort and should reduce their independent value.

When the same employer or opening appears through several materially distinct strategy angles, preserve that multi-strategy provenance. It can be useful evidence for employer-deepening priority or discovery confidence, but it must not replace opportunity fit scoring.

## Location-aware market coverage

A configured starting location represents a labor market to investigate, not merely a literal string appended to every query.

Job Scout should derive useful nearby locations cheaply from cached public geographic reference data and retain which aliases actually produce useful employers or openings. Geometry, metro membership, and simple distance are sufficient discovery priors; expensive route-time enrichment belongs on promising opportunities.

Opening-level location evidence must remain separate from company-presence evidence:

- an opening should retain raw source location text and normalized structured evidence with provenance;
- a company may have verified relevant local presence even when a particular opening is remote or elsewhere;
- generic `remote`, `nationwide`, aggregator-only, or ambiguous text must not manufacture local certainty;
- direct local/regional listing evidence should influence deterministic scope and ranking without requiring an LLM call.

Discovery learning must distinguish total yield from location-conditioned yield. A location-seeded strategy may deserve general credit for finding a useful employer, but later deepening into distant openings must not falsely teach the system that the original location seed was locally productive.

Broad discovery remains mandatory. Location relevance changes allocation and ranking; it does not become a hidden hard filter for otherwise useful remote or adjacent-market opportunities.

## User feedback and learning

Discovery learning asks where the next search effort should go. Opportunity ranking asks which discovered opportunity deserves attention first. These loops are related but distinct.

User actions may inform both, but only with contextual meaning. For example, repeated domain irrelevance can down-weight a domain strategy, while dismissing one role because it requires relocation should primarily inform location/ranking behavior rather than condemn the employer or source.

Explicit user rules remain authoritative. Learned negatives may deprioritize but must not silently become hard exclusions.

## Source portfolio and failure behavior

No single search engine, job board, ATS, or employer source is authoritative enough to end discovery.

Use a portfolio of public acquisition paths and continue through other safe strategies when one source throttles, challenges, or yields little signal. Cache repeated queries, pace requests, and record provider/source health.

Do not defeat CAPTCHAs, use stealth fingerprinting, reuse authenticated personal LinkedIn/job-board sessions, submit applications, or automate outreach.

## Coverage and observability

The user must be able to distinguish a genuinely thin result set from a shallow search.

Session reporting and the read-only discovery audit should expose useful signals, including:

- waves/cycles completed;
- strategies and public searches attempted;
- hypothesis family and compiled query/source path;
- results examined;
- companies and career sources discovered;
- known sources revisited;
- postings inspected;
- unique opportunities retained;
- provisional/full scores completed during the window;
- location-scope counts and location-conditioned strategy yield;
- strategies promoted/down-weighted and before/after weight movement;
- employer/opening overlap from materially distinct strategies;
- explicit coverage gaps and reflection hypotheses;
- source warnings/challenges;
- current next-work decision and terminal reason;
- consumed and remaining request/LLM budget where available.
- configured duration and effective request, LLM, and full-score ceilings before work starts;
- family-level attempts, location-conditioned yield, learned influence, and weight movement.
- effective target titles, locations, work-arrangement preference, score-success target, and score-failure ceiling inherited from the workspace or supplied by the runner;
- successful full scores separately from attempted and failed full-score analyses;
- rolling marginal-yield windows, low-yield backoff count, and request/result/opportunity efficiency;
- grouped location, source-domain, and hypothesis-family evidence for explaining local-market allocation.

These are observability metrics, not quotas. Ordinary unattended sessions remain autonomous; viewing strategy audit information does not create an approval step.

## Current implementation priority

The first four-hour soak completed and produced the evidence for Issue #53. Job Scout now distinguishes planned manager wind-down from deadline completion, targets successful scores with a separate failure ceiling, slows repeated zero-marginal-yield work through bounded backoff, adds evidence-derived local-employer search hypotheses, and records effective configuration plus grouped location-family diagnostics. The next checkpoint is a short live acceptance run, followed by a repeat unattended soak if those diagnostics remain coherent.

## Deferred work

- People enrichment and richer relationship intelligence; preserve external person/relationship seams for a future dedicated product instead of growing a CRM inside Job Scout.
