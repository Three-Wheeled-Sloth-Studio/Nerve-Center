---
type: Decision Register
title: Decision Register
description: Durable accepted, deferred, rejected, and open product and architecture decisions for Nerve Center.
status: stable
tags: [nerve-center, planning, decisions]
---
# Decision Register

Status values: `accepted`, `deferred`, `rejected`, `open`.

| ID | Status | Decision |
|---|---|---|
| NC-001 | accepted | Nerve Center is a reusable local orchestration platform; Job Scout is its first task plugin. |
| NC-002 | accepted | The product is single-user and local-first. |
| NC-003 | accepted | Windows is the initial platform. Cross-platform packaging is deferred. |
| NC-004 | accepted | Python hosts orchestration and local APIs; React and TypeScript will host the UI; Tauri v2 will provide the desktop shell. |
| NC-005 | accepted | SQLite with WAL is the durable local database. A dedicated vector database is deferred. |
| NC-006 | accepted | Runtime data is stored outside the public repository checkout. Credentials use operating-system storage where practical. |
| NC-007 | accepted | Ollama is the default MVP LLM provider behind provider-neutral structured contracts modeled after Review Room. |
| NC-008 | accepted | Users manage one canonical career evidence profile, not multiple target profiles. |
| NC-009 | accepted | The system may propose learned positioning hypotheses and remember approve or disapprove feedback. |
| NC-010 | accepted | Job discovery may use public APIs, structured feeds, public HTML, broad web search, and approved public browser automation. |
| NC-011 | accepted | Automated access to authenticated LinkedIn and job-board sessions is prohibited. |
| NC-012 | accepted | The system may recommend applications, outreach, account interactions, and profile changes but may not execute them. |
| NC-013 | accepted | Automated job submission, outreach, and profile modification are permanent non-goals. |
| NC-014 | accepted | Future resume tailoring may change only a reviewable copy, initially limited to the headline outside career history. |
| NC-015 | accepted | Future cover letters are generated from an immutable master and verified evidence, never submitted automatically. |
| NC-016 | accepted | Location response preference is local hybrid, local on-site, regional hybrid, regional remote, then distant remote. Relocation-required roles are excluded. |
| NC-017 | accepted | Local commute eligibility extends to 90 minutes, with closer opportunities scoring better. |
| NC-018 | accepted | Remote roles without nearby company presence receive a response-likelihood penalty unless the remaining match is exceptional. |
| NC-019 | accepted | Scores remain decomposed into fit, response likelihood, opportunity value, confidence, and calculated priority. |
| NC-020 | accepted | Score weights, thresholds, and gates are configurable and explanations are mandatory. |
| NC-021 | accepted | Application tracking is part of MVP because outcomes are needed to calibrate response scoring. |
| NC-022 | accepted | Company, domain, title, location, and source rules support hard include, hard exclude, prefer, deprioritize, and watch behavior. |
| NC-023 | accepted | Wake-from-sleep is not an MVP requirement. |
| NC-024 | rejected | Cloud synchronization. |
| NC-025 | rejected | Mobile access. |
| NC-026 | rejected | Multi-user support. |
| NC-027 | accepted | The long-term runtime is dual-track: local execution with local SQLite storage remains the default, while an optional hosted execution mode uses PostgreSQL. Hosted tenancy, authentication, deployment, and migration details remain outside the MVP. |
| NC-028 | deferred | Remote LLM providers. |
| NC-029 | deferred | Resume-copy generation. |
| NC-030 | deferred | Cover-letter generation. |
| NC-031 | deferred | Gmail integration. |
| NC-032 | deferred | Network and referral analysis. |
| NC-033 | deferred | ComfyUI integration. |
| NC-034 | deferred | Dedicated vector storage. |
| NC-035 | deferred | Wake-from-sleep. |
| NC-036 | deferred | Cross-platform packaging. |
| NC-037 | accepted | The repository is public; source, tests, issues, logs, and fixtures must be safe for public disclosure. |
| NC-038 | accepted | Packaged Windows builds bundle the Python API as a self-contained local executable while source development retains an explicit Python fallback. |
| NC-039 | accepted | The first distributable artifact is an unsigned per-user NSIS development package; signing, automatic updates, and release channels are deferred. |
| NC-040 | accepted | Job Scout discovery is a continuous double-diamond loop: expand search hypotheses, converge on useful signal, deepen productive companies/sources, reflect on what remains unexplored, then expand again until the authorized work window drains. |
| NC-041 | accepted | Job Scout discovery optimizes recall and useful coverage rather than any minimum job count. A small result set is acceptable only when coverage telemetry shows the market was searched broadly and deeply. |
| NC-042 | accepted | Companies are first-class durable discovery targets. Job Scout should liberally discover plausible local employers, resolve and revisit their career surfaces, and retain them even when they currently expose zero relevant openings. |
| NC-043 | accepted | Discovery strategies retain yield telemetry and learned weights. User feedback and pursuit outcomes may promote, deprioritize, or negatively weight titles, terms, domains, companies, locations, and source strategies, while an exploration floor prevents premature lock-in. |
| NC-044 | accepted | A configured starting location defines a labor market to investigate. Job Scout should cheaply derive nearby cities, metro aliases, and plausible adjacent markets from cached public geographic data before spending expensive enrichment on individual opportunities. |
| NC-045 | accepted | Discovery learning and opportunity ranking are separate but related feedback loops: one allocates future search effort, the other sorts already discovered opportunities. Feedback must preserve enough provenance to affect the correct loop. |
| NC-046 | deferred | People enrichment may later identify likely functional leaders, recruiters, and other useful contacts from ordinary public-web sources, including search-indexed LinkedIn profiles, without authenticated LinkedIn crawling or automation. Retain bounded person/contact references and leave a clean integration path for a future Farley File product. |
