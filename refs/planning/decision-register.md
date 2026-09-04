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
| NC-027 | rejected | Hosted deployment. |
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
