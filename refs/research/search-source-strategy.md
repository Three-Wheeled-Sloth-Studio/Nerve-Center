---
type: Research Strategy
title: Search and Source Strategy
description: Acquisition classifications, source-portfolio behavior, company-first discovery, local-market expansion, and soft-barrier policy for Job Scout.
status: stable
tags: [nerve-center, job-scout, research, search]
---
# Search and Source Strategy

## Product posture

Job Scout discovery is a continuous search-and-learning loop, not a small fixed set of board queries. The authoritative behavior is defined in `refs/planning/job-scout-discovery-and-learning-contract.md`.

Search providers, boards, employer pages, ATS APIs, sitemaps, and public web search are complementary acquisition paths. No one successful provider is sufficient reason to stop looking, and no one provider failure should end a session when other safe paths remain.

## Acquisition classifications

Each source is registered as one of:

- `official_api`
- `public_structured_feed`
- `public_html_allowed`
- `browser_assisted_manual`
- `manual_import_only`
- `blocked`

The registry stores acquisition method, source policy notes, ATS type, scan cadence, last success, parser version, access failures, rate-limit responses, challenge frequency, and posting-history observations.

## Source portfolio

Initial direct-source connector order remains useful:

1. Greenhouse public Job Board API.
2. Lever public Postings API.
3. Generic `JobPosting` JSON-LD on employer career pages.
4. Public sitemaps and job feeds.
5. Direct employer career pages and ATS surfaces discovered from public search.
6. Broad public web-search discovery.
7. Major job boards as discovery inputs and secondary provenance.
8. Manual import or unauthenticated external discovery for LinkedIn-listed roles.

The ordering is not a one-pass pipeline. Productive paths should be revisited and deepened while exploration continues elsewhere.

## Company-first discovery

A posting found on a board should normally be treated as evidence about both the opening and the employer.

For plausible employers, discovery should attempt to resolve the canonical company domain, career page, ATS platform, feeds, sitemaps, and other public job surfaces. The company should remain durable market intelligence even when it currently has no relevant opening.

Known company career sources should be revisited according to source health and cadence. This lets Job Scout progressively build a local employer universe instead of rediscovering the same companies from scratch every session.

## Broad public search

The original Playwright adapter was a proof of concept for query planning, result parsing, URL classification, caching, and career-domain discovery. Broad search is now a continuing product capability behind an interchangeable adapter boundary rather than the product definition itself.

Broad search adapters should:

- use ordinary public search behavior;
- cache repeated queries and pace requests conservatively;
- isolate challenge/throttle failures to the affected provider or strategy;
- discover both postings and companies;
- support title, geography, employer, industry, and source-specific query variants;
- never access authenticated LinkedIn or job-board sessions;
- avoid stealth plugins, fingerprint spoofing, or CAPTCHA circumvention.

A local SearXNG connector remains a possible zero-cost path. Low-cost commercial search APIs may later improve reliability behind the same adapter contract.

## Local-market expansion

A configured location should seed a broader employment market rather than remain a literal string appended to every query.

The implementation should prefer cheap cached public geographic reference data. For the U.S. MVP, evaluate Census Places, Core Based Statistical Areas, counties, urban areas, and related Gazetteer-style datasets as the initial source for nearby city and metro expansion. Confirm the current public data contract before implementation rather than pinning the architecture to one download format prematurely.

The discovery layer needs only enough geography to generate plausible nearby search labels and simple distance/market priors. Exact route-time enrichment should be reserved for opportunities worth ranking more precisely.

The system should retain which city, metro, county, and regional labels actually produce useful employers or openings so location expansion becomes evidence-driven over time.

## Strategy learning

Search terms, title families, domains, employer archetypes, locations, and source paths should accumulate yield telemetry. Productive strategies receive more effort; noisy or unproductive strategies may be deprioritized or negatively weighted. Explicit user rules remain authoritative.

An exploration floor is mandatory. Job Scout should continue spending some discovery effort on novel or stale strategies so yesterday's success does not permanently narrow tomorrow's market.

## People and LinkedIn boundary

People enrichment is deferred from the immediate discovery slice. Future enrichment may use ordinary public web results, company pages, conference pages, press releases, and search-indexed LinkedIn profile pages to identify likely functional leaders, recruiters, or other useful contacts.

Do not crawl authenticated LinkedIn, automate LinkedIn interactions, defeat access controls, or reuse the user's personal browser session. The output is public identity/contact guidance for manual follow-up, not automated outreach.

Rich relationship management should remain separable from Job Scout so a future Farley File product can own people and relationship intelligence.

## Soft barriers

Occasional manual challenge completion is acceptable when a connector explicitly supports it. Automated CAPTCHA solving, browser fingerprint spoofing, or escalating attempts to defeat explicit blocking are not platform responsibilities.

Connectors should prefer useful information over a tiny robot arms race. When a source pushes back, record the signal, cool that path down, and continue discovering through other safe strategies.
