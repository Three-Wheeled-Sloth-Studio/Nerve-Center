---
type: Research Strategy
title: Search and Source Strategy
description: Acquisition classifications, connector order, broad-search approach, and soft-barrier policy for Job Scout sources.
status: stable
tags: [nerve-center, job-scout, research, search]
---
# Search and Source Strategy

## Acquisition classifications

Each source is registered as one of:

- `official_api`
- `public_structured_feed`
- `public_html_allowed`
- `browser_assisted_manual`
- `manual_import_only`
- `blocked`

The registry stores acquisition method, source policy notes, ATS type, scan cadence, last success, parser version, access failures, rate-limit responses, challenge frequency, and posting-history observations.

## Initial connector order

1. Greenhouse public Job Board API.
2. Lever public Postings API.
3. Generic `JobPosting` JSON-LD on employer career pages.
4. Public sitemaps and job feeds.
5. Selected direct career pages.
6. Broad web-search discovery.
7. Manual import or unauthenticated external discovery for LinkedIn-listed roles.

## Zero-cost search proof of concept

The first broad-search adapter may use Playwright with a dedicated unauthenticated Chromium profile. The goal is to validate query planning, result parsing, URL classification, caching, and career-domain discovery without committing the architecture to one search provider.

The connector must:

- Run at low concurrency and conservative cadence.
- Cache results and avoid repeated identical searches.
- Use ordinary browser behavior rather than stealth plugins or user-profile reuse.
- Detect challenge pages, checkpoint, back off, and allow manual continuation.
- Never access authenticated LinkedIn or job-board sessions.

A local SearXNG connector may be evaluated as another zero-cost option. A commercial search API such as Brave can later become the reliable default behind the same adapter contract.

## Soft barriers

Occasional manual challenge completion is acceptable. Automated CAPTCHA solving, browser fingerprint spoofing, or escalating attempts to defeat explicit blocking are not platform responsibilities. Connectors should prefer useful information over a tiny robot arms race.
