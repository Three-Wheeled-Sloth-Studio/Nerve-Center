---
type: Implementation Handoff
title: Job Discovery Sources Handoff
description: Accepted source registry, direct connectors, source-health, deduplication, scheduler, and broad-search checkpoint.
status: stable
tags: [nerve-center, handoff, job-scout, discovery]
---
# Job Discovery Sources Handoff

## Accepted baseline

- Branch: `dev`.
- Accepted code through commit: `7a8ff2f9542d3372034d01ae61c78e8f8a897962` plus this documentation commit.
- Visible version: `0.3.0`.
- Schema version: `4`.
- Python requirement: `3.12+`.
- Tracking issue: `#3`.

## Implemented

### Source registry

The local database now persists:

- Companies, canonical domains, career URLs, and known ATS types.
- Discovery source kind and acquisition classification.
- Source configuration, parser version, policy notes, enabled state, and cadence.
- Last scan, last success, next scan, consecutive failures, challenge count, and rate-limit count.
- Bounded source scan history with request count, openings found, HTTP status, and safe failure detail.

Accepted acquisition classifications remain:

- `official_api`
- `public_structured_feed`
- `public_html_allowed`
- `browser_assisted_manual`
- `manual_import_only`
- `blocked`

Blocked or disabled sources cannot execute.

### Initial direct-source connectors

Implemented connectors:

- Greenhouse public Job Board API.
- Lever public Postings API with bounded pagination.
- Generic schema.org `JobPosting` JSON-LD extraction.
- Public sitemap URL discovery.

All connectors emit the same normalized opening contract. The contract includes company identity, title, description, locations, work arrangement, employment type, department or team when available, source and canonical URLs, external identifier, posting dates, parser confidence, active state, and full provenance.

The connector registry is independent of downstream storage and scoring. Future Brave, SearXNG, or other search adapters can feed the same discovery and normalization layer.

### Acquisition safety and source health

HTTP acquisition uses one concurrent request per domain by default. The shared fetcher identifies throttling and common challenge pages without escalating around explicit blocking.

Source outcomes update durable health:

- Successful scans reset failures and use the configured cadence.
- Partial scans retain success history but mark the source degraded.
- Repeated failures receive exponential cadence backoff.
- Challenges and rate limits increment dedicated counters.
- Explicit 401 or 403 access failures may mark a source blocked.

Source scan records contain only bounded operational detail. Full page bodies, cookies, credentials, and authenticated state are never written to scan history.

### Sitemap handoff

Sitemap scans identify likely job, career, position, opening, and vacancy URLs. Discovered XML sitemap URLs become nested sitemap sources. Likely job pages become JSON-LD page sources.

Repeated discovery upserts source definitions without resetting accumulated source health.

### Normalization and deduplication

URL normalization removes fragments, common campaign parameters, and known ATS tracking parameters.

Openings deduplicate by stable identifier, canonical URL, or a company-title-location fingerprint. When a direct employer listing and an indirect copy describe the same opening, the direct employer record becomes canonical while useful secondary fields and all distinct provenance are retained.

No opportunity fit or pursuit score is calculated in this increment.

### Scheduled discovery task

The `job_scout.discovery` plugin runs through the generic orchestration framework.

It:

- Scans explicitly configured source identifiers or all currently due sources.
- Consumes the run's outbound-request budget.
- Uses shared bounded work slots.
- Stops at cancellation or deadline.
- Checkpoints completed sources, last source, and openings found.
- Returns partial status when one or more sources fail.

### Broad web-search proof of concept

An optional Playwright adapter can run ordinary unauthenticated Google searches in a dedicated application-data Chromium profile.

It:

- Never opens the user's ordinary browser profile.
- Normalizes redirect URLs and removes tracking parameters.
- Classifies Greenhouse, Lever, LinkedIn, major job-board, direct company-career, and other results.
- Caches successful identical searches for seven days.
- Registers direct company-career results for later JSON-LD scanning.
- Stores a one-hour cooldown after a challenge to prevent repeated headless attempts.
- Supports a bounded headful window for occasional manual challenge completion.

The adapter does not automate CAPTCHA solving, fingerprint spoofing, authenticated LinkedIn access, or stealth behavior.

## Local API

The local API supports:

- Create and list companies.
- Create and list discovery sources.
- Run one source immediately.
- Inspect bounded source scan history.
- List normalized active openings.
- Run optional broad browser search.

## Validation

The Issue #3 isolated slice passes 11 tests covering:

- Greenhouse normalization.
- Lever pagination and normalization.
- Nested JSON-LD extraction.
- Sitemap filtering.
- Company, source, health, job, provenance, and cache persistence.
- Direct-employer-preferred deduplication.
- Search-cache expiration.
- Source execution and job persistence.
- Scheduler checkpoint and request-budget behavior.
- Search URL normalization and classification.
- Browser challenge cooldown.
- Discovery API registration, scans, scan history, and job inspection.

The combined Issue #2 and Issue #3 local slice passes 22 tests using synthetic public-safe data. Python compilation also passes.

## Known limits

- Live Greenhouse, Lever, JSON-LD, sitemap, and Google browser smoke tests were not run from this connector execution environment.
- Ruff was not installed in the local execution environment, so the committed GitHub workflow remains the authoritative lint check.
- The GitHub connector did not return a pull-request-triggered workflow run for the latest direct `dev` commits.
- Playwright and its Chromium browser are optional and are not installed by the normal package dependency set.
- JavaScript-rendered career pages without usable JSON-LD are not parsed by the direct HTML connector yet.
- Posting closure and stale-opening reconciliation are not implemented yet.
- Company names discovered only from a domain remain domain-based until company enrichment.
- Search query generation from the canonical career profile belongs to the scoring and pursuit-planning increment.
- Source policy classification and notes are explicit registry data; policy interpretation is not delegated to an LLM.

## Next increment

Proceed with Issue `#4`, location enrichment and opportunity scoring.

Required sequence:

1. Define versioned score inputs, factors, hard gates, and explanations.
2. Add configurable component weights, thresholds, and confidence handling.
3. Add user location preferences without placing personal defaults in the repository.
4. Enrich company and job locations through deterministic providers and cached travel-time estimates.
5. Implement the accepted local, regional, and distant work-arrangement ordering.
6. Add fit, response likelihood, opportunity value, confidence, and calculated priority.
7. Preserve historical scoring versions and expose reconstructable factor detail.
8. Add rule handling for hard include, hard exclude, prefer, deprioritize, and watch.

Do not build the Tauri desktop UI inside the scoring increment.
