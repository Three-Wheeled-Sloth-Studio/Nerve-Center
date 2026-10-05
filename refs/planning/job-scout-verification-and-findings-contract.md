---
type: Product Contract
title: Job Scout Verification and Findings Contract
description: Accepted verification semantics, multi-resume scoring, employer tracking, findings views, and terminology-alignment behavior.
status: stable
tags: [nerve-center, job-scout, verification, findings, resume]
---
# Job Scout Verification and Findings Contract

## Purpose

Job Scout discovers broadly but distinguishes discovery evidence from employer-authoritative verification. Search engines, major job boards, directories, and other secondary sources may create durable leads. Employer or employer-authorized ATS evidence determines verification confidence and canonical application guidance.

The product must not confuse "verification could not be completed" with "the employer source was successfully read and the listing was not present."

## Verification states

The implementation may represent these as a status plus reason rather than one enum, but behavior must distinguish:

- `verified_present`: an employer-authoritative source was successfully read and the opening is present.
- `unverified_source_unresolved`: no employer-authoritative career source has been resolved yet.
- `unverified_source_unavailable`: an authoritative source is known but could not be reached or access was blocked.
- `unverified_parse_failed`: an authoritative source was reached but its content could not be interpreted reliably.
- `verified_absent`: an authoritative source was successfully read and the candidate opening is not present.
- `stale_verification`: prior authoritative verification exists but is no longer fresh enough to treat as current.

Behavior:

- verified presence receives the strongest source-confidence reward;
- unverified states are non-blocking, visibly flagged, and receive less source-confidence reward;
- verified absence normally withholds the opening from the actionable findings list;
- failed, blocked, challenged, timed-out, or unparsable authoritative scans never imply verified absence;
- stale verification remains auditable and may remain visible with reduced confidence until refreshed.

Employer-authoritative includes the employer's own career pages and external ATS surfaces that are credibly associated with that employer.

## Provenance and URL precedence

Every opening should retain:

1. discovery provenance: where Job Scout first or subsequently learned that the opening may exist;
2. authoritative provenance: employer-authoritative observations that verify the opening;
3. observation timing sufficient to distinguish first discovery from later verification and syndication.

User-facing application links prefer:

1. the verified employer-authoritative opening URL;
2. the verified employer career page when a specific opening URL is unavailable;
3. a secondary discovery URL only when authoritative access is unresolved/unavailable, with a visible warning.

A successful authoritative read that does not contain the opening must not silently fall back to a secondary board link as if the listing were current.

## Staleness and disappearance

Track enough evidence to explain:

- first discovered;
- last observed anywhere;
- last authoritative verification;
- last successful authoritative scan;
- verification failure reason/count where useful.

Explicit closure or expiration on an authoritative source may deactivate an opening immediately.

Absence from a successful authoritative refresh is evidence of possible closure and should follow a deterministic source-specific confirmation policy.

Failed/challenged/throttled/blocked/parser-failed scans are not negative evidence.

## Multi-resume scoring

A candidate may maintain multiple active resumes for adjacent target roles.

Each opening is evaluated independently against each selected resume. Do not merge multiple resumes into a synthetic super-resume for fit scoring.

Persist or derive:

- fit score by resume;
- best-fit resume;
- best-fit score;
- factor/evidence explanations by resume.

Opportunity priority may use the best applicable resume while keeping the alternative resume scores inspectable.

## Employer tracking

Tracked employers are first-class findings entities. The product should expose at least:

- local/regional presence strength and evidence;
- authoritative career-source health;
- last career-source scan;
- current relevant-role count;
- recent relevant-role activity;
- highest-priority current role;
- best current resume fit;
- direct-discovery count where supported;
- board-only/unverified lead count;
- verification health.

Employer-level local presence must be evidence-backed. Search-query geography or result co-occurrence alone does not establish an office.

## Findings views

### Employers

Provide a user-friendly employer view oriented around "which employers in my market are worth tracking?"

Useful fields include:

- employer;
- local/regional presence;
- current relevant roles;
- best current fit;
- last new relevant role;
- career-source health;
- last scanned.

Employer detail should explain presence evidence, show the employer-authoritative career link, list current matching roles, show recent role activity, and expose source health/verification failures.

The model must preserve a clean seam for later key-personnel/relationship enrichment without embedding CRM behavior into Job Scout discovery.

### Opportunities

Default sort is priority.

Useful visible fields include:

- priority;
- role;
- employer;
- best resume;
- fit;
- local-presence advantage;
- freshness;
- verification status;
- discovery/syndication advantage where known.

Provide a friendly employer-authoritative link whenever possible. Secondary links may be shown when authoritative access is unresolved/unavailable, but must be visibly flagged.

## Light terminology alignment

For a selected opening and base resume, Job Scout may suggest small wording substitutions that express already-supported experience using terminology from the listing.

This is not autonomous resume rewriting.

Each suggestion should retain:

- resume ID;
- opening ID;
- original text;
- suggested text;
- listing terminology;
- supporting career-claim/evidence IDs;
- reason;
- confidence.

Hard rules:

- never invent skills or technologies;
- never inflate scope;
- never change dates, employers, titles, or factual outcomes without explicit user action;
- preserve quantified outcomes;
- every suggestion must remain supported by existing resume/career evidence;
- user review is required before any export/use.

## Separation of concerns

Keep these distinct:

- discovery provenance: did we find it?
- verification confidence: can we establish that it currently exists?
- resume fit: how well does this specific resume match?
- opportunity priority: how worthwhile is it to pursue relative to alternatives?

Local employer presence, freshness, source confidence, and observed syndication affect opportunity priority. They must not rewrite factual resume fit.

## Implementation order

1. Verification states and failure semantics.
2. Canonical URL and discovery-vs-authoritative provenance behavior.
3. Stale/closure lifecycle.
4. Multi-resume scoring.
5. Employer-presence tracking metrics.
6. Employers and Opportunities findings views.
7. Light terminology-alignment suggestions.
8. Observed syndication/discovery-advantage refinement.

Each slice should be independently testable and should extend existing mechanisms rather than redesigning settled provider, scheduler, or reflection behavior.
